import logging
from collections import defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ConversationHandler, ContextTypes

import config
import sheets
from formatters import parse_amount, bold_money, safe_cell, parse_month, esc, send_html

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

            if month and is_refund != 'yes' and type_val == 'spending':
                monthly_data[month][card].append({'desc': desc, 'amount': amount})

        sorted_months = sorted(monthly_data.keys(), key=parse_month)

        now = datetime.now(config.VN_TZ)
        current_month_dt = datetime(now.year, now.month, 1)

        lines = ["<b>📈 Detailed Spending Report</b>"]

        for m in sorted_months:
            m_dt = parse_month(m)
            if m_dt >= current_month_dt - relativedelta(months=1):
                month_total = sum(
                    item['amount']
                    for card_items in monthly_data[m].values()
                    for item in card_items
                )
                lines.append(f"\n📅 <b>{esc(m)}</b> · Total: {bold_money(month_total)}")
                lines.append(SEP)

                for c, items in monthly_data[m].items():
                    card_total = sum(item['amount'] for item in items)
                    lines.append(f"  💳 <b>{esc(c)}</b>: {bold_money(card_total)}")
                    for item in items:
                        short_desc = (item['desc'][:32] + '…') if len(item['desc']) > 32 else item['desc']
                        lines.append(f"     ├ {esc(short_desc)}: {bold_money(item['amount'])}")

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

            if item:
                installments_by_card[card].append({
                    'item': item,
                    'monthly': monthly_payment,
                    'periods': periods,
                    'paid': paid,
                    'left': left,
                })

        lines = ["<b>🙏🏼 All Tracked Installments</b>"]

        for c, items in installments_by_card.items():
            active_monthly = sum(i['monthly'] for i in items if i['left'] > 0)
            lines.append(f"\n{SEP}")
            lines.append(f"💳 <b>{esc(c)}</b> · Active monthly: {bold_money(active_monthly)}")
            for i in items:
                status = "✅ Completed" if i['left'] <= 0 else f"{i['paid']}/{i['periods']} paid, {i['left']} left"
                lines.append(f"   ├ {esc(i['item'])}: {bold_money(i['monthly'])}/mo [{status}]")

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

            if not col_a or "💰" in col_a or "Next statement" in col_a or "Monthly Cash Flow" in col_a or col_a == "Card":
                capture_main = False
                capture_cat = False
                continue

            val = str(row[1]).strip() if len(row) > 1 else ""

            if capture_main and val:
                dashboard_lines.append(f"🔹 <b>{esc(col_a)}</b>: {esc(val)}")
            if capture_cat and val:
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

                status_emoji = "✅" if "Plenty" in status else "⚠️" if "Soon" in status else "🚨"
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

                total_income = safe_cell(row, 3) or "0"
                total_expenses = safe_cell(row, 6) or "0"
                remains = safe_cell(row, 7) or "0"
                budget_used = safe_cell(row, 8) or "0%"

                lines.append(
                    f"🗓️ <b>{esc(col_a)}</b>\n"
                    f"Income: {esc(total_income)} | Expenses: {esc(total_expenses)}\n"
                    f"Remains: {esc(remains)} | Used: {esc(budget_used)}\n"
                )
                count += 1
                if count >= 3:
                    break

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception:
        logger.exception("Error fetching budget")
        await update.message.reply_text("❌ Failed to fetch budget data.")
