# handlers/commands_handler.py
# Команды: /info, /chart, /daily, /stats, /search <запрос>
from urllib.parse import quote

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from yandex_music_service import get_chart_tracks, get_daily_track
from music_providers import search_tracks
from database import get_last_reviews, get_user_progress, get_favorites
from keyboards import chart_list_buttons_paginated, back_to_menu_button, main_menu
from utils import hash_id, hash_to_track_id, level_progress_bar
from handlers.track_card_handler import send_track_card


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /info — информация о боте и список команд."""
    text = (
        "🎧 *Музыкальный бот*\n\n"
        "Ищи треки, ставь оценки по 5 критериям, пиши рецензии, копи EXP и прокачивай уровень. "
        "Профиль с аватаркой, описанием и закреплённым треком. Лидерборд — самые активные пользователи.\n\n"
        "*Команды:*\n"
        "/start — главное меню\n"
        "/info — эта справка\n"
        "/chart — чарт Яндекс.Музыки\n"
        "/daily — трек дня\n"
        "/stats — моя статистика\n"
        "/search _запрос_ — быстрый поиск трека\n\n"
        "Всё остальное — через кнопки в меню."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /chart — открыть чарт (первая страница с пагинацией)."""
    from database import get_user_reviewed_track_ids
    from handlers.chart_handler import CHART_FETCH_LIMIT, PAGE_SIZE
    tracks = get_chart_tracks(chart_id="world", limit=CHART_FETCH_LIMIT)
    if not tracks:
        await update.message.reply_text(
            "❌ Не удалось загрузить чарт. Попробуй позже.",
            reply_markup=back_to_menu_button(),
        )
        return
    total_pages = (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE
    uid = update.effective_user.id
    reviewed_set = set(get_user_reviewed_track_ids(uid))
    text = f"📊 *Чарт Яндекс.Музыки* — стр. 1/{total_pages}\n\nВыбери трек:\n_✓ — вы уже оценивали_"
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=chart_list_buttons_paginated(
            tracks, page=0, per_page=PAGE_SIZE, reviewed_ids=reviewed_set
        ),
    )


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /daily — трек дня."""
    track = get_daily_track()
    if not track:
        await update.message.reply_text(
            "❌ Не удалось загрузить трек дня.",
            reply_markup=back_to_menu_button(),
        )
        return
    user_id = update.message.from_user.id
    await send_track_card(update.message, track["id"], user_id, track_dict=track)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — моя статистика (оценки, уровень, плейлист)."""
    user_id = update.message.from_user.id
    progress = get_user_progress(user_id)
    fav_count = len(get_favorites(user_id))
    reviews = get_last_reviews(user_id, limit=10)

    if not reviews:
        await update.message.reply_text(
            f"📊 {level_progress_bar(progress['level'], progress['exp'])}\n"
            f"🎵 Мой плейлист: {fav_count}\n\n"
            "У тебя пока нет оценок. Самое время начать! 🎧",
            reply_markup=main_menu(),
        )
        return

    message = (
        f"📊 *Моя статистика*\n"
        f"{level_progress_bar(progress['level'], progress['exp'])}\n"
        f"🎵 Мой плейлист: {fav_count}\n\n"
        "📌 Твои последние 10 оценок:\n\n"
    )
    buttons = [[InlineKeyboardButton(f"🎵 Мой плейлист ({fav_count})", callback_data="view_favorites")]]
    for r in reviews:
        safe_hash = hash_id(r["track_id"])
        hash_to_track_id[safe_hash] = r["track_id"]
        btn_text = f"{r['title']} — {r['artist']} | {r['total']}/50"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"detail_{safe_hash}")])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /search <запрос> — быстрый поиск трека."""
    query_text = (context.args or [])
    if not query_text:
        await update.message.reply_text(
            "🔍 Использование: /search _Исполнитель — Название_\n\nПример: /search Платина — Бассок",
            parse_mode="Markdown",
        )
        return
    query = " ".join(query_text).strip()
    await update.message.reply_text("🔍 Ищу трек...")
    tracks = search_tracks(query, limit=3)
    if not tracks:
        await update.message.reply_text(
            "❌ Не нашёл такой трек. Попробуй: /search Исполнитель — Название"
        )
        return
    user_id = update.message.from_user.id
    await send_track_card(update.message, tracks[0]["id"], user_id, track_dict=tracks[0])


async def invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает персональную реферальную ссылку для приглашения друзей.
    """
    user = update.effective_user
    if not user:
        return
    user_id = user.id
    bot_username = (context.bot.username or "").lstrip("@")
    if not bot_username:
        await update.effective_message.reply_text(
            "Реферальная ссылка пока недоступна. Бот не знает своё имя."
        )
        return
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = (
        "Присоединяйся к музыкальной игре! Перейди по ссылке и зарегистрируйся — "
        "бонусы EXP за приглашение и за оценки треков 🎵"
    )
    # t.me/share/url — нативное меню «Отправить» в чат, а не открытие бота с /start
    share_menu_url = (
        "https://t.me/share/url?"
        f"url={quote(ref_link, safe='')}&text={quote(share_text, safe='')}"
    )
    text = (
        "👥 *Пригласи друзей в игру!*\n\n"
        "Друг переходит по ссылке и регистрируется — *+100 EXP* тебе.\n"
        "Когда друг поставит *первую оценку* треку — *ещё +200 EXP* тебе и *+500 EXP* ему.\n\n"
        f"`{ref_link}`"
    )
    buttons = [[InlineKeyboardButton("📤 Отправить ссылку", url=share_menu_url)]]
    await update.effective_message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )
