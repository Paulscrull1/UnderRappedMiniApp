# handlers/track_card_handler.py
"""Единая карточка трека и обработчики кнопок: Оценить, Рецензия, Скачать, Плейлист."""
import asyncio
import io
import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from telegram.error import TimedOut, BadRequest
from yandex_music_service import download_track_bytes as yandex_download_track_bytes
from soundcloud_service import download_track_bytes as soundcloud_download_track_bytes
from music_providers import get_track_by_id
import config
from database import (
    is_in_favorites,
    add_favorite,
    remove_favorite,
    add_exp,
    add_download,
    get_track_rating_stats,
    mark_daily_favorite_task,
    user_has_reviewed,
)
from keyboards import track_card_buttons, rating_buttons
from utils import user_states, hash_to_track_id, CRITERIA_NAMES, EXP_FOR_FAVORITE
from database import get_user_nickname


def _get_track_dict(track_id, track_dict=None):
    """Возвращает словарь трека: либо переданный, либо загрузка по id."""
    if track_dict and isinstance(track_dict, dict) and track_dict.get("id"):
        return track_dict
    return get_track_by_id(track_id)


def build_card_caption(track, user_id: int = None):
    """Текст карточки: название, исполнитель, жанр; средний балл; пометка «уже оценили вы»."""
    title = track.get("title", "Без названия")
    artist = track.get("artist", "Неизвестен")
    genre = track.get("genre", "—")
    lines = [f"🎧 *{title}*", f"👤 {artist}", f"🏷 {genre}"]
    track_id = track.get("id")
    if track_id and user_id is not None and user_has_reviewed(user_id, track_id):
        lines.append("✅ *Вы уже оценивали этот трек*")
    if track_id:
        stats = get_track_rating_stats(track_id)
        if stats:
            lines.append(f"📊 Средний балл: {stats['avg']}/50, оценок: {stats['count']}")
    lines.append("━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def send_track_card(message_or_query, track_id, user_id, track_dict=None, parse_mode="Markdown"):
    """
    Отправляет карточку трека (фото + подпись + кнопки).
    message_or_query — объект message (для reply_photo) или callback_query (для answer + reply_photo от имени message).
    """
    track = _get_track_dict(track_id, track_dict)
    if not track:
        if hasattr(message_or_query, "reply_text"):
            await message_or_query.reply_text("❌ Не удалось загрузить трек.")
        return None
    caption = build_card_caption(track, user_id)
    url = track.get("track_url") or ""
    if not url and track.get("source") != "soundcloud":
        url = f"https://music.yandex.ru/search?text={track.get('artist', '')}+{track.get('title', '')}"
    in_fav = is_in_favorites(user_id, track["id"])
    markup = track_card_buttons(track["id"], url, in_fav, track.get("source") or "")
    photo = track.get("cover_url") or None
    msg = getattr(message_or_query, "message", message_or_query)
    if photo:
        await msg.reply_photo(photo=photo, caption=caption, reply_markup=markup, parse_mode=parse_mode)
    else:
        await msg.reply_text(caption, reply_markup=markup, parse_mode=parse_mode)
    return track


async def handle_chart_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback chart_track_{hash} — показать карточку выбранного трека из чарта."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("chart_track_"):
        return
    track_hash = data.replace("chart_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.edit_message_text("❌ Трек не найден.", reply_markup=None)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.edit_message_text("❌ Не удалось загрузить трек.")
        return
    caption = build_card_caption(track, user_id)
    url = track.get("track_url") or ""
    in_fav = is_in_favorites(user_id, track["id"])
    markup = track_card_buttons(track["id"], url, in_fav, track.get("source") or "")
    photo = track.get("cover_url")
    try:
        if photo:
            await query.message.reply_photo(photo=photo, caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            await query.message.reply_text(caption, reply_markup=markup, parse_mode="Markdown")
        await query.delete_message()
    except Exception:
        await query.edit_message_text(caption, reply_markup=markup, parse_mode="Markdown")


async def handle_playlist_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback playlist_track_{hash} — карточка трека из плейлиста (как в чарте)."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("playlist_track_"):
        return
    track_hash = data.replace("playlist_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.edit_message_text("❌ Трек не найден.", reply_markup=None)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.edit_message_text("❌ Не удалось загрузить трек.")
        return
    caption = build_card_caption(track, user_id)
    url = track.get("track_url") or ""
    in_fav = is_in_favorites(user_id, track["id"])
    markup = track_card_buttons(track["id"], url, in_fav, track.get("source") or "")
    photo = track.get("cover_url")
    try:
        if photo:
            await query.message.reply_photo(photo=photo, caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            await query.message.reply_text(caption, reply_markup=markup, parse_mode="Markdown")
        await query.delete_message()
    except Exception:
        await query.edit_message_text(caption, reply_markup=markup, parse_mode="Markdown")


async def handle_search_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback search_track_{hash} — карточка трека из результатов поиска."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("search_track_"):
        return
    track_hash = data.replace("search_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.edit_message_text("❌ Трек не найден.", reply_markup=None)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.edit_message_text("❌ Не удалось загрузить трек.")
        return
    caption = build_card_caption(track, user_id)
    url = track.get("track_url") or ""
    in_fav = is_in_favorites(user_id, track["id"])
    markup = track_card_buttons(track["id"], url, in_fav, track.get("source") or "")
    photo = track.get("cover_url")
    try:
        if photo:
            await query.message.reply_photo(photo=photo, caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            await query.message.reply_text(caption, reply_markup=markup, parse_mode="Markdown")
        await query.delete_message()
    except Exception:
        await query.edit_message_text(caption, reply_markup=markup, parse_mode="Markdown")


async def handle_rate_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback rate_track_{hash} — начать оценку трека (переход в состояние rating)."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("rate_track_"):
        return
    track_hash = data.replace("rate_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Трек не найден.", show_alert=True)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.answer("❌ Не удалось загрузить трек.", show_alert=True)
        return
    nickname = get_user_nickname(user_id) or user_states.get(user_id, {}).get("nickname", "Аноним")
    prev_explore = None
    if user_id in user_states and isinstance(user_states[user_id], dict):
        prev_explore = user_states[user_id].get("explore")
    user_states[user_id] = {
        "stage": "rating",
        "track_id": track_id,
        "track_title": track["title"],
        "track_artist": track["artist"],
        "ratings": {},
        "current_criteria": "rhymes",
        "nickname": nickname,
        "genre": track.get("genre"),
        "is_daily": False,
    }
    if prev_explore:
        user_states[user_id]["explore"] = prev_explore
    await query.message.reply_text(
        f"Оценим этот трек!\n\n🔹 *{CRITERIA_NAMES['rhymes']}*\nВыбери оценку от 1 до 10:",
        parse_mode="Markdown",
        reply_markup=rating_buttons(),
    )


# Блокировка повторного нажатия «Скачать»: (user_id, track_id) в процессе загрузки
_downloading = set()

DOWNLOAD_MAX_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAY = 2


async def _retry_on_timeout(coro, max_attempts=DOWNLOAD_MAX_ATTEMPTS, delay=DOWNLOAD_RETRY_DELAY):
    """Выполняет coroutine с повтором при telegram.error.TimedOut."""
    last_error = None
    for attempt in range(max_attempts):
        try:
            return await coro()
        except TimedOut as e:
            last_error = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
    raise last_error


def _download_key(user_id: int, track_id: str):
    return (user_id, track_id)


async def handle_download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback download_track_{hash} — скачать трек через API и отправить пользователю файлом."""
    query = update.callback_query
    data = query.data
    if not data.startswith("download_track_"):
        await query.answer()
        return
    track_hash = data.replace("download_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Трек не найден.", show_alert=True)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    is_soundcloud = str(track_id).startswith("sc_")
    key = _download_key(user_id, track_id)
    if key in _downloading:
        await query.answer("⏳ Загрузка уже идёт, подожди.", show_alert=True)
        return
    _downloading.add(key)
    await query.answer("⏳ Начинаю загрузку...")
    status_msg = None
    try:
        if is_soundcloud:
            status_msg = await query.message.reply_text(
                "⏳ _Загружаю трек из SoundCloud..._", parse_mode="Markdown"
            )
            audio_bytes, title, performer = soundcloud_download_track_bytes(track_id)
        else:
            status_msg = await query.message.reply_text(
                "⏳ _Загружаю трек из Яндекс.Музыки..._", parse_mode="Markdown"
            )
            audio_bytes, title, performer = yandex_download_track_bytes(track_id)

        if not audio_bytes or len(audio_bytes) == 0:
            if status_msg:
                src = "SoundCloud" if is_soundcloud else "Яндекс.Музыки"
                await status_msg.edit_text(
                    f"❌ Не удалось скачать трек из {src}. Проверьте доступность трека."
                )
            return
        if len(audio_bytes) > 50 * 1024 * 1024:
            if status_msg:
                await status_msg.edit_text("❌ Файл слишком большой для отправки в Telegram (лимит 50 МБ).")
            return

        # Этап 2: отправка в Telegram
        if status_msg:
            await status_msg.edit_text("✅ _Трек загружен. Отправляю в Telegram..._", parse_mode="Markdown")
        filename = f"{performer} - {title}.mp3"[:60].strip() or "track.mp3"
        bio = io.BytesIO(audio_bytes)
        bio.name = filename

        async def send_audio():
            bio.seek(0)
            return await query.message.reply_audio(
                audio=InputFile(bio, filename=filename),
                title=title[:64] if title else None,
                performer=performer[:64] if performer else None,
            )

        try:
            audio_msg = await _retry_on_timeout(lambda: send_audio())
            if config.STORAGE_CHAT_ID:
                try:
                    bio.seek(0)
                    storage_msg = await context.bot.send_audio(
                        chat_id=config.STORAGE_CHAT_ID,
                        audio=InputFile(bio, filename=filename),
                        title=title[:64] if title else None,
                        performer=performer[:64] if performer else None,
                    )
                    add_download(
                        user_id, track_id,
                        title or "Без названия", performer or "Неизвестен",
                        message_id=storage_msg.message_id,
                        chat_id=storage_msg.chat_id,
                    )
                    state = user_states.get(user_id, {})
                    to_del = state.get("messages_to_delete_on_back") or []
                    to_del.append((audio_msg.chat_id, audio_msg.message_id))
                    user_states[user_id] = {**state, "messages_to_delete_on_back": to_del}
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "Не удалось отправить трек в хранилище (STORAGE_CHAT_ID): %s. Сохраняю сообщение пользователя.",
                        e,
                    )
                    add_download(
                        user_id, track_id,
                        title or "Без названия", performer or "Неизвестен",
                        message_id=audio_msg.message_id,
                        chat_id=audio_msg.chat_id,
                    )
            else:
                add_download(
                    user_id, track_id,
                    title or "Без названия", performer or "Неизвестен",
                    message_id=audio_msg.message_id,
                    chat_id=audio_msg.chat_id,
                )
        except TimedOut:
            if status_msg:
                await status_msg.edit_text(
                    "❌ Таймаут при _отправке файла в Telegram_. Трек загружен, но Telegram не принял за время. Попробуй ещё раз или подожди при медленном интернете."
                )
            return
        except BadRequest as e:
            if status_msg:
                msg = "❌ Не удалось отправить файл в Telegram."
                if "non-empty" in str(e).lower() or "empty" in str(e).lower():
                    msg = "❌ Файл трека пришёл пустым. Попробуй другой трек или нажми «Скачать» ещё раз."
                await status_msg.edit_text(msg)
            return

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
    finally:
        _downloading.discard(key)


async def handle_fav_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback fav_toggle_{hash} — добавить/убрать из избранного и обновить кнопку."""
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("fav_toggle_"):
        return
    track_hash = data.replace("fav_toggle_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.answer("❌ Трек не найден.", show_alert=True)
        return
    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id
    track = _get_track_dict(track_id)
    if not track:
        await query.answer("❌ Ошибка загрузки трека.", show_alert=True)
        return
    url = track.get("track_url") or ""
    in_fav = is_in_favorites(user_id, track_id)
    if in_fav:
        remove_favorite(user_id, track_id)
        in_fav = False
    else:
        add_favorite(user_id, track_id, track["title"], track["artist"])
        add_exp(user_id, EXP_FOR_FAVORITE)
        mark_daily_favorite_task(user_id)
        in_fav = True
    markup = track_card_buttons(track_id, url, in_fav, track.get("source") or "")
    caption = build_card_caption(track, user_id)
    try:
        await query.edit_message_reply_markup(reply_markup=markup)
    except Exception:
        if query.message.photo:
            await query.edit_message_caption(caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            await query.edit_message_text(caption, reply_markup=markup, parse_mode="Markdown")
