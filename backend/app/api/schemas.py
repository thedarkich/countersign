from typing import Literal

from pydantic import Field

from app.schemas import Extraction, Flag, HiddenText, StrictModel

Network = Literal["mainnet", "testnet"]
Agent = Literal["guarded", "naive"]
Source = Literal["bounty", "seed", "team", "batch"]
Outcome = Literal["paid", "blocked", "refused", "no_invoice", "error"]


class Step(StrictModel):
    name: Literal["extract", "hidden_text", "match", "guard", "chain"]
    status: Literal["pending", "running", "done", "skipped", "failed"]
    started_at: str | None = None
    ended_at: str | None = None
    detail: str | None = None


class Proposal(StrictModel):
    vendor_id: int | None = None
    vendor_name: str | None = None
    pay_to: str | None = None
    registry_payout: str | None = None
    po_id: int | None = None
    po_ref: str | None = None
    amount: str | None = None
    invoice_hash: str | None = None


class TxInfo(StrictModel):
    hash: str
    explorer_url: str
    event: Literal["Paid", "Blocked"]
    reason: str | None = None
    reason_label_en: str | None = None
    reason_label_zh: str | None = None
    network: Network


class AttemptView(StrictModel):
    id: str
    status: Literal["queued", "extracting", "checking", "deciding", "sending", "done", "error"]
    outcome: Outcome | None
    agent: Agent
    source: Source
    nickname: str | None = None
    input_kind: Literal["pdf", "image", "text"] | None = None
    file_name: str | None = None
    preview_url: str | None = None
    steps: list[Step] = Field(default_factory=list)
    extraction: Extraction | None = None
    hidden_text: HiddenText | None = None
    flags: list[Flag] = Field(default_factory=list)
    proposal: Proposal | None = None
    tx: TxInfo | None = None
    ai_fooled: bool
    created_at: str
    latency_ms: int | None = None


class StatBlock(StrictModel):
    attempts: int = 0
    people: int = 0
    guard_catches: int = 0
    ai_fooled: dict[Agent, int] = Field(default_factory=lambda: {"guarded": 0, "naive": 0})
    chain_blocks: int = 0
    paid_real_vendor_on_fake_invoice: str = "0"
    money_lost: str = "0"


class Stats(StrictModel):
    outside: StatBlock
    seed: StatBlock
    since: str | None


class LeaderboardEntry(StrictModel):
    nickname: str
    agent: Agent
    attempt_id: str
    created_at: str
    summary_en: str
    summary_zh: str


class LedgerEventView(StrictModel):
    id: str
    name: Literal[
        "Paid",
        "Blocked",
        "ChangeQueued",
        "ChangeExecuted",
        "ChangeCancelled",
        "VendorDeactivated",
        "POClosed",
        "AgentRevoked",
        "DailyCapLowered",
        "Paused",
    ]
    tx_hash: str
    explorer_url: str
    block_time: str
    agent: Agent | None = None
    vendor_id: int | None = None
    vendor_name: str | None = None
    amount: str | None = None
    pay_to: str | None = None
    reason: str | None = None
    reason_label_en: str | None = None
    reason_label_zh: str | None = None
    summary_en: str | None = None
    summary_zh: str | None = None
    network: Network


class VendorView(StrictModel):
    id: int
    name_en: str
    name_zh: str
    payout: str
    active: bool


class POView(StrictModel):
    po_id: int
    ref: str
    vendor_id: int
    cap: str
    remaining: str
    expiry: str
    period_days: int
    closed: bool


class PendingChange(StrictModel):
    id: str
    kind: Literal[
        "AddVendor", "SetPayout", "AddPO", "AddAgent", "RaiseDailyCap", "Unpause", "Withdraw"
    ]
    decoded: dict[str, str | int]
    eta: str
    ready: bool


class AgentView(StrictModel):
    address: str
    label: str
    active: bool
    balance: str
    gas: Literal["self", "sponsored"]


class Registry(StrictModel):
    vendors: list[VendorView]
    pos: list[POView]
    pending_changes: list[PendingChange]
    daily_cap: str
    remaining_today: str
    paused: bool
    vault_balance: str
    agents: list[AgentView]


class Token(StrictModel):
    address: str
    symbol: str
    decimals: int


class AppConfig(StrictModel):
    network: Network
    chain_id: int
    rpc_url: str
    explorer_url: str
    contract_address: str
    token: Token
    owner_address: str
    agents: dict[Agent, str]
    public_base_url: str
    timelock_seconds: int
    bounty_network: Network


class EvalSide(StrictModel):
    catch: float = Field(ge=0, le=1)
    false_alarm: float = Field(ge=0, le=1)
    catch_ci: tuple[float, float] | None = None
    false_alarm_ci: tuple[float, float] | None = None


class EvalResults(StrictModel):
    created_at: str | None = None
    n_train_attacks: int | None = None
    n_heldout_attacks: int | None = None
    n_heldout_clean: int | None = None
    v1: EvalSide | None = None
    v2: EvalSide | None = None
    split: str | None = None


class DemoInvoice(StrictModel):
    name: str
    kind: Literal["clean", "poisoned"]
    title_en: str
    title_zh: str
    note_en: str | None = None
    note_zh: str | None = None


class BatchSummary(StrictModel):
    total: int
    done: int
    paid: int
    refused: int
    blocked: int
    no_invoice: int
    false_alarms: int


class BatchInput(StrictModel):
    folder: Literal["clean"]


class OwnerTxInput(StrictModel):
    tx_hash: str = Field(pattern=r"^0x[0-9a-fA-F]{64}$")
