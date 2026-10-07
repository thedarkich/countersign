"""Private persistence models. Public responses must use explicit projections."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def initial_steps() -> list[dict]:
    return [
        {"name": name, "status": "pending", "started_at": None, "ended_at": None, "detail": None}
        for name in ("extract", "hidden_text", "match", "guard", "chain")
    ]


class Attempt(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    created_at: str = Field(default_factory=now_iso, index=True)
    network: str
    chain_id: int
    source: str
    agent: str
    agent_address: str
    contract_address: str
    scenario: str = "unlabeled"
    model_versions: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    device_id: str | None = None
    nickname: str | None = None
    claimed_address: str | None = None
    input_kind: str = "text"
    file_path: str | None = None
    file_name: str | None = None
    input_text: str | None = None
    preview_path: str | None = None
    demo_name: str | None = None
    summary_en: str | None = None
    summary_zh: str | None = None
    status: str = Field(default="queued", index=True)
    outcome: str | None = None
    steps: list = Field(default_factory=initial_steps, sa_column=Column(JSON, nullable=False))
    extraction: dict | None = Field(default=None, sa_column=Column(JSON))
    hidden_text: dict | None = Field(default=None, sa_column=Column(JSON))
    match: dict | None = Field(default=None, sa_column=Column(JSON))
    guard: dict | None = Field(default=None, sa_column=Column(JSON))
    flags: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    proposal: dict | None = Field(default=None, sa_column=Column(JSON))
    tx_hash: str | None = Field(default=None, index=True)
    tx: dict | None = Field(default=None, sa_column=Column(JSON))
    block_reason: str | None = None
    guard_version: str | None = None
    ai_fooled: bool = False
    latency_ms: int | None = None
    error: str | None = None


class ChainEvent(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("network", "contract_address", "tx_hash", "log_index"),)
    id: int | None = Field(default=None, primary_key=True)
    network: str
    contract_address: str
    tx_hash: str
    log_index: int
    block_number: int
    block_time: str
    name: str
    args: dict = Field(sa_column=Column(JSON, nullable=False))


class RateBucket(SQLModel, table=True):
    key: str = Field(primary_key=True)
    count: int = 0
    expires_at: int = Field(index=True)


class ModelCallReservation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    reserved_at: float = Field(index=True)


class SubmissionMeta(SQLModel, table=True):
    attempt_id: str = Field(primary_key=True)
    ip_hash: str | None = None


class BatchRecord(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    created_at: str = Field(default_factory=now_iso)
    attempt_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class StateCache(SQLModel, table=True):
    network: str = Field(primary_key=True)
    updated_at: str = Field(default_factory=now_iso)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class IndexCursor(SQLModel, table=True):
    key: str = Field(primary_key=True)
    network: str
    contract_address: str
    start_block: int
    last_block: int
    last_hash: str | None = None
    updated_at: str | None = None
    error: str | None = None


class RecoveryCheck(SQLModel, table=True):
    attempt_id: str = Field(primary_key=True)
    checked_at: str = Field(default_factory=now_iso, index=True)
    result: str


class ReceiptAnchor(SQLModel, table=True):
    key: str = Field(primary_key=True)
    network: str
    contract_address: str
    tx_hash: str
    block_number: int
    block_hash: str


class EventAudit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recorded_at: str = Field(default_factory=now_iso)
    reason: str
    payload: dict = Field(sa_column=Column(JSON, nullable=False))


class UserAccount(SQLModel, table=True):
    """Workspace account. Sees only its own invoices; never has wallet authority."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    password_hash: str
    created_at: str = Field(default_factory=now_iso)


class AttemptOwner(SQLModel, table=True):
    """The account that submitted a team attempt. Accounts see only their own attempts."""

    attempt_id: str = Field(primary_key=True)
    user_id: str = Field(index=True)


class UserSession(SQLModel, table=True):
    """Only the SHA-256 of the session cookie is stored."""

    token_hash: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    expires_at: int = Field(index=True)
    created_at: str = Field(default_factory=now_iso)


class WalletLink(SQLModel, table=True):
    """The wallet an account proved it controls by signing a one-time message."""

    user_id: str = Field(primary_key=True)
    address: str = Field(index=True)
    linked_at: str = Field(default_factory=now_iso)


class WalletChallenge(SQLModel, table=True):
    """One pending link message per account; single use, short-lived."""

    user_id: str = Field(primary_key=True)
    address: str
    message: str
    expires_at: int


class WalletPolicy(SQLModel, table=True):
    """The account's own maximum per payment, in wei. Raising it waits; lowering is immediate."""

    user_id: str = Field(primary_key=True)
    max_wei: str
    pending_max_wei: str | None = None
    pending_at: int | None = None


class Payee(SQLModel, table=True):
    """A whitelisted address. It can receive only from active_at on."""

    __table_args__ = (UniqueConstraint("user_id", "address"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(index=True)
    address: str
    label: str
    created_at: str = Field(default_factory=now_iso)
    active_at: int


class WalletPayment(SQLModel, table=True):
    """A payment the service approved, then the transaction the wallet actually sent for it."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(index=True)
    chain_id: int
    wallet: str
    payee: str
    payee_label: str
    amount_wei: str
    status: str = "approved"  # approved, then sent, then confirmed | failed | mismatch; or expired
    tx_hash: str | None = Field(default=None, unique=True)
    block_number: int | None = None
    detail: str | None = None
    created_at: str = Field(default_factory=now_iso)
    expires_at: int
