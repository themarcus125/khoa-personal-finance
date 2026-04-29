import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, filters

import config
import sheets
import commands
import conversations

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing. Check your .env file.")
        return

    if not config.ALLOWED_USER_ID:
        logger.error("ALLOWED_USER_ID is missing. Set it in .env to restrict bot access.")
        return

    logger.info("Fetching initial settings from Google Sheets...")
    sheets.load_settings()

    user_filter = filters.User(user_id=config.ALLOWED_USER_ID)

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', commands.start, filters=user_filter))
    app.add_handler(CommandHandler('refresh', commands.refresh_settings, filters=user_filter))
    app.add_handler(CommandHandler('report', commands.get_report, filters=user_filter))
    app.add_handler(CommandHandler('report_installments', commands.get_installments, filters=user_filter))
    app.add_handler(CommandHandler('dashboard', commands.get_dashboard, filters=user_filter))
    app.add_handler(CommandHandler('closing', commands.get_closing, filters=user_filter))
    app.add_handler(CommandHandler('budget', commands.get_budget, filters=user_filter))
    app.add_handler(conversations.build_expense_handler(user_filter))
    app.add_handler(conversations.build_installment_handler(user_filter))

    logger.info(f"Bot is starting... Access restricted to user ID {config.ALLOWED_USER_ID}.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
