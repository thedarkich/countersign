"""Rehearse the BOT mainnet rollout on a local Anvil fork of chain 677. Nothing is broadcast to a real network.

Runs the real Deploy, FundGas, Setup and Execute scripts with the public owner/agent/vendor addresses, then the
demo payments and protective actions. Anvil's well-known development key stands in for the deployer; no .env or
private key is loaded. Contracts and public fixtures are copied to a temporary directory first.

Usage (Ubuntu, after `source ~/.nvm/nvm.sh` so forge/cast/anvil are on PATH):
    python3 scripts/rehearse_mainnet_fork.py native|usdt
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE = sys.argv[1] if len(sys.argv) > 1 else "native"
assert MODE in ("native", "usdt"), "mode must be native or usdt"
FORK = "https://rpc.botchain.ai"
EXPLORER_API = "https://scan.botchain.ai/api/v2"
PORT = 8547 if MODE == "native" else 8548
RPC = f"http://127.0.0.1:{PORT}"
USDT = "0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C"
ZERO = "0x0000000000000000000000000000000000000000"
OWNER = "0x94Eb49F414A609c954e623fc5216a0944Aa4e0c4"
GUARDED = "0x10840Aea6D6f835560f43656768a0d5B2A4ef063"
NAIVE = "0x8CF8109e5817fACB3235c01E93E233BF478c0659"
VENDORS = {
    1: "0x419D0c4F429981b45548724404E5a2CeFcB303d0",
    2: "0x68024ee76537AA843aaf06509bCc4f742554539d",
    3: "0x4BF6056A6369e1176A0bD7cc7CAC0C859Dc31600",
}
ATTACKER = "0x3135Ee6Aa8e71E2e51E56314f23c7a96c72DF47b"
# Public Anvil development key #0: a local stand-in for the real deployer, never funded on a real chain.
STANDIN_DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
REASONS = ["None", "Paused", "ZeroAmount", "UnknownVendor", "VendorInactive", "PayoutMismatch", "UnknownPO",
           "POVendorMismatch", "POExpired", "OverBudget", "DuplicateInvoice", "OverDailyCap", "InsufficientFunds"]
TOKEN = ZERO if MODE == "native" else USDT
DEC = 18 if MODE == "native" else 6
UNIT = "BOT" if MODE == "native" else "USDT"
GAS_OWNER, GAS_AGENT = Decimal("0.1"), Decimal("0.02")  # BOT forwarded by FundGas, the amounts the runbook uses
gas = {"deployer": 0, "owner": 0, "agents": 0, "funder": 0}
txs = dict.fromkeys(gas, 0)


def run(cmd, env=None, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and p.returncode != 0:
        sys.exit(f"FAILED: {' '.join(cmd[:3])}\n{p.stdout[-2500:]}\n{p.stderr[-2500:]}")
    return p.stdout.strip() if check else p


def cast(*args):
    return run(["cast", *args, "--rpc-url", RPC])


def first(value):
    return value.split()[0]


def units(human, decimals=DEC):
    return int(Decimal(human) * 10**decimals)


def bot(wei):
    return Decimal(wei) / Decimal(10**18)


def check(label, ok):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        sys.exit(1)


def send(role, frm, to, sig=None, *args, value=None):
    cmd = ["cast", "send", to] + ([sig, *map(str, args)] if sig else [])
    cmd += ["--from", frm, "--unlocked", "--legacy", "--json", "--rpc-url", RPC]
    if value is not None:
        cmd += ["--value", str(value)]
    r = json.loads(run(cmd))
    assert int(r["status"], 16) == 1, f"tx reverted: {r['transactionHash']}"
    gas[role] += int(r["gasUsed"], 16)
    txs[role] += 1
    return r


def forge(script, role, extra=(), env_extra=None, expect_fail=False):
    env = {**os.environ, **ENV, **(env_extra or {})}
    cmd = ["forge", "script", f"script/{script}.s.sol:{script}", "--rpc-url", RPC, "--broadcast", "--legacy",
           "--slow", *extra]
    # forge can exit 0 after a reverted script, so the "script failed" message is the reliable signal
    result = run(cmd, env=env, cwd=WORK / "contracts", check=False)
    failed = result.returncode != 0 or "script failed" in result.stdout + result.stderr
    if expect_fail:
        return failed, result.stdout + result.stderr
    if failed:
        sys.exit(f"FAILED: forge script {script}\n{(result.stdout + result.stderr)[-2500:]}")
    latest = json.loads((WORK / f"contracts/broadcast/{script}.s.sol/677/run-latest.json").read_text())
    for receipt in latest["receipts"]:
        assert int(receipt["status"], 16) == 1, f"{script} tx reverted"
        gas[role] += int(receipt["gasUsed"], 16)
        txs[role] += 1
    return latest


def outcome(receipt):
    for log in receipt["logs"]:
        if log["address"].lower() != VAULT.lower():
            continue
        words = [log["data"][2:][i:i + 64] for i in range(0, len(log["data"]) - 2, 64)]
        if log["topics"][0] == PAID_TOPIC:
            return "Paid", "", int(words[1], 16)
        if log["topics"][0] == BLOCKED_TOPIC:
            return "Blocked", REASONS[int(words[0], 16)], int(words[2], 16)
    return "no vault event", "", 0


def balance(addr, token=None):
    token = TOKEN if token is None else token
    if token == ZERO:
        return int(cast("balance", addr))
    return int(first(cast("call", token, "balanceOf(address)(uint256)", addr)))


def advance(seconds):
    cast("rpc", "evm_increaseTime", str(seconds))
    cast("rpc", "evm_mine")


for a in [OWNER, GUARDED, NAIVE, ATTACKER, USDT, *VENDORS.values()]:
    assert run(["cast", "to-check-sum-address", a]) == a, f"bad checksum {a}"
gas_price = int(run(["cast", "gas-price", "--rpc-url", FORK]))

WORK = Path(tempfile.mkdtemp(prefix=f"cs-mainnet-{MODE}-"))
shutil.copytree(ROOT / "contracts", WORK / "contracts",
                ignore=shutil.ignore_patterns("broadcast", "cache", "out", ".env*", "*.env"))
(WORK / "data").mkdir()
for name in ("vendors.json", "pos.json"):
    shutil.copy(ROOT / "data" / name, WORK / "data" / name)
assert not [p for p in WORK.rglob("*") if p.name.startswith(".env") or p.name.endswith(".env")]

anvil = subprocess.Popen(["anvil", "--fork-url", FORK, "--port", str(PORT), "--auto-impersonate", "--silent"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(90):
        if subprocess.run(["cast", "chain-id", "--rpc-url", RPC], capture_output=True).returncode == 0:
            break
        time.sleep(1)
    print(f"== {MODE} rehearsal on a local fork of BOT mainnet, block {cast('block-number')}, "
          f"gas price {gas_price / 10**9:g} gwei")
    check("fork reports chain 677", cast("chain-id") == "677")
    if MODE == "usdt":
        check("USDT metadata: 6 decimals, symbol USDT",
              cast("call", USDT, "decimals()(uint8)") == "6" and cast("call", USDT, "symbol()(string)") == '"USDT"')
    start = {a: balance(a, ZERO) for a in (OWNER, GUARDED, NAIVE)}

    daily_cap = units("15")
    ENV = {"NETWORK": "mainnet", "PAY_TOKEN_MAINNET": TOKEN, "OWNER_ADDRESS": OWNER,
           "DEPLOYER_PK": STANDIN_DEPLOYER_KEY, "TIMELOCK_DELAY_SECONDS": "120", "INITIAL_DAILY_CAP": str(daily_cap),
           "AGENT_GUARDED_ADDRESS": GUARDED, "AGENT_NAIVE_ADDRESS": NAIVE,
           "GAS_OWNER_WEI": str(units(GAS_OWNER, 18)), "GAS_AGENT_WEI": str(units(GAS_AGENT, 18)),
           **{f"VENDOR{i}_PAYOUT": a for i, a in VENDORS.items()}}

    print("-- Deploy.s.sol (deployer, NETWORK=mainnet)")
    latest = forge("Deploy", "deployer")
    VAULT = run(["cast", "to-check-sum-address", latest["transactions"][0]["contractAddress"]])
    ENV["CONTRACT_ADDRESS_MAINNET"] = VAULT
    print(f"  vault {VAULT}")
    check("owner() is the human mainnet owner", cast("call", VAULT, "owner()(address)") == OWNER)
    check(f"token() is {UNIT}", cast("call", VAULT, "token()(address)").lower() == TOKEN.lower())
    check("delay() is 120 s", first(cast("call", VAULT, "delay()(uint64)")) == "120")
    check(f"dailyCap() is 15 {UNIT} in base units", int(first(cast("call", VAULT, "dailyCap()(uint256)"))) == daily_cap)

    print("-- FundGas.s.sol (deployer forwards gas)")
    failed, output = forge("FundGas", "deployer", env_extra={"GAS_AGENT_WEI": str(units("0.6", 18))}, expect_fail=True)
    check("refuses an amount above the 0.5 BOT cap", failed and "above cap" in output)
    if MODE == "usdt":
        failed, output = forge("FundGas", "deployer", env_extra={"VAULT_FUND_WEI": str(units("1", 18))}, expect_fail=True)
        check("refuses BOT funding for a USDT vault", failed and "token vault" in output)
    forge("FundGas", "deployer", env_extra={"VAULT_FUND_WEI": str(units("1", 18))} if MODE == "native" else None)
    check(f"owner received {GAS_OWNER} BOT", balance(OWNER, ZERO) - start[OWNER] == units(GAS_OWNER, 18))
    check(f"each agent received {GAS_AGENT} BOT",
          all(balance(a, ZERO) - start[a] == units(GAS_AGENT, 18) for a in (GUARDED, NAIVE)))

    print("-- Setup.s.sol as the owner (stands in for `--account owner`)")
    forge("Setup", "owner", ("--unlocked", "--sender", OWNER))
    check("8 changes queued", cast("call", VAULT, "changeCount()(uint256)") == "8")
    check("agents inactive until the time lock passes", cast("call", VAULT, "isAgent(address)(bool)", GUARDED) == "false")

    advance(121)
    print("-- Execute.s.sol (permissionless; the deployer pays gas)")
    forge("Execute", "deployer")
    check("both agents authorized",
          all(cast("call", VAULT, "isAgent(address)(bool)", a) == "true" for a in (GUARDED, NAIVE)))
    for po, cap in ((1, "10"), (2, "5"), (3, "3")):
        check(f"PO {po} budget {cap} {UNIT}",
              int(first(cast("call", VAULT, "poRemaining(uint256)(uint256)", str(po)))) == units(cap))

    if MODE == "usdt":
        print("-- fund the vault with 1 USDT (a public holder, impersonated on the fork)")
        req = urllib.request.Request(f"{EXPLORER_API}/tokens/{USDT}/holders",
                                     headers={"User-Agent": "Mozilla/5.0 (countersign rehearsal)"})
        holders = json.load(urllib.request.urlopen(req, timeout=30))["items"]
        holder = next(h["address"]["hash"] for h in holders if int(h["value"]) >= units("2"))
        cast("rpc", "anvil_setBalance", holder, hex(10**18))
        send("funder", holder, USDT, "transfer(address,uint256)", VAULT, units("1"))
    check(f"vaultBalance() is 1 {UNIT}", int(first(cast("call", VAULT, "vaultBalance()(uint256)"))) == units("1"))

    PAID_TOPIC = run(["cast", "sig-event", "Paid(uint256,uint256,address,address,uint256,bytes32)"])
    BLOCKED_TOPIC = run(["cast", "sig-event", "Blocked(uint256,uint256,address,uint8,address,uint256,bytes32)"])
    invoice = run(["cast", "keccak", f"mainnet-rehearsal-{MODE}-INV-1"])
    vendor_before, attacker_before = balance(VENDORS[1]), balance(ATTACKER)
    pay = "pay(uint256,address,uint256,uint256,bytes32)"
    print("-- payments")
    for label, agent, args, want in (
        ("guarded pays vendor 1, 0.01", GUARDED, (1, VENDORS[1], 1, units("0.01"), invoice), ("Paid", "")),
        ("naive pays the attacker address", NAIVE, (1, ATTACKER, 1, units("0.01"), run(["cast", "keccak", "i2"])),
         ("Blocked", "PayoutMismatch")),
        ("guarded, 11 against a 10 budget", GUARDED, (1, VENDORS[1], 1, units("11"), run(["cast", "keccak", "i3"])),
         ("Blocked", "OverBudget")),
        ("same invoice, changed amount", GUARDED, (1, VENDORS[1], 1, units("0.02"), invoice),
         ("Blocked", "DuplicateInvoice")),
    ):
        got = outcome(send("agents", agent, VAULT, pay, *args))
        check(f"{label}: {got[0]} {got[1]}".rstrip(), got[:2] == want)
    check(f"vendor 1 received exactly 0.01 {UNIT}", balance(VENDORS[1]) - vendor_before == units("0.01"))
    check("attacker received nothing", balance(ATTACKER) == attacker_before)

    print("-- protective actions are immediate; resuming waits for the time lock")
    send("owner", OWNER, VAULT, "pause()")
    got = outcome(send("agents", GUARDED, VAULT, pay, 1, VENDORS[1], 1, units("0.01"), run(["cast", "keccak", "i4"])))
    check(f"pay while paused: {got[0]} {got[1]}", got[:2] == ("Blocked", "Paused"))
    send("owner", OWNER, VAULT, "queueUnpause()")
    advance(121)
    forge("Execute", "deployer")
    check("unpaused after the time lock", cast("call", VAULT, "paused()(bool)") == "false")
    send("owner", OWNER, VAULT, "revokeAgent(address)", NAIVE)
    check("isAgent(naive) is false after revokeAgent", cast("call", VAULT, "isAgent(address)(bool)", NAIVE) == "false")
    before = balance(VENDORS[1])
    attempt = run(["cast", "send", VAULT, pay, "1", VENDORS[1], "1", str(units("0.01")), run(["cast", "keccak", "i5"]),
                   "--from", NAIVE, "--unlocked", "--legacy", "--rpc-url", RPC], check=False)
    # cast can exit 0 after a failed gas estimate, so require the contract's NotAgent revert explicitly
    check("revoked naive agent cannot pay (NotAgent)", "NotAgent" in attempt.stderr and balance(VENDORS[1]) == before)

    print(f"== gas on the fork, priced at {gas_price / 10**9:g} gwei (legacy)")
    for role, count in txs.items():
        if count:
            print(f"  {role:9} {count:2} txs {gas[role]:>10,} gas = {bot(gas[role] * gas_price):.6f} BOT")
    total = sum(gas.values())
    print(f"  total     {sum(txs.values()):2} txs {total:>10,} gas = {bot(total * gas_price):.6f} BOT")
    per_payment = gas["agents"] / txs["agents"] * gas_price
    print(f"  at this gas price: the owner's {GAS_OWNER} BOT leaves {GAS_OWNER - bot(gas['owner'] * gas_price):.4f} BOT "
          f"after setup; {GAS_AGENT} BOT covers about {int(units(GAS_AGENT, 18) // per_payment)} payments per agent")
    print("REHEARSAL PASSED")
finally:
    anvil.terminate()
    shutil.rmtree(WORK, ignore_errors=True)
