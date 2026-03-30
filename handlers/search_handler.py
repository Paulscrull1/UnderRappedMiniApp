# handlers/search_handler.py
from telegram import Update
from telegram.ext import ContextTypes

from music_providers import search_tracks
from database import save_review
from keyboards import rating_buttons, after_review_buttons, back_to_menu_button
from utils import user_states, CRITERIA_NAMES
from handlers.track_card_handler import send_track_card

SEARCH_STAGE = "awaiting_search_query"


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка start_search_yandex и start_search_soundcloud: показ подсказки и сохранение источника."""
    query = update.callback_query
    await query.answer()
    data = (query.data or "").strip()
    if data == "start_search_yandex":
        source = "yandex"
        label = "Яндекс.Музыке"
    elif data == "start_search_soundcloud":
        source = "soundcloud"
        label = "SoundCloud"
    else:
        return
    user_id = query.from_user.id
    user_states[user_id] = {"stage": SEARCH_STAGE, "source": source}
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"🔍 *Поиск в {label}*\n\n"
        "Напиши запрос в чат (исполнитель, название трека или любой текст).\n\n"
        "Пример: `Платина — Бассок`",
        parse_mode="Markdown",
        reply_markup=back_to_menu_button(),
    )


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет поиск по выбранному источнику (yandex или soundcloud). Вызывается из handle_message при stage=awaiting_search_query."""
    user_id = update.message.from_user.id
    state = user_states.get(user_id, {})
    if state.get("stage") != SEARCH_STAGE:
        return False
    source = state.get("source", "yandex")
    query_text = update.message.text.strip()
    if query_text.startswith("/"):
        return True
    # Сбрасываем состояние сразу, чтобы следующий ввод не считался поиском
    del user_states[user_id]
    await update.message.reply_text("🔍 Ищу трек...")
    tracks = search_tracks(query_text, limit=5, sources=(source,))
    if not tracks:
        await update.message.reply_text(
            "❌ Ничего не найдено. Попробуй другой запрос.",
            reply_markup=back_to_menu_button(),
        )
        return True
    await send_track_card(update.message, tracks[0]["id"], user_id, track_dict=tracks[0])
    return True


async def handle_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states or user_states[user_id]['stage'] != 'rating':
        await query.answer("Сессия истекла.", show_alert=True)
        try:
            await query.message.delete()
        except:
            pass
        return

    state = user_states[user_id]
    current = state['current_criteria']
    await query.answer()

    if data == "cancel_rating":
        explore = state.get("explore")
        nick = state.get("nickname")
        await query.edit_message_text("❌ Оценка отменена.", reply_markup=back_to_menu_button())
        if user_id in user_states:
            del user_states[user_id]
        if explore:
            user_states[user_id] = {"stage": "menu", "explore": explore}
            if nick:
                user_states[user_id]["nickname"] = nick
        return

    if data.startswith("rate_"):
        try:
            score = int(data.split("_")[1])
            if not 1 <= score <= 10:
                raise ValueError()
        except ValueError:
            await query.answer("Введите число от 1 до 10.", show_alert=True)
            return

        state['ratings'][current] = score
        criteria_list = ["rhymes", "rhythm", "style", "charisma", "vibe"]
        idx = criteria_list.index(current)

        if idx < len(criteria_list) - 1:
            next_crit = criteria_list[idx + 1]
            state['current_criteria'] = next_crit
            await query.edit_message_text(
                f"🔹 *{CRITERIA_NAMES[next_crit]}*\nВыбери оценку от 1 до 10:",
                parse_mode='Markdown',
                reply_markup=rating_buttons()
            )
        else:
            total = sum(state['ratings'].values())
            result_text = (
                f"✅ Оценка завершена!\nОбщий балл: *{total}/50*\n\n"
                f"🔸 Рифмы/образы: {state['ratings']['rhymes']}\n"
                f"🔸 Структура/ритмика: {state['ratings']['rhythm']}\n"
                f"🔸 Реализация стиля: {state['ratings']['style']}\n"
                f"🔸 Индивидуальность/харизма: {state['ratings']['charisma']}\n"
                f"🔸 Атмосфера/вайб: {state['ratings']['vibe']}"
            )
            await query.edit_message_text(result_text, parse_mode='Markdown')

            explore = state.get("explore")
            track_rated = state["track_id"]
            nick = state.get("nickname")

            save_review(
                user_id=user_id,
                track_id=track_rated,
                ratings=state['ratings'],
                track_title=state['track_title'],
                track_artist=state['track_artist'],
                nickname=state['nickname'],
                genre=state['genre']
            )

            if explore:
                ids = list(explore["track_ids"])
                idx = explore["index"]
                if idx < len(ids) and str(ids[idx]) == str(track_rated):
                    idx += 1
                new_st = {"stage": "menu", "explore": {"track_ids": ids, "index": idx}}
                if nick:
                    new_st["nickname"] = nick
                user_states[user_id] = new_st
                from handlers.chart_explore_handler import chart_explore_send_current

                await query.message.reply_text("✅ Оценка сохранена!")
                await chart_explore_send_current(update, context, 0)
            else:
                if user_id in user_states:
                    del user_states[user_id]
                await query.message.reply_text(
                    "✅ Оценка сохранена!",
                    reply_markup=after_review_buttons(track_id=track_rated),
                )