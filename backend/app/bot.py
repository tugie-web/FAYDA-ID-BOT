from __future__ import annotations

import asyncio
import logging
import os
import time
from io import BytesIO

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters,
)
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import FreeAccessUser, has_free_access, is_admin_telegram_user
from app.services.esignet import EsignetClient, EsignetError
from app.services.identity_documents import render_identity_pdf, render_printable_summary_png

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
    buttons = [[InlineKeyboardButton("▶ Start", callback_data="begin_fayda_flow")]]
    if mini_app_url.startswith("https://"):
        buttons.append([
            InlineKeyboardButton("Open FAYDA ID Mini App", web_app=WebAppInfo(url=mini_app_url))
        ])
    keyboard = InlineKeyboardMarkup(buttons)
    message = (
        "Welcome to FAYDA ID BOT.\n\n"
        "Tap Start to begin. The next step will be FAN entry, followed by the OTP process.\n"
        "Only enter your FAN after tapping Start. Your FAN and OTP are sensitive; the bot will try to delete your messages after receiving them."
    )
    if update.effective_message:
        await update.effective_message.reply_text(message, reply_markup=keyboard)


async def begin_fayda_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    context.user_data.pop("identity_summary_data", None)
    context.user_data["identity_flow_stage"] = "awaiting_fan"
    await query.message.reply_text(
        "Please enter your FAN (Fayda Identification Number).\n\n"
        "Your FAN is used only to start the secure Fayda verification process."
    )


def otp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↻ Resend OTP", callback_data="resend_fayda_otp")
    ]])


async def resend_fayda_otp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    user_id = query.from_user.id
    if context.user_data.get("identity_flow_stage") != "awaiting_otp":
        await query.answer("Start a new Fayda request first.", show_alert=True)
        return

    if time.monotonic() > float(context.user_data.get("identity_session_expires_at", 0)):
        stale = context.application.bot_data.setdefault("esignet_clients", {}).pop(user_id, None)
        if stale:
            stale.close()
        context.user_data.pop("identity_flow_stage", None)
        await query.answer("Your Fayda session expired. Please start again.", show_alert=True)
        return

    clients = context.application.bot_data.setdefault("esignet_clients", {})
    client = clients.get(user_id)
    if client is None:
        context.user_data.pop("identity_flow_stage", None)
        await query.answer("Your Fayda session expired. Please start again.", show_alert=True)
        return

    now = time.monotonic()
    next_allowed = float(context.user_data.get("otp_resend_after", 0))
    if now < next_allowed:
        wait_seconds = max(1, int(next_allowed - now + 0.999))
        await query.answer(f"Please wait {wait_seconds} seconds before resending.", show_alert=True)
        return

    resend_count = int(context.user_data.get("otp_resend_count", 0))
    if resend_count >= 3:
        await query.answer("You have reached the resend limit. Please start again later.", show_alert=True)
        return

    await query.answer("Requesting a new OTP…")
    try:
        result = await asyncio.to_thread(client.send_otp)
        context.user_data["otp_resend_count"] = resend_count + 1
        context.user_data["otp_resend_after"] = time.monotonic() + 60
        destination = result.get("maskedMobile") or result.get("maskedEmail")
        suffix = f"\nOTP destination: {destination}" if destination else ""
        await query.message.reply_text(
            "A new OTP request was sent by Fayda. Use the latest OTP; an earlier code may no longer work."
            + suffix,
            reply_markup=otp_keyboard(),
        )
    except EsignetError as exc:
        await query.message.reply_text(
            f"Fayda could not resend the OTP. Please try again later. Reference: {exc.code}",
            reply_markup=otp_keyboard(),
        )
    except Exception:
        logger.warning("Fayda OTP resend failed; sensitive request details are omitted.")
        await query.message.reply_text(
            "We could not resend the OTP right now. Please try again later.",
            reply_markup=otp_keyboard(),
        )


def user_has_free_access(telegram_user_id: int) -> bool:
    if is_admin_telegram_user(telegram_user_id):
        return True
    db = SessionLocal()
    try:
        return has_free_access(db, telegram_user_id)
    except Exception:
        logger.warning("Could not check free-access status; access is denied.")
        return False
    finally:
        db.close()


async def delete_sensitive_message(message) -> None:
    try:
        await message.delete()
    except Exception:
        # Telegram may reject deletion due to chat or message permissions.
        pass


def identity_output_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("PDF summary", callback_data="identity_pdf")],
        [InlineKeyboardButton("Printable summary", callback_data="identity_print")],
        [InlineKeyboardButton("Both files", callback_data="identity_both")],
    ])


async def deliver_identity_output(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    identity = context.user_data.get("identity_summary_data")
    if not isinstance(identity, dict):
        await query.message.reply_text("Your document session expired. Please tap Start and verify again.")
        return
    if not user_has_free_access(query.from_user.id):
        context.user_data.pop("identity_summary_data", None)
        await query.message.reply_text(
            "Document delivery requires wallet payment. Wallet charging is not enabled yet, "
            "so no paid file has been delivered and no charge has been taken."
        )
        return

    choice = query.data
    try:
        if choice in ("identity_pdf", "identity_both"):
            pdf_bytes = await asyncio.to_thread(render_identity_pdf, identity)
            await query.message.reply_document(
                document=InputFile(BytesIO(pdf_bytes), filename="identity-information-summary.pdf"),
                caption="Personal identity information summary. This is not an official identity document.",
            )
        if choice in ("identity_print", "identity_both"):
            png_bytes = await asyncio.to_thread(render_printable_summary_png, identity)
            await query.message.reply_document(
                document=InputFile(BytesIO(png_bytes), filename="printable-identity-summary.png"),
                caption="Printable personal information panel. This is not an official identity card.",
            )
        context.user_data.pop("identity_summary_data", None)
        context.user_data.pop("identity_flow_stage", None)
        await query.message.reply_text("Your requested summary file(s) have been delivered.")
    except Exception:
        logger.warning("Identity summary generation or delivery failed; personal data omitted.")
        await query.message.reply_text("We could not create or deliver the summary. No payment was taken.")


async def receive_fan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    fan = (message.text or "").strip()
    if not fan or len(fan) > 64:
        await message.reply_text("Please enter a valid FAN.")
        return

    client = EsignetClient()
    try:
        await delete_sensitive_message(message)
        client.check_configuration()
        await message.reply_text("Connecting securely to Fayda and requesting your OTP. Please wait…")
        await asyncio.to_thread(client.initialize, fan)
        await asyncio.to_thread(client.get_oauth_details)
        masked = await asyncio.to_thread(client.send_otp)
        clients = context.application.bot_data.setdefault("esignet_clients", {})
        previous = clients.pop(user.id, None)
        if previous:
            previous.close()
        clients[user.id] = client
        context.user_data["identity_flow_stage"] = "awaiting_otp"
        context.user_data["otp_resend_count"] = 0
        context.user_data["otp_resend_after"] = time.monotonic() + 60
        context.user_data["identity_session_expires_at"] = time.monotonic() + 600
        destination = masked.get("maskedMobile") or masked.get("maskedEmail")
        suffix = f"\nOTP destination: {destination}" if destination else ""
        await message.reply_text(
            "OTP request successful. Please enter the OTP sent by Fayda." + suffix
            + "\nIf it does not arrive, you can request another one after 60 seconds.",
            reply_markup=otp_keyboard(),
        )
    except EsignetError as exc:
        client.close()
        context.user_data.pop("identity_flow_stage", None)
        await message.reply_text(
            "Fayda could not start the OTP process. Please check the FAN and try again. "
            f"Reference: {exc.code}"
        )
    except Exception:
        client.close()
        context.user_data.pop("identity_flow_stage", None)
        logger.warning("Fayda OTP request failed; sensitive request details are omitted.")
        await message.reply_text(
            "We could not contact Fayda right now. Please try again later. No payment was taken."
        )


async def receive_otp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return
    otp = (message.text or "").strip()
    await delete_sensitive_message(message)
    if time.monotonic() > float(context.user_data.get("identity_session_expires_at", 0)):
        stale = context.application.bot_data.setdefault("esignet_clients", {}).pop(user.id, None)
        if stale:
            stale.close()
        context.user_data.pop("identity_flow_stage", None)
        await message.reply_text("Your Fayda session expired. Please tap Start and begin again.")
        return
    clients = context.application.bot_data.setdefault("esignet_clients", {})
    client = clients.get(user.id)
    if client is None:
        context.user_data.pop("identity_flow_stage", None)
        await message.reply_text("Your Fayda session expired. Please tap Start and enter your FAN again.")
        return
    otp_verified = False
    try:
        await message.reply_text("Verifying your OTP with Fayda. Please wait…")
        await asyncio.to_thread(client.verify_otp, otp)
        otp_verified = True
        context.user_data["identity_flow_stage"] = "retrieving_identity"
        await message.reply_text("OTP verified. Retrieving your identity information securely…")
        auth_code = await asyncio.to_thread(client.get_auth_code)
        await asyncio.to_thread(client.exchange_auth_code, auth_code)
        raw_identity = await asyncio.to_thread(client.get_identity)
        identity = await asyncio.to_thread(client.parse_identity, raw_identity, client.fan)

        # Keep only the fields needed for the requested summary; never retain photo or tokens.
        summary = {
            key: identity.get(key)
            for key in ("fullName", "dateOfBirth", "gender", "phone", "uin",
                        "region", "zone", "woreda", "residenceStatus", "email")
        }
        clients.pop(user.id, None)
        client.close()
        context.user_data.pop("identity_flow_stage", None)
        context.user_data.pop("identity_session_expires_at", None)

        if not user_has_free_access(user.id):
            await message.reply_text(
                "Your identity information was retrieved successfully. Document delivery is a paid service, "
                "but wallet charging is not enabled yet. No file was delivered and no payment was taken."
            )
            return

        context.user_data["identity_summary_data"] = summary
        await message.reply_text(
            "Identity information retrieved. Choose which summary file you want. "
            "These are personal-information summaries, not official Fayda identity documents.",
            reply_markup=identity_output_keyboard(),
        )
    except EsignetError as exc:
        if otp_verified:
            clients.pop(user.id, None)
            client.close()
            context.user_data.pop("identity_flow_stage", None)
            context.user_data.pop("identity_session_expires_at", None)
            await message.reply_text(
                "OTP was accepted, but Fayda could not return the identity information. "
                "Please tap Start and try again. Reference: " + exc.code
            )
        else:
            await message.reply_text(
                "Fayda did not accept that OTP. Please check it and try again, or request a new OTP. "
                f"Reference: {exc.code}",
                reply_markup=otp_keyboard(),
            )
    except Exception:
        if otp_verified:
            clients.pop(user.id, None)
            client.close()
            context.user_data.pop("identity_flow_stage", None)
            context.user_data.pop("identity_session_expires_at", None)
        logger.warning("Fayda identity retrieval failed; sensitive request details are omitted.")
        await message.reply_text("We could not complete the Fayda request. Please try again later.")


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stage = context.user_data.get("identity_flow_stage")
    if stage == "awaiting_fan":
        await receive_fan(update, context)
        return
    if stage == "awaiting_otp":
        await receive_otp(update, context)
        return
    await receive_free_user_id(update, context)


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
    application.add_handler(CallbackQueryHandler(begin_fayda_flow, pattern="^begin_fayda_flow$"))
    application.add_handler(CallbackQueryHandler(resend_fayda_otp, pattern="^resend_fayda_otp$"))
    application.add_handler(CallbackQueryHandler(deliver_identity_output, pattern="^identity_(pdf|print|both)$"))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("freeusers", freeusers_command))
    application.add_handler(CommandHandler("revokefree", revokefree_command))
    application.add_handler(CallbackQueryHandler(free_access_button, pattern="^free_access_add$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))
    logger.info("Starting FAYDA ID Telegram bot using long polling.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
