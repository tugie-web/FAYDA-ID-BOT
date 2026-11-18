from __future__ import annotations

import logging
import os

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import FreeAccessUser, is_admin_telegram_user

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "Open FAYDA ID BOT"),
        BotCommand("help", "Show help and available commands"),
        BotCommand("admin", "Open administrator controls"),
        BotCommand("freeusers", "List users with free access"),
        BotCommand("revokefree", "Remove a user's free access"),
    ])


def admin_only(update: Update) -> bool:
    user = update.effective_user
    return bool(user and is_admin_telegram_user(user.id))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mini_app_url = os.getenv("TELEGRAM_MINI_APP_URL", "").strip()
    keyboard = None
    if mini_app_url.startswith("https://"):
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open FAYDA ID", web_app=WebAppInfo(url=mini_app_url))]]
        )
        message = (
            "Welcome to FAYDA ID BOT.\n\n"
            "Tap the button below to open the Mini App and explore available services.\n"
            "Identity services remain unavailable until an authorized official integration is configured."
        )
    else:
        message = (
            "Welcome to FAYDA ID BOT.\n\n"
            "The Mini App is not configured yet. Please try again later.\n"
            "Identity services remain unavailable until an authorized official integration is configured."
        )
    if update.effective_message:
        await update.effective_message.reply_text(message, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "FAYDA ID BOT help\n\n"
            "/start — open the welcome screen and Mini App\n"
            "/help — show this help message\n"
            "/admin — administrator controls (admin only)\n\n"
            "For account or payment questions, use the support option in the Mini App."
        )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin_only(update):
        return
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("＋ Add free user", callback_data="free_access_add")
    ]])
    await update.effective_message.reply_text(
        "Administrator controls\n\nYour account always has free access. "
        "Use the button to whitelist another Telegram user.",
        reply_markup=keyboard,
    )


async def free_access_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if not is_admin_telegram_user(query.from_user.id):
        await query.answer("Administrator access required.", show_alert=True)
        return
    await query.answer()
    context.user_data["awaiting_free_user_id"] = True
    await query.message.reply_text(
        "Send the user's numeric Telegram ID. They will receive free access to all services."
    )


async def receive_free_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_free_user_id"):
        return
    if not admin_only(update):
        context.user_data.pop("awaiting_free_user_id", None)
        return
    raw_id = (update.effective_message.text or "").strip()
    if not raw_id.isdigit() or int(raw_id) <= 0:
        await update.effective_message.reply_text("That ID is not valid. Send a positive numeric Telegram ID.")
        return
    target_id = int(raw_id)
    if is_admin_telegram_user(target_id):
        context.user_data.pop("awaiting_free_user_id", None)
        await update.effective_message.reply_text("That account is already an administrator and always has free access.")
        return
    db = SessionLocal()
    try:
        existing = db.query(FreeAccessUser).filter_by(telegram_user_id=target_id).first()
        if existing:
            reply = f"User {target_id} already has free access."
        else:
            db.add(FreeAccessUser(telegram_user_id=target_id, granted_by=update.effective_user.id))
            db.commit()
            reply = f"Free access granted to Telegram user {target_id}."
    except IntegrityError:
        db.rollback()
        reply = "This user already has free access."
    finally:
        db.close()
        context.user_data.pop("awaiting_free_user_id", None)
    await update.effective_message.reply_text(reply)


async def freeusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin_only(update):
        return
    db = SessionLocal()
    try:
        ids = [str(row.telegram_user_id) for row in db.query(FreeAccessUser).order_by(FreeAccessUser.created_at).all()]
    finally:
        db.close()
    await update.effective_message.reply_text(
        "Whitelisted users:\n" + ("\n".join(ids) if ids else "No additional users yet.")
        + "\n\nAdministrator accounts are free automatically."
    )


async def revokefree_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not admin_only(update):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Usage: /revokefree TELEGRAM_ID")
        return
    target_id = int(context.args[0])
    db = SessionLocal()
    try:
        row = db.query(FreeAccessUser).filter_by(telegram_user_id=target_id).first()
        if row:
            db.delete(row)
            db.commit()
            reply = f"Free access removed from user {target_id}."
        else:
            reply = "That user is not on the free-access list."
    finally:
        db.close()
    await update.effective_message.reply_text(reply)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram bot.")
    application = Application.builder().token(token).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("freeusers", freeusers_command))
    application.add_handler(CommandHandler("revokefree", revokefree_command))
    application.add_handler(CallbackQueryHandler(free_access_button, pattern="^free_access_add$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_free_user_id))
    logger.info("Starting FAYDA ID Telegram bot using long polling.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
