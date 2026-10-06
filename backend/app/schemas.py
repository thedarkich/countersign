from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, hide_input_in_errors=True)


class Extraction(StrictModel):
    is_invoice: bool
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    amount_total: float | None = None
    po_reference: str | None = None
    payee_address: str | None = None
    notes_to_payer: str | None = None
    language: Literal["zh", "en", "mixed"] = "en"
    visible_text: str = Field(default="", max_length=2000)


class Flag(StrictModel):
    code: str
    severity: Literal["high", "medium", "low"]
    detail_en: str
    detail_zh: str


class HiddenSpan(StrictModel):
    text: str
    reason: Literal["near_white", "tiny_font", "off_page", "zero_area"]
    bbox: tuple[float, float, float, float]
    page: int


class HiddenText(StrictModel):
    has_hidden_text: bool
    page_size: tuple[float, float] | None
    spans: list[HiddenSpan] = Field(default_factory=list)
    diff_words: list[str] = Field(default_factory=list)


class GuardReason(StrictModel):
    code: str
    detail_en: str
    detail_zh: str


class GuardVerdict(StrictModel):
    verdict: Literal["ok", "suspicious", "malicious"]
    risk: float = Field(ge=0, le=1)
    reasons: list[GuardReason] = Field(default_factory=list)
    instructions_found: list[str] = Field(default_factory=list)


class NaiveDecision(StrictModel):
    vendor_id: int = Field(ge=0, le=2**256 - 1)
    pay_to: str
    po_id: int = Field(ge=0, le=2**256 - 1)
    amount: float
    invoice_number: str
    explanation: str = ""
