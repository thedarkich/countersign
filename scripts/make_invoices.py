"""Generate synthetic invoices using the backend's configured public vault registry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cli import main

if __name__ == "__main__":
    sys.argv.insert(1, "fixtures")
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- sanitize top-level provider/configuration errors
        print("Invoice generation failed: " + type(exc).__name__)
        raise SystemExit(1) from None
