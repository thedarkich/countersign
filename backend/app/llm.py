"""Bounded model transport. Disabled by default; tests inject an HTTP mock."""

import asyncio
import base64
import json
import time
from collections import deque
from collections.abc import Callable
from typing import TypeVar

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

Model = TypeVar("Model", bound=BaseModel)


class ModelUnavailable(RuntimeError):
    pass


class CallLimitReached(ModelUnavailable):
    pass


class ModelGateway:
    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        enabled: bool = False,
        hourly_cap: int = 20,
        max_tokens: int = 512,
        clock=time.monotonic,
    ):
        if hourly_cap < 1 or not 1 <= max_tokens <= 2048:
            raise ValueError("invalid model limits")
        self.client = client
        self.enabled = enabled
        self.hourly_cap = hourly_cap
        self.max_tokens = max_tokens
        self.clock = clock
        self.calls: deque[float] = deque()
        self.lock = asyncio.Lock()

    @classmethod
    def tokenrouter(
        cls, api_key: str, *, enabled: bool = False, hourly_cap: int = 20, max_tokens: int = 1024
    ):
        client = AsyncOpenAI(
            api_key=api_key, base_url="https://api.tokenrouter.com/v1", timeout=30.0, max_retries=0
        )
        return cls(client, enabled=enabled, hourly_cap=hourly_cap, max_tokens=max_tokens)

    async def _reserve(self):
        if not self.enabled:
            raise ModelUnavailable("Paid AI calls are disabled.")
        async with self.lock:
            now = self.clock()
            while self.calls and self.calls[0] <= now - 3600:
                self.calls.popleft()
            if len(self.calls) >= self.hourly_cap:
                raise CallLimitReached("Hourly AI call limit reached.")
            # Failed requests count too. No automatic paid retries or fallback.
            self.calls.append(now)

    async def json_response(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[Model],
        images: list[bytes] | None = None,
        on_model: Callable[[str], None] | None = None,
    ) -> Model:
        await self._reserve()
        content = [{"type": "text", "text": user}]
        for image in images or []:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64," + base64.b64encode(image).decode("ascii")
                    },
                }
            )
        prompt = (
            system
            + "\nReturn only JSON matching this schema:\n"
            + json.dumps(schema.model_json_schema())
        )
        try:
            response = await self.client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content},
                ],
            )
            if on_model:
                on_model(response.model or model)
            if not response.choices or response.choices[0].finish_reason != "stop":
                raise ModelUnavailable("Model returned incomplete output.")
            payload = response.choices[0].message.content
            if not payload:
                raise ModelUnavailable("Model returned empty output.")
            return schema.model_validate_json(payload)
        except (APIError, ValidationError):
            # Do not leak provider bodies, submitted invoice text or credentials.
            raise ModelUnavailable("Model request or response validation failed.") from None
