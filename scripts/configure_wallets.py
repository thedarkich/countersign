# /// script
# requires-python = ">=3.11"
# dependencies = ["eth-account", "python-dotenv"]
# ///
"""Interactive local-only setup. Never send private keys to chat or command arguments."""

import getpass
import os
import re
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from eth_account import Account

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
EXPECTED = {
    "DEPLOYER_PK": "0x8218A9c48fbf28206bb5C75Ed6A69D161BD45023",
    "TESTNET_OWNER_PK": "0xCEC6a9DFA4318A9AacFF50a8fdC88eBb20059272",
    "AGENT_GUARDED_PK": "0x10840Aea6D6f835560f43656768a0d5B2A4ef063",
    "AGENT_NAIVE_PK": "0x8CF8109e5817fACB3235c01E93E233BF478c0659",
}


def main():
    if not os.isatty(0):
        raise SystemExit("Run this helper in your own interactive Ubuntu terminal.")
    print("Private wallet setup: input is hidden. No key is printed or sent over the network.")
    print("Export only the four named demo accounts. Never export the mainnet owner.")
    existing = dotenv_values(ENV) if ENV.exists() else {}
    updates = {}
    entered_new_key = False
    for name, expected in EXPECTED.items():
        current = existing.get(name)
        if current:
            try:
                if Account.from_key(current).address.lower() == expected.lower():
                    updates[name] = "0x" + Account.from_key(current).key.hex().removeprefix("0x")
                    print(name + ": already verified")
                    continue
            except (ValueError, TypeError):
                pass
        print("\n" + name + " — " + expected)
        while True:
            try:
                value = getpass.getpass("Paste private key (hidden; Ctrl+C cancels): ").strip()
                account = Account.from_key(value)
                if account.address.lower() != expected.lower():
                    print("That key belongs to a different account. Nothing saved.")
                    continue
                updates[name] = "0x" + account.key.hex().removeprefix("0x")
                entered_new_key = True
                break
            except (ValueError, TypeError):
                print("Invalid private key. Nothing saved.")
    # Runtime-only reading is permitted; contents never leave this process.
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    # Replace all duplicate definitions, including dotenv's export / quoted-key syntax.
    pattern = re.compile(r"^\s*(?:export\s+)?['\"]?(" + "|".join(EXPECTED) + r")[ '\"]*=")
    lines = [line for line in lines if not pattern.match(line)]
    lines.extend(name + "=" + value for name, value in updates.items())
    fd, temporary = tempfile.mkstemp(prefix=".wallet-setup-", dir=ROOT)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write("\n".join(lines) + "\n")
        os.replace(temporary, ENV)
        os.chmod(ENV, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    action = "Saved and verified" if entered_new_key else "Verified"
    print(action + " all four wallet identities. No transaction was sent.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled. No new keys were saved.")
