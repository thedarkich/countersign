import re
import unicodedata

from rapidfuzz.fuzz import partial_ratio

from app.pipeline.ingest import Document
from app.schemas import Flag, HiddenSpan, HiddenText

KEYWORDS = (
    "pay",
    "transfer",
    "address",
    "wallet",
    "ignore",
    "instruction",
    "支付",
    "转账",
    "地址",
    "钱包",
    "忽略",
    "指令",
)


def normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def inspect_hidden_text(document: Document, visible_text: str) -> tuple[HiddenText, list[Flag]]:
    if document.kind != "pdf":
        return HiddenText(has_hidden_text=False, page_size=None), []
    spans: list[HiddenSpan] = []
    for index, page in enumerate(document.pages):
        width, height = page["width"], page["height"]
        for block in page.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    box = tuple(span["bbox"])
                    x0, y0, x1, y1 = box
                    color = span.get("color", 0)
                    reasons = []
                    if x1 <= x0 or y1 <= y0:
                        reasons.append("zero_area")
                    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
                        reasons.append("off_page")
                    if span.get("size", 0) < 4:
                        reasons.append("tiny_font")
                    if all(((color >> shift) & 255) >= 240 for shift in (16, 8, 0)):
                        reasons.append("near_white")
                    for reason in reasons:
                        spans.append(HiddenSpan(text=text, reason=reason, bbox=box, page=index + 1))
    diff = []
    if len(visible_text) < 2000:
        words = set(re.findall(r"\w{3,}", normalized(document.text)))
        words.update(word for word in KEYWORDS if word in normalized(document.text))
        visible = normalized(visible_text)
        diff = sorted(word for word in words if partial_ratio(word, visible) < 80)
    hidden = (
        bool(spans)
        or len(diff) >= 5
        or any(keyword in word for word in diff for keyword in KEYWORDS)
    )
    flags = []
    if hidden:
        flags.append(
            Flag(
                code="HIDDEN_TEXT",
                severity="high",
                detail_en="Hidden or untranscribed document text was detected.",
                detail_zh="发现隐藏文字或未显示在转录中的文字。",
            )
        )
    if document.page_count > 2:
        flags.append(
            Flag(
                code="UNREVIEWED_PAGES",
                severity="high",
                detail_en="Only the first two pages were visually reviewed.",
                detail_zh="仅前两页经过视觉检查，其他页面需要人工核查。",
            )
        )
    first = document.pages[0]
    return HiddenText(
        has_hidden_text=hidden,
        page_size=(first["width"], first["height"]),
        spans=spans,
        diff_words=diff,
    ), flags
