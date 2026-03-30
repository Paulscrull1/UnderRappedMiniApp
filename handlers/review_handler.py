# handlers/review_handler.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import user_states, hash_id, hash_to_track_id
from keyboards import back_to_menu_button, cancel_review_button
import sqlite3


async def ask_for_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запускает процесс написания рецензии.
    Вызывается по кнопке после оценки трека.
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("ask_review_"):
        return

    track_hash = data.replace("ask_review_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.edit_message_text("❌ Данные устарели.", reply_markup=back_to_menu_button())
        return

    track_id = hash_to_track_id[track_hash]
    user_id = query.from_user.id

    prev = user_states.get(user_id, {})
    prev_explore = prev.get("explore")
    prev_nickname = prev.get("nickname")
    user_states[user_id] = {
        'stage': 'writing_review',
        'track_id': track_id
    }
    if prev_explore:
        user_states[user_id]["explore"] = prev_explore
    if prev_nickname:
        user_states[user_id]["nickname"] = prev_nickname

    await query.edit_message_text(
        "✍️ Напиши свою рецензию (до 500 символов):",
        reply_markup=cancel_review_button(),
    )


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода рецензии — возврат в меню."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_states.get(user_id, {}).get("stage") == "writing_review":
        explore = user_states[user_id].get("explore")
        nickname = user_states[user_id].get("nickname")
        del user_states[user_id]
        if explore or nickname:
            user_states[user_id] = {"stage": "menu"}
            if explore:
                user_states[user_id]["explore"] = explore
            if nickname:
                user_states[user_id]["nickname"] = nickname
    await query.edit_message_text(
        "❌ Рецензия отменена.",
        reply_markup=back_to_menu_button(),
    )


async def show_reviews_for_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает все текстовые рецензии по выбранному треку
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("reviews_for_track_"):
        return

    track_hash = data.replace("reviews_for_track_", "", 1)
    if track_hash not in hash_to_track_id:
        await query.edit_message_text("❌ Трек не найден.", reply_markup=back_to_menu_button())
        return

    track_id = hash_to_track_id[track_hash]
    conn = sqlite3.connect('reviews.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nickname, review_text, total, timestamp
        FROM reviews
        WHERE track_id = ? AND review_text IS NOT NULL AND review_text != ''
        ORDER BY total DESC
    ''', (track_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await query.edit_message_text(
            "📖 По этому треку пока нет текстовых рецензий.",
            reply_markup=back_to_menu_button()
        )
        return

    message = f"💬 *Рецензии по треку*\n\n"
    for nickname, text, score, ts in rows:
        nick_display = nickname or "Аноним"
        try:
            date_part = ts.split()[0][5:].replace('-', '.')
            time_part = ts.split()[1][:5]
            time_str = f"{date_part} {time_part}"
        except:
            time_str = "недавно"
        message += f"👤 *{nick_display}*\n📊 {score}/50 | ⏰ {time_str}\n💬 _{text}_\n\n"

    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=back_to_menu_button())