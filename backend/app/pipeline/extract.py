import json
from pathlib import Path

from app.llm import ModelGateway
from app.pipeline.ingest import Document
from app.schemas import Extraction, GuardVerdict, NaiveDecision

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


class InvoiceModels:
    def __init__(
        self,
        gateway: ModelGateway,
        *,
        text_model: str,
        vision_model: str,
        guard_version: str = "v1",
    ):
        if guard_version not in {"v1", "v2"}:
            raise ValueError("Unknown guard version")
        self.gateway = gateway
        self.text_model = text_model
        self.vision_model = vision_model
        self.guard_version = guard_version
        self.extract_prompt = (PROMPTS / "extract.md").read_text()
        self.guard_prompt = (PROMPTS / f"guard_{guard_version}.md").read_text()
        self.naive_prompt = (PROMPTS / "naive_agent.md").read_text()

    @classmethod
    def from_settings(cls, settings):
        gateway = ModelGateway.tokenrouter(
            settings.tokenrouter_api_key.get_secret_value() or "disabled",
            enabled=settings.llm_enabled,
            hourly_cap=settings.llm_hourly_call_cap,
            max_tokens=settings.llm_max_output_tokens,
        )
        return cls(
            gateway,
            text_model=settings.tokenrouter_text_model,
            vision_model=settings.tokenrouter_vision_model,
            guard_version=settings.guard_version,
        )

    async def extract(self, document: Document, versions: dict) -> Extraction:
        return await self.gateway.json_response(
            model=self.text_model if document.kind == "text" else self.vision_model,
            system=self.extract_prompt,
            # PDF text layers deliberately do not enter the visual extraction request.
            user=document.text
            if document.kind == "text"
            else "Extract the visible invoice from these pages.",
            images=document.images,
            schema=Extraction,
            on_model=lambda name: versions.update(extract=name),
        )

    async def guard(self, payload: dict, versions: dict) -> GuardVerdict:
        return await self.gateway.json_response(
            model=self.text_model,
            system=self.guard_prompt,
            user=json.dumps(payload, ensure_ascii=False),
            schema=GuardVerdict,
            on_model=lambda name: versions.update(guard=name),
        )

    async def naive(self, payload: dict, versions: dict) -> NaiveDecision:
        return await self.gateway.json_response(
            model=self.text_model,
            system=self.naive_prompt,
            user=json.dumps(payload, ensure_ascii=False),
            schema=NaiveDecision,
            on_model=lambda name: versions.update(naive=name),
        )
