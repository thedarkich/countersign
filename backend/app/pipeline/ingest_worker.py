"""One document per Linux worker. Install limits before loading native parsers."""

import base64
import json
import resource
import sys
from dataclasses import asdict


def limit_resources():
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (6, 6))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))


def main():
    limit_resources()
    from app.pipeline.ingest import MAX_BYTES, ingest_bytes

    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    document = ingest_bytes(data)
    payload = asdict(document)
    payload["images"] = [base64.b64encode(item).decode("ascii") for item in document.images]
    result = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode()
    if len(result) > 24 * 1024 * 1024:
        raise ValueError("document result too large")
    sys.stdout.buffer.write(result)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never forward parser traces, document contents or paths to the API.
        sys.exit(1)
