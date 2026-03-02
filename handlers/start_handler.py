# handlers/start_handler.py
import config
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from keyboards import main_menu
from database import get_user_nickname, save_user_nickname, get_user_progress, set_referrer_if_empty
from utils import user_states, level_progress_bar, EXP_FOR_REFERRAL
from database import add_exp


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главное меню: Трек дня, Чарт, Найти трек, Моя статистика, Общая статистика, Топ треков.
    Если start=track_XXX — приглашение открыть трек в Mini App.
    Если start=ref_XXX — реферальная ссылка.
    """
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    user_id = user.id
    nickname = get_user_nickname(user_id)

    text = (update.message.text or "").strip()
    args = text.split(maxsplit=1)
    start_param = args[1] if len(args) > 1 else ""
    pending_track_param = start_param if start_param.startswith("track_") else ""
    pending_ref_param = start_param if start_param.startswith("ref_") else ""

    # Новый пользователь: сначала регистрация (ник), но запоминаем, по какой ссылке он пришёл
    if not nickname:
        await update.message.reply_text(
            "👋 Привет! Как тебя зовут?\n"
            "Это имя будет отображаться при оценке треков."
        )
        state = {"stage": "awaiting_nickname"}
        if pending_track_param:
            state["pending_track"] = pending_track_param
        if pending_ref_param:
            state["pending_ref"] = pending_ref_param
        user_states[user_id] = state
        return

    # Зарегистрированный пользователь
    user_states[user_id] = {"stage": "menu", "nickname": nickname}

    # Реферальная ссылка для уже зарегистрированного пользователя:
    # не меняем referrer и не начисляем бонус, просто игнорируем.

    # Если есть deep-link с треком — сразу даём кнопку «Открыть и оценить»
    if pending_track_param and config.MINI_APP_URL:
        from urllib.parse import quote

        track_encoded = pending_track_param[6:].strip()
        track_id = track_encoded.replace("_", ":", 1) if "_" in track_encoded else track_encoded
        url = f"{config.MINI_APP_URL.rstrip('/')}?track={quote(track_id, safe='')}"
        await update.message.reply_text(
            "🎵 Тебе прислали трек!\n\nОткрой игру и оцени его:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🎮 Открыть и оценить", web_app=WebAppInfo(url=url))]]
            ),
        )
        return
    progress = get_user_progress(user_id)
    lvl, exp = progress["level"], progress["exp"]
    bar = level_progress_bar(lvl, exp)

    await update.message.reply_text(
        f"🎧 *С возвращением, {nickname}!*\n\n"
        f"📊 {bar}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Выбери действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


async def handle_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод никнейма
    """
    if not update.message or not update.message.from_user:
        return

    user_id = update.message.from_user.id
    prev_state = user_states.get(user_id, {}) or {}
    text = update.message.text.strip()

    if not text or len(text) > 30:
        await update.message.reply_text("Никнейм должен быть от 1 до 30 символов. Попробуй ещё раз:")
        return

    save_user_nickname(user_id, text)
    user_states[user_id] = {"stage": "menu", "nickname": text}

    await update.message.reply_text(
        f"🎤 *Отлично, {text}!*\n\n"
        "Теперь можно искать треки, ставить оценки и копить EXP.\n"
        f"━━━━━━━━━━━━━━━━\n"
        "Выбери действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    # Реферальная ссылка: если пользователь пришёл по ref_XXX,
    # пробуем установить реферера и начислить ему бонус EXP один раз.
    pending_ref = prev_state.get("pending_ref")
    if pending_ref and pending_ref.startswith("ref_"):
        try:
            ref_id = int(pending_ref[4:])
        except ValueError:
            ref_id = None
        if ref_id:
            if set_referrer_if_empty(user_id, ref_id):
                add_exp(ref_id, EXP_FOR_REFERRAL)

    # Если пользователь пришёл по ссылке вида /start track_XXX,
    # после регистрации покажем ему кнопку открытия трека в Mini App.
    pending_track = prev_state.get("pending_track")
    if pending_track and pending_track.startswith("track_") and config.MINI_APP_URL:
        from urllib.parse import quote

        track_encoded = pending_track[6:].strip()
        track_id = track_encoded.replace("_", ":", 1) if "_" in track_encoded else track_encoded
        url = f"{config.MINI_APP_URL.rstrip('/')}?track={quote(track_id, safe='')}"
        await update.message.reply_text(
            "🎵 Тебе прислали трек!\n\nОткрой игру и оцени его:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🎮 Открыть и оценить", web_app=WebAppInfo(url=url))]]
            ),
        )


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Кнопка 'Назад' — возвращает в главное меню.
    Если были показаны «Мои скачанные», удаляем пересланные аудио из чата.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id, {})
    to_delete = state.get("messages_to_delete_on_back") or []
    for cid, mid in to_delete:
        try:
            await context.bot.delete_message(chat_id=cid, message_id=mid)
        except Exception:
            pass
    nickname = get_user_nickname(user_id) or state.get("nickname") or "Пользователь"
    user_states[user_id] = {"stage": "menu", "nickname": nickname}
    progress = get_user_progress(user_id)
    lvl, exp = progress["level"], progress["exp"]
    bar = level_progress_bar(lvl, exp)
    text = (
        f"🎵 *Главное меню*\n\n"
        f"Привет, {nickname}!\n\n"
        f"📊 {bar}\n"
        f"━━━━━━━━━━━━━━━━\n"
        "Выбери действие:"
    )
    try:
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")
    except Exception:
        try:
            await query.delete_message()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )