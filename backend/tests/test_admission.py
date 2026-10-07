import asyncio
import gc
import stat
import weakref

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select
from test_api import ADMIN, DEVICE, ApiChain, add_fixture, done, make_pdf, public_state
from test_api import api_system as api_system
from test_runner import Models

from app import storage
from app.api.batch import create_batch
from app.api.runtime import Runtime
from app.config import Settings
from app.models import Attempt, BatchRecord
from app.pipeline.ingest import MAX_BYTES, Document, InputError
from app.pipeline.runner import new_attempt


def runtime_for(directory):
    settings = Settings(
        _env_file=None,
        data_dir=directory,
        llm_enabled=True,
        transactions_enabled=True,
        batch_enabled=True,
    )
    chain = ApiChain()
    runtime = Runtime(settings, chain=chain, models=Models(), state_reader=public_state)
    chain.engine = runtime.store.engine
    return runtime


def test_upload_queue_retains_ids_not_rendered_documents(api_system, monkeypatch):
    client, runtime, chain, _ = api_system
    references = []
    original = runtime.ingest

    async def track(**kwargs):
        document = await original(**kwargs)
        references.append(weakref.ref(document))
        return document

    async def pause_workers():
        for task in runtime.tasks[:3]:
            task.cancel()
        await asyncio.gather(*runtime.tasks[:3], return_exceptions=True)

    monkeypatch.setattr(runtime, "ingest", track)
    client.portal.call(pause_workers)
    result = client.post(
        "/api/bounty/attempts",
        headers=DEVICE,
        data={"nickname": "Queue test"},
        files={"file": ("invoice.pdf", make_pdf(), "application/pdf")},
    )
    assert result.status_code == 202
    attempt_id = result.json()["attempt_id"]
    assert len(references) == 1 and references[0]() is None
    assert runtime.queue.qsize() == 1 and not chain.sent

    async def resume():
        queued = runtime.queue.get_nowait()
        runtime.queue.task_done()
        assert queued == attempt_id and isinstance(queued, str)
        runtime.queue.put_nowait(queued)
        runtime.tasks[0] = asyncio.create_task(runtime.worker())

    client.portal.call(resume)
    assert done(client, attempt_id, ADMIN)["outcome"] == "paid"
    assert len(references) == 2 and len(chain.sent) == 1

    async def settled():
        await runtime.queue.join()
        await asyncio.sleep(0)

    client.portal.call(settled)
    gc.collect()
    assert all(ref() is None for ref in references)


def test_batch_releases_each_render_and_enqueues_only_ids(tmp_path, monkeypatch):
    runtime = runtime_for(tmp_path)
    for index in range(3):
        add_fixture(runtime, f"clean/{index}.pdf")
    references = []

    async def render(**kwargs):
        assert all(ref() is None for ref in references)
        document = Document(kind="pdf", page_count=1, images=[b"synthetic" * 10000])
        references.append(weakref.ref(document))
        return document

    monkeypatch.setattr(runtime, "ingest", render)
    try:
        result = asyncio.run(create_batch(runtime))
        with Session(runtime.store.engine) as session:
            record = session.get(BatchRecord, result["batch_id"])
            queued = [runtime.queue.get_nowait() for _ in range(3)]
            assert queued == record.attempt_ids
            assert len(session.exec(select(Attempt)).all()) == 3
        assert all(ref() is None for ref in references)
    finally:
        runtime.store.engine.dispose()


@pytest.mark.parametrize("failure", ["cancel", "parse", "gate"])
def test_incomplete_batch_cleans_its_files_without_partial_jobs(tmp_path, monkeypatch, failure):
    runtime = runtime_for(tmp_path)
    add_fixture(runtime, "clean/one.pdf")
    add_fixture(runtime, "clean/two.pdf")
    previews = tmp_path / "previews"
    previews.mkdir()
    retained = previews / "prior.png"
    retained.write_bytes(b"existing evidence")
    count = 0

    async def render(**kwargs):
        nonlocal count
        count += 1
        if count == 2:
            assert len(list(previews.iterdir())) == 2
            if failure == "cancel":
                raise asyncio.CancelledError
            if failure == "parse":
                raise InputError("synthetic bad fixture")
            runtime.settings.batch_enabled = False
        return Document(kind="pdf", page_count=1, images=[b"private preview"])

    monkeypatch.setattr(runtime, "ingest", render)
    expected = {"cancel": asyncio.CancelledError, "parse": InputError, "gate": HTTPException}[
        failure
    ]
    try:
        with pytest.raises(expected):
            asyncio.run(create_batch(runtime))
        assert runtime.queue.empty() and not runtime.admission.locked()
        assert list(previews.iterdir()) == [retained]
        assert retained.read_bytes() == b"existing evidence"
        with Session(runtime.store.engine) as session:
            assert session.exec(select(Attempt)).all() == []
            assert session.exec(select(BatchRecord)).all() == []
        assert not runtime.chain.sent
    finally:
        runtime.store.engine.dispose()


def test_batch_rechecks_gate_after_waiting_for_admission(tmp_path):
    async def run():
        runtime = runtime_for(tmp_path)
        add_fixture(runtime)
        try:
            async with runtime.admission:
                waiting = asyncio.create_task(create_batch(runtime))
                await asyncio.sleep(0)
                runtime.settings.batch_enabled = False
            with pytest.raises(HTTPException) as exc:
                await waiting
            assert exc.value.status_code == 503
            assert not (tmp_path / "previews").exists()
            assert runtime.queue.empty()
        finally:
            runtime.store.engine.dispose()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["missing", "outside", "oversized"])
def test_worker_stored_input_failure_sends_nothing_and_recovers(tmp_path, failure):
    async def run():
        runtime = runtime_for(tmp_path)
        inputs = tmp_path / "uploads"
        inputs.mkdir()
        path = inputs / "bad.pdf"
        if failure == "outside":
            path = tmp_path / "outside.pdf"
            path.write_bytes(make_pdf())
        elif failure == "oversized":
            path.write_bytes(b"x" * (MAX_BYTES + 1))
        bad = new_attempt(
            runtime.chain.registry,
            network="testnet",
            source="team",
            agent="guarded",
            input_kind="pdf",
            file_path=str(path),
        )
        good = new_attempt(
            runtime.chain.registry,
            network="testnet",
            source="team",
            agent="guarded",
            input_kind="text",
            input_text="Invoice",
        )
        runtime.store.save(bad)
        runtime.store.save(good)
        runtime.queue.put_nowait(bad.id)
        worker = asyncio.create_task(runtime.worker())
        try:
            await asyncio.wait_for(runtime.queue.join(), 3)
            failed = runtime.store.get(bad.id)
            assert failed.outcome == "error" and failed.error == "WORKER_ERROR"
            assert [step["status"] for step in failed.steps] == ["failed"] + ["skipped"] * 4
            assert failed.tx_hash is None and not runtime.chain.sent
            runtime.queue.put_nowait(good.id)
            await asyncio.wait_for(runtime.queue.join(), 3)
            assert runtime.store.get(good.id).outcome == "paid"
            assert len(runtime.chain.sent) == 1
            # Re-delivery of a terminal job must not reload or pay it again.
            runtime.queue.put_nowait(good.id)
            await asyncio.wait_for(runtime.queue.join(), 3)
            assert len(runtime.chain.sent) == 1
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            runtime.store.engine.dispose()

    asyncio.run(run())


def test_private_write_permissions_and_existing_file_preserved(tmp_path):
    path = tmp_path / "uploads" / "invoice.pdf"
    storage.write_private_bytes(path, b"private invoice")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        storage.write_private_bytes(path, b"replacement")
    assert path.read_bytes() == b"private invoice"


def test_partial_private_write_is_removed(tmp_path, monkeypatch):
    original = storage.os.fdopen

    class FailedWrite:
        def __init__(self, descriptor, mode, **kwargs):
            self.stream = original(descriptor, mode, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, data):
            self.stream.write(data[:3])
            self.stream.flush()
            raise OSError("synthetic disk failure")

    monkeypatch.setattr(storage.os, "fdopen", FailedWrite)
    path = tmp_path / "uploads" / "failed.pdf"
    with pytest.raises(OSError, match="synthetic"):
        storage.write_private_bytes(path, b"invoice")
    assert not path.exists()
