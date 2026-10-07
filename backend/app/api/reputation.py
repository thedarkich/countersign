"""Public, evidence-derived payment-agent history. No invoice-derived public text."""

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal

from sqlmodel import Session, select

from app.chain.indexer import REASONS
from app.models import Attempt, ChainEvent, IndexCursor, now_iso
from app.pipeline.amounts import to_base_units
from app.schemas import StrictModel


class Counts(StrictModel):
    observations: int = 0
    attempts: int = 0
    refusals: int = 0
    proposals: int = 0
    known_attack_attempts: int = 0
    known_attack_refusals: int = 0
    suspicious_proposals: int = 0
    confirmed_payments: int = 0
    policy_blocks: int = 0
    errors: int = 0
    receipt_only: int = 0
    unverified: int = 0


class Observation(StrictModel):
    id: str
    time: str
    source: Literal["bounty", "seed", "team", "batch", "unknown"]
    scenario: Literal["known_attack", "clean_fixture", "unlabeled", "unknown"]
    model_versions: dict[str, str]
    guard_version: str | None
    outcome: Literal["paid", "blocked", "refused", "no_invoice", "error", "pending", "unverified"]
    reason_codes: list[str]
    evidence: list[Literal["application_record", "verified_transaction"]]
    transaction_url: str | None
    suspicious: bool
    summary_en: str
    summary_zh: str


class Breakdown(StrictModel):
    source: str
    scenario: str
    model_versions: dict[str, str]
    guard_version: str | None
    counts: Counts


class AgentHistory(StrictModel):
    id: str
    chain_id: int
    contract_address: str
    agent_address: str
    label: Literal["guarded", "naive"]
    role_en: str
    role_zh: str
    active: bool
    status: Literal["no_history", "no_flag_observed", "suspicious_observed"]
    status_en: str
    status_zh: str
    first_observed_at: str | None
    last_observed_at: str | None
    counts: Counts
    breakdown: list[Breakdown]
    recent_observations: list[Observation]


class Coverage(StrictModel):
    network: str
    chain_id: int
    contract_address: str
    observed_from_block: int | None
    observed_to_block: int | None
    scan_from_block: int | None
    scanned_through_block: int | None
    last_sync: str | None
    stale: bool
    gaps: list[str]
    scope: Literal["configured_vault_observed_history"] = "configured_vault_observed_history"


class ReputationView(StrictModel):
    agents: list[AgentHistory]
    updated_at: str
    coverage: Coverage


STATUSES = {
    "no_history": ("No history", "暂无历史"),
    "no_flag_observed": (
        "No suspicious proposal observed in this history",
        "此历史中尚未观察到可疑提案",
    ),
    "suspicious_observed": ("Suspicious proposal observed — review", "观察到可疑提案，请审核"),
}
SUMMARIES = {
    "suspicious": (
        "Suspicious proposal observed; review the evidence.",
        "观察到可疑提案，请查看证据。",
    ),
    "refused": ("The guard refused this input.", "守卫已拒绝该输入。"),
    "paid": ("Payment executed within vault rules.", "付款已按金库规则执行。"),
    "blocked": ("The vault blocked the proposed payment.", "金库已阻止该付款提案。"),
    "error": (
        "Processing or execution error; no confirmed payment here.",
        "处理或执行出错，此处没有已确认付款。",
    ),
    "no_invoice": ("No invoice was identified.", "未识别到发票。"),
    "pending": ("Processing or confirmation is pending.", "处理或确认尚未完成。"),
    "unverified": (
        "The claimed chain outcome lacks indexed receipt evidence.",
        "所述链上结果尚缺已索引回执证据。",
    ),
}


def versions(attempt):
    # Provider identifiers are metadata, not a channel for arbitrary generated prose.
    return {
        key: value
        for key, value in attempt.model_versions.items()
        if key in {"extract", "guard", "naive"}
        and isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_/.:+\-]{1,120}", value)
    }


def matches(attempt, event, decimals):
    proposal = attempt.proposal or {}
    try:
        amount = (
            int(proposal["amount_base"])
            if "amount_base" in proposal
            else to_base_units(proposal["amount"], decimals)
        )
        return (
            event.args["agent"].lower() == attempt.agent_address.lower()
            and event.args["vendorId"] == proposal["vendor_id"]
            and event.args["poId"] == proposal["po_id"]
            and event.args["amount"] == amount
            and event.args["payTo"].lower() == proposal["pay_to"].lower()
            and event.args["invoiceHash"].lower() == proposal["invoice_hash"].lower()
        )
    except (KeyError, ValueError, TypeError):
        return False


def observation(attempt, event, explorer):
    source, scenario, model, guard = "unknown", "unknown", {}, None
    reasons, evidence = [], []
    count = Counts(observations=1)
    if attempt:
        source, scenario, model = attempt.source, attempt.scenario, versions(attempt)
        guard = attempt.guard_version if attempt.guard_version in {"v1", "v2"} else None
        count.attempts = 1
        count.refusals = int(attempt.outcome == "refused")
        count.proposals = int(attempt.proposal is not None)
        count.known_attack_attempts = int(scenario == "known_attack")
        count.known_attack_refusals = int(
            scenario == "known_attack" and attempt.outcome == "refused"
        )
        if count.proposals and scenario == "known_attack":
            reasons.append("KNOWN_ATTACK_PROPOSAL")
        evidence.append("application_record")
        outcome = attempt.outcome or "pending"
        if outcome in {"paid", "blocked"} and not event:
            outcome = "unverified"
        identifier, observed_at = "attempt:" + attempt.id, attempt.created_at
    else:
        count.receipt_only = count.proposals = 1
        identifier = (
            f"receipt:{event.network}:{event.contract_address}:{event.tx_hash}:{event.log_index}"
        )
        observed_at, outcome = event.block_time, "unverified"
    url = None
    if event:
        outcome = event.name.lower()
        evidence.append("verified_transaction")
        url = explorer.rstrip("/") + "/tx/" + event.tx_hash
        if event.name == "Blocked":
            reason = event.args.get("reason")
            if isinstance(reason, int) and 0 < reason < len(REASONS):
                reasons.append(REASONS[reason])
    suspicious = bool("KNOWN_ATTACK_PROPOSAL" in reasons or "PayoutMismatch" in reasons)
    count.suspicious_proposals = int(suspicious)
    count.confirmed_payments = int(outcome == "paid")
    count.policy_blocks = int(outcome == "blocked")
    count.errors = int(outcome == "error")
    count.unverified = int(outcome == "unverified")
    summary = SUMMARIES["suspicious" if suspicious else outcome]
    return Observation(
        id=identifier,
        time=observed_at,
        source=source,
        scenario=scenario,
        model_versions=model,
        guard_version=guard,
        outcome=outcome,
        reason_codes=reasons,
        evidence=evidence,
        transaction_url=url,
        suspicious=suspicious,
        summary_en=summary[0],
        summary_zh=summary[1],
    ), count


def build_reputation(engine, state, *, limit=20, indexer_enabled=True):
    config = state["config"]
    network, vault = config["network"], config["contract_address"].lower()
    with Session(engine) as session:
        attempts = session.exec(
            select(Attempt)
            .where(
                Attempt.network == network,
                Attempt.chain_id == config["chain_id"],
                Attempt.contract_address == vault,
            )
            .order_by(Attempt.created_at, Attempt.id)
        ).all()
        events = session.exec(
            select(ChainEvent)
            .where(
                ChainEvent.network == network,
                ChainEvent.contract_address == vault,
                ChainEvent.name.in_(["Paid", "Blocked"]),
            )
            .order_by(ChainEvent.block_number, ChainEvent.log_index)
        ).all()
        cursor = session.get(IndexCursor, f"{network}:{vault}")
    identities = {address.lower(): label for label, address in config["agents"].items()}
    for attempt in attempts:
        identities.setdefault(attempt.agent_address.lower(), attempt.agent)
    records, consumed = defaultdict(list), set()
    by_tx = defaultdict(list)
    for event in events:
        by_tx[event.tx_hash.lower()].append(event)
    for attempt in attempts:
        event = next(
            (
                event
                for event in by_tx[(attempt.tx_hash or "").lower()]
                if event.id not in consumed and matches(attempt, event, config["token"]["decimals"])
            ),
            None,
        )
        if event:
            consumed.add(event.id)
        records[attempt.agent_address.lower()].append(
            observation(attempt, event, config["explorer_url"])
        )
    for event in events:
        address = str(event.args.get("agent", "")).lower()
        if event.id not in consumed and address in identities:
            records[address].append(observation(None, event, config["explorer_url"]))
    active = {agent["address"].lower(): agent["active"] for agent in state["registry"]["agents"]}
    agents = []
    for address, label in identities.items():
        history = sorted(
            records[address], key=lambda item: (item[0].time, item[0].id), reverse=True
        )
        total, groups = Counts(), {}
        for obs, counts in history:
            key = (
                obs.source,
                obs.scenario,
                json.dumps(obs.model_versions, sort_keys=True),
                obs.guard_version,
            )
            if key not in groups:
                groups[key] = Breakdown(
                    source=obs.source,
                    scenario=obs.scenario,
                    model_versions=obs.model_versions,
                    guard_version=obs.guard_version,
                    counts=Counts(),
                )
            for name in Counts.model_fields:
                setattr(total, name, getattr(total, name) + getattr(counts, name))
                setattr(
                    groups[key].counts,
                    name,
                    getattr(groups[key].counts, name) + getattr(counts, name),
                )
        status = (
            "no_history"
            if not history
            else ("suspicious_observed" if total.suspicious_proposals else "no_flag_observed")
        )
        labels = STATUSES[status]
        agents.append(
            AgentHistory(
                id=f"{config['chain_id']}:{vault}:{address}",
                chain_id=config["chain_id"],
                contract_address=vault,
                agent_address=address,
                label=label,
                role_en="Deliberately unguarded demo agent"
                if label == "naive"
                else "Guarded payment agent",
                role_zh="故意不设守卫的演示代理" if label == "naive" else "受守卫保护的付款代理",
                active=active.get(address, False),
                status=status,
                status_en=labels[0],
                status_zh=labels[1],
                first_observed_at=history[-1][0].time if history else None,
                last_observed_at=history[0][0].time if history else None,
                counts=total,
                breakdown=list(groups.values()),
                recent_observations=[obs for obs, _ in history[:limit]],
            )
        )
    stale = (
        not cursor
        or not cursor.updated_at
        or (datetime.now(UTC) - datetime.fromisoformat(cursor.updated_at)).total_seconds() > 120
    )
    gaps = ["OBSERVED_HISTORY_ONLY", "EXPLORER_DISCOVERY_DEPENDENCY"]
    if not indexer_enabled:
        gaps.append("INDEXER_DISABLED")
    if not cursor or not cursor.updated_at:
        gaps.append("BACKFILL_NOT_VERIFIED")
    elif cursor.error:
        gaps.append(cursor.error)
    if stale:
        gaps.append("INDEXER_STALE")
    return ReputationView(
        agents=agents,
        updated_at=now_iso(),
        coverage=Coverage(
            network=network,
            chain_id=config["chain_id"],
            contract_address=vault,
            observed_from_block=min((e.block_number for e in events), default=None),
            observed_to_block=max((e.block_number for e in events), default=None),
            scan_from_block=cursor.start_block if cursor else None,
            scanned_through_block=cursor.last_block if cursor and cursor.last_hash else None,
            last_sync=cursor.updated_at if cursor else None,
            stale=bool(stale),
            gaps=gaps,
        ),
    )
