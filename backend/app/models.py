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
