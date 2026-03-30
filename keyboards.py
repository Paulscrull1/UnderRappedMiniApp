# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
import config


def main_menu():
    """Главное меню (используется при пустых списках и т.д.)"""
    keyboard = []
    if config.MINI_APP_URL:
        keyboard.append([
            InlineKeyboardButton("🎮 Играть", web_app=WebAppInfo(url=config.MINI_APP_URL)),
        ])
    keyboard.extend([
        [InlineKeyboardButton("👤 Профиль", callback_data="show_profile")],
        [InlineKeyboardButton("🎲 Топ-100 на оценку", callback_data="chart_explore_start")],
        [InlineKeyboardButton("⭐ Premium", callback_data="show_premium")],
        [InlineKeyboardButton("🏆 Лидерборд", callback_data="show_leaderboard")],
        [InlineKeyboardButton("🌞 Трек дня", callback_data="show_daily_track")],
        [InlineKeyboardButton("📊 Чарт Яндекс Музыки", callback_data="show_chart")],
        [InlineKeyboardButton("🔍 Поиск в Яндекс.Музыке", callback_data="start_search_yandex")],
        [InlineKeyboardButton("🔍 Поиск в SoundCloud", callback_data="start_search_soundcloud")],
        [InlineKeyboardButton("📑 Треки из плейлиста", callback_data="start_playlist")],
        [InlineKeyboardButton("🎵 Мой плейлист", callback_data="view_favorites")],
        [InlineKeyboardButton("📥 Мои скачанные", callback_data="view_downloads")],
        [InlineKeyboardButton("📋 Моя статистика", callback_data="view_reviews")],
        [InlineKeyboardButton("🌍 Общая статистика", callback_data="view_global_reviews")],
        [InlineKeyboardButton("🏆 Топ треков", callback_data="show_top_tracks")],
        [InlineKeyboardButton("👥 Пригласить друзей", callback_data="invite_friends")],
    ])
    return InlineKeyboardMarkup(keyboard)


def profile_view_buttons():
    """Кнопки экрана профиля: Редактировать, Лидерборд, Назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Редактировать профиль", callback_data="profile_edit")],
        [InlineKeyboardButton("🏆 Лидерборд", callback_data="show_leaderboard")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")],
    ])


def leaderboard_buttons(leaders):
    """
    Кнопки лидерборда: топ-3 — «Профиль» для просмотра профиля.
    leaders — список dict с ключом user_id (первые 3).
    """
    buttons = []
    for u in leaders[:3]:
        label = f"👤 {u.get('nickname', 'User')[:25]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"leader_{u['user_id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(buttons)


def back_to_leaderboard_button():
    """Кнопка «Назад к лидерборду» при просмотре профиля из лидерборда."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад к лидерборду", callback_data="show_leaderboard")],
    ])


def profile_edit_buttons():
    """Меню редактирования: Аватар, Никнейм, Описание, Закрепить трек, Назад."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 Аватар", callback_data="profile_set_avatar")],
        [InlineKeyboardButton("📝 Никнейм", callback_data="profile_set_nickname")],
        [InlineKeyboardButton("📄 Описание", callback_data="profile_set_description")],
        [InlineKeyboardButton("📌 Закрепить трек", callback_data="profile_pin_track")],
        [InlineKeyboardButton("🔙 Назад к профилю", callback_data="show_profile")],
    ])


def profile_pin_track_buttons(tracks, page=0, per_page=8):
    """Список треков для закрепления: из оценок и плейлиста. callback pin_track_{hash}."""
    from utils import hash_id, hash_to_track_id
    start = page * per_page
    chunk = tracks[start : start + per_page]
    buttons = []
    for t in chunk:
        safe_hash = hash_id(t["track_id"])
        hash_to_track_id[safe_hash] = t["track_id"]
        label = f"{t.get('title', t.get('track_title', ''))} — {t.get('artist', t.get('track_artist', ''))}"[:50]
        buttons.append([InlineKeyboardButton(label, callback_data=f"pin_track_{safe_hash}")])
    total_pages = (len(tracks) + per_page - 1) // per_page if tracks else 1
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"profile_pin_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"Стр. {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"profile_pin_page_{page + 1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("❌ Убрать закрепление", callback_data="profile_unpin_track")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="profile_edit")])
    return InlineKeyboardMarkup(buttons)


def rating_buttons():
    """Кнопки оценки 1–10 и отмена"""
    row1 = [
        InlineKeyboardButton(str(i), callback_data=f"rate_{i}") for i in range(1, 6)
    ]
    row2 = [
        InlineKeyboardButton(str(i), callback_data=f"rate_{i}") for i in range(6, 11)
    ]
    row3 = [InlineKeyboardButton("❌ Отмена", callback_data="cancel_rating")]
    return InlineKeyboardMarkup([row1, row2, row3])


def back_to_menu_button():
    """Одна кнопка «Назад в меню»"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")]
    ])


def cancel_review_button():
    """Кнопка «Отмена» при вводе рецензии."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_review")]
    ])


def back_to_list_button(back_callback: str):
    """Кнопка «Назад» к списку (callback_data = back_callback)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]
    ])


def after_review_buttons(track_id=None):
    """
    Кнопки после оценки: написать рецензию, скачать, плейлист, назад.
    track_id — для ask_review_ и favorite_ (передаётся как hash).
    """
    from utils import hash_id, hash_to_track_id
    buttons = []
    if track_id:
        safe_hash = hash_id(track_id)
        hash_to_track_id[safe_hash] = track_id
        buttons.append([
            InlineKeyboardButton("✍️ Рецензия", callback_data=f"ask_review_{safe_hash}"),
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(buttons)


def track_card_buttons(track_id: str, track_url: str, in_favorites: bool, source: str = ""):
    """
    Клавиатура карточки трека: Слушать | Оценить | Рецензия | Скачать | В плейлист, Назад.
    Скачать доступен и для Яндекс.Музыки, и для SoundCloud.
    """
    from utils import hash_id, hash_to_track_id
    safe_hash = hash_id(track_id)
    hash_to_track_id[safe_hash] = track_id

    rows = []
    if track_url:
        rows.append([InlineKeyboardButton("▶ Слушать", url=track_url)])
    row1 = [
        InlineKeyboardButton("⭐ Оценить", callback_data=f"rate_track_{safe_hash}"),
        InlineKeyboardButton("✍️ Рецензия", callback_data=f"ask_review_{safe_hash}"),
    ]
    rows.append(row1)
    row2 = [
        InlineKeyboardButton("📥 Скачать", callback_data=f"download_track_{safe_hash}"),
        InlineKeyboardButton(
            "❤️ Убрать из плейлиста" if in_favorites else "🤍 В плейлист",
            callback_data=f"fav_toggle_{safe_hash}"
        ),
    ]
    rows.append(row2)
    rows.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(rows)


def track_card_buttons_with_explore(track_id: str, track_url: str, in_favorites: bool, source: str = ""):
    """Карточка трека в режиме подборки чарта: строка «Пропустить» / «Выход»."""
    m = track_card_buttons(track_id, track_url, in_favorites, source)
    rows = [list(row) for row in m.inline_keyboard]
    explore_row = [
        InlineKeyboardButton("⏭ Дальше", callback_data="chart_explore_skip"),
        InlineKeyboardButton("🛑 Закончить", callback_data="chart_explore_exit"),
    ]
    if rows:
        rows.insert(-1, explore_row)
    else:
        rows.append(explore_row)
    return InlineKeyboardMarkup(rows)


def chart_list_buttons(tracks):
    """
    Список кнопок для чарта: каждая — callback chart_track_{hash}.
    tracks — список dict с ключами id, title, artist (для подписи кнопки).
    """
    from utils import hash_id, hash_to_track_id
    buttons = []
    for t in tracks:
        safe_hash = hash_id(t["id"])
        hash_to_track_id[safe_hash] = t["id"]
        label = f"{t['title']} — {t['artist']}"[:60]
        buttons.append([InlineKeyboardButton(label, callback_data=f"chart_track_{safe_hash}")])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(buttons)


CHART_PAGE_SIZE = 20


def chart_list_buttons_paginated(tracks, page=0, per_page=None, reviewed_ids=None):
    """
    Чарт с пагинацией: tracks — полный список, page — номер страницы (0-based).
    reviewed_ids — set строковых track_id для префикса ✓ на кнопке.
    """
    per_page = per_page or CHART_PAGE_SIZE
    start = page * per_page
    chunk = tracks[start : start + per_page]
    from utils import hash_id, hash_to_track_id
    reviewed_ids = reviewed_ids or set()
    reviewed_str = {str(x) for x in reviewed_ids}
    buttons = []
    for t in chunk:
        safe_hash = hash_id(t["id"])
        hash_to_track_id[safe_hash] = t["id"]
        tid = str(t["id"])
        prefix = "✓ " if tid in reviewed_str else ""
        label = f"{prefix}{t['title']} — {t['artist']}"[:64]
        buttons.append([InlineKeyboardButton(label, callback_data=f"chart_track_{safe_hash}")])
    total_pages = (len(tracks) + per_page - 1) // per_page if tracks else 1
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"chart_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"Стр. {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"chart_page_{page + 1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(buttons)


PLAYLIST_PAGE_SIZE = 10


def playlist_list_buttons_paginated(tracks, page=0, per_page=None):
    """
    Плейлист с пагинацией по 10 треков: callback playlist_track_{hash}, playlist_page_N.
    """
    per_page = per_page or PLAYLIST_PAGE_SIZE
    start = page * per_page
    chunk = tracks[start : start + per_page]
    from utils import hash_id, hash_to_track_id
    buttons = []
    for t in chunk:
        safe_hash = hash_id(t["id"])
        hash_to_track_id[safe_hash] = t["id"]
        label = f"{t['title']} — {t['artist']}"[:60]
        buttons.append([InlineKeyboardButton(label, callback_data=f"playlist_track_{safe_hash}")])
    total_pages = (len(tracks) + per_page - 1) // per_page if tracks else 1
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"playlist_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"Стр. {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"playlist_page_{page + 1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(buttons)


def search_list_buttons(tracks):
    """
    Список результатов поиска: каждая кнопка — search_track_{hash}.
    tracks — список dict с ключами id, title, artist.
    """
    from utils import hash_id, hash_to_track_id
    buttons = []
    for t in tracks:
        safe_hash = hash_id(t["id"])
        hash_to_track_id[safe_hash] = t["id"]
        label = f"{t['title']} — {t['artist']}"[:60]
        buttons.append([InlineKeyboardButton(label, callback_data=f"search_track_{safe_hash}")])
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(buttons)


REVIEWS_PAGE_SIZE = 10


def reviews_list_buttons_paginated(reviews, page=0, per_page=None, fav_count=0):
    """
    Список «Мои оценки» с пагинацией.
    reviews — полный список, page — номер страницы.
    Кнопки: detail_{hash}, навигация view_reviews_page_N, Назад в меню.
    """
    per_page = per_page or REVIEWS_PAGE_SIZE
    from utils import hash_id, hash_to_track_id
    start = page * per_page
    chunk = reviews[start : start + per_page]
    fav_label = f"🎵 Мой плейлист ({fav_count})" if fav_count is not None else "🎵 Мой плейлист"
    buttons = [[InlineKeyboardButton(fav_label, callback_data="view_favorites")]]
    for r in chunk:
        safe_hash = hash_id(r["track_id"])
        hash_to_track_id[safe_hash] = r["track_id"]
        text = f"{r['title']} — {r['artist']} | {r['total']}/50"[:60]
        buttons.append([InlineKeyboardButton(text, callback_data=f"detail_{safe_hash}")])
    total_pages = (len(reviews) + per_page - 1) // per_page if reviews else 1
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"view_reviews_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"Стр. {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"view_reviews_page_{page + 1}"))
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(buttons)
