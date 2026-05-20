import logging
from datetime import datetime

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
from formatters import bold_money, esc
from sheets import calculate_statement_month, get_card_keyboard, get_sheet

logger = logging.getLogger(__name__)

# Conversation states
(
    EXP_CARD,
    EXP_AMOUNT,
    EXP_CATEGORY,
    EXP_DESC,
    INST_ITEM,
    INST_CARD,
    INST_START_DATE,
    INST_FULL_PRICE,
    INST_PERIODS,
) = range(9)


# ==========================================
#         ADD EXPENSE CONVERSATION
# ==========================================


async def start_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Quick-add: /expense\ncard\namount\ncategory\ndescription
    if len(lines) >= 5:
        card = lines[1]
        try:
            amount = float(lines[2].replace(",", ""))
        except ValueError:
            await update.message.reply_text("❌ Invalid amount on line 3.")
            return ConversationHandler.END
        category = lines[3]
        description = "\n".join(lines[4:])

        date_obj = datetime.now(config.VN_TZ)
        statement_month = calculate_statement_month(date_obj, card)
        row = [
            date_obj.strftime("%m/%d/%Y"),
            card,
            amount,
            category,
            "Spending",
            description,
            statement_month,
            "No",
        ]
        try:
            sh = get_sheet()
            ws = sh.worksheet("Transactions")
            ws.append_row(row, value_input_option="USER_ENTERED")
            await update.message.reply_text(
                f"✅ <b>Expense added</b>\n\n"
                f"💳 <b>{esc(card)}</b>\n"
                f"💰 {bold_money(amount)}\n"
                f"🏷️ {esc(category)} · 📅 {date_obj.strftime('%m/%d/%Y')}\n"
                f"📝 {esc(description)}\n"
                f"<i>Target statement: {esc(statement_month)}</i>",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("Error appending expense row")
            await update.message.reply_text("❌ Failed to add to Google Sheets. Check logs.")
        return ConversationHandler.END

    await update.message.reply_text(
        "💸 Let's log a new expense.\nWhich card did you use?",
        reply_markup=get_card_keyboard(),
    )
    return EXP_CARD


async def exp_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["card"] = update.message.text
    await update.message.reply_text(
        "Got it. How much did you spend? (e.g. 128900)",
        reply_markup=ReplyKeyboardRemove(),
    )
    return EXP_AMOUNT


async def exp_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.replace(",", ""))
        context.user_data["amount"] = amount
        await update.message.reply_text(
            "What category does this fall under?",
            reply_markup=config.CATEGORY_KEYBOARD,
        )
        return EXP_CATEGORY
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return EXP_AMOUNT


async def exp_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text
    await update.message.reply_text(
        "Briefly describe the purchase:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return EXP_DESC


async def exp_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    card = context.user_data["card"]
    amount = context.user_data["amount"]
    category = context.user_data["category"]

    date_obj = datetime.now(config.VN_TZ)
    statement_month = calculate_statement_month(date_obj, card)

    row = [
        date_obj.strftime("%m/%d/%Y"),
        card,
        amount,
        category,
        "Spending",
        description,
        statement_month,
        "No",
    ]

    try:
        sh = get_sheet()
        ws = sh.worksheet("Transactions")
        ws.append_row(row, value_input_option="USER_ENTERED")

        await update.message.reply_text(
            f"✅ <b>Expense added</b>\n\n"
            f"💳 <b>{esc(card)}</b>\n"
            f"💰 {bold_money(amount)}\n"
            f"🏷️ {esc(category)} · 📅 {date_obj.strftime('%m/%d/%Y')}\n"
            f"📝 {esc(description)}\n"
            f"<i>Target statement: {esc(statement_month)}</i>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Error appending expense row")
        await update.message.reply_text(
            "❌ Failed to add to Google Sheets. Check logs."
        )

    return ConversationHandler.END


# ==========================================
#       ADD INSTALLMENT CONVERSATION
# ==========================================


async def start_installment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🙏🏼 Let's add a new installment.\nWhat is the name of the item?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return INST_ITEM


async def inst_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["item"] = update.message.text
    await update.message.reply_text(
        "Which card did you use for this installment?",
        reply_markup=get_card_keyboard(),
    )
    return INST_CARD


async def inst_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["card"] = update.message.text
    await update.message.reply_text(
        "What is the start date? (DD/MM/YYYY, e.g. 01/05/2026 or type 'today')",
        reply_markup=ReplyKeyboardRemove(),
    )
    return INST_START_DATE


async def inst_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    if text == "today":
        date_obj = datetime.now(config.VN_TZ)
    else:
        try:
            date_obj = datetime.strptime(text, "%d/%m/%Y")
        except ValueError:
            await update.message.reply_text(
                "Invalid format. Please use DD/MM/YYYY or type 'today'."
            )
            return INST_START_DATE

    context.user_data["start_date"] = date_obj
    await update.message.reply_text(
        "What is the full price of the item? (e.g. 24997000)"
    )
    return INST_FULL_PRICE


async def inst_full_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        full_price = float(update.message.text.replace(",", ""))
        context.user_data["full_price"] = full_price
        await update.message.reply_text(
            "How many months is the installment period? (e.g. 12)"
        )
        return INST_PERIODS
    except ValueError:
        await update.message.reply_text(
            "Please enter a valid number for the full price."
        )
        return INST_FULL_PRICE


async def inst_periods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        periods = int(update.message.text)

        item = context.user_data["item"]
        card = context.user_data["card"]
        start_date = context.user_data["start_date"]
        full_price = context.user_data["full_price"]
        monthly = full_price / periods if periods > 0 else full_price

        row = [
            item,
            card,
            start_date.strftime("%d/%m/%Y"),
            full_price,
            periods,
        ]

        sh = get_sheet()
        ws = sh.worksheet("Installments")
        ws.append_row(row, value_input_option="USER_ENTERED")

        await update.message.reply_text(
            f"✅ <b>Installment added</b>\n\n"
            f"🛒 <b>{esc(item)}</b>\n"
            f"💳 {esc(card)}\n"
            f"💰 {bold_money(full_price)} · ⏱️ {periods} months\n"
            f"📅 Start: {start_date.strftime('%d/%m/%Y')}\n"
            f"≈ {bold_money(monthly)}/mo\n\n"
            f"<i>Reminder: open the sheet and drag the formulas in columns F–M down into the new row.</i>",
            parse_mode="HTML",
        )
    except ValueError:
        await update.message.reply_text("Please enter a valid integer for the periods.")
        return INST_PERIODS
    except Exception:
        logger.exception("Error appending installment row")
        await update.message.reply_text(
            "❌ Failed to add to Google Sheets. Check logs."
        )

    return ConversationHandler.END


# ==========================================
#           HANDLER FACTORIES
# ==========================================


def build_expense_handler(user_filter=None) -> ConversationHandler:
    from commands import cancel

    cmd_filter = user_filter if user_filter is not None else filters.ALL
    text = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[CommandHandler("expense", start_expense, filters=cmd_filter)],
        states={
            EXP_CARD: [MessageHandler(text, exp_card)],
            EXP_AMOUNT: [MessageHandler(text, exp_amount)],
            EXP_CATEGORY: [MessageHandler(text, exp_category)],
            EXP_DESC: [MessageHandler(text, exp_desc)],
        },
        fallbacks=[CommandHandler("cancel", cancel, filters=cmd_filter)],
    )


def build_installment_handler(user_filter=None) -> ConversationHandler:
    from commands import cancel

    cmd_filter = user_filter if user_filter is not None else filters.ALL
    text = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[
            CommandHandler("installment", start_installment, filters=cmd_filter)
        ],
        states={
            INST_ITEM: [MessageHandler(text, inst_item)],
            INST_CARD: [MessageHandler(text, inst_card)],
            INST_START_DATE: [MessageHandler(text, inst_start_date)],
            INST_FULL_PRICE: [MessageHandler(text, inst_full_price)],
            INST_PERIODS: [MessageHandler(text, inst_periods)],
        },
        fallbacks=[CommandHandler("cancel", cancel, filters=cmd_filter)],
    )
