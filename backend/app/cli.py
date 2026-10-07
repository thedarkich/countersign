"""Operator commands. AI and transaction admission obey the runtime switches."""

import argparse
import asyncio
import json
from pathlib import Path

from app.api.runtime import Runtime
from app.chain.client import VaultClient
from app.config import Settings
from app.fixtures import generate
from app.pipeline.runner import new_attempt


async def execute(settings, args):
    if args.command == "fixtures":
        vault = VaultClient.from_settings(settings)
        snapshot = await vault.snapshot(args.network)
        print(
            json.dumps(
                generate(
                    settings.data_dir / "invoices",
                    snapshot,
                    attacker=args.attacker,
                    run_id=args.run_id,
                )
            )
        )
        return
    runtime = Runtime(
        settings.model_copy(update={"network": args.network, "indexer_enabled": False})
    )
    # A CLI process cannot compete with a running API for its DB/transaction nonces.
    await runtime.start()
    try:
        if runtime.screening.enabled:
            await runtime.screening.refresh()
        runtime.check_submission(batch=args.command in {"batch", "seed"})
        source = args.source if args.command == "run" else args.command
        if args.command == "run":
            if bool(args.path) == bool(args.text):
                raise ValueError("Provide exactly one file or --text")
            paths = [Path(args.path).resolve()] if args.path else [None]
        else:
            split = "clean" if args.command == "batch" else "poisoned"
            paths = [
                (settings.data_dir / "invoices" / entry["name"]).resolve()
                for entry in runtime.manifest()
                if entry.get("split", entry["name"].split("/")[0]) == split
            ]
            if not paths:
                raise ValueError("Generate the active fixture manifest first")
        outcomes = {}
        for path in paths:
            if path and path.stat().st_size > 5 * 1024 * 1024:
                raise ValueError("Input exceeds file limit")
            document = (
                await runtime.ingest(data=path.read_bytes())
                if path
                else await runtime.ingest(text=args.text)
            )
            snapshot = await runtime.chain.snapshot(args.network)
            fixture = next(
                (
                    e
                    for e in runtime.manifest()
                    if path and (settings.data_dir / "invoices" / e["name"]).resolve() == path
                ),
                None,
            )
            for agent in ["guarded", "naive"] if args.command == "seed" else [args.agent]:
                item = new_attempt(
                    snapshot,
                    network=args.network,
                    source=source,
                    agent=agent,
                    input_kind=document.kind,
                    file_path=str(path) if path else None,
                    file_name=path.name if path else None,
                    input_text=args.text if not path else None,
                    fixture_kind=fixture["kind"] if fixture else None,
                    demo_name=fixture["name"] if fixture else None,
                )
                if document.images:
                    preview = settings.data_dir / "previews" / (item.id + ".png")
                    preview.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    preview.write_bytes(document.images[0])
                    preview.chmod(0o600)
                    item.preview_path = str(preview)
                runtime.store.save(item)
                result = await runtime.runner.run(item.id, document)
                print(
                    json.dumps(
                        {
                            "attempt_id": result.id,
                            "agent": agent,
                            "outcome": result.outcome,
                            "error_code": result.error,
                            "steps": [
                                {"name": step["name"], "status": step["status"]}
                                for step in result.steps
                            ],
                            "transaction_url": result.tx.get("explorer_url") if result.tx else None,
                        }
                    )
                )
                outcomes[result.outcome] = outcomes.get(result.outcome, 0) + 1
                # Provider/chain failure is not a reason to keep consuming test credit.
                if result.outcome == "error":
                    raise RuntimeError(
                        "Run stopped after a processing error; review the saved attempt"
                    )
        print(json.dumps({"summary": outcomes}))
    finally:
        await runtime.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "batch", "seed", "fixtures"):
        command = sub.add_parser(name)
        command.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
        if name == "fixtures":
            command.add_argument("--run-id", default="R1")
            command.add_argument(
                "--attacker", required=True, help="Public team-owned test attacker address"
            )
        else:
            command.add_argument("--agent", choices=["guarded", "naive"], default="guarded")
            command.set_defaults(text=None)
        if name == "run":
            command.add_argument("path", nargs="?")
            command.add_argument("--text")
            command.add_argument("--source", choices=["team", "seed", "batch"], default="team")
    args = parser.parse_args()
    asyncio.run(execute(Settings(), args))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Raw provider/configuration errors may contain secrets or invoice text.
        print(json.dumps({"error": "COMMAND_FAILED", "category": type(exc).__name__}))
        raise SystemExit(1) from None
