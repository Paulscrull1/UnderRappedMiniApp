from urllib.parse import quote

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes

from music_providers import search_tracks
from utils import hash_id


def _listen_label(track):
    """Текст «Слушать в …» по источнику трека."""
    url = (track.get("track_url") or "").strip()
    if not url:
        return None
    source = track.get("source") or ""
    if source == "soundcloud":
        return f"▶ Слушать в SoundCloud: {url}"
    return f"▶ Слушать в Яндекс.Музыке: {url}"


async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Inline-режим: @bot <запрос> — быстрый поиск треков (Яндекс + SoundCloud).
    По выбору отправляет текст с ссылкой на трек и ссылкой в бот.
    """
    query = update.inline_query
    if not query or query.query is None:
        return
    q = query.query.strip()
    if not q:
        await query.answer([], is_personal=True, cache_time=0)
        return

    tracks = search_tracks(q, limit=10) or []
    results = []
    bot_username = (context.bot.username or "").lstrip("@")
    for t in tracks:
        track_id = t.get("id") or t.get("track_id")
        if not track_id:
            continue
        title = t.get("title") or "Без названия"
        artist = t.get("artist") or "Неизвестен"
        text = f"{title} — {artist}"
        safe_id = str(track_id).replace(":", "_")
        bot_link = f"https://t.me/{bot_username}?start=track_{quote(safe_id, safe='')}" if bot_username else "https://t.me/"
        listen_line = _listen_label(t)
        if listen_line:
            message_text = f"🎵 {text}\n\n{listen_line}\n\nОценить в игре: {bot_link}"
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

