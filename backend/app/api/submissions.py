import unicodedata

from eth_utils import is_address
from fastapi import Request
from sqlmodel import Session
from starlette.datastructures import UploadFile

from app.api.accounts import throttle
from app.api.security import (
    device_id,
    has_admin_token,
    hash_private,
    problem,
    session_user,
)
from app.models import AttemptOwner, SubmissionMeta
from app.pipeline.ingest import MAX_BYTES, InputError
from app.pipeline.runner import new_attempt
from app.storage import write_private_bytes


def clean_label(value, maximum):
    value = unicodedata.normalize("NFKC", value).strip()
    if not 1 <= len(value) <= maximum or any(
        unicodedata.category(c).startswith("C") for c in value
    ):
        raise problem(400, "Invalid nickname or filename.", "昵称或文件名无效。")
    return value


async def submit(request: Request, *, source):
    runtime = request.app.state.runtime
    bounty = source == "bounty"
    runtime.check_submission(bounty=bounty)
    device = device_id(request, required=bounty)
    try:
        async with request.form(max_files=1, max_fields=6, max_part_size=16384) as form:
            allowed = {"nickname", "address", "agent", "text", "file"} | (
                {"demo"} if not bounty else set()
            )
            if set(form) - allowed or any(len(form.getlist(k)) != 1 for k in form):
                raise problem(400, "Unexpected or repeated form field.", "表单包含未知或重复字段。")
            fields = {k: v for k, v in form.items() if k != "file"}
            if any(not isinstance(v, str) for v in fields.values()):
                raise problem(400, "Invalid form fields.", "表单字段无效。")
            nickname = clean_label(
                fields.get("nickname", "") if bounty else fields.get("nickname") or "Team", 24
            )
            agent = fields.get("agent", "guarded")
            address = fields.get("address") or None
            if agent not in {"guarded", "naive"} or (address and not is_address(address)):
                raise problem(400, "Invalid agent or address.", "代理或地址无效。")
            text, demo, upload = fields.get("text"), fields.get("demo"), form.get("file")
            if sum(bool(v) for v in (text, demo, upload)) != 1:
                raise problem(
                    400,
                    "Choose exactly one invoice file or text input.",
                    "请仅选择一份发票文件或一段文本。",
                )
            if bounty:
                runtime.limiter.reserve(device, nickname)
            elif not has_admin_token(request) and (account := session_user(request)):
                # open sign-up: each account gets a bounded share of the AI budget and the vault
                throttle(
                    request,
                    [
                        ("account-minute", account["id"], 60, 3),
                        ("account-day", account["id"], 86400, 30),
                    ],
                )
            data, file_name, fixture_kind = None, None, None
            if upload is not None:
                if not isinstance(upload, UploadFile):
                    raise problem(400, "Invalid file field.", "文件字段无效。")
                data = await upload.read(MAX_BYTES + 1)
                file_name = clean_label(
                    (upload.filename or "invoice").replace("\\", "/").split("/")[-1], 180
                )
            elif demo:
                path, entry = runtime.demo(demo)
                if path.stat().st_size > MAX_BYTES:
                    raise InputError("Demo file too large")
                data = path.read_bytes()
                file_name, fixture_kind = path.name, entry.kind
            document = await runtime.ingest(data=data, text=text)
    except InputError:
        raise problem(
            400,
            "Use a valid PDF, PNG or JPEG up to 5 MB, or 1–4000 characters of text.",
            "请使用不超过 5 MB 的有效 PDF、PNG、JPEG，或 1–4000 字文本。",
        ) from None

    network = runtime.settings.bounty_network if bounty else runtime.settings.network
    try:
        snapshot = await runtime.chain.snapshot(network)
    except Exception:
        raise problem(
            503, "Payment rules are temporarily unavailable.", "暂时无法获取付款规则。"
        ) from None
    attempt = new_attempt(
        snapshot,
        network=network,
        source=source,
        agent=agent,
        fixture_kind=fixture_kind,
        device_id=device if bounty else None,
        nickname=nickname,
        claimed_address=address,
        input_kind=document.kind,
        input_text=text,
        file_name=file_name,
        demo_name=demo,
    )
    async with runtime.admission:
        runtime.check_submission(bounty=bounty)
        created = []
        try:
            if data is not None:
                suffix = ".pdf" if document.kind == "pdf" else ".image"
                path = runtime.settings.data_dir / "uploads" / (attempt.id + suffix)
                write_private_bytes(path, data)
                created.append(path)
                attempt.file_path = str(path)
            if document.images:
                preview = runtime.settings.data_dir / "previews" / (attempt.id + ".png")
                write_private_bytes(preview, document.images[0])
                created.append(preview)
                attempt.preview_path = str(preview)
            with Session(runtime.store.engine) as session:
                session.add(attempt)
                owner = None if bounty else session_user(request)
                if owner:
                    session.add(AttemptOwner(attempt_id=attempt.id, user_id=owner["id"]))
                if bounty:
                    salt = runtime.settings.ip_hash_salt.get_secret_value()
                    ip = request.client.host if request.client else "unknown"
                    session.add(
                        SubmissionMeta(attempt_id=attempt.id, ip_hash=hash_private(ip, salt))
                    )
                session.commit()
                attempt_id = attempt.id
            runtime.queue.put_nowait(attempt_id)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
    return {"attempt_id": attempt_id}
