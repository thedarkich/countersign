from sqlmodel import Session

from app.api.security import problem
from app.models import BatchRecord
from app.pipeline.ingest import MAX_BYTES
from app.pipeline.runner import new_attempt
from app.storage import write_private_bytes


async def create_batch(runtime):
    runtime.check_submission(batch=True)
    entries = [
        e
        for e in runtime.manifest()
        if e.get("kind") == "clean" and e.get("name", "").startswith("clean/")
    ]
    if not entries:
        raise problem(
            400, "No clean training fixtures have been generated.", "尚未生成干净训练发票。"
        )
    async with runtime.admission:
        # The request may have waited behind another batch while gates changed.
        runtime.check_submission(batch=True)
        if len(entries) > runtime.queue.maxsize - runtime.queue.qsize():
            raise problem(
                503, "Not enough queue space for this batch.", "队列空间不足，无法接收此批次。"
            )
        snapshot = await runtime.chain.snapshot(runtime.settings.network)
        prepared, previews = [], []
        try:
            for entry in entries:
                path, demo = runtime.demo(entry["name"], stage=False)
                if path.stat().st_size > MAX_BYTES:
                    raise problem(400, "Fixture is too large.", "发票样本过大。")
                document = await runtime.ingest(data=path.read_bytes())
                attempt = new_attempt(
                    snapshot,
                    network=runtime.settings.network,
                    source="batch",
                    agent="guarded",
                    fixture_kind="clean",
                    file_path=str(path),
                    file_name=path.name,
                    input_kind=document.kind,
                    demo_name=demo.name,
                )
                if document.images:
                    preview = runtime.settings.data_dir / "previews" / (attempt.id + ".png")
                    write_private_bytes(preview, document.images[0])
                    previews.append(preview)
                    attempt.preview_path = str(preview)
                prepared.append(attempt)
                del document
            runtime.check_submission(batch=True)
            record = BatchRecord(attempt_ids=[a.id for a in prepared])
            batch_id = record.id
            jobs = [a.id for a in prepared]
            with Session(runtime.store.engine) as session:
                session.add_all(prepared)
                session.add(record)
                session.commit()
            for job in jobs:
                runtime.queue.put_nowait(job)
            return {"batch_id": batch_id}
        except BaseException:
            # Cancellation must clean only files created by this uncommitted batch.
            # CancelledError is a BaseException; always propagate after cleanup.
            for path in previews:
                path.unlink(missing_ok=True)
            raise
