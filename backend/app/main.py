"""Single-process API. Runtime settings are loaded only during startup."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from web3.exceptions import TransactionNotFound

from app.api.accounts import router as accounts
from app.api.reputation import ReputationView, build_reputation
from app.api.runtime import Runtime
from app.api.schemas import (
    AppConfig,
    AttemptView,
    BatchInput,
    BatchSummary,
    DemoInvoice,
    EvalResults,
    LeaderboardEntry,
    LedgerEventView,
    OwnerTxInput,
    Registry,
    Stats,
)
from app.api.security import RequestBoundary, can_read_private, problem, require_admin
from app.api.submissions import submit
from app.api.views import CHANGE_LABELS, attempt_view, ledger_view, stat_block
from app.chain.errors import ChainSendError
from app.config import Settings
from app.models import Attempt, BatchRecord, ChainEvent
from app.threat_intel import WalletSecurityView


def create_app(settings=None, *, runtime=None):
    @asynccontextmanager
    async def lifespan(app):
        current = runtime or Runtime(settings or Settings())
        app.state.runtime = current
        if current.settings.static_dir.is_dir():
            app.mount(
                "/", StaticFiles(directory=current.settings.static_dir, html=True), name="frontend"
            )
        await current.start()
        try:
            yield
        finally:
            await current.stop()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(RequestBoundary)
    # Validate Host against the app's configured origin, plus local development/test hosts.
    origin = settings or (runtime.settings if runtime else None)
    hosts = ["localhost", "127.0.0.1", "testserver"]
    if origin and urlparse(origin.public_base_url).hostname:
        hosts.append(urlparse(origin.public_base_url).hostname)
    # Runtime production settings are not loaded at import; validate those hosts per request below.

    @app.middleware("http")
    async def host_boundary(request, call_next):
        current = getattr(app.state, "runtime", None)
        configured = urlparse(current.settings.public_base_url).hostname if current else None
        if request.url.hostname not in {*hosts, configured}:
            return JSONResponse(
                {"message_en": "Unrecognized host.", "message_zh": "未知主机。"}, status_code=400
            )
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        body = (
            exc.detail
            if isinstance(exc.detail, dict) and "message_en" in exc.detail
            else {"message_en": "Request could not be completed.", "message_zh": "无法完成请求。"}
        )
        return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(
            {"message_en": "Invalid request fields.", "message_zh": "请求字段无效。"},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def failure(request, exc):
        return JSONResponse(
            {
                "message_en": "Processing is temporarily unavailable.",
                "message_zh": "处理服务暂时不可用。",
            },
            status_code=503,
        )

    def get_attempt(request, attempt_id):
        try:
            return request.app.state.runtime.store.get(str(attempt_id))
        except KeyError:
            raise problem(404, "Attempt not found.", "未找到该尝试。") from None

    async def current_state(request, network=None):
        current = request.app.state.runtime
        return await current.state(network or current.settings.network)

    def current_rows(current, model, state):
        config = state["config"]
        return select(model).where(
            model.network == config["network"],
            model.contract_address == config["contract_address"].lower(),
        )

    @app.get("/api/health")
    async def health(request: Request):
        return request.app.state.runtime.health()

    @app.get("/api/security/wallets", response_model=WalletSecurityView)
    async def wallet_security(
        request: Request,
        address: str | None = Query(None, pattern=r"^0x[0-9a-fA-F]{40}$", max_length=42),
    ):
        return request.app.state.runtime.screening.view([address] if address else [])

    @app.get("/api/config", response_model=AppConfig)
    async def config(request: Request):
        return (await current_state(request))["config"]

    @app.get("/api/registry", response_model=Registry)
    async def registry(request: Request):
        return (await current_state(request))["registry"]

    @app.post("/api/bounty/attempts", status_code=202)
    async def bounty(request: Request):
        return await submit(request, source="bounty")

    @app.get(
        "/api/attempts/{attempt_id}", response_model=AttemptView, response_model_exclude_unset=True
    )
    async def attempt(request: Request, attempt_id: UUID):
        value = get_attempt(request, attempt_id)
        return attempt_view(value, private=can_read_private(request, value))

    @app.get("/api/attempts/{attempt_id}/preview.png")
    async def preview(request: Request, attempt_id: UUID):
        value = get_attempt(request, attempt_id)
        if not can_read_private(request, value):
            raise problem(403, "This invoice preview is private.", "此发票预览为私有内容。")
        if not value.preview_path:
            raise problem(404, "No preview available.", "暂无预览。")
        root = (request.app.state.runtime.settings.data_dir / "previews").resolve()
        path = Path(value.preview_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise problem(404, "No preview available.", "暂无预览。")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/api/stats", response_model=Stats)
    async def stats(request: Request):
        current = request.app.state.runtime
        state = await current_state(request, current.settings.bounty_network)
        with Session(current.store.engine) as session:
            attempts = session.exec(
                current_rows(current, Attempt, state).where(Attempt.source.in_(["bounty", "seed"]))
            ).all()
            events = session.exec(current_rows(current, ChainEvent, state)).all()
        return Stats(
            outside=stat_block(
                [a for a in attempts if a.source == "bounty"],
                events,
                state["config"]["token"]["decimals"],
            ),
            seed=stat_block(
                [a for a in attempts if a.source == "seed"],
                events,
                state["config"]["token"]["decimals"],
            ),
            since=min((a.created_at for a in attempts), default=None),
        )

    @app.get("/api/leaderboard", response_model=list[LeaderboardEntry])
    async def leaderboard(request: Request):
        current = request.app.state.runtime
        state = await current_state(request, current.settings.bounty_network)
        with Session(current.store.engine) as session:
            values = session.exec(
                current_rows(current, Attempt, state)
                .where(Attempt.source == "bounty", Attempt.ai_fooled.is_(True))
                .order_by(Attempt.agent, Attempt.created_at)
                .limit(20)
            ).all()
        return [
            LeaderboardEntry(
                nickname=a.nickname or "Anonymous",
                agent=a.agent,
                attempt_id=a.id,
                created_at=a.created_at,
                summary_en="Got a payment proposed",
                summary_zh="让 AI 提出了一笔付款",
            )
            for a in values
        ]

    @app.get("/api/ledger", response_model=list[LedgerEventView])
    async def ledger(
        request: Request,
        kind: Literal["paid", "blocked", "changes", "all"] = "all",
        limit: int = Query(100, ge=1, le=100),
    ):
        current = request.app.state.runtime
        state = await current_state(request)
        names = {
            "paid": ["Paid"],
            "blocked": ["Blocked"],
            "changes": list(CHANGE_LABELS),
            "all": ["Paid", "Blocked", *CHANGE_LABELS],
        }[kind]
        with Session(current.store.engine) as session:
            events = session.exec(
                current_rows(current, ChainEvent, state)
                .where(ChainEvent.name.in_(names))
                .order_by(ChainEvent.block_number.desc(), ChainEvent.id.desc())
                .limit(limit)
            ).all()
        return [ledger_view(e, state) for e in events]

    @app.get("/api/reputation", response_model=ReputationView)
    async def reputation(
        request: Request,
        network: Literal["mainnet", "testnet"] | None = None,
        limit: int = Query(20, ge=1, le=100),
    ):
        current = request.app.state.runtime
        selected = network or current.settings.network
        stale = False
        try:
            state = await current_state(request, selected)
        except StarletteHTTPException as exc:
            if exc.status_code != 503 or selected not in current.states:
                raise
            state, stale = current.states[selected], True
        result = build_reputation(
            current.store.engine,
            state,
            limit=limit,
            indexer_enabled=current.settings.indexer_enabled,
        )
        if stale:
            result.coverage.stale = True
            result.coverage.gaps.append("CHAIN_STATE_STALE")
        return result

    @app.get("/api/eval", response_model=EvalResults, response_model_exclude_none=True)
    async def evaluation(request: Request):
        path = request.app.state.runtime.settings.data_dir / "eval" / "results.json"
        return (
            EvalResults.model_validate(json.loads(path.read_text()))
            if path.is_file()
            else EvalResults()
        )

    team = APIRouter(prefix="/api/team", dependencies=[Depends(require_admin)])

    @team.post("/attempts", status_code=202)
    async def team_submit(request: Request):
        return await submit(request, source="team")

    @team.get("/attempts", response_model=list[AttemptView])
    async def team_attempts(
        request: Request,
        source: Literal["bounty", "seed", "team", "batch"] | None = None,
        limit: int = Query(100, ge=1, le=200),
    ):
        current = request.app.state.runtime
        state = await current_state(request)
        query = (
            current_rows(current, Attempt, state).order_by(Attempt.created_at.desc()).limit(limit)
        )
        if source:
            query = query.where(Attempt.source == source)
        with Session(current.store.engine) as session:
            values = session.exec(query).all()
        return [attempt_view(a, private=True) for a in values]

    @team.get("/demo-invoices", response_model=list[DemoInvoice], response_model_exclude_none=True)
    async def demos(request: Request):
        current = request.app.state.runtime
        return [
            current.demo(entry["name"])[1]
            for entry in current.manifest()
            if entry.get("stage") is True
        ]

    @team.post("/batch", status_code=202)
    async def batch(request: Request, body: BatchInput):
        from app.api.batch import create_batch

        return await create_batch(request.app.state.runtime)

    @team.get("/batch/{batch_id}", response_model=BatchSummary)
    async def batch_status(request: Request, batch_id: UUID):
        current = request.app.state.runtime
        with Session(current.store.engine) as session:
            record = session.get(BatchRecord, str(batch_id))
            if not record:
                raise problem(404, "Batch not found.", "未找到该批次。")
            attempts = session.exec(select(Attempt).where(Attempt.id.in_(record.attempt_ids))).all()
        counts = {
            outcome: sum(a.outcome == outcome for a in attempts)
            for outcome in ("paid", "refused", "blocked", "no_invoice")
        }
        return BatchSummary(
            total=len(record.attempt_ids),
            done=sum(a.status in {"done", "error"} for a in attempts),
            false_alarms=counts["refused"],
            **counts,
        )

    @team.post("/owner-tx")
    async def owner_tx(request: Request, body: OwnerTxInput):
        current = request.app.state.runtime
        try:
            events = await asyncio.to_thread(
                current.receipt_reader, current.settings.network, body.tx_hash
            )
        except TransactionNotFound:
            raise problem(409, "Transaction is not confirmed yet.", "交易尚未确认。") from None
        except ChainSendError:
            raise problem(
                400,
                "Receipt does not belong to a successful vault transaction.",
                "回执不是该金库的成功交易。",
            ) from None
        await current.state(current.settings.network, force=True)
        # The endpoint is only a receipt reporter; it cannot sign owner actions.
        return {"decoded_events": events}

    app.include_router(team)
    app.include_router(accounts)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def unknown_api(path: str):
        raise problem(404, "API endpoint not found.", "未找到 API 接口。")

    return app


app = create_app()
