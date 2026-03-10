# handlers/my_reviews_db_handler.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_last_reviews, get_user_progress, get_favorites, get_downloads
from keyboards import back_to_menu_button, back_to_list_button, reviews_list_buttons_paginated
from utils import user_states, hash_id, hash_to_track_id, level_progress_bar

REVIEWS_FETCH_LIMIT = 100
PAGE_SIZE = 10


def _page_from_callback(data: str) -> int:
    if data == "view_reviews":
        return 0
    if data.startswith("view_reviews_page_"):
        try:
            return max(0, int(data.split("_")[-1]))
        except ValueError:
            return 0
    return 0


async def view_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    progress = get_user_progress(user_id)
    fav_count = len(get_favorites(user_id))
    reviews = get_last_reviews(user_id, limit=REVIEWS_FETCH_LIMIT)

    if not reviews:
        from keyboards import main_menu
        await query.edit_message_text(
            f"📊 {level_progress_bar(progress['level'], progress['exp'])}\n"
            f"🎵 Мой плейлист: {fav_count}\n\n"
            "У тебя пока нет оценок. Самое время начать! 🎧",
            reply_markup=main_menu()
        )
        return

    page = _page_from_callback(query.data or "")
    total_pages = (len(reviews) + PAGE_SIZE - 1) // PAGE_SIZE
    if page >= total_pages:
        page = max(0, total_pages - 1)

    message = (
        f"📊 *Моя статистика*\n"
        f"{level_progress_bar(progress['level'], progress['exp'])}\n"
        f"🎵 Мой плейлист: {fav_count}\n\n"
        f"📌 Твои оценки — стр. {page + 1}/{total_pages}\n\n"
    )
    reply_markup = reviews_list_buttons_paginated(
        reviews, page=page, per_page=PAGE_SIZE, fav_count=fav_count
    )
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")


async def show_detail_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("detail_"):
        return

    track_hash = data.replace("detail_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Оценка не найдена.", show_alert=True)
        return

    real_track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    reviews = get_last_reviews(user_id, limit=100)
    review = next((r for r in reviews if r['track_id'] == real_track_id), None)

    if not review:
        await query.answer("❌ Оценка не найдена.", show_alert=True)
        return

    detail_text = (
        f"🎵 *{review['title']}*\n"
        f"👤 {review['artist']}\n\n"
        f"📊 *Подробная оценка: {review['total']}/50*\n\n"
        f"🔸 Рифмы/образы: {review['ratings']['rhymes']}\n"
        f"🔸 Структура/ритмика: {review['ratings']['rhythm']}\n"
        f"🔸 Реализация стиля: {review['ratings']['style']}\n"
        f"🔸 Харизма: {review['ratings']['charisma']}\n"
        f"🔸 Вайб: {review['ratings']['vibe']}"
    )

    reply_markup = back_to_list_button("view_reviews")
    await query.edit_message_text(detail_text, parse_mode='Markdown', reply_markup=reply_markup)


async def view_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мой плейлист (избранные треки); по нажатию — карточка трека."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    favs = get_favorites(user_id, limit=30)
    if not favs:
        await query.edit_message_text(
            "🎵 В плейлисте пока пусто. Добавляй треки кнопкой «В плейлист» на карточке.",
            reply_markup=back_to_menu_button(),
        )
        return
    tracks_for_buttons = [{"id": t["track_id"], "title": t["title"], "artist": t["artist"]} for t in favs]
    from keyboards import chart_list_buttons, back_to_menu_button
    text = f"🎵 *Мой плейлист* ({len(favs)})\n\nВыбери трек:"
    reply_markup = chart_list_buttons(tracks_for_buttons)
    # Клавиатура возвращает tuple; делаем список строк и заменяем последнюю на «Назад в меню»
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [list(row) for row in reply_markup.inline_keyboard]
    rows = rows[:-1] + [[InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(rows)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def view_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сначала копирует сохранённые сообщения с треками; если сообщение удалено — переотправляет через API."""
    import io
    from telegram import InputFile
    from yandex_music_service import download_track_bytes as yandex_download_track_bytes
    from soundcloud_service import download_track_bytes as soundcloud_download_track_bytes

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    downloads = get_downloads(user_id, limit=30)
    if not downloads:
        await query.edit_message_text(
            "📥 Здесь будут треки, которые ты скачал по кнопке «Скачать» на карточке.",
            reply_markup=back_to_menu_button(),
        )
        return
    await query.edit_message_text("📥 _Отправляю твои скачанные треки..._", parse_mode="Markdown")
    sent = 0
    sent_message_ids = []
    for d in downloads:
        copied = False
        if d.get("message_id") and d.get("chat_id"):
            try:
                result = await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=d["chat_id"],
                    message_id=d["message_id"],
                )
                new_id = result.message_id if hasattr(result, "message_id") else getattr(result, "message_id", None)
                if new_id:
                    sent_message_ids.append((chat_id, new_id))
                sent += 1
                copied = True
            except Exception:
                pass
        if not copied:
            try:
                tid = d.get("track_id") or ""
                if str(tid).startswith("sc_"):
                    audio_bytes, title, performer = soundcloud_download_track_bytes(tid)
                else:
                    audio_bytes, title, performer = yandex_download_track_bytes(tid)
                if not audio_bytes or len(audio_bytes) == 0:
                    continue
                if len(audio_bytes) > 50 * 1024 * 1024:
                    continue
                filename = f"{performer or 'Unknown'} - {title or 'Track'}.mp3"[:60].strip() or "track.mp3"
                bio = io.BytesIO(audio_bytes)
                bio.name = filename
                bio.seek(0)
                msg = await query.message.reply_audio(
                    audio=InputFile(bio, filename=filename),
                    title=(title or "")[:64] or None,
                    performer=(performer or "")[:64] or None,
                )
                sent_message_ids.append((msg.chat_id, msg.message_id))
                sent += 1
            except Exception:
                continue
    if sent_message_ids:
        prev = user_states.get(user_id, {})
        user_states[user_id] = {**prev, "messages_to_delete_on_back": sent_message_ids, "stage": "menu"}
    await query.edit_message_text(
        f"📥 Отправлено треков: {sent}.",
        reply_markup=back_to_menu_button(),
    )