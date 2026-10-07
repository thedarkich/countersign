from app.api.schemas import AttemptView, LedgerEventView, Proposal, StatBlock
from app.chain.indexer import LABELS, REASONS
from app.pipeline.agents import human_amount

CHANGE_LABELS = {
    "ChangeQueued": ("Rule change queued", "规则变更已排队"),
    "ChangeExecuted": ("Rule change executed", "规则变更已执行"),
    "ChangeCancelled": ("Rule change cancelled", "规则变更已取消"),
    "VendorDeactivated": ("Vendor deactivated", "供应商已停用"),
    "POClosed": ("Purchase order closed", "采购订单已关闭"),
    "AgentRevoked": ("Agent key revoked", "代理密钥已撤销"),
    "DailyCapLowered": ("Daily cap lowered", "每日限额已降低"),
    "Paused": ("Vault paused", "金库已暂停"),
}


def attempt_view(attempt, *, private):
    fields = {
        key: getattr(attempt, key)
        for key in ("id", "status", "outcome", "agent", "source", "ai_fooled", "created_at")
    }
    fields.update(steps=[], extraction=None, hidden_text=None, flags=[], proposal=None, tx=None)
    # Anonymous requests get outcomes only, including none of the uploaded/LLM-derived text.
    if private:
        fields.update(
            {
                key: getattr(attempt, key)
                for key in (
                    "nickname",
                    "input_kind",
                    "file_name",
                    "steps",
                    "extraction",
                    "hidden_text",
                    "flags",
                    "proposal",
                    "tx",
                    "latency_ms",
                )
            }
        )
        if attempt.proposal:
            fields["proposal"] = {
                key: value
                for key, value in attempt.proposal.items()
                if key in Proposal.model_fields
            }
        fields["preview_url"] = (
            f"/api/attempts/{attempt.id}/preview.png" if attempt.preview_path else None
        )
    return AttemptView(**fields)


def ledger_view(event, state):
    config = state["config"]
    args = event.args
    agent = next(
        (
            label
            for label, address in config["agents"].items()
            if address.lower() == str(args.get("agent", "")).lower()
        ),
        None,
    )
    reason = None
    if event.name == "Blocked":
        index = args.get("reason", 0)
        reason = REASONS[index] if isinstance(index, int) and 0 < index < len(REASONS) else None
    labels = LABELS.get(reason, (None, None))
    summary = CHANGE_LABELS.get(event.name, (None, None))
    vendor = next(
        (v for v in state["registry"]["vendors"] if v["id"] == args.get("vendorId")), None
    )
    return LedgerEventView(
        id=f"{event.network}:{event.contract_address}:{event.tx_hash}:{event.log_index}",
        name=event.name,
        tx_hash=event.tx_hash,
        explorer_url=config["explorer_url"].rstrip("/") + "/tx/" + event.tx_hash,
        block_time=event.block_time,
        agent=agent,
        vendor_id=args.get("vendorId"),
        vendor_name=vendor["name_en"] if vendor else None,
        amount=human_amount(args["amount"], config["token"]["decimals"])
        if "amount" in args
        else None,
        pay_to=args.get("payTo"),
        reason=reason,
        reason_label_en=labels[0],
        reason_label_zh=labels[1],
        summary_en=summary[0],
        summary_zh=summary[1],
        network=event.network,
    )


def stat_block(attempts, events, decimals):
    result = StatBlock(
        attempts=len(attempts), people=len({a.device_id for a in attempts if a.device_id})
    )
    indexed = {
        (e.network, e.contract_address.lower(), e.tx_hash.lower()): e
        for e in events
        if e.name in {"Paid", "Blocked"}
    }
    paid_base = 0
    for attempt in attempts:
        if attempt.outcome == "refused" and attempt.agent == "guarded":
            result.guard_catches += 1
        if attempt.ai_fooled:
            result.ai_fooled[attempt.agent] += 1
        event = indexed.get(
            (attempt.network, attempt.contract_address.lower(), (attempt.tx_hash or "").lower())
        )
        if not event or event.args.get("agent", "").lower() != attempt.agent_address.lower():
            continue
        if event.name == "Blocked":
            result.chain_blocks += 1
        elif event.name == "Paid":
            # This vault emits Paid only after paying its registry address. Proposed addresses,
            # post-payment registry edits and unconfirmed RPC results are not loss evidence.
            paid_base += int(event.args["amount"])
    result.paid_real_vendor_on_fake_invoice = human_amount(paid_base, decimals)
    return result
