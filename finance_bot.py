import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, CommandHandler, filters

import commands
import config
import conversations
import sheets

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):  # silence per-request logging
        pass


def start_health_server():
    """Bind to $PORT so Render's port scan marks the deploy as Live.

    A polling bot never opens an HTTP port on its own, which leaves a Render
    Web Service stuck on "Deploying". This lightweight server satisfies the
    port check and doubles as a health/keep-alive endpoint.
    """
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Health server listening on port {port}.")


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing. Check your .env file.")
        return

    if not config.ALLOWED_USER_ID:
        logger.error(
            "ALLOWED_USER_ID is missing. Set it in .env to restrict bot access."
        )
        return

    start_health_server()

    logger.info("Fetching initial settings from Google Sheets...")
    sheets.load_settings()

    user_filter = filters.User(user_id=config.ALLOWED_USER_ID)

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", commands.start, filters=user_filter))
    app.add_handler(CommandHandler("help", commands.help_command, filters=user_filter))
    app.add_handler(
        CommandHandler("refresh", commands.refresh_settings, filters=user_filter)
    )
    app.add_handler(CommandHandler("report", commands.get_report, filters=user_filter))
    app.add_handler(
        CommandHandler(
            "report_installments", commands.get_installments, filters=user_filter
        )
    )
    app.add_handler(
        CommandHandler("dashboard", commands.get_dashboard, filters=user_filter)
    )
    app.add_handler(
        CommandHandler("closing", commands.get_closing, filters=user_filter)
    )
    app.add_handler(CommandHandler("budget", commands.get_budget, filters=user_filter))
    app.add_handler(conversations.build_expense_handler(user_filter))
    app.add_handler(conversations.build_installment_handler(user_filter))

    logger.info(
        f"Bot is starting... Access restricted to user ID {config.ALLOWED_USER_ID}."
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
