import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.llm import ModelGateway
from app.pipeline.extract import InvoiceModels
from app.pipeline.ingest import Document


@pytest.mark.parametrize("kind", ["text", "pdf"])
def test_extraction_routes_inputs_and_records_actual_model(kind):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "mock",
                "object": "chat.completion",
                "created": 0,
                "model": "actual-provider-model-version",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"is_invoice":false}'},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    client = AsyncOpenAI(
        api_key="synthetic",
        base_url="https://api.tokenrouter.com/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    gateway = ModelGateway(client, enabled=True)
    models = InvoiceModels(gateway, text_model="text-route", vision_model="vision-route")
    versions = {}
    document = Document(
        kind=kind, text="UNTRUSTED TEXT LAYER", images=[b"image"] if kind == "pdf" else []
    )

    async def invoke():
        try:
            return await models.extract(document, versions)
        finally:
            await client.close()

    assert asyncio.run(invoke()).is_invoice is False
    assert versions == {"extract": "actual-provider-model-version"}
    user = requests[0]["messages"][1]["content"]
    assert requests[0]["model"] == ("text-route" if kind == "text" else "vision-route")
    if kind == "pdf":
        assert "UNTRUSTED TEXT LAYER" not in json.dumps(user)
        assert user[1]["image_url"]["url"].startswith("data:image/png;base64,")
    else:
        assert user == [{"type": "text", "text": document.text}]
