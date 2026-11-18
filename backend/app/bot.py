from __future__ import annotations

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mini_app_url = os.getenv("TELEGRAM_MINI_APP_URL", "").strip()
    keyboard = None
    if mini_app_url.startswith("https://"):
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open FAYDA ID", web_app=WebAppInfo(url=mini_app_url))]]
        )

    message = (
        "Welcome to FAYDA ID BOT.\n\n"
        "Use the button below to open the Mini App and explore the available services.\n"
        "Identity services are not active until an authorized official integration is configured."
    )
    if update.effective_message:
        await update.effective_message.reply_text(message, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "Available commands:\n"
            "/start — open the FAYDA ID welcome screen\n"
            "/help — show this help message"
        )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram bot.")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    logger.info("Starting FAYDA ID Telegram bot using long polling.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
