"""Resource isolation for untrusted documents (not a filesystem/network sandbox)."""

import asyncio
import base64
import os
import signal
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.pipeline.ingest import MAX_BYTES, MAX_PAGES, MAX_TEXT, Document, InputError

WALL_SECONDS = 12
MAX_RESULT_BYTES = 24 * 1024 * 1024
BACKEND = Path(__file__).resolve().parents[2]
# All command arguments are application constants, never invoice text or filenames.
BOOTSTRAP = (
    "import runpy,sys;sys.path.insert(0,sys.argv[1]);"
    "runpy.run_module('app.pipeline.ingest_worker',run_name='__main__')"
)


class ParsedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    kind: Literal["pdf", "image"]
    images: list[str] = Field(max_length=2)
    pages: list[dict] = Field(max_length=MAX_PAGES)
    text: str = Field(max_length=MAX_TEXT)
    page_count: int = Field(ge=1, le=MAX_PAGES)


async def _exchange(process, data):
    async def feed():
        try:
            process.stdin.write(data)
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            process.stdin.close()

    writer = asyncio.create_task(feed())
    try:
        result = bytearray()
        while chunk := await process.stdout.read(65536):
            if len(result) + len(chunk) > MAX_RESULT_BYTES:
                raise InputError("document output exceeds resource limit")
            result.extend(chunk)
        await writer
        await process.wait()
        return bytes(result)
    finally:
        writer.cancel()
        await asyncio.gather(writer, return_exceptions=True)


async def ingest_isolated(data: bytes) -> Document:
    if not data or len(data) > MAX_BYTES:
        raise InputError("file must contain at most 5 MB")
    if not sys.platform.startswith("linux"):
        raise InputError("document processing requires the Linux worker")
    # exec a fresh interpreter: no inherited Python objects, signer clients or
    # credentials in its environment. The worker still has the same OS UID.
    with tempfile.TemporaryDirectory(prefix="countersign-ingest-") as directory:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-B",
            "-c",
            BOOTSTRAP,
            str(BACKEND),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=directory,
            env={"LANG": "C.UTF-8"},
            start_new_session=True,
            close_fds=True,
        )
        try:
            async with asyncio.timeout(WALL_SECONDS):
                raw = await _exchange(process, data)
            if process.returncode != 0:
                raise InputError("document parser rejected input or exceeded resource limits")
            parsed = ParsedDocument.model_validate_json(raw)
            images = [base64.b64decode(item, validate=True) for item in parsed.images]
            return Document(
                kind=parsed.kind,
                images=images,
                pages=parsed.pages,
                text=parsed.text,
                page_count=parsed.page_count,
            )
        except (TimeoutError, ValidationError, ValueError):
            raise InputError("document is invalid or exceeds processing limits") from None
        finally:
            # A timeout/cancel must actually stop native parsing, then reap the
            # process before releasing the concurrency slot. Also stop descendants.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.communicate()
