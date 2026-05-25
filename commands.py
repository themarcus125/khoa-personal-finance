import logging
from collections import defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes, ConversationHandler

import config
import sheets
from formatters import bold_money, esc, parse_amount, parse_month, safe_cell, send_html

logger = logging.getLogger(__name__)

SEP = "─────"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Welcome to your Personal Finance Bot!</b>\n\n"
        "Here is what I can do for you:\n"
        "💸 /expense — Add a new transaction\n"
        "🙏🏼 /installment — Add a new installment plan\n"
        "📊 /report — Spending summary by statement month\n"
        "📦 /report_installments — All tracked installments\n"
        "📈 /dashboard — This month's totals overview\n"
        "📅 /closing — Upcoming card statement dates\n"
        "💰 /budget — Monthly cash flow and budget used\n"
        "🔄 /refresh — Reload settings from Google Sheet\n\n"
        "Type /cancel at any time to abort the current entry.",
        parse_mode="HTML",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Action canceled. Let me know when you need me again!",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def refresh_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Refreshing settings from Google Sheets...")
    sheets.load_settings()
    await update.message.reply_text(
        f"✅ Settings updated! Found <b>{len(sheets.CLOSING_DAYS_CACHE)}</b> cards.",
        parse_mode="HTML",
    )


async def get_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = " ".join(context.args).strip() if context.args else ""
    show_all = arg.lower() == "all"
    target_month_dt = None

    if arg and not show_all:
        target_month_dt = parse_month(arg)
        if target_month_dt == datetime.min:
            await update.message.reply_text(
                "❌ Unrecognized month format. Try <code>/report May-2026</code>, <code>/report all</code>, or just <code>/report</code>.",
                parse_mode="HTML",
            )
            return

    await update.message.reply_text("📊 Fetching your detailed financial summary...")
    try:
        sh = sheets.get_sheet()
        ws = sh.worksheet("Transactions")
        data = ws.get_all_values()

        monthly_data = defaultdict(lambda: defaultdict(list))

        for row in data[1:]:
            if len(row) < 8:
                continue
            month = safe_cell(row, config.TxnCol.MONTH)
            card = safe_cell(row, config.TxnCol.CARD)
            desc = safe_cell(row, config.TxnCol.DESC)
            amount = parse_amount(safe_cell(row, config.TxnCol.AMOUNT))
            type_val = safe_cell(row, config.TxnCol.TYPE).lower()
            is_refund = safe_cell(row, config.TxnCol.REFUND).lower()

            if month and is_refund != "yes" and type_val == "spending":
                monthly_data[month][card].append({"desc": desc, "amount": amount})

        sorted_months = sorted(monthly_data.keys(), key=parse_month)

        if not show_all and target_month_dt is None:
            # Default: latest month only
            if sorted_months:
                sorted_months = [sorted_months[-1]]
            else:
                sorted_months = []

        if target_month_dt is not None:
            sorted_months = [m for m in sorted_months if parse_month(m) == target_month_dt]

        lines = ["<b>📈 Detailed Spending Report</b>"]

        for m in sorted_months:
            month_total = sum(
                item["amount"]
                for card_items in monthly_data[m].values()
                for item in card_items
            )
            lines.append(f"\n📅 <b>{esc(m)}</b> · Total: {bold_money(month_total)}")
            lines.append(SEP)

            for c, items in monthly_data[m].items():
                card_total = sum(item["amount"] for item in items)
                lines.append(f"  💳 <b>{esc(c)}</b>: {bold_money(card_total)}")
                for item in items:
                    short_desc = (
                        (item["desc"][:32] + "…")
                        if len(item["desc"]) > 32
                        else item["desc"]
                    )
                    lines.append(
                        f"     ├ {esc(short_desc)}: {bold_money(item['amount'])}"
                    )

        if len(lines) == 1:
            lines.append("\n🗒️ No transactions yet for this period.")

        await send_html(update, "\n".join(lines))

    except Exception:
        logger.exception("Error fetching report")
        await update.message.reply_text(
            "❌ Failed to fetch report. Please ensure your 'Transactions' sheet has the standard columns."
        )


async def get_installments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 Fetching your active installments...")
    try:
        sh = sheets.get_sheet()
        ws = sh.worksheet("Installments")
        data = ws.get_all_values()

        installments_by_card = defaultdict(list)

        for row in data[1:]:
            if len(row) < 5:
                continue

            item = safe_cell(row, config.InstCol.ITEM)
            card = safe_cell(row, config.InstCol.CARD)
            start_date_str = safe_cell(row, config.InstCol.START)
            price = parse_amount(safe_cell(row, config.InstCol.PRICE))

            try:
                periods = int(safe_cell(row, config.InstCol.PERIODS))
            except ValueError:
                periods = 0

            monthly_payment = price / periods if periods > 0 else price

            paid = 0
            left = periods
            if periods > 0 and start_date_str:
                try:
                    from formatters import parse_flexible_date

                    start_date = parse_flexible_date(start_date_str)
                    now = datetime.now(config.VN_TZ).date()
                    if now >= start_date:
                        diff = relativedelta(now, start_date)
                        paid = min(diff.years * 12 + diff.months + 1, periods)
                    left = periods - paid
                except Exception:
                    logger.warning(f"Failed to parse date for {item!r}")

            if (
                item
                and card.lower() != "card"
                and item.lower() not in ("item", "totals")
            ):
                installments_by_card[card].append(
                    {
                        "item": item,
                        "monthly": monthly_payment,
                        "periods": periods,
                        "paid": paid,
                        "left": left,
                    }
                )

        lines = ["<b>🙏🏼 All Tracked Installments</b>"]

        for c, items in installments_by_card.items():
            active_monthly = sum(i["monthly"] for i in items if i["left"] > 0)
            lines.append(f"\n{SEP}")
            lines.append(
                f"💳 <b>{esc(c)}</b> · Active monthly: {bold_money(active_monthly)}"
            )
            for i in items:
                status = (
                    "✅ Completed"
                    if i["left"] <= 0
                    else f"{i['paid']}/{i['periods']} paid, {i['left']} left"
                )
                lines.append(
                    f"   ├ {esc(i['item'])}: {bold_money(i['monthly'])}/mo [{status}]"
                )

        total_active = sum(
            i["monthly"]
            for items in installments_by_card.values()
            for i in items
            if i["left"] > 0
        )
        lines.append(f"\n{SEP}")
        lines.append(f"💰 <b>TOTALS: {bold_money(total_active)}/mo</b>")

        await send_html(update, "\n".join(lines))

    except Exception:
        logger.exception("Error fetching installments")
        await update.message.reply_text("❌ Failed to fetch installments.")


async def get_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Fetching your monthly dashboard...")
    try:
        sh = sheets.get_sheet()
        ws = sh.worksheet("Dashboard")
        data = ws.get_all_values()

        dashboard_lines = ["<b>💸 This Month's Overview</b>\n"]
        category_lines = ["\n<b>🏷️ Category Breakdown</b>\n"]

        capture_main = False
        capture_cat = False

        for row in data:
            if not row:
                continue
            col_a = str(row[0]).strip()

            if "This month" in col_a:
                capture_main = True
                capture_cat = False
                continue

            if "Category" in col_a or "🏷️" in col_a:
                capture_main = False
                capture_cat = True
                continue

            if (
                not col_a
                or "💰" in col_a
                or "Next statement" in col_a
                or "Monthly Cash Flow" in col_a
                or col_a == "Card"
            ):
                capture_main = False
                capture_cat = False
                continue

            val = str(row[1]).strip() if len(row) > 1 else ""

            if capture_main and val:
                if "Total Outflow" in col_a:
                    dashboard_lines.append(f"\n<b>{esc(col_a)}: {esc(val)}</b>")
                else:
                    dashboard_lines.append(f"🔹 <b>{esc(col_a)}</b>: {esc(val)}")
            if capture_cat and val:
                if col_a.upper() == "TOTAL":
                    category_lines.append(f"\n<b>{esc(col_a)}: {esc(val)}</b>")
                else:
                    category_lines.append(f"🔸 <b>{esc(col_a)}</b>: {esc(val)}")

        if len(category_lines) > 1:
            dashboard_lines.extend(category_lines)

        await update.message.reply_text("\n".join(dashboard_lines), parse_mode="HTML")

    except Exception:
        logger.exception("Error fetching dashboard")
        await update.message.reply_text("❌ Failed to fetch dashboard data.")


async def get_closing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Checking upcoming statement dates...")
    try:
        sh = sheets.get_sheet()
        ws = sh.worksheet("Dashboard")
        data = ws.get_all_values()

        lines = ["<b>📅 Next Statement Closing Dates</b>\n"]
        capture = False

        for row in data:
            if not row:
                continue
            col_a = str(row[0]).strip()

            if col_a == "📅 Next statement closing dates":
                capture = True
                continue

            if capture:
                if col_a == "Card":
                    continue
                if not col_a or col_a.startswith("💸"):
                    break

                date_val = safe_cell(row, 2)
                days_until = safe_cell(row, 3)
                status = safe_cell(row, 4)

                status_emoji = (
                    "✅" if "Plenty" in status else "⚠️" if "Soon" in status else "🚨"
                )
                lines.append(
                    f"💳 <b>{esc(col_a)}</b>: {esc(date_val)} ({esc(days_until)} days) {status_emoji}"
                )

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception:
        logger.exception("Error fetching closing dates")
        await update.message.reply_text("❌ Failed to fetch closing dates.")


async def get_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 Fetching budget and cash flow...")
    try:
        sh = sheets.get_sheet()
        ws = sh.worksheet("Dashboard")
        data = ws.get_all_values()

        lines = ["<b>💰 Monthly Cash Flow</b>\n"]
        capture = False
        count = 0

        for row in data:
            if not row:
                continue
            col_a = str(row[0]).strip()

            if col_a == "💰 Monthly Cash Flow":
                capture = True
                continue

            if capture:
                if col_a == "Month":
                    continue
                if not col_a:
                    break

                # Skip description/header rows — real month rows contain a "-" year pattern
                if "-20" not in col_a:
                    continue

                total_income = safe_cell(row, 3) or "0"
                total_expenses = safe_cell(row, 6) or "0"
                remains = safe_cell(row, 7) or "0"
                budget_used = safe_cell(row, 8) or "0%"

                try:
                    used_pct = float(budget_used.replace("%", "").strip())
                except ValueError:
                    used_pct = 0.0
                if used_pct < 80:
                    used_emoji = "🟢"
                elif used_pct < 95:
                    used_emoji = "🟡"
                else:
                    used_emoji = "🔴"

                lines.append(
                    f"🗓️ <b>{esc(col_a)}</b>\n"
                    f"Income: <b>{esc(total_income)}</b> | Expenses: <b>{esc(total_expenses)}</b>\n"
                    f"Remains: <b>{esc(remains)}</b> | {used_emoji} Used: <b>{esc(budget_used)}</b>\n"
                )
                count += 1
                if count >= 2:
                    break

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception:
        logger.exception("Error fetching budget")
        await update.message.reply_text("❌ Failed to fetch budget data.")
