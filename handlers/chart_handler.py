# handlers/chart_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from database import get_user_reviewed_track_ids
from yandex_music_service import get_chart_tracks
from keyboards import chart_list_buttons_paginated, back_to_menu_button

CHART_FETCH_LIMIT = 60
PAGE_SIZE = 20


def _page_from_callback(data: str) -> int:
    if data == "show_chart":
        return 0
    if data.startswith("chart_page_"):
        try:
            return max(0, int(data.split("_")[-1]))
        except ValueError:
            return 0
    return 0


async def show_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = _page_from_callback(query.data or "")

    tracks = get_chart_tracks(chart_id="world", limit=CHART_FETCH_LIMIT)
    if not tracks:
        await query.edit_message_text(
            "❌ Не удалось загрузить чарт. Попробуй позже.",
            reply_markup=back_to_menu_button()
        )
        return

    total_pages = (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE
    if page >= total_pages:
        page = max(0, total_pages - 1)

    user_id = query.from_user.id
    reviewed_set = set(get_user_reviewed_track_ids(user_id))
    text = f"📊 *Чарт Яндекс.Музыки* — стр. {page + 1}/{total_pages}\n\nВыбери трек:\n_✓ — вы уже оценивали_"
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=chart_list_buttons_paginated(
            tracks, page=page, per_page=PAGE_SIZE, reviewed_ids=reviewed_set
        ),
    )
