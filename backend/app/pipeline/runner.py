"""Persistent pipeline orchestration; chain access is an injected adapter."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol

from app.chain.errors import ChainSendError
from app.db import AttemptStore
from app.llm import ModelUnavailable
from app.models import Attempt, now_iso
from app.pipeline.agents import PaymentProposal, guarded_proposal, human_amount, naive_proposal
from app.pipeline.extract import InvoiceModels
from app.pipeline.guard import evaluate_guard
from app.pipeline.hidden_text import inspect_hidden_text
from app.pipeline.ingest import Document
from app.pipeline.match import PurchaseOrder, Vendor, flag, match_invoice


@dataclass(frozen=True)
class RegistrySnapshot:
    chain_id: int
    contract_address: str
    agent_addresses: dict[str, str]
    vendors: list[Vendor]
    pos: list[PurchaseOrder]
    decimals: int
    symbol: str


class ChainAdapter(Protocol):
    async def snapshot(self, network: str) -> RegistrySnapshot: ...
    async def invoice_paid(self, network: str, invoice_hash: str) -> bool: ...
    async def send(
        self,
        network: str,
        agent: str,
        proposal: PaymentProposal,
        on_broadcast: Callable[[str], None],
        *,
        on_prepared: Callable[[str], None] | None = None,
    ) -> dict: ...


def new_attempt(
    snapshot: RegistrySnapshot,
    *,
    network: str,
    source: str,
    agent: str,
    fixture_kind: str | None = None,
    **private_fields,
) -> Attempt:
    if (
        network not in {"mainnet", "testnet"}
        or snapshot.chain_id != {"mainnet": 677, "testnet": 968}[network]
    ):
        raise ValueError("Network identity mismatch")
    if source not in {"bounty", "seed", "team", "batch"} or agent not in {"guarded", "naive"}:
        raise ValueError("Invalid attempt source or agent")
    # fixture_kind comes only from a server manifest, never a submitted form.
    scenario = (
        "known_attack"
        if source in {"bounty", "seed"} or fixture_kind == "poisoned"
        else ("clean_fixture" if fixture_kind == "clean" else "unlabeled")
    )
    allowed = {
        "device_id",
        "nickname",
        "claimed_address",
        "input_kind",
        "file_path",
        "file_name",
        "input_text",
        "preview_path",
        "demo_name",
    }
    if set(private_fields) - allowed:
        raise ValueError("Unexpected attempt metadata")
    return Attempt(
        network=network,
        chain_id=snapshot.chain_id,
        source=source,
        agent=agent,
        agent_address=snapshot.agent_addresses[agent].lower(),
        contract_address=snapshot.contract_address.lower(),
        scenario=scenario,
        **private_fields,
    )


class PipelineRunner:
    def __init__(self, store: AttemptStore, models: InvoiceModels, chain: ChainAdapter):
        self.store, self.models, self.chain = store, models, chain
        self.pool = asyncio.Semaphore(3)

    def _step(self, attempt: Attempt, name: str, status: str, detail: str | None = None):
        for step in attempt.steps:
            if step["name"] == name:
                step["status"], step["detail"] = status, detail
                step["started_at" if status == "running" else "ended_at"] = now_iso()
                break
        self.store.save(attempt)

    def _finish(self, attempt: Attempt, outcome: str):
        attempt.outcome = outcome
        attempt.status = "error" if outcome == "error" else "done"
        for step in attempt.steps:
            if step["status"] == "pending":
                step.update(status="skipped", ended_at=now_iso())
        self.store.save(attempt)

    async def run(self, attempt_id: str, document: Document) -> Attempt:
        async with self.pool:
            attempt = self.store.claim(attempt_id)
            if attempt is None:
                return self.store.get(attempt_id)
            started = time.monotonic()
            try:
                await self._run(attempt, document)
            except Exception as exc:
                if isinstance(exc, ChainSendError) and exc.tx_hash:
                    attempt.tx_hash = exc.tx_hash
                # Do not publish exception strings: provider/RPC errors can contain private inputs.
                attempt.error = (
                    "MODEL_UNAVAILABLE" if isinstance(exc, ModelUnavailable) else "PROCESSING_ERROR"
                )
                for step in attempt.steps:
                    if step["status"] == "running":
                        step.update(status="failed", ended_at=now_iso(), detail=attempt.error)
                self._finish(attempt, "error")
            finally:
                attempt.latency_ms = int((time.monotonic() - started) * 1000)
                self.store.save(attempt)
            return attempt

    async def _run(self, attempt: Attempt, document: Document):
        registry = await self.chain.snapshot(attempt.network)
        if (
            registry.chain_id != attempt.chain_id
            or registry.contract_address.lower() != attempt.contract_address
            or registry.agent_addresses[attempt.agent].lower() != attempt.agent_address
        ):
            raise ValueError("Chain identity changed")
        self._step(attempt, "extract", "running")
        extraction = await self.models.extract(document, attempt.model_versions)
        attempt.extraction = extraction.model_dump()
        self._step(attempt, "extract", "done")
        if not extraction.is_invoice:
            self._finish(attempt, "no_invoice")
            return
        attempt.status = "checking"
        self._step(attempt, "hidden_text", "running")
        hidden, flags = inspect_hidden_text(document, extraction.visible_text)
        attempt.hidden_text = hidden.model_dump()
        self._step(attempt, "hidden_text", "done" if document.kind == "pdf" else "skipped")
        self._step(attempt, "match", "running")
        matched = match_invoice(
            extraction,
            registry.vendors,
            registry.pos,
            registry.decimals,
            lambda _: False,
            token_symbol=registry.symbol,
        )
        if matched.invoice_hash and await self.chain.invoice_paid(
            attempt.network, matched.invoice_hash
        ):
            matched.flags.append(
                flag("DUPLICATE_INVOICE", "This invoice was already paid.", "该发票已支付。")
            )
        flags.extend(matched.flags)
        attempt.match = asdict(matched)
        # Pydantic flags need JSON dictionaries inside the internal dataclass snapshot.
        attempt.match["flags"] = [item.model_dump() for item in matched.flags]
        attempt.flags = [item.model_dump() for item in flags]
        self._step(attempt, "match", "done")
        attempt.status = "deciding"
        self._step(attempt, "guard", "running")
        if attempt.agent == "guarded":
            attempt.guard_version = self.models.guard_version
            # A deterministic refusal needs no paid second opinion.
            verdict = None
            if not any(item.severity == "high" for item in flags):
                verdict = await self.models.guard(
                    {
                        "extraction": extraction.model_dump(),
                        "hidden_text": hidden.model_dump(),
                        "vendor": asdict(matched.vendor) if matched.vendor else None,
                        "purchase_order": asdict(matched.po) if matched.po else None,
                        "flags": attempt.flags,
                    },
                    attempt.model_versions,
                )
                attempt.guard = verdict.model_dump()
            refused, flags = evaluate_guard(flags, verdict)
            attempt.flags = [item.model_dump() for item in flags]
            self._step(attempt, "guard", "done", "refused" if refused else None)
            if refused:
                self._finish(attempt, "refused")
                return
            proposal = guarded_proposal(matched)
        else:
            decision = await self.models.naive(
                {
                    "visible_text": extraction.visible_text,
                    "full_text_layer": document.text,
                    "extraction": extraction.model_dump(),
                    "vendors": [asdict(vendor) for vendor in registry.vendors],
                    "purchase_orders": [asdict(po) for po in registry.pos],
                },
                attempt.model_versions,
            )
            proposal = naive_proposal(decision, registry.vendors, registry.decimals)
            self._step(attempt, "guard", "skipped", "Deliberately unguarded demo agent")
        vendor = next((item for item in registry.vendors if item.id == proposal.vendor_id), None)
        po = next((item for item in registry.pos if item.id == proposal.po_id), None)
        attempt.proposal = {
            "vendor_id": proposal.vendor_id,
            "vendor_name": vendor.name_en if vendor else None,
            "pay_to": proposal.pay_to,
            "registry_payout": vendor.payout if vendor else None,
            "po_id": proposal.po_id,
            "po_ref": po.ref if po else None,
            "amount": human_amount(proposal.amount_base, registry.decimals),
            "amount_base": str(proposal.amount_base),
            "invoice_hash": proposal.invoice_hash,
        }
        attempt.status = "sending"
        self._step(attempt, "chain", "running")

        def broadcast(tx_hash: str):
            attempt.tx_hash = tx_hash
            attempt.ai_fooled = attempt.source in {"bounty", "seed"}
            self.store.save(attempt)

        def prepared(tx_hash: str):
            attempt.tx_hash = tx_hash
            self.store.save(attempt)

        tx = await self.chain.send(
            attempt.network, attempt.agent, proposal, broadcast, on_prepared=prepared
        )
        if (
            not attempt.tx_hash
            or tx.get("hash") != attempt.tx_hash
            or tx.get("event") not in {"Paid", "Blocked"}
        ):
            raise ValueError("Missing or mismatched confirmed payment event")
        attempt.tx = tx
        attempt.block_reason = tx.get("reason")
        self._step(attempt, "chain", "done")
        if attempt.ai_fooled and attempt.source == "bounty":
            # Fixed neutral fallback; do not spend the user's test balance on public copy.
            attempt.summary_en, attempt.summary_zh = (
                "Got a payment proposed",
                "让 AI 提出了一笔付款",
            )
        self._finish(attempt, "paid" if tx["event"] == "Paid" else "blocked")
