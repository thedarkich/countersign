"""Local, provenance-pinned Scam Sniffer screening. Never send payee addresses upstream."""

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel

from app.storage import write_private_bytes

SOURCE = "https://github.com/scamsniffer/scam-database"
COMMITS = "https://api.github.com/repos/scamsniffer/scam-database/commits/main"
RAW = "https://raw.githubusercontent.com/scamsniffer/scam-database/"
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
MAX_BYTES = 4 * 1024 * 1024


class ScreeningUnavailable(RuntimeError):
    code = "WALLET_SCREENING_UNAVAILABLE"


class WalletCheck(BaseModel):
    address: str
    verdict: Literal["listed", "not_listed", "unavailable"]


class WalletSecurityView(BaseModel):
    enabled: bool
    ready: bool
    status: Literal["fresh", "stale", "unavailable", "disabled"]
    source_url: str = SOURCE
    license_url: str = SOURCE + "/blob/main/LICENSE"
    revision: str | None
    checked_at: str | None
    source_updated_at: str | None
    address_count: int
    publication_delay_days: int = 7
    chain_scope: str = "address_match_without_chain_attribution"
    last_refresh_failed: bool
    checks: list[WalletCheck]


@dataclass(frozen=True)
class Snapshot:
    revision: str
    source_updated_at: str
    checked_at: float
    addresses: frozenset[str]


def parse_snapshot(payload, now):
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Unsupported snapshot")
    revision = payload["revision"]
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise ValueError("Invalid revision")
    checked = payload["checked_at"]
    if type(checked) not in (int, float) or not 0 < checked <= now + 60:
        raise ValueError("Invalid check time")
    updated = payload["source_updated_at"]
    stamp = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.timestamp() > now + 300:
        raise ValueError("Invalid source time")
    raw = payload["address_json"].encode("utf-8")
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != payload["source_sha256"]:
        raise ValueError("Snapshot digest mismatch")
    addresses = json.loads(raw)
    if not isinstance(addresses, list) or not 1 <= len(addresses) <= 100_000:
        raise ValueError("Invalid address list")
    if any(not isinstance(a, str) or not ADDRESS.fullmatch(a) for a in addresses):
        raise ValueError("Unsupported address format")
    license_text = payload["license_text"]
    if not isinstance(license_text, str) or not 1000 < len(license_text) < 100_000:
        raise ValueError("Missing license")
    if "GNU GENERAL PUBLIC LICENSE" not in license_text or "Version 3" not in license_text:
        raise ValueError("Unexpected license; operator review required")
    return Snapshot(revision, updated, checked, frozenset(a.lower() for a in addresses))


class WalletScreening:
    def __init__(self, data_dir: Path, *, enabled=True, max_age=172800, clock=time.time):
        self.enabled, self.max_age, self.clock = enabled, max_age, clock
        self.path = data_dir / "threat-intel" / "scamsniffer.json"
        self.snapshot = None
        self.last_refresh_failed = False
        self.refresh_lock = asyncio.Lock()
        if self.enabled:
            try:
                with self.path.open("rb") as stream:
                    raw = stream.read(MAX_BYTES * 2 + 1)
                if len(raw) > MAX_BYTES * 2:
                    raise ValueError("Oversized cache")
                self.snapshot = parse_snapshot(json.loads(raw), self.clock())
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                # Missing/corrupt cache cannot silently authorize a payment.
                self.last_refresh_failed = True

    def view(self, addresses=()):
        snap = self.snapshot
        age = self.clock() - snap.checked_at if snap else None
        fresh = snap is not None and 0 <= age <= self.max_age
        status = (
            "disabled"
            if not self.enabled
            else "unavailable"
            if snap is None
            else "fresh"
            if fresh
            else "stale"
        )
        ready = self.enabled and fresh
        checks = []
        for address in addresses:
            if not ADDRESS.fullmatch(address):
                raise ValueError("Invalid address")
            verdict = (
                "listed"
                if snap and address.lower() in snap.addresses
                else "not_listed"
                if ready
                else "unavailable"
            )
            checks.append(WalletCheck(address=address.lower(), verdict=verdict))
        return WalletSecurityView(
            enabled=self.enabled,
            ready=ready,
            status=status,
            revision=snap.revision if snap else None,
            checked_at=datetime.fromtimestamp(snap.checked_at, UTC).isoformat() if snap else None,
            source_updated_at=snap.source_updated_at if snap else None,
            address_count=len(snap.addresses) if snap else 0,
            last_refresh_failed=self.last_refresh_failed,
            checks=checks,
        )

    def require_ready(self):
        if self.enabled and not self.view().ready:
            raise ScreeningUnavailable()

    async def refresh(self, *, transport=None):
        if not self.enabled:
            return
        async with self.refresh_lock:
            try:
                # Fixed HTTPS origins and paths only. Do not follow redirects, use
                # environment proxies, or fetch anything from submitted documents.
                async with asyncio.timeout(30):
                    async with httpx.AsyncClient(
                        timeout=10,
                        follow_redirects=False,
                        trust_env=False,
                        transport=transport,
                        headers={
                            "User-Agent": "Countersign-wallet-screening",
                            "Accept": "application/json",
                        },
                    ) as client:

                        async def fetch(url, limit):
                            async with client.stream("GET", url) as response:
                                if response.status_code != 200:
                                    raise ValueError("Feed request failed")
                                result = bytearray()
                                async for chunk in response.aiter_bytes():
                                    result.extend(chunk)
                                    if len(result) > limit:
                                        raise ValueError("Feed response too large")
                                return bytes(result)

                        meta = json.loads(await fetch(COMMITS, 1024 * 1024))
                        revision = meta["sha"]
                        if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                            raise ValueError("Invalid upstream revision")
                        raw = await fetch(RAW + revision + "/blacklist/address.json", MAX_BYTES)
                        license_bytes = await fetch(RAW + revision + "/LICENSE", 100_000)
                        payload = {
                            "version": 1,
                            "revision": revision,
                            "source_updated_at": meta["commit"]["committer"]["date"],
                            "checked_at": self.clock(),
                            "address_json": raw.decode("utf-8"),
                            "source_sha256": hashlib.sha256(raw).hexdigest(),
                            "license_text": license_bytes.decode("utf-8"),
                        }
                        candidate = parse_snapshot(payload, self.clock())
                        if self.snapshot and datetime.fromisoformat(
                            candidate.source_updated_at.replace("Z", "+00:00")
                        ) < datetime.fromisoformat(
                            self.snapshot.source_updated_at.replace("Z", "+00:00")
                        ):
                            raise ValueError("Feed revision rollback requires operator review")
                        temp = self.path.with_name("scamsniffer-" + uuid4().hex + ".tmp")
                        try:
                            write_private_bytes(temp, json.dumps(payload).encode())
                            os.replace(temp, self.path)
                        finally:
                            temp.unlink(missing_ok=True)
                        self.snapshot = candidate
                        self.last_refresh_failed = False
            except Exception:
                self.last_refresh_failed = True
                raise ScreeningUnavailable() from None

    async def refresh_loop(self):
        while True:
            try:
                await self.refresh()
            except ScreeningUnavailable:
                pass
            # Free repository data only; no model calls or paid premium service.
            await asyncio.sleep(900 if self.last_refresh_failed else 21600)
