import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.llm import CallLimitReached, ModelGateway, ModelUnavailable
from app.schemas import GuardVerdict


def make_gateway(handler, **options):
    transport = httpx.MockTransport(handler)
    client = AsyncOpenAI(
        api_key="synthetic-test-key",
        base_url="https://api.tokenrouter.com/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=transport),
    )
    return ModelGateway(client, **options)


def invoke(gateway):
    return gateway.json_response(
        model="qwen/qwen3.8-flash", system="review", user="synthetic", schema=GuardVerdict
    )


def response(content):
    return httpx.Response(
        200,
        json={
            "id": "mock",
            "object": "chat.completion",
            "created": 0,
            "model": "qwen/qwen3.8-flash",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def test_paid_calls_disabled_by_default():
    requests = []
    gateway = make_gateway(lambda request: requests.append(request))
    with pytest.raises(ModelUnavailable, match="disabled"):
        asyncio.run(invoke(gateway))
    assert requests == []


def test_success_uses_only_selected_gateway_and_bounded_output():
    requests = []

    def handler(request):
        requests.append(request)
        return response('{"verdict":"ok","risk":0,"reasons":[],"instructions_found":[]}')

    gateway = make_gateway(handler, enabled=True, max_tokens=32)
    result = asyncio.run(invoke(gateway))
    assert result.verdict == "ok"
    assert len(requests) == 1
    assert requests[0].url.host == "api.tokenrouter.com"
    body = json.loads(requests[0].content)
    assert body["max_tokens"] == 32
    assert body["temperature"] == 0


@pytest.mark.parametrize("status", [401, 429, 500])
def test_provider_errors_never_retry_or_fan_out(status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": "synthetic provider error"}})

    gateway = make_gateway(handler, enabled=True)
    with pytest.raises(ModelUnavailable):
        asyncio.run(invoke(gateway))
    assert len(requests) == 1
    assert len(gateway.calls) == 1


def test_parse_error_is_not_retried():
    requests = []

    def handler(request):
        requests.append(request)
        return response("not JSON")

    with pytest.raises(ModelUnavailable):
        asyncio.run(invoke(make_gateway(handler, enabled=True)))
    assert len(requests) == 1


def test_rejected_output_logs_shape_without_content(caplog):
    def handler(request):
        return response('{"verdict": "pay", "private": "invoice text 0xSECRET"}')

    with caplog.at_level("WARNING", logger="app.llm"), pytest.raises(ModelUnavailable):
        asyncio.run(invoke(make_gateway(handler, enabled=True)))
    assert "GuardVerdict" in caplog.text and "extra_forbidden" in caplog.text
    assert "0xSECRET" not in caplog.text and "invoice text" not in caplog.text


def test_hourly_limit_reserves_concurrent_calls_and_rolls():
    now = [10000.0]
    requests = []

    def handler(request):
        requests.append(request)
        return response('{"verdict":"ok","risk":0}')

    gateway = make_gateway(handler, enabled=True, hourly_cap=2, clock=lambda: now[0])

    async def run():
        outcomes = await asyncio.gather(
            *(invoke(gateway) for _ in range(3)), return_exceptions=True
        )
        assert sum(isinstance(item, CallLimitReached) for item in outcomes) == 1
        now[0] += 3600
        assert (await invoke(gateway)).verdict == "ok"

    asyncio.run(run())
    assert len(requests) == 3


def test_model_timeout_comes_from_settings(tmp_path):
    from app.config import Settings
    from app.db import AttemptStore
    from app.pipeline.extract import InvoiceModels

    settings = Settings(_env_file=None, llm_timeout_seconds=60)
    extractor = InvoiceModels.from_settings(settings, engine=AttemptStore(tmp_path / "t.db").engine)
    assert extractor.gateway.client.timeout == 60
    assert extractor.gateway.client.max_retries == 0
    assert Settings(_env_file=None).llm_timeout_seconds == 75


OK_VERDICT = {"verdict": "ok", "risk": 0, "reasons": [], "instructions_found": []}


@pytest.mark.parametrize(
    "content, accepted",
    [
        (json.dumps([OK_VERDICT]), True),
        (json.dumps(json.dumps(OK_VERDICT)), True),
        (json.dumps([OK_VERDICT, {"verdict": "pay"}]), False),
        (json.dumps([{**OK_VERDICT, "extra": 1}]), False),
        ("[]", False),
    ],
)
def test_one_wrapped_object_is_unwrapped_then_strictly_validated(content, accepted):
    """Live logs showed Extraction model_type errors: the object came wrapped in a list."""
    gateway = make_gateway(lambda request: response(content), enabled=True)
    if accepted:
        assert asyncio.run(invoke(gateway)).verdict == "ok"
    else:
        with pytest.raises(ModelUnavailable):
            asyncio.run(invoke(gateway))
