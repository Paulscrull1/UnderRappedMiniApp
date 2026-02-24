# handlers/web_handler.py
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
import json
from database import save_review, get_user_nickname
from utils import CRITERIA, MAX_SCORE


def _normalize_ratings(payload: dict) -> dict:
    """Приводит оценки из Mini App к формату БД: 5 критериев, 1–10 каждый."""
    ratings = {}
    for key in CRITERIA:
        val = payload.get(key)
        if val is not None:
            try:
                ratings[key] = max(1, min(10, int(val)))
            except (TypeError, ValueError):
                ratings[key] = 5
        else:
            ratings[key] = 5
    return ratings


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает данные, отправленные из Telegram Mini App через tg.sendData().
    user_id всегда берётся из сообщения (отправитель), не из payload.
    """
    if not update.message or not update.message.from_user:
        return
    user_id = update.message.from_user.id

    try:
        data = update.message.web_app_data.data
        review = json.loads(data)

        track_id = review.get("track_id")
        track_title = review.get("track_title") or "Без названия"
        track_artist = review.get("track_artist") or "Неизвестен"
        if not track_id:
            await update.message.reply_text("❌ Не указан трек.")
            return

        ratings = _normalize_ratings(review.get("ratings") or review)
        genre = review.get("genre")
        review_text = review.get("review_text")

        save_review(
            user_id=user_id,
            track_id=track_id,
            ratings=ratings,
            track_title=track_title,
            track_artist=track_artist,
            nickname=get_user_nickname(user_id) or "Игрок",
            genre=genre,
            review_text=review_text,
        )
        total = sum(ratings.values())

        await update.message.reply_text(
            f"✅ Спасибо за оценку!\n"
            f"Балл: *{total}/{MAX_SCORE}*\n\n"
            f"Трек: *{track_title}* — {track_artist}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при обработке оценки: {str(e)}")
        print("Ошибка в handle_webapp_data:", e)


# Готовый обработчик для добавления в app
webapp_handler = MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data)