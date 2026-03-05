from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from yandex import search_track
from utils import hash_id


async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Inline-режим: @bot <запрос> — быстрый поиск треков.
    Показывает до 10 треков, по выбору отправляет текст с ссылкой в бот.
    """
    query = update.inline_query
    if not query or query.query is None:
        return
    q = query.query.strip()
    if not q:
        # Пустой запрос — ничего не показываем, чтобы не спамить.
        await query.answer([], is_personal=True, cache_time=0)
        return

    tracks = search_track(q, limit=10) or []
    results = []
    for t in tracks:
        track_id = t.get("id") or t.get("track_id")
        if not track_id:
            continue
        title = t.get("title") or "Без названия"
        artist = t.get("artist") or "Неизвестен"
        text = f"{title} — {artist}"
        from urllib.parse import quote

        safe_id = str(track_id).replace(":", "_")
        bot_username = (context.bot.username or "").lstrip("@")
        if not bot_username:
            bot_link = "https://t.me/"
        else:
            bot_link = f"https://t.me/{bot_username}?start=track_{quote(safe_id, safe='')}"
        yandex_url = (t.get("track_url") or "").strip()
        if yandex_url:
            message_text = f"🎵 {text}\n\n▶ Слушать в Яндекс.Музыке: {yandex_url}\n\nОценить в игре: {bot_link}"
        else:
            message_text = f"🎵 {text}\n\nОценить в игре: {bot_link}"
        results.append(
            InlineQueryResultArticle(
                id=hash_id(track_id),
                title=text,
                description="Отправить трек на оценку",
                input_message_content=InputTextMessageContent(message_text),
            )
        )

    await query.answer(results, is_personal=True, cache_time=5)

