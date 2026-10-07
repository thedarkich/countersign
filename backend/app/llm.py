"""Bounded model transport. Disabled by default; tests inject an HTTP mock."""

import asyncio
import base64
import json
import time
from collections import deque
from collections.abc import Callable
from typing import TypeVar

from openai import APIError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.model_budget import BudgetExhausted

Model = TypeVar("Model", bound=BaseModel)


MODEL_ERROR_CODES = frozenset(
    {
        "MODEL_UNAVAILABLE",
        "MODEL_OUTPUT_INCOMPLETE",
        "MODEL_OUTPUT_EMPTY",
        "MODEL_OUTPUT_INVALID",
        "MODEL_TIMEOUT",
        "MODEL_AUTH_FAILED",
        "MODEL_RATE_LIMITED",
        "MODEL_PROVIDER_ERROR",
    }
)


class ModelUnavailable(RuntimeError):
    def __init__(self, message, *, code="MODEL_UNAVAILABLE"):
        super().__init__(message)
        # Only application-owned codes may enter durable/public step diagnostics.
        self.code = code if code in MODEL_ERROR_CODES else "MODEL_UNAVAILABLE"


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
        budget=None,
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
        self.budget = budget

    @classmethod
    def tokenrouter(
        cls,
        api_key: str,
        *,
        enabled: bool = False,
        hourly_cap: int = 20,
        max_tokens: int = 1024,
        budget=None,
    ):
        client = AsyncOpenAI(
            api_key=api_key, base_url="https://api.tokenrouter.com/v1", timeout=30.0, max_retries=0
        )
        return cls(
            client, enabled=enabled, hourly_cap=hourly_cap, max_tokens=max_tokens, budget=budget
        )

    def exhausted(self):
        if self.budget is not None:
            return self.budget.exhausted()
        return sum(call > self.clock() - 3600 for call in self.calls) >= self.hourly_cap

    async def _reserve(self):
        if not self.enabled:
            raise ModelUnavailable("Paid AI calls are disabled.")
        if self.budget is not None:
            try:
                await asyncio.to_thread(self.budget.reserve)
            except BudgetExhausted:
                raise CallLimitReached("Hourly AI call limit reached.") from None
            except Exception:
                raise ModelUnavailable("AI call budget is unavailable.") from None
            return
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
        except APITimeoutError:
            raise ModelUnavailable("Model request timed out.", code="MODEL_TIMEOUT") from None
        except APIStatusError as exc:
            code = {
                401: "MODEL_AUTH_FAILED",
                403: "MODEL_AUTH_FAILED",
                429: "MODEL_RATE_LIMITED",
            }.get(exc.status_code, "MODEL_PROVIDER_ERROR")
            raise ModelUnavailable("Model provider rejected the request.", code=code) from None
        except APIError:
            raise ModelUnavailable(
                "Model provider request failed.", code="MODEL_PROVIDER_ERROR"
            ) from None
        try:
            if on_model:
                returned = response.model
                on_model(returned if isinstance(returned, str) and len(returned) <= 120 else model)
            if not isinstance(response.choices, list):
                raise TypeError("Invalid choices envelope")
            if not response.choices or response.choices[0].finish_reason != "stop":
                raise ModelUnavailable(
                    "Model returned incomplete output.", code="MODEL_OUTPUT_INCOMPLETE"
                )
            payload = response.choices[0].message.content
            if payload is None or payload == "":
                raise ModelUnavailable("Model returned empty output.", code="MODEL_OUTPUT_EMPTY")
            if not isinstance(payload, str):
                raise TypeError("Invalid content envelope")
            return schema.model_validate_json(payload)
        except (ValidationError, AttributeError, TypeError):
            # Never retain the provider body, validation input or raw exception.
            raise ModelUnavailable(
                "Model output did not match the required schema.", code="MODEL_OUTPUT_INVALID"
            ) from None
