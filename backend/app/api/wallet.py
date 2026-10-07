"""Pay from your own wallet: link it, keep a whitelist and your own maximum, and send BOT the service approved.

The service never holds keys or funds; the wallet signs every transaction. It approves a payment only to a
whitelisted address whose waiting period has passed and only up to the account's own maximum, then checks
the transaction the wallet actually sent against what it approved. Until the whitelist contract ships these
rules are enforced here, not on chain: a wallet can still send directly, outside the service.
"""

import asyncio
import re
import secrets
import time
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import is_address, to_checksum_address
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from web3 import HTTPProvider, Web3
from web3.exceptions import TransactionNotFound
from web3.middleware import ExtraDataToPOAMiddleware

from app.api.accounts import throttle
from app.api.security import SAFE_METHODS, problem, same_origin, session_user
from app.models import Payee, WalletChallenge, WalletLink, WalletPayment, WalletPolicy

CHAIN_IDS = {"mainnet": 677, "testnet": 968}
WEI = Decimal(10**18)
MAX_BOT = Decimal(1_000_000)
APPROVAL_SECONDS = 600
CHALLENGE_SECONDS = 300
MAX_PAYEES = 100
TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


def account(request: Request):
    """Wallet features belong to a signed-in account; the team token has no wallet."""
    user = session_user(request)
    if user is None:
        raise problem(401, "Sign in to use your wallet.", "请先登录再使用钱包。")
    if request.method not in SAFE_METHODS and not same_origin(request):
        raise problem(403, "Cross-site request refused.", "已拒绝跨站请求。")
    return user


router = APIRouter(prefix="/api/wallet", dependencies=[Depends(account)])


class ChallengeInput(BaseModel):
    address: str = Field(min_length=42, max_length=42)


class LinkInput(ChallengeInput):
    signature: str = Field(min_length=132, max_length=200)


class LimitInput(BaseModel):
    max: str = Field(min_length=1, max_length=40)


class PayeeInput(BaseModel):
    address: str = Field(min_length=42, max_length=42)
    label: str = Field(min_length=1, max_length=60)


class PaymentInput(BaseModel):
    payee_id: str = Field(min_length=1, max_length=64)
    amount: str = Field(min_length=1, max_length=40)


class SentInput(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66)


class WalletChain:
    """Read-only lookups of a sent transaction and its receipt."""

    def __init__(self, rpc_url: str):
        self.w3 = Web3(HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    def transaction(self, tx_hash: str):
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
        except TransactionNotFound:
            return None
        return {"from": tx["from"], "to": tx.get("to"), "value": int(tx["value"])}

    def receipt(self, tx_hash: str):
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
        except TransactionNotFound:
            return None
        return {"status": int(receipt["status"]), "block_number": int(receipt["blockNumber"])}


def chain(request: Request) -> WalletChain:
    state = request.app.state
    if getattr(state, "wallet_chain", None) is None:
        settings = state.runtime.settings
        rpc = (
            settings.botchain_mainnet_rpc
            if settings.wallet_network == "mainnet"
            else settings.botchain_testnet_rpc
        )
        state.wallet_chain = WalletChain(rpc)
    return state.wallet_chain


def network(request: Request):
    settings = request.app.state.runtime.settings
    name = settings.wallet_network
    explorer = settings.explorer_url_mainnet if name == "mainnet" else settings.explorer_url_testnet
    return name, CHAIN_IDS[name], explorer.rstrip("/")


def to_wei(value: str, *, allow_zero=False) -> int:
    try:
        amount = Decimal(value.strip())
    except InvalidOperation:
        raise problem(422, "Enter an amount like 0.05.", "请输入金额，例如 0.05。") from None
    if not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero) or amount > MAX_BOT:
        raise problem(422, "Enter an amount above zero.", "请输入大于零的金额。")
    wei = amount * WEI
    if wei != wei.to_integral_value():
        raise problem(422, "Use at most 18 decimal places.", "最多 18 位小数。")
    return int(wei)


def bot(wei: int | str | None) -> str | None:
    if wei is None:
        return None
    text = format(Decimal(int(wei)) / WEI, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def checksum(value: str) -> str:
    if not is_address(value):
        raise problem(422, "That is not a valid wallet address.", "这不是有效的钱包地址。")
    return to_checksum_address(value)


def clean_label(value: str) -> str:
    label = " ".join(unicodedata.normalize("NFKC", value).split())
    if not 1 <= len(label) <= 60 or any(unicodedata.category(c).startswith("C") for c in label):
        raise problem(422, "Use 1–60 characters for the name.", "名称需为 1–60 个字符。")
    return label


def policy(session: Session, user_id: str, now: int) -> WalletPolicy | None:
    """The account's maximum, promoting a raised value once its waiting period has passed."""
    current = session.get(WalletPolicy, user_id)
    if current and current.pending_at is not None and current.pending_at <= now:
        current.max_wei, current.pending_max_wei, current.pending_at = (
            current.pending_max_wei,
            None,
            None,
        )
        session.add(current)
        session.commit()
        session.refresh(current)
    return current


def payment_view(payment: WalletPayment, explorer: str):
    return {
        "id": payment.id,
        "status": payment.status,
        "payee": payment.payee,
        "payee_label": payment.payee_label,
        "amount": bot(payment.amount_wei),
        "tx_hash": payment.tx_hash,
        "explorer_url": f"{explorer}/tx/{payment.tx_hash}" if payment.tx_hash else None,
        "block_number": payment.block_number,
        "detail": payment.detail,
        "created_at": payment.created_at,
    }


async def verify(request: Request, payment: WalletPayment):
    """Compare the sent transaction with the approval, then settle it once its receipt exists."""
    lookup = chain(request)
    try:
        tx = await asyncio.wait_for(asyncio.to_thread(lookup.transaction, payment.tx_hash), 15)
        if tx is None:
            return
        differs = [
            name
            for name, ok in (
                ("sender", (tx["from"] or "").lower() == payment.wallet.lower()),
                ("recipient", (tx["to"] or "").lower() == payment.payee.lower()),
                ("amount", tx["value"] == int(payment.amount_wei)),
            )
            if not ok
        ]
        receipt = await asyncio.wait_for(asyncio.to_thread(lookup.receipt, payment.tx_hash), 15)
    except Exception:
        return  # the RPC is unavailable; the payment stays "sent" and is checked again later
    if differs:
        payment.status, payment.detail = (
            "mismatch",
            "The wallet changed the " + ", ".join(differs) + ".",
        )
        if receipt:
            payment.block_number = receipt["block_number"]
    elif receipt:
        payment.status = "confirmed" if receipt["status"] == 1 else "failed"
        payment.block_number = receipt["block_number"]
        payment.detail = None if receipt["status"] == 1 else "The transaction reverted on chain."


@router.get("")
async def overview(request: Request):
    user = session_user(request)
    name, chain_id, explorer = network(request)
    now = int(time.time())
    with Session(request.app.state.runtime.store.engine) as session:
        link = session.get(WalletLink, user["id"])
        limit = policy(session, user["id"], now)
        payees = (
            session.execute(
                select(Payee).where(Payee.user_id == user["id"]).order_by(Payee.created_at)
            )
            .scalars()
            .all()
        )
    return {
        "network": name,
        "chain_id": chain_id,
        "explorer_url": explorer,
        "payee_delay_seconds": request.app.state.runtime.settings.payee_delay_seconds,
        "now": now,
        "wallet": {"address": link.address, "linked_at": link.linked_at} if link else None,
        "limit": (
            {
                "max": bot(limit.max_wei),
                "pending_max": bot(limit.pending_max_wei),
                "pending_at": limit.pending_at,
            }
            if limit
            else None
        ),
        "payees": [
            {
                "id": p.id,
                "address": p.address,
                "label": p.label,
                "created_at": p.created_at,
                "active_at": p.active_at,
                "active": p.active_at <= now,
            }
            for p in payees
        ],
    }


@router.post("/challenge")
async def challenge(request: Request, body: ChallengeInput):
    user = session_user(request)
    throttle(request, [("wallet-challenge", user["id"], 60, 10)])
    address = checksum(body.address)
    _, chain_id, _ = network(request)
    expires = int(time.time()) + CHALLENGE_SECONDS
    message = (
        "Countersign: link this wallet to your account.\n\n"
        f"Account: {user['email']}\n"
        f"Wallet: {address}\n"
        f"Network: BOT Chain (chain ID {chain_id})\n"
        f"Nonce: {secrets.token_hex(16)}\n"
        f"Expires: {datetime.fromtimestamp(expires, UTC).isoformat(timespec='seconds')}\n\n"
        "Signing is free. It does not send a transaction or give anyone access to your funds."
    )
    with Session(request.app.state.runtime.store.engine) as session:
        session.merge(
            WalletChallenge(
                user_id=user["id"], address=address, message=message, expires_at=expires
            )
        )
        session.commit()
    return {"message": message}


@router.post("/link")
async def link(request: Request, body: LinkInput):
    user = session_user(request)
    throttle(request, [("wallet-link", user["id"], 60, 10)])
    address = checksum(body.address)
    with Session(request.app.state.runtime.store.engine) as session:
        pending = session.get(WalletChallenge, user["id"])
        expected = (pending.address, pending.message, pending.expires_at) if pending else None
        if pending:
            session.delete(pending)  # single use, whatever the outcome
            session.commit()
        if expected is None or expected[0] != address or expected[2] < int(time.time()):
            raise problem(
                409,
                "The link request expired. Connect your wallet again.",
                "链接请求已过期，请重新连接钱包。",
            )
        try:
            signer = Account.recover_message(
                encode_defunct(text=expected[1]), signature=body.signature
            )
        except Exception:
            signer = None
        if signer is None or signer.lower() != address.lower():
            raise problem(401, "The signature does not match this wallet.", "签名与该钱包不符。")
        session.merge(WalletLink(user_id=user["id"], address=address))
        session.commit()
    return {"wallet": {"address": address}}


@router.delete("")
async def unlink(request: Request):
    user = session_user(request)
    with Session(request.app.state.runtime.store.engine) as session:
        session.execute(delete(WalletLink).where(WalletLink.user_id == user["id"]))
        session.commit()
    return {"ok": True}


@router.put("/limit")
async def set_limit(request: Request, body: LimitInput):
    """Lowering applies at once. Raising waits like a new payee, so a hijacked session cannot raise it and pay."""
    user = session_user(request)
    wei = to_wei(body.max)
    now = int(time.time())
    delay = request.app.state.runtime.settings.payee_delay_seconds
    with Session(request.app.state.runtime.store.engine) as session:
        current = policy(session, user["id"], now)
        if current is None:
            current = WalletPolicy(user_id=user["id"], max_wei=str(wei))
        elif wei <= int(current.max_wei) or delay == 0:
            current.max_wei, current.pending_max_wei, current.pending_at = str(wei), None, None
        else:
            current.pending_max_wei, current.pending_at = str(wei), now + delay
        session.add(current)
        session.commit()
        session.refresh(current)
        return {
            "max": bot(current.max_wei),
            "pending_max": bot(current.pending_max_wei),
            "pending_at": current.pending_at,
        }


@router.post("/payees", status_code=201)
async def add_payee(request: Request, body: PayeeInput):
    user = session_user(request)
    throttle(request, [("wallet-payee", user["id"], 60, 20)])
    address, label = checksum(body.address), clean_label(body.label)
    now = int(time.time())
    payee = Payee(
        user_id=user["id"],
        address=address,
        label=label,
        active_at=now + request.app.state.runtime.settings.payee_delay_seconds,
    )
    with Session(request.app.state.runtime.store.engine) as session:
        count = len(session.execute(select(Payee.id).where(Payee.user_id == user["id"])).all())
        if count >= MAX_PAYEES:
            raise problem(
                409, "Your whitelist is full (100 addresses).", "白名单已满（100 个地址）。"
            )
        session.add(payee)
        try:
            session.commit()
        except IntegrityError:
            raise problem(
                409, "This address is already on your whitelist.", "该地址已在白名单中。"
            ) from None
        session.refresh(payee)
        return {
            "id": payee.id,
            "address": address,
            "label": label,
            "active_at": payee.active_at,
            "active": False,
        }


@router.delete("/payees/{payee_id}")
async def remove_payee(request: Request, payee_id: str):
    user = session_user(request)
    with Session(request.app.state.runtime.store.engine) as session:
        removed = session.execute(
            delete(Payee).where(Payee.id == payee_id, Payee.user_id == user["id"])
        ).rowcount
        session.commit()
    if not removed:
        raise problem(404, "That address is not on your whitelist.", "该地址不在白名单中。")
    return {"ok": True}


@router.post("/payments", status_code=201)
async def approve_payment(request: Request, body: PaymentInput):
    user = session_user(request)
    throttle(
        request, [("wallet-pay", user["id"], 60, 10), ("wallet-pay-day", user["id"], 86400, 200)]
    )
    wei = to_wei(body.amount)
    _, chain_id, explorer = network(request)
    now = int(time.time())
    with Session(request.app.state.runtime.store.engine) as session:
        link = session.get(WalletLink, user["id"])
        if link is None:
            raise problem(409, "Link a wallet first.", "请先链接钱包。")
        payee = session.get(Payee, body.payee_id)
        if payee is None or payee.user_id != user["id"]:
            raise problem(404, "That address is not on your whitelist.", "该地址不在白名单中。")
        if payee.active_at > now:
            wait = payee.active_at - now
            raise problem(
                409,
                f"This address was just added. It can receive in {wait} s.",
                f"该地址刚刚加入白名单，{wait} 秒后才能收款。",
            )
        limit = policy(session, user["id"], now)
        if limit is None:
            raise problem(409, "Set your maximum per payment first.", "请先设置单笔最高金额。")
        if wei > int(limit.max_wei):
            raise problem(
                409,
                f"Above your maximum of {bot(limit.max_wei)} BOT per payment.",
                f"超出你设置的单笔最高 {bot(limit.max_wei)} BOT。",
            )
        payment = WalletPayment(
            user_id=user["id"],
            chain_id=chain_id,
            wallet=link.address,
            payee=payee.address,
            payee_label=payee.label,
            amount_wei=str(wei),
            expires_at=now + APPROVAL_SECONDS,
        )
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return {
            "payment": payment_view(payment, explorer),
            "tx": {
                "from": link.address,
                "to": payee.address,
                "value": str(wei),
                "chain_id": chain_id,
            },
        }


@router.post("/payments/{payment_id}/sent")
async def payment_sent(request: Request, payment_id: str, body: SentInput):
    user = session_user(request)
    if not TX_HASH.match(body.tx_hash):
        raise problem(422, "Invalid transaction hash.", "交易哈希无效。")
    _, _, explorer = network(request)
    with Session(request.app.state.runtime.store.engine) as session:
        payment = session.get(WalletPayment, payment_id)
        if payment is None or payment.user_id != user["id"]:
            raise problem(404, "Payment not found.", "找不到这笔付款。")
        if payment.status != "approved" or payment.expires_at < int(time.time()):
            raise problem(
                409, "This approval was already used or expired.", "该付款批准已使用或已过期。"
            )
        payment.tx_hash, payment.status = body.tx_hash.lower(), "sent"
        session.add(payment)
        try:
            session.commit()
        except IntegrityError:
            raise problem(
                409, "This transaction is already recorded.", "这笔交易已记录。"
            ) from None
        session.refresh(payment)
        await verify(request, payment)
        session.add(payment)
        session.commit()
        session.refresh(payment)
        return {"payment": payment_view(payment, explorer)}


@router.get("/payments")
async def payments(request: Request):
    user = session_user(request)
    _, _, explorer = network(request)
    now = int(time.time())
    with Session(request.app.state.runtime.store.engine) as session:
        rows = (
            session.execute(
                select(WalletPayment)
                .where(WalletPayment.user_id == user["id"])
                .order_by(WalletPayment.created_at.desc())
                .limit(50)
            )
            .scalars()
            .all()
        )
        checked = 0
        for payment in rows:
            if payment.status == "approved" and payment.expires_at < now:
                payment.status = "expired"
                session.add(payment)
            elif payment.status == "sent" and checked < 5:
                checked += 1
                await verify(request, payment)
                session.add(payment)
        session.commit()
        return {"payments": [payment_view(p, explorer) for p in rows if p.tx_hash]}
