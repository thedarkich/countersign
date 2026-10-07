"""Small operational commands. No secret values are printed."""

import argparse
import json
import os
import shutil
import sqlite3
from pathlib import Path
from urllib.request import urlopen


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError("Database does not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    # SQLite's online backup includes a consistent snapshot, including WAL state.
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as incoming:
        with sqlite3.connect(destination) as outgoing:
            incoming.backup(outgoing)
            if outgoing.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    commands.add_parser("liveness")
    commands.add_parser("check")
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "liveness":
        with urlopen("http://127.0.0.1:8000/api/health", timeout=3) as response:
            body = json.load(response)
        # Disabled AI/bounty is a readiness gate, not a reason to restart a healthy process.
        if not isinstance(body.get("ok"), bool):
            raise SystemExit(1)
        return
    from app.config import Settings

    settings = Settings()
    if args.command == "backup":
        backup(settings.data_dir / "countersign.db", args.destination)
        print("Database backup verified. Protect it as private invoice data.")
    elif args.command == "check":
        print(
            json.dumps(
                {
                    "network": settings.network,
                    "bounty_network": settings.bounty_network,
                    "vault_configured": bool(
                        getattr(settings, "contract_address_" + settings.network)
                    ),
                    "admin_configured": len(settings.admin_token.get_secret_value()) >= 32,
                    "privacy_salt_configured": len(settings.ip_hash_salt.get_secret_value()) >= 32,
                    "llm_enabled": settings.llm_enabled,
                    "transactions_enabled": settings.transactions_enabled,
                    "bounty_enabled": settings.bounty_enabled,
                    "batch_enabled": settings.batch_enabled,
                    "static_build_present": (settings.static_dir / "index.html").is_file(),
                },
                indent=2,
            )
        )
    elif args.command == "serve":
        import uvicorn

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        for name in ("vendors.json", "pos.json"):
            target = settings.data_dir / name
            if not target.exists():
                shutil.copyfile(Path("/app/seed") / name, target)
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            workers=1,
            proxy_headers=False,
            access_log=False,
            log_level="warning",
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": "OPERATION_FAILED", "category": type(exc).__name__}))
        raise SystemExit(1) from None
