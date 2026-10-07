"""Runtime configuration; never log or expose the complete settings object."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    network: Literal["testnet", "mainnet"] = "testnet"
    bounty_network: Literal["testnet", "mainnet"] = "testnet"
    botchain_mainnet_rpc: str = "https://rpc.botchain.ai"
    botchain_testnet_rpc: str = "https://rpc.bohr.life"
    explorer_url_mainnet: str = "https://scan.botchain.ai"
    explorer_url_testnet: str = "https://scan.bohr.life"
    contract_address_mainnet: str = ""
    contract_address_testnet: str = ""
    agent_guarded_address: str = ""
    agent_naive_address: str = ""
    agent_guarded_pk: SecretStr = Field(default=SecretStr(""), repr=False)
    agent_naive_pk: SecretStr = Field(default=SecretStr(""), repr=False)
    tokenrouter_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    tokenrouter_base_url: Literal["https://api.tokenrouter.com/v1"] = (
        "https://api.tokenrouter.com/v1"
    )
    tokenrouter_text_model: str = "qwen/qwen3.8-flash"
    tokenrouter_vision_model: str = "qwen/qwen3.8-flash"
    guard_version: Literal["v1", "v2"] = "v1"
    transactions_enabled: bool = False
    llm_enabled: bool = False
    llm_hourly_call_cap: int = Field(default=20, ge=1, le=1000)
    llm_max_output_tokens: int = Field(default=1024, ge=1, le=2048)
    admin_token: SecretStr = Field(default=SecretStr(""), repr=False)
    ip_hash_salt: SecretStr = Field(default=SecretStr(""), repr=False)
    public_base_url: str = "http://localhost:8000"
    data_dir: Path = ROOT / "data"
    static_dir: Path = ROOT / "frontend" / "dist"
    bounty_enabled: bool = False
    batch_enabled: bool = False
    eval_enabled: bool = False
    queue_capacity: int = Field(default=60, ge=3, le=200)
    rate_device_per_min: int = Field(default=3, ge=1)
    rate_device_per_day: int = Field(default=30, ge=1)
    rate_nickname_per_day: int = Field(default=30, ge=1)
    rate_global_per_min: int = Field(default=60, ge=1)
    indexer_enabled: bool = True
    indexer_interval_seconds: int = Field(default=20, ge=5, le=300)
    indexer_start_block_testnet: int | None = Field(default=None, ge=0)
    indexer_start_block_mainnet: int | None = Field(default=None, ge=0)
    indexer_block_window: int = Field(default=50000, ge=1, le=100000)
    indexer_overlap_blocks: int = Field(default=128, ge=1, le=10000)
    indexer_lag_blocks: int = Field(default=128, ge=1, le=10000)
    indexer_request_budget: int = Field(default=20, ge=1, le=100)
    scam_screening_enabled: bool = True
    scam_snapshot_max_age_seconds: int = Field(default=172800, ge=3600, le=259200)
    recovery_batch_size: int = Field(default=20, ge=1, le=100)
