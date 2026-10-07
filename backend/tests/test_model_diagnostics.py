"""Sanitized operational diagnostics without provider bodies or paid retries."""

import asyncio
import json

import httpx
import pytest
from openai import APITimeoutError
from test_llm import invoke, make_gateway, response
from test_runner import make, run, system  # noqa: F401 -- isolated runner fixture

from app.llm import ModelUnavailable

PRIVATE = "private invoice text and synthetic provider credential"


@pytest.mark.parametrize(
    "case,code",
    [
        ("length", "MODEL_OUTPUT_INCOMPLETE"),
        ("empty", "MODEL_OUTPUT_EMPTY"),
        ("json", "MODEL_OUTPUT_INVALID"),
        ("schema", "MODEL_OUTPUT_INVALID"),
        ("envelope", "MODEL_OUTPUT_INVALID"),
        ("timeout", "MODEL_TIMEOUT"),
        (401, "MODEL_AUTH_FAILED"),
        (403, "MODEL_AUTH_FAILED"),
        (429, "MODEL_RATE_LIMITED"),
        (500, "MODEL_PROVIDER_ERROR"),
    ],
)
def test_failures_have_safe_specific_codes_without_retry(case, code):
    requests = []

    def handler(request):
        requests.append(request)
        if isinstance(case, int):
            return httpx.Response(case, json={"error": {"message": PRIVATE, "code": PRIVATE}})
        if case == "timeout":
            raise APITimeoutError(request=request)
        payload = response('{"verdict":"ok","risk":0}').json()
        choice = payload["choices"][0]
        if case == "length":
            choice["finish_reason"] = "length"
            choice["message"]["content"] = PRIVATE
        elif case == "empty":
            choice["message"]["content"] = None
        elif case == "json":
            choice["message"]["content"] = PRIVATE
        elif case == "schema":
            choice["message"]["content"] = json.dumps({"verdict": PRIVATE, "risk": 9})
        elif case == "envelope":
            payload["choices"] = {"unexpected": PRIVATE}
        return httpx.Response(200, json=payload)

    gateway = make_gateway(handler, enabled=True)
    with pytest.raises(ModelUnavailable) as error:
        asyncio.run(invoke(gateway))
    assert error.value.code == code
    assert PRIVATE not in str(error.value)
    assert len(requests) == len(gateway.calls) == 1


@pytest.mark.parametrize("phase", ["extract", "guard", "naive"])
def test_safe_code_reaches_failed_step_and_never_a_payment(system, phase):  # noqa: F811
    async def fail(*args):
        raise ModelUnavailable(PRIVATE, code="MODEL_OUTPUT_INVALID")

    setattr(system[1], phase, fail)
    item = make(system, agent="naive" if phase == "naive" else "guarded")
    result = run(system, item)
    assert result.error == "MODEL_OUTPUT_INVALID" and result.outcome == "error"
    failed = [step for step in result.steps if step["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["detail"] == "MODEL_OUTPUT_INVALID"
    assert failed[0]["name"] == ("extract" if phase == "extract" else "guard")
    assert not system[2].sent and result.tx is None
    assert PRIVATE not in result.model_dump_json()


def test_unknown_diagnostic_code_is_not_persisted(system):  # noqa: F811
    async def fail(*args):
        raise ModelUnavailable(PRIVATE, code=PRIVATE)

    system[1].extract = fail
    result = run(system, make(system))
    assert result.error == "MODEL_UNAVAILABLE"
    assert PRIVATE not in result.model_dump_json()
