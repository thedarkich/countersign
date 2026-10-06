import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from eth_utils import is_address, to_checksum_address
from rapidfuzz import fuzz, process

from app.pipeline.amounts import invoice_hash, normalize_po_reference, to_base_units
from app.schemas import Extraction, Flag


@dataclass(frozen=True)
class Vendor:
    id: int
    name_en: str
    name_zh: str
    aliases: tuple[str, ...]
    payout: str  # Trusted vault state, never invoice text or names JSON.


@dataclass(frozen=True)
class PurchaseOrder:
    id: int
    ref: str
    vendor_id: int
    remaining_base: int


@dataclass
class Match:
    vendor: Vendor | None = None
    po: PurchaseOrder | None = None
    amount_base: int | None = None
    invoice_hash: str | None = None
    flags: list[Flag] = field(default_factory=list)


def confusable(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return text.translate(
        str.maketrans(
            {"0": "o", "1": "l", "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x"}
        )
    ).replace("rn", "m")


def flag(code: str, en: str, zh: str) -> Flag:
    return Flag(code=code, severity="high", detail_en=en, detail_zh=zh)


def match_invoice(
    extraction: Extraction,
    vendors: list[Vendor],
    pos: list[PurchaseOrder],
    decimals: int,
    already_paid: Callable[[str], bool],
    *,
    token_symbol: str,
    evaluation: bool = False,
) -> Match:
    result = Match()
    if not extraction.currency or extraction.currency.casefold() != token_symbol.casefold():
        result.flags.append(
            flag(
                "CURRENCY_MISMATCH",
                "Invoice currency does not match the vault asset.",
                "发票币种与金库支付资产不一致。",
            )
        )
    names = [
        (name, vendor)
        for vendor in vendors
        for name in (vendor.name_en, vendor.name_zh, *vendor.aliases)
    ]
    raw_name = extraction.vendor_name or ""
    best = process.extractOne(
        raw_name,
        [name for name, _ in names],
        scorer=fuzz.WRatio,
        processor=lambda value: unicodedata.normalize("NFKC", value).casefold(),
    )
    suspicious_name = False
    if best and best[1] >= 80:
        result.vendor = names[best[2]][1]
        suspicious_name = best[1] < 92
    for name, vendor in names:
        if confusable(raw_name) == confusable(name) and raw_name.casefold() != name.casefold():
            result.vendor = vendor
            suspicious_name = True
            break
    if result.vendor is None:
        result.flags.append(
            flag("UNKNOWN_VENDOR", "Vendor could not be matched.", "无法匹配供应商。")
        )
    if suspicious_name:
        result.flags.append(
            flag(
                "LOOKALIKE_VENDOR", "Vendor name resembles another vendor.", "供应商名称疑似仿冒。"
            )
        )
    reference = normalize_po_reference(extraction.po_reference or "")
    result.po = next((po for po in pos if normalize_po_reference(po.ref) == reference), None)
    if result.po is None:
        result.flags.append(flag("UNKNOWN_PO", "Purchase order was not found.", "未找到采购订单。"))
    elif result.vendor and result.po.vendor_id != result.vendor.id:
        result.flags.append(
            flag(
                "PO_VENDOR_MISMATCH",
                "Purchase order belongs to another vendor.",
                "采购订单属于其他供应商。",
            )
        )
    try:
        if extraction.amount_total is None:
            raise ValueError("missing amount")
        result.amount_base = to_base_units(extraction.amount_total, decimals)
    except ValueError:
        result.flags.append(
            flag("INVALID_AMOUNT", "Amount is missing or invalid.", "金额缺失或无效。")
        )
    if result.po and result.amount_base is not None and not evaluation:
        if result.amount_base > result.po.remaining_base:
            result.flags.append(
                flag("OVER_BUDGET", "Amount exceeds the remaining budget.", "金额超过剩余预算。")
            )
    if result.vendor:
        try:
            result.invoice_hash = invoice_hash(result.vendor.id, extraction.invoice_number or "")
        except ValueError:
            result.flags.append(
                flag(
                    "INVALID_INVOICE_NUMBER",
                    "Invoice number is missing or invalid.",
                    "发票号码缺失或无效。",
                )
            )
        if result.invoice_hash and not evaluation and already_paid(result.invoice_hash):
            result.flags.append(
                flag("DUPLICATE_INVOICE", "This invoice was already paid.", "该发票已支付。")
            )
        printed = extraction.payee_address
        if printed and (
            not is_address(printed)
            or to_checksum_address(printed) != to_checksum_address(result.vendor.payout)
        ):
            result.flags.append(
                flag(
                    "PAYOUT_CHANGED",
                    "Invoice payout differs from the registry.",
                    "发票收款地址与登记地址不同。",
                )
            )
    return result
