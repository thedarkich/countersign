import warnings
from dataclasses import dataclass, field
from io import BytesIO
from typing import Literal

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 20
MAX_PIXELS = 20_000_000
MAX_TEXT = 200_000


class InputError(ValueError):
    pass


@dataclass
class Document:
    kind: Literal["pdf", "image", "text"]
    images: list[bytes] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)
    text: str = ""
    page_count: int = 0


def ingest_text(text: str) -> Document:
    if not text.strip() or len(text) > 4000:
        raise InputError("text must contain 1–4000 characters")
    return Document(kind="text", text=text)


def ingest_bytes(data: bytes) -> Document:
    if not data or len(data) > MAX_BYTES:
        raise InputError("file must contain at most 5 MB")
    if data.startswith(b"%PDF"):
        return _pdf(data)
    if data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff"):
        return _image(data)
    raise InputError("only PDF, PNG and JPEG are accepted")


def _image(data: bytes) -> Document:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.width * original.height > MAX_PIXELS:
                    raise InputError("image dimensions are too large")
                clean = ImageOps.exif_transpose(original).convert("RGB")
                clean.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                output = Image.new("RGB", clean.size)
                output.paste(clean)
                buffer = BytesIO()
                output.save(buffer, format="PNG")
        return Document(kind="image", images=[buffer.getvalue()], page_count=1)
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InputError("invalid or oversized image") from exc


def _pdf(data: bytes) -> Document:
    result = Document(kind="pdf")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.is_encrypted or pdf.needs_pass:
                raise InputError("encrypted PDFs are not accepted")
            if not 1 <= len(pdf) <= MAX_PAGES:
                raise InputError("PDF must contain 1–20 pages")
            result.page_count = len(pdf)
            for index, page in enumerate(pdf):
                page.set_rotation(0)
                raw = page.get_text(
                    "dict",
                    flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES,
                    clip=pymupdf.INFINITE_RECT(),
                )
                raw["width"], raw["height"] = page.rect.width, page.rect.height
                result.pages.append(raw)
                spans = [
                    span["text"]
                    for block in raw["blocks"]
                    if block.get("type") == 0
                    for line in block["lines"]
                    for span in line["spans"]
                ]
                result.text += "\n".join(spans) + "\n"
                if len(result.text) > MAX_TEXT:
                    raise InputError("PDF text layer is too large")
                if index < 2:
                    width, height = page.rect.width, page.rect.height
                    if min(width, height) <= 0:
                        raise InputError("invalid PDF page geometry")
                    scale = min(150 / 72, 1600 / max(width, height))
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                    result.images.append(pixmap.tobytes("png"))
        return result
    except InputError:
        raise
    except (RuntimeError, ValueError, pymupdf.FileDataError) as exc:
        raise InputError("invalid PDF") from exc
