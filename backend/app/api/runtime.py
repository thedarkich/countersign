import asyncio
import fcntl
import json
import os
import time
from contextlib import suppress
from pathlib import Path

from sqlmodel import Session, select

from app.api.schemas import AppConfig, DemoInvoice, Registry
from app.api.security import RateLimiter, problem
from app.chain.backfill import Backfiller
from app.chain.client import VaultClient
from app.chain.recovery import Reconciler
from app.chain.state import read_state, report_receipt
from app.db import AttemptStore
from app.models import Attempt, StateCache, now_iso
from app.pipeline.extract import InvoiceModels
from app.pipeline.ingest import MAX_BYTES, InputError, ingest_text
from app.pipeline.isolated_ingest import ingest_isolated
from app.pipeline.runner import PipelineRunner
from app.threat_intel import WalletScreening


class Runtime:
    def __init__(
        self, settings, *, chain=None, models=None, state_reader=None, receipt_reader=None
    ):
        self.settings = settings
        self.store = AttemptStore(settings.data_dir / "countersign.db")
        self.chain = chain or VaultClient.from_settings(settings, engine=self.store.engine)
        self.models = models or InvoiceModels.from_settings(settings, engine=self.store.engine)
        self.screening = WalletScreening(
            settings.data_dir,
            enabled=settings.scam_screening_enabled,
            max_age=settings.scam_snapshot_max_age_seconds,
        )
        self.runner = PipelineRunner(self.store, self.models, self.chain, screening=self.screening)
        self.limiter = RateLimiter(self.store.engine, settings)
        # Retain IDs only. A count-bounded queue of decoded PDFs can still consume
        # gigabytes; documents are loaded under worker limits when needed.
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.queue_capacity)
        self.ingest_slots = asyncio.Semaphore(2)
        self.admission = asyncio.Lock()
        self.states = {}
        self.refreshed = {}
        self.state_locks = {name: asyncio.Lock() for name in ("mainnet", "testnet")}
        self.state_reader = state_reader or (
            lambda network: read_state(self.chain, network, settings)
        )
        self.receipt_reader = receipt_reader or (
            lambda network, tx: report_receipt(self.chain, network, tx, self.store.engine)
        )
        self.tasks = []
        self.process_lease = None
        self.sync_errors = set()
        self.reconciler = (
            Reconciler(self.chain, self.store) if isinstance(self.chain, VaultClient) else None
        )
        self.backfiller = (
            Backfiller(self.chain, self.store, settings)
            if self.reconciler and settings.indexer_enabled
            else None
        )

    async def start(self):
        descriptor = os.open(
            self.settings.data_dir / ".runtime.lock", os.O_CREAT | os.O_RDWR, 0o600
        )
        self.process_lease = os.fdopen(descriptor, "w")
        try:
            fcntl.flock(self.process_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.process_lease.close()
            self.process_lease = None
            raise RuntimeError("Only one backend process may own this data directory") from None
        # No blind replay after a crash: a sending job may already have spent money.
        with Session(self.store.engine) as session:
            unfinished = session.exec(
                select(Attempt).where(Attempt.status.notin_(["done", "error"]))
            ).all()
            for attempt in unfinished:
                attempt.status, attempt.outcome, attempt.error = (
                    "error",
                    "error",
                    "INTERRUPTED_REVIEW_REQUIRED",
                )
                attempt.steps = [
                    dict(step, status="failed", detail=attempt.error, ended_at=now_iso())
                    if step["status"] in {"pending", "running"}
                    else step
                    for step in attempt.steps
                ]
                session.add(attempt)
            session.commit()
        self.tasks = [asyncio.create_task(self.worker()) for _ in range(3)]
        self.tasks.append(asyncio.create_task(self.refresh_loop()))
        if self.screening.enabled:
            self.tasks.append(asyncio.create_task(self.screening.refresh_loop()))
        if self.reconciler:
            self.tasks.append(asyncio.create_task(self.recovery_loop()))
        if self.backfiller:
            self.tasks.append(asyncio.create_task(self.backfill_loop()))

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        gateway = getattr(self.models, "gateway", None)
        if gateway:
            await gateway.client.close()
        if self.backfiller:
            self.backfiller.close()
        self.store.engine.dispose()
        if self.process_lease:
            self.process_lease.close()
            self.process_lease = None

    async def worker(self):
        while True:
            attempt_id = await self.queue.get()
            document = None
            try:
                attempt = self.store.get(attempt_id)
                if attempt.status != "queued":
                    continue
                document = await self.load_document(attempt)
                await self.runner.run(attempt_id, document)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Persistence/worker failures contain no provider body in public records.
                with suppress(Exception):
                    attempt = self.store.get(attempt_id)
                    attempt.status = attempt.outcome = "error"
                    attempt.error = "WORKER_ERROR"
                    attempt.steps = [
                        dict(
                            step,
                            status="failed" if step["name"] == "extract" else "skipped",
                            detail=attempt.error if step["name"] == "extract" else None,
                            ended_at=now_iso(),
                        )
                        if step["status"] in {"pending", "running"}
                        else step
                        for step in attempt.steps
                    ]
                    self.store.save(attempt)
            finally:
                # Do not retain the last image while this worker waits for a job.
                document = None
                self.queue.task_done()

    async def load_document(self, attempt):
        if attempt.input_kind == "text":
            return await self.ingest(text=attempt.input_text or "")
        path = Path(attempt.file_path or "").resolve(strict=True)
        roots = [(self.settings.data_dir / folder).resolve() for folder in ("uploads", "invoices")]
        if not path.is_file() or not any(path.is_relative_to(root) for root in roots):
            raise InputError("Stored invoice is outside the input directories")
        # Bound the actual read too, even if the file changed after admission.
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        return await self.ingest(data=data)

    def check_submission(self, *, bounty=False, batch=False):
        if bounty and not self.settings.bounty_enabled:
            raise problem(503, "The public bounty is not open yet.", "公开挑战尚未开放。")
        if batch and not self.settings.batch_enabled:
            raise problem(503, "Paid batch runs are disabled.", "付费批量处理尚未启用。")
        if not self.settings.llm_enabled:
            raise problem(
                503, "AI processing is disabled for this checkpoint.", "当前版本尚未启用 AI 处理。"
            )
        if self.screening.enabled and not self.screening.view().ready:
            raise problem(
                503,
                "Wallet risk data is unavailable or stale; payments are held.",
                "钱包风险数据不可用或已过期，付款暂缓。",
            )
        gateway = getattr(self.models, "gateway", None)
        if gateway and gateway.exhausted():
            raise problem(503, "Hourly AI call limit reached.", "已达到每小时 AI 调用上限。")
        if self.queue.full():
            raise problem(503, "Processing queue is full. Try later.", "处理队列已满，请稍后再试。")

    async def ingest(self, *, data=None, text=None):
        async with self.ingest_slots:
            return await ingest_isolated(data) if data is not None else ingest_text(text)

    async def state(self, network, *, force=False):
        # A background RPC refresh must not block readers of a still-fresh snapshot.
        if (
            not force
            and network in self.states
            and time.monotonic() - self.refreshed.get(network, 0) < 10
        ):
            return self.states[network]
        async with self.state_locks[network]:
            if (
                not force
                and network in self.states
                and time.monotonic() - self.refreshed.get(network, 0) < 10
            ):
                return self.states[network]
            try:
                state = await asyncio.to_thread(self.state_reader, network)
                AppConfig.model_validate(state["config"])
                Registry.model_validate(state["registry"])
                if (
                    state["config"]["network"] != network
                    or state["config"]["chain_id"] != {"testnet": 968, "mainnet": 677}[network]
                ):
                    raise ValueError("State network mismatch")
                self.states[network], self.refreshed[network] = state, time.monotonic()
                with Session(self.store.engine) as session:
                    session.merge(StateCache(network=network, updated_at=now_iso(), payload=state))
                    session.commit()
                self.sync_errors.discard(network)
                return state
            except Exception:
                self.sync_errors.add(network)
                raise problem(
                    503,
                    "Verified chain state is temporarily unavailable.",
                    "暂时无法获取已验证的链上状态。",
                ) from None

    async def refresh_loop(self):
        while True:
            for network in {self.settings.network, self.settings.bounty_network}:
                with suppress(Exception):
                    await self.state(network, force=True)
            await asyncio.sleep(10)

    async def recovery_loop(self):
        while True:
            with suppress(Exception):
                await asyncio.to_thread(self.reconciler.run, self.settings.recovery_batch_size)
            await asyncio.sleep(self.settings.indexer_interval_seconds)

    async def backfill_loop(self):
        while True:
            for network in self.chain.networks:
                with suppress(Exception):
                    await asyncio.to_thread(self.backfiller.sync, network)
            await asyncio.sleep(self.settings.indexer_interval_seconds)

    def manifest(self):
        path = self.settings.data_dir / "invoices" / "manifest.json"
        if not path.exists():
            return []
        entries = json.loads(path.read_text())
        if not isinstance(entries, list):
            raise ValueError("Manifest must be a list")
        return entries

    def demo(self, name, *, stage=True):
        entry = next(
            (
                e
                for e in self.manifest()
                if e.get("name") == name and (not stage or e.get("stage") is True)
            ),
            None,
        )
        if not entry:
            raise problem(400, "Unknown demo invoice.", "未知演示发票。")
        # Membership in a server manifest is required in addition to path confinement.
        root = (self.settings.data_dir / "invoices").resolve()
        path = (root / name).resolve()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}
        ):
            raise problem(400, "Invalid demo invoice.", "演示发票无效。")
        public = DemoInvoice.model_validate(
            {k: entry[k] for k in DemoInvoice.model_fields if k in entry}
        )
        return path, public

    def health(self):
        reasons = []
        if self.screening.enabled and not self.screening.view().ready:
            reasons.append("WALLET_SCREENING_UNAVAILABLE")
        if self.backfiller:
            reasons.extend(self.backfiller.health())
        if not self.settings.llm_enabled:
            reasons.append("AI_DISABLED")
        if not self.settings.transactions_enabled:
            reasons.append("TRANSACTIONS_DISABLED")
        if not self.settings.bounty_enabled:
            reasons.append("BOUNTY_NOT_OPEN")
        for network in {self.settings.network, self.settings.bounty_network}:
            if (
                network not in self.states
                or network in self.sync_errors
                or time.monotonic() - self.refreshed.get(network, 0) > 60
            ):
                reasons.append("CHAIN_STATE_UNAVAILABLE:" + network)
            elif any(
                float(agent["balance"]) < 0.5
                for agent in self.states[network]["registry"]["agents"]
                if agent["active"]
            ):
                reasons.append("LOW_AGENT_GAS:" + network)
        return {"ok": not reasons, "degraded_reasons": reasons}
