from dataclasses import dataclass

from eth_utils import is_address, to_checksum_address

from app.pipeline.amounts import invoice_hash, to_base_units
from app.pipeline.match import Match, Vendor
from app.schemas import NaiveDecision


@dataclass(frozen=True)
class PaymentProposal:
    vendor_id: int
    pay_to: str
    po_id: int
    amount_base: int
    invoice_hash: str


def guarded_proposal(match: Match) -> PaymentProposal:
    if (
        match.vendor is None
        or match.po is None
        or match.amount_base is None
        or match.invoice_hash is None
        or any(f.severity == "high" for f in match.flags)
    ):
        raise ValueError("Guarded proposal requires a valid match")
    return PaymentProposal(
        match.vendor.id, match.vendor.payout, match.po.id, match.amount_base, match.invoice_hash
    )


def naive_proposal(
    decision: NaiveDecision, vendors: list[Vendor], decimals: int
) -> PaymentProposal:
    payout = decision.pay_to
    if not is_address(payout):
        vendor = next((item for item in vendors if item.id == decision.vendor_id), None)
        if vendor is None:
            raise ValueError("No registry payout for unknown vendor")
        payout = vendor.payout
    # Unknown IDs intentionally pass through: only the contract can authorize payment.
    return PaymentProposal(
        decision.vendor_id,
        to_checksum_address(payout),
        decision.po_id,
        to_base_units(decision.amount, decimals),
        invoice_hash(decision.vendor_id, decision.invoice_number),
    )


def human_amount(amount_base: int, decimals: int) -> str:
    if decimals == 0:
        return str(amount_base)
    digits = str(amount_base).zfill(decimals + 1)
    return (digits[:-decimals] + "." + digits[-decimals:]).rstrip("0").rstrip(".")
