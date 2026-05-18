import html
import re
from datetime import date, datetime


def parse_amount(text: str) -> float:
    clean = re.sub(r"[^\d.-]", "", str(text))
    try:
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0


def format_money(v: float) -> str:
    return f"{v:,.0f} ₫"


def bold_money(v: float) -> str:
    return f"<b>{format_money(v)}</b>"


def safe_cell(row: list, idx: int) -> str:
    return str(row[idx]).strip() if idx < len(row) else ""


def parse_month(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%b-%Y")
    except ValueError:
        return datetime.min


def parse_flexible_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return datetime.strptime(s, "%m/%d/%Y").date()


def esc(s: str) -> str:
    return html.escape(str(s))


async def send_html(update, text: str) -> None:
    if len(text) <= 4000:
        await update.message.reply_text(text, parse_mode="HTML")
        return

    chunk_lines: list[str] = []
    chunk_len = 0
    for line in text.split("\n"):
        line_len = len(line) + 1  # +1 for the newline
        if chunk_lines and chunk_len + line_len > 4000:
            await update.message.reply_text("\n".join(chunk_lines), parse_mode="HTML")
            chunk_lines = []
            chunk_len = 0
        chunk_lines.append(line)
        chunk_len += line_len
    if chunk_lines:
        await update.message.reply_text("\n".join(chunk_lines), parse_mode="HTML")
