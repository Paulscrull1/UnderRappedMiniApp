# handlers/chart_explore_handler.py — подряд случайные треки из топ-100 чарта (как в Mini App)
import logging
import random

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TelegramError, TimedOut

from database import get_user_reviewed_track_ids, is_in_favorites
from handlers.track_card_handler import build_card_caption, _get_track_dict
from keyboards import main_menu, track_card_buttons_with_explore
from utils import user_states
from yandex_music_service import get_chart_tracks


async def chart_explore_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню → «Топ-100 на оценку»: перемешанная очередь без уже оценённых."""
    q = update.callback_query
    if not q:
        return
    await q.answer()
    user_id = q.from_user.id
    try:
        raw = get_chart_tracks(chart_id="world", limit=100)
    except Exception as e:
        logging.exception("get_chart_tracks failed: %s", e)
        await q.edit_message_text(
            "❌ Не удалось загрузить чарт Яндекса.\n"
            "Проверьте токен API и сеть. Попробуйте позже или откройте Mini App.",
            reply_markup=main_menu(),
        )
        return
    if not raw:
        await q.edit_message_text(
            "❌ Чарт временно пуст или недоступен. Попробуйте позже.",
            reply_markup=main_menu(),
        )
        return
    reviewed = set(get_user_reviewed_track_ids(user_id))
    pool_ids = [str(t["id"]) for t in raw if t.get("id") and str(t["id"]) not in reviewed]
    random.shuffle(pool_ids)
    if not pool_ids:
        await q.edit_message_text(
            "🎲 В чарте не осталось треков без вашей оценки.\n"
            "Оцените треки в других разделах или попробуйте позже.",
            reply_markup=main_menu(),
        )
        return
    base = user_states.setdefault(user_id, {})
    base["explore"] = {"track_ids": pool_ids, "index": 0}
    user_states[user_id] = base
    n = len(pool_ids)
    await q.edit_message_text(
        "🎲 *Топ-100 на оценку*\n\n"
        f"В очереди *{n}* треков (уже оценённые из чарта не попадают).\n"
        "Оценивайте по критериям или нажимайте «Дальше» — следующий трек придёт отдельным сообщением.\n"
        "Прогресс показан в подписи к каждой карточке.",
        parse_mode="Markdown",
    )
    await chart_explore_send_current(update, context, skip_failures=0)


async def chart_explore_send_current(update: Update, context: ContextTypes.DEFAULT_TYPE, skip_failures: int = 0):
    """Отправляет текущий трек подборки (по explore.index)."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    st = user_states.get(user_id) or {}
    exp = st.get("explore")
    if not exp:
        return
    ids = exp["track_ids"]
    i = exp["index"]
    if i >= len(ids):
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 Подборка завершена: вы прошли все треки в этой очереди.\n"
            "Можно начать новую из меню — «Топ-100 на оценку».",
            reply_markup=main_menu(),
        )
        st.pop("explore", None)
        return
    if skip_failures > 120:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Слишком много треков подряд не удалось показать (сеть или сервис музыки).\n"
            "Попробуйте позже или откройте Mini App.",
            reply_markup=main_menu(),
        )
        st.pop("explore", None)
        return
    tid = ids[i]
    track = _get_track_dict(tid)
    if not track:
        exp["index"] = i + 1
        await chart_explore_send_current(update, context, skip_failures + 1)
        return
    caption = build_card_caption(track, user_id)
    caption = f"{caption}\n📍 *{i + 1}/{len(ids)}* в подборке"
    url = track.get("track_url") or ""
    in_fav = is_in_favorites(user_id, track["id"])
    markup = track_card_buttons_with_explore(track["id"], url, in_fav, track.get("source") or "")
    photo = track.get("cover_url")
    try:
        if photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=markup,
                parse_mode="Markdown",
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=markup,
                parse_mode="Markdown",
            )
    except (TimedOut, BadRequest, TelegramError) as e:
        logging.warning("chart_explore send media failed (%s), fallback to text", e)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=markup,
                parse_mode="Markdown",
            )
        except (TimedOut, BadRequest, TelegramError) as e2:
            logging.warning("chart_explore text send failed: %s", e2)
            exp["index"] = i + 1
            await chart_explore_send_current(update, context, skip_failures + 1)


async def chart_explore_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустить текущий трек в подборке."""
    q = update.callback_query
    uid = q.from_user.id
    st = user_states.setdefault(uid, {})
    exp = st.get("explore")
    if not exp:
        await q.answer("Сначала откройте: меню → Топ-100 на оценку.", show_alert=True)
        return
    await q.answer()
    exp["index"] = exp.get("index", 0) + 1
    await chart_explore_send_current(update, context, 0)


async def chart_explore_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из режима подборки."""
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = user_states.get(uid)
    if st:
        st.pop("explore", None)
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text="🛑 Подборка остановлена. Прогресс очереди сброшен — при следующем запуске будет новая перемешанная выборка.",
        reply_markup=main_menu(),
    )
