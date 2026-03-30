# handlers/premium_handler.py — Premium за Telegram Stars (XTR)
from datetime import datetime, timezone

from telegram import LabeledPrice, Update
from telegram.ext import ContextTypes

import config
from database import get_premium_status, get_user_nickname, try_record_premium_payment_and_extend
from keyboards import main_menu


def _premium_status_text(user_id: int) -> str:
    st = get_premium_status(user_id)
    lines = [
        "⭐ *UnderRapped Premium*\n",
        "• Значок премиум в Mini App",
        "• Ранний доступ к новым функциям",
        "• Прямая поддержка развития бота\n",
        f"Стоимость: *{config.PREMIUM_STAR_PRICE}* ⭐ за *{config.PREMIUM_DURATION_DAYS}* дн.",
    ]
    if st["active"] and st["until"]:
        try:
            s = str(st["until"]).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            human = dt.strftime("%d.%m.%Y %H:%M UTC")
        except Exception:
            human = str(st["until"])
        lines.append(f"\n✅ У тебя уже активна подписка до: `{human}`")
    return "\n".join(lines)


async def send_premium_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет инвойс Stars в текущий чат.
    Не передаём reply_markup: для invoice пустая разметка = одна кнопка «Оплатить» от Telegram.
    Своя клавиатура без pay-кнопки первой строкой даёт BadRequest: Reply_markup_buy_empty.
    """
    chat = update.effective_chat
    if not chat:
        return
    prices = [LabeledPrice(config.PREMIUM_PRODUCT_LABEL, config.PREMIUM_STAR_PRICE)]
    await context.bot.send_invoice(
        chat_id=chat.id,
        title=config.PREMIUM_PRODUCT_TITLE,
        description=config.PREMIUM_PRODUCT_DESCRIPTION,
        payload=config.PREMIUM_INVOICE_PAYLOAD,
        currency="XTR",
        prices=prices,
        provider_token="",
    )


async def show_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        text = _premium_status_text(user_id)
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"Оформить за {config.PREMIUM_STAR_PRICE} ⭐", callback_data="premium_buy")],
                [InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")],
            ]
        )
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=kb, parse_mode="Markdown")


async def premium_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user_id = query.from_user.id
    if not get_user_nickname(user_id):
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Сначала задайте никнейм: команда /start",
        )
        return
    await send_premium_invoice(update, context)


async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.pre_checkout_query
    if not q:
        return
    if q.invoice_payload != config.PREMIUM_INVOICE_PAYLOAD:
        await q.answer(ok=False, error_message="Неизвестный товар.")
        return
    if (q.currency or "").upper() != "XTR" or q.total_amount != config.PREMIUM_STAR_PRICE:
        await q.answer(ok=False, error_message="Неверная сумма.")
        return
    await q.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.successful_payment or not msg.from_user:
        return
    sp = msg.successful_payment
    user_id = msg.from_user.id
    is_new, until_iso = try_record_premium_payment_and_extend(
        user_id,
        sp.telegram_payment_charge_id,
        sp.invoice_payload,
        sp.total_amount,
        expected_payload=config.PREMIUM_INVOICE_PAYLOAD,
        expected_amount=config.PREMIUM_STAR_PRICE,
        duration_days=config.PREMIUM_DURATION_DAYS,
    )
    if until_iso is None:
        await msg.reply_text("Не удалось подтвердить платёж. Напишите администратору бота.")
        return
    try:
        s = until_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        human = dt.strftime("%d.%m.%Y %H:%M UTC")
    except Exception:
        human = until_iso
    if is_new:
        await msg.reply_text(
            f"✅ *Premium активирован* до `{human}`\n\nСпасибо за поддержку 💜",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    else:
        await msg.reply_text(
            f"Платёж уже был учтён ранее. Подписка действует до `{human}`.",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )


async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return
    user_id = update.message.from_user.id
    if not get_user_nickname(user_id):
        await update.message.reply_text("Сначала нажми /start и представься.")
        return
    text = _premium_status_text(user_id)
    await update.message.reply_text(text, parse_mode="Markdown")
    await send_premium_invoice(update, context)
