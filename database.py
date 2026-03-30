# database.py
import os
import sqlite3
from typing import Optional

DATABASE_PATH = os.environ.get("MUSIC_BOT_DB", "reviews.db")


def _connect():
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    """
    Создаёт таблицы при первом запуске
    """
    conn = _connect()
    cursor = conn.cursor()

    # Основная таблица оценок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            user_id INTEGER,
            track_id TEXT,
            rhymes INTEGER,
            rhythm INTEGER,
            style INTEGER,
            charisma INTEGER,
            vibe INTEGER,
            total REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            track_title TEXT,
            track_artist TEXT,
            nickname TEXT,
            genre TEXT,
            review_text TEXT,
            PRIMARY KEY (user_id, track_id)
        )
    ''')

    # Таблица пользователей: никнейм, профиль (аватар, описание, закреплённый трек, реферал)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT NOT NULL,
            avatar_file_id TEXT,
            description TEXT,
            pinned_track_id TEXT,
            pinned_track_title TEXT,
            pinned_track_artist TEXT
        )
    ''')
    users_cols = {col[1] for col in cursor.execute("PRAGMA table_info(users)").fetchall()}
    for col_name, col_def in [
        ("avatar_file_id", "ALTER TABLE users ADD COLUMN avatar_file_id TEXT"),
        ("description", "ALTER TABLE users ADD COLUMN description TEXT"),
        ("pinned_track_id", "ALTER TABLE users ADD COLUMN pinned_track_id TEXT"),
        ("pinned_track_title", "ALTER TABLE users ADD COLUMN pinned_track_title TEXT"),
        ("pinned_track_artist", "ALTER TABLE users ADD COLUMN pinned_track_artist TEXT"),
        ("avatar_emoji", "ALTER TABLE users ADD COLUMN avatar_emoji TEXT"),
        ("avatar_url", "ALTER TABLE users ADD COLUMN avatar_url TEXT"),
        ("referrer_id", "ALTER TABLE users ADD COLUMN referrer_id INTEGER"),
    ]:
        if col_name not in users_cols:
            cursor.execute(col_def)

    # Проверяем, есть ли новые колонки, и добавляем при необходимости
    existing_columns = {col[1] for col in cursor.execute("PRAGMA table_info(reviews)").fetchall()}
    if 'nickname' not in existing_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN nickname TEXT DEFAULT 'Аноним'")
    if 'genre' not in existing_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN genre TEXT")
    if 'review_text' not in existing_columns:
        cursor.execute("ALTER TABLE reviews ADD COLUMN review_text TEXT")

    # Избранное пользователя (треки)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_favorites (
            user_id INTEGER,
            track_id TEXT,
            track_title TEXT,
            track_artist TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, track_id)
        )
    ''')

    # LVL/Exp: прогресс пользователя
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER PRIMARY KEY,
            exp INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Скачанные пользователем треки (по кнопке «Скачать»); message_id/chat_id для пересылки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_downloads (
            user_id INTEGER,
            track_id TEXT,
            track_title TEXT,
            track_artist TEXT,
            downloaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            message_id INTEGER,
            chat_id INTEGER,
            PRIMARY KEY (user_id, track_id)
        )
    ''')
    existing = {col[1] for col in cursor.execute("PRAGMA table_info(user_downloads)").fetchall()}
    if 'message_id' not in existing:
        cursor.execute("ALTER TABLE user_downloads ADD COLUMN message_id INTEGER")
    if 'chat_id' not in existing:
        cursor.execute("ALTER TABLE user_downloads ADD COLUMN chat_id INTEGER")

    # Трек дня: один общий трек, обновляется раз в 24 часа
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_track (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            track_id TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Достижения (игровая система поощрений)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            key TEXT PRIMARY KEY,
            name_ru TEXT NOT NULL,
            description_ru TEXT NOT NULL,
            icon TEXT NOT NULL,
            condition_type TEXT NOT NULL,
            condition_value INTEGER NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id INTEGER,
            achievement_key TEXT,
            unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, achievement_key),
            FOREIGN KEY (achievement_key) REFERENCES achievements(key)
        )
    ''')
    # Красивые достижения: запоминающиеся названия и описания
    default_achievements = [
        ('first_rating', 'Первый шаг', 'Поставь свою первую оценку треку', '🌱', 'reviews_count', 1),
        ('reviews_5', 'Ценитель звука', 'Оцени 5 треков — ты в деле!', '🎧', 'reviews_count', 5),
        ('reviews_10', 'Меломан', '10 оценок — твой вкус находит голос', '🎵', 'reviews_count', 10),
        ('reviews_25', 'Звукорежиссёр', '25 треков — ты чувствуешь каждый бит', '🎚️', 'reviews_count', 25),
        ('reviews_50', 'Легенда чартов', '50 оценок — ты знаешь музыку изнутри', '🏆', 'reviews_count', 50),
        ('level_5', 'Восходящая звезда', 'Достигни 5 уровня', '⭐', 'level', 5),
        ('level_10', 'Голос сообщества', '10 уровень — твоё мнение важно', '🌟', 'level', 10),
        ('level_25', 'Мастер вкуса', '25 уровень — ты эталон для других', '👑', 'level', 25),
        ('streak_3', 'На волне', '3 дня подряд с оценками', '🔥', 'streak_days', 3),
        ('streak_7', 'Неделя огня', '7 дней подряд', '🔥', 'streak_days', 7),
        ('streak_30', 'Месяц дисциплины', '30 дней подряд', '💎', 'streak_days', 30),
        ('daily_warrior', 'Ежедневник', 'Выполни все задания дня 5 раз (счётчик)', '✅', 'daily_tasks_all', 5),
    ]
    cursor.executemany(
        'INSERT OR IGNORE INTO achievements (key, name_ru, description_ru, icon, condition_type, condition_value) VALUES (?, ?, ?, ?, ?, ?)',
        default_achievements,
    )
    for key, name_ru, desc_ru, icon, ctype, cval in default_achievements:
        cursor.execute(
            'UPDATE achievements SET name_ru = ?, description_ru = ?, icon = ? WHERE key = ?',
            (name_ru, desc_ru, icon, key),
        )

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_streaks (
            user_id INTEGER PRIMARY KEY,
            last_activity_date TEXT NOT NULL,
            current_streak INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_daily_tasks (
            user_id INTEGER NOT NULL,
            day_utc TEXT NOT NULL,
            task_id TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            exp_awarded INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day_utc, task_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_streak_milestones (
            user_id INTEGER NOT NULL,
            milestone INTEGER NOT NULL,
            PRIMARY KEY (user_id, milestone)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_daily_all_completed (
            user_id INTEGER NOT NULL,
            day_utc TEXT NOT NULL,
            PRIMARY KEY (user_id, day_utc)
        )
    ''')

    users_cols2 = {col[1] for col in cursor.execute("PRAGMA table_info(users)").fetchall()}
    for col_name, col_def in [
        ("referral_welcome_exp_claimed", "ALTER TABLE users ADD COLUMN referral_welcome_exp_claimed INTEGER DEFAULT 0"),
        ("referral_inviter_bonus_paid", "ALTER TABLE users ADD COLUMN referral_inviter_bonus_paid INTEGER DEFAULT 0"),
        ("daily_tasks_all_count", "ALTER TABLE users ADD COLUMN daily_tasks_all_count INTEGER DEFAULT 0"),
    ]:
        if col_name not in users_cols2:
            cursor.execute(col_def)

    users_cols3 = {col[1] for col in cursor.execute("PRAGMA table_info(users)").fetchall()}
    if "premium_until" not in users_cols3:
        cursor.execute("ALTER TABLE users ADD COLUMN premium_until TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_payments (
            telegram_charge_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            invoice_payload TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


DAILY_TRACK_TTL_SECONDS = 86400  # 24 часа


def get_cached_daily_track():
    """
    Возвращает (track_id, updated_at) если трек дня закэширован и не старше 24 ч,
    иначе None.
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT track_id, updated_at FROM daily_track WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    track_id, updated_at = row[0], row[1]
    if not track_id or not updated_at:
        return None
    try:
        from datetime import datetime, timezone
        updated = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age = (now - updated).total_seconds()
        if age < 0 or age > DAILY_TRACK_TTL_SECONDS:
            return None
        return (track_id, updated_at)
    except Exception:
        return None


def set_daily_track(track_id: str):
    """Сохраняет трек дня и время обновления (UTC)."""
    from datetime import datetime, timezone
    conn = _connect()
    cursor = conn.cursor()
    now_utc = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        'INSERT INTO daily_track (id, track_id, updated_at) VALUES (1, ?, ?) '
        'ON CONFLICT(id) DO UPDATE SET track_id = ?, updated_at = ?',
        (track_id, now_utc, track_id, now_utc),
    )
    conn.commit()
    conn.close()


def save_user_nickname(user_id: int, nickname: str):
    """
    Сохраняет или обновляет только никнейм. Не трогает description, avatar, pinned_track.
    """
    if not nickname or len(nickname.strip()) == 0:
        return
    nickname = nickname.strip()[:50]

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, nickname) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET nickname = excluded.nickname
    ''', (user_id, nickname))
    conn.commit()
    conn.close()


def set_referrer_if_empty(user_id: int, referrer_id: int) -> bool:
    """
    Устанавливает referrer_id для пользователя, если он ещё не задан.
    Возвращает True, если значение было установлено.
    """
    if not referrer_id or referrer_id == user_id:
        return False
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row and row[0] is not None:
        conn.close()
        return False
    cursor.execute(
        'INSERT INTO users (user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING',
        (user_id, get_user_nickname(user_id) or f'User_{user_id}'),
    )
    cursor.execute(
        'UPDATE users SET referrer_id = ? WHERE user_id = ? AND (referrer_id IS NULL)',
        (referrer_id, user_id),
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def get_user_nickname(user_id: int) -> str:
    """
    Возвращает сохранённый никнейм пользователя
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT nickname FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_profile(user_id: int) -> dict:
    """
    Профиль пользователя: nickname, avatar_file_id, description, pinned_track_*.
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT nickname, avatar_file_id, description, pinned_track_id, pinned_track_title, pinned_track_artist, avatar_emoji, avatar_url '
        'FROM users WHERE user_id = ?',
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'nickname': row[0] or 'Без имени',
        'avatar_file_id': row[1],
        'description': row[2] or '',
        'pinned_track_id': row[3],
        'pinned_track_title': row[4],
        'pinned_track_artist': row[5],
        'avatar_emoji': row[6] if len(row) > 6 else None,
        'avatar_url': row[7] if len(row) > 7 else None,
    }


def update_profile_avatar(user_id: int, file_id: str):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING',
        (user_id, f'User_{user_id}'),
    )
    cursor.execute('UPDATE users SET avatar_file_id = ? WHERE user_id = ?', (file_id, user_id))
    conn.commit()
    conn.close()


def update_profile_description(user_id: int, description: str):
    description = (description or '').strip()[:500]
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING',
        (user_id, get_user_nickname(user_id) or f'User_{user_id}'),
    )
    cursor.execute('UPDATE users SET description = ? WHERE user_id = ?', (description, user_id))
    conn.commit()
    conn.close()


def update_profile_avatar_emoji(user_id: int, emoji: str):
    """Установить аватар-эмодзи (один символ или короткая строка, напр. 🎸)."""
    emoji = (emoji or '').strip()[:10]
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING',
        (user_id, get_user_nickname(user_id) or f'User_{user_id}'),
    )
    cursor.execute('UPDATE users SET avatar_emoji = ? WHERE user_id = ?', (emoji or None, user_id))
    conn.commit()
    conn.close()


def update_profile_avatar_url(user_id: int, url: str):
    """Сохранить URL загруженного аватара (путь вида /avatars/123.jpg). Сбрасывает avatar_emoji."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO users (user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING',
        (user_id, get_user_nickname(user_id) or f'User_{user_id}'),
    )
    cursor.execute(
        'UPDATE users SET avatar_url = ?, avatar_emoji = NULL WHERE user_id = ?',
        (url or None, user_id),
    )
    conn.commit()
    conn.close()


def clear_profile_avatar_custom(user_id: int):
    """Сбросить свой аватар (эмодзи и загруженное фото) — будет показано фото из Telegram."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET avatar_emoji = NULL, avatar_url = NULL WHERE user_id = ?',
        (user_id,),
    )
    conn.commit()
    conn.close()


def set_pinned_track(user_id: int, track_id: str, title: str, artist: str):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET pinned_track_id = ?, pinned_track_title = ?, pinned_track_artist = ? WHERE user_id = ?',
        (track_id, (title or '')[:200], (artist or '')[:200], user_id),
    )
    conn.commit()
    conn.close()


def clear_pinned_track(user_id: int):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET pinned_track_id = NULL, pinned_track_title = NULL, pinned_track_artist = NULL WHERE user_id = ?',
        (user_id,),
    )
    conn.commit()
    conn.close()


def user_has_reviewed(user_id, track_id):
    """True, если пользователь уже оценивал этот трек (тогда при повторной оценке EXP не начисляем)."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM reviews WHERE user_id = ? AND track_id = ?', (user_id, track_id))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_user_reviewed_track_ids(user_id: int) -> list:
    """Список track_id, по которым у пользователя уже есть оценка."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT track_id FROM reviews WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [str(r[0]) for r in rows if r[0] is not None]


def save_review(user_id, track_id, ratings, track_title, track_artist, nickname, genre=None, review_text=None):
    """
    Сохраняет или обновляет оценку трека. EXP начисляется только при первой оценке трека.
    """
    total = sum(ratings.values())
    already_rated = user_has_reviewed(user_id, track_id)

    final_nickname = get_user_nickname(user_id) or nickname or f"Пользователь {user_id}"

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO reviews 
        (user_id, track_id, rhymes, rhythm, style, charisma, vibe, total,
         track_title, track_artist, nickname, genre, review_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, track_id,
        ratings['rhymes'], ratings['rhythm'], ratings['style'],
        ratings['charisma'], ratings['vibe'], total,
        track_title, track_artist, final_nickname, genre, review_text
    ))
    conn.commit()
    conn.close()

    if not already_rated:
        from utils import EXP_FOR_RATING
        add_exp(user_id, EXP_FOR_RATING)

    return _after_review_gamification(user_id, track_id, not already_rated)


def get_last_reviews(user_id, limit=10):
    """
    Последние оценки пользователя
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_id, track_title, track_artist, total, rhymes, rhythm, style, charisma, vibe, review_text
        FROM reviews WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'track_id': r[0],
            'title': r[1],
            'artist': r[2],
            'total': r[3],
            'ratings': {
                'rhymes': r[4], 'rhythm': r[5], 'style': r[6],
                'charisma': r[7], 'vibe': r[8]
            },
            'review_text': r[9]
        }
        for r in rows
    ]


def get_top_tracks_by_rating(limit=10):
    """
    Топ треков по среднему баллу (с track_id для ссылок и избранного).
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_id, track_title, track_artist, AVG(total), COUNT(*)
        FROM reviews
        GROUP BY track_id
        HAVING COUNT(*) >= 1
        ORDER BY AVG(total) DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'track_id': r[0],
            'title': r[1],
            'artist': r[2],
            'avg_score': round(r[3], 1),
            'count': r[4]
        }
        for r in rows
    ]


def get_track_rating_stats(track_id: str):
    """
    Средний балл и количество оценок по треку. Возвращает None, если оценок нет.
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT AVG(total), COUNT(*) FROM reviews WHERE track_id = ?',
        (track_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or row[1] == 0:
        return None
    return {'avg': round(row[0], 1), 'count': row[1]}


def get_last_reviews_global(limit=10):
    """
    Последние оценки всех пользователей
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, track_id, track_title, track_artist, total, nickname, timestamp
        FROM reviews
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()

    def format_time(ts):
        try:
            date_part = ts.split()[0][5:].replace('-', '.')
            time_part = ts.split()[1][:5]
            return f"{date_part} {time_part}"
        except:
            return "недавно"

    return [
        {
            'user_id': r[0],
            'track_id': r[1],
            'title': r[2],
            'artist': r[3],
            'total': r[4],
            'nickname': r[5] or f"Пользователь {r[0]}",
            'timestamp': format_time(r[6])
        }
        for r in rows
    ]


# --- Избранное ---

def add_favorite(user_id: int, track_id: str, track_title: str, track_artist: str):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_favorites (user_id, track_id, track_title, track_artist)
        VALUES (?, ?, ?, ?)
    ''', (user_id, track_id, track_title, track_artist))
    conn.commit()
    conn.close()


def remove_favorite(user_id: int, track_id: str):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_favorites WHERE user_id = ? AND track_id = ?', (user_id, track_id))
    conn.commit()
    conn.close()


def is_in_favorites(user_id: int, track_id: str) -> bool:
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM user_favorites WHERE user_id = ? AND track_id = ?', (user_id, track_id))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_favorites(user_id: int, limit=50):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_id, track_title, track_artist FROM user_favorites
        WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{'track_id': r[0], 'title': r[1], 'artist': r[2]} for r in rows]


def add_download(
    user_id: int,
    track_id: str,
    track_title: str,
    track_artist: str,
    message_id: int = None,
    chat_id: int = None,
):
    """Сохраняет факт скачивания трека и сообщение с аудио (для пересылки в «Мои скачанные»)."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_downloads
        (user_id, track_id, track_title, track_artist, downloaded_at, message_id, chat_id)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
    ''', (user_id, track_id, track_title, track_artist, message_id, chat_id))
    conn.commit()
    conn.close()


def get_downloads(user_id: int, limit=50):
    """Список скачанных треков (последние первыми); message_id/chat_id для быстрого копирования."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT track_id, track_title, track_artist, message_id, chat_id
        FROM user_downloads
        WHERE user_id = ?
        ORDER BY downloaded_at DESC LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [
        {'track_id': r[0], 'title': r[1], 'artist': r[2], 'message_id': r[3], 'chat_id': r[4]}
        for r in rows
    ]


# --- LVL / Exp ---

def add_exp(user_id: int, amount: int):
    before = get_user_progress(user_id)
    old_level = before["level"]
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_progress (user_id, exp, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            exp = exp + ?,
            updated_at = CURRENT_TIMESTAMP
    ''', (user_id, amount, amount))
    conn.commit()
    conn.close()
    after = get_user_progress(user_id)
    if after["level"] > old_level:
        try:
            from telegram_notify import schedule_notify_level_up

            schedule_notify_level_up(user_id, after["level"])
        except Exception:
            pass
    _check_achievements(user_id)


def get_recent_reviews_with_text(limit=5):
    """Последние текстовые рецензии по всем пользователям (для раздела «Общая статистика»)."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nickname, track_title, track_artist, review_text, total, timestamp
        FROM reviews
        WHERE review_text IS NOT NULL AND review_text != ''
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            'nickname': r[0] or 'Аноним',
            'title': r[1],
            'artist': r[2],
            'text': r[3],
            'total': r[4],
            'timestamp': r[5],
        }
        for r in rows
    ]


def get_user_progress(user_id: int):
    """Возвращает dict с ключами exp, level. Уровень: 1 + exp // 100."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT exp FROM user_progress WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    exp = row[0] if row else 0
    level = 1 + exp // 100
    return {'exp': exp, 'level': level}


def get_leaderboard(limit: int = 20):
    """
    Лидерборд по EXP: user_id, nickname, exp, level, avatar_url, avatar_emoji, description (профиль).
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.user_id, COALESCE(u.nickname, 'Пользователь ' || p.user_id), p.exp,
               u.avatar_url, u.avatar_emoji, u.description
        FROM user_progress p
        LEFT JOIN users u ON u.user_id = p.user_id
        ORDER BY p.exp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            'user_id': r[0],
            'nickname': r[1] or f'User_{r[0]}',
            'exp': r[2],
            'level': 1 + r[2] // 100,
            'avatar_url': r[3] if len(r) > 3 else None,
            'avatar_emoji': r[4] if len(r) > 4 else None,
            'description': (r[5] or '').strip() if len(r) > 5 else '',
        }
        for r in rows
    ]


# --- Достижения ---

def get_achievements_definitions():
    """Список всех достижений: key, name_ru, description_ru, icon, condition_type, condition_value."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT key, name_ru, description_ru, icon, condition_type, condition_value FROM achievements ORDER BY condition_type, condition_value')
    rows = cursor.fetchall()
    conn.close()
    return [
        {'key': r[0], 'name_ru': r[1], 'description_ru': r[2], 'icon': r[3], 'condition_type': r[4], 'condition_value': r[5]}
        for r in rows
    ]


def get_user_achievements(user_id: int):
    """Ключи разблокированных достижений пользователя."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT achievement_key FROM user_achievements WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def unlock_achievement(user_id: int, achievement_key: str) -> bool:
    """Разблокирует достижение, если ещё не разблокировано. Возвращает True если только что разблокировано."""
    conn = _connect()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT OR IGNORE INTO user_achievements (user_id, achievement_key) VALUES (?, ?)',
            (user_id, achievement_key),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _utc_today_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _yesterday_str(today: str) -> str:
    from datetime import datetime, timezone, timedelta
    d = datetime.strptime(today, "%Y-%m-%d").replace(tzinfo=timezone.utc) - timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def get_user_streak_data(user_id: int) -> dict:
    """Текущий стрик пользователя (UTC-дни с хотя бы одной новой оценкой)."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT last_activity_date, current_streak, best_streak FROM user_streaks WHERE user_id = ?',
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"current_streak": 0, "best_streak": 0, "last_activity_date": None}
    return {
        "current_streak": row[1] or 0,
        "best_streak": row[2] or 0,
        "last_activity_date": row[0],
    }


def _update_streak_for_user(user_id: int) -> dict:
    """
    Вызывается при новой оценке трека (первой для этого трека).
    Возвращает {current_streak, best_streak, milestone_exp_gained}.
    """
    from utils import EXP_STREAK_MILESTONE

    today = _utc_today_str()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT last_activity_date, current_streak, best_streak FROM user_streaks WHERE user_id = ?',
        (user_id,),
    )
    row = cursor.fetchone()
    milestone_exp = 0
    if not row:
        cur, best = 1, 1
        cursor.execute(
            'INSERT INTO user_streaks (user_id, last_activity_date, current_streak, best_streak) VALUES (?, ?, ?, ?)',
            (user_id, today, cur, best),
        )
    else:
        last_d, cur, best = row[0], row[1] or 0, row[2] or 0
        if last_d == today:
            conn.commit()
            conn.close()
            return {"current_streak": cur, "best_streak": best, "milestone_exp_gained": 0}
        if last_d == _yesterday_str(today):
            cur = cur + 1
        else:
            cur = 1
        best = max(best, cur)
        cursor.execute(
            'UPDATE user_streaks SET last_activity_date = ?, current_streak = ?, best_streak = ? WHERE user_id = ?',
            (today, cur, best, user_id),
        )
    conn.commit()
    conn.close()

    for milestone, exp_amt in sorted(EXP_STREAK_MILESTONE.items()):
        if cur >= milestone:
            conn = _connect()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO user_streak_milestones (user_id, milestone) VALUES (?, ?)',
                (user_id, milestone),
            )
            if cursor.rowcount > 0:
                add_exp(user_id, exp_amt)
                milestone_exp += exp_amt
                try:
                    from telegram_notify import schedule_notify_streak_milestone

                    schedule_notify_streak_milestone(user_id, milestone, exp_amt)
                except Exception:
                    pass
            conn.commit()
            conn.close()

    return {
        "current_streak": cur,
        "best_streak": best,
        "milestone_exp_gained": milestone_exp,
    }


def _try_award_daily_task(user_id: int, task_id: str, exp_amount: int) -> int:
    """Отмечает ежедневное задание и начисляет EXP один раз за календарный день UTC. Возвращает начисленный EXP."""
    day = _utc_today_str()
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT completed, exp_awarded FROM user_daily_tasks WHERE user_id = ? AND day_utc = ? AND task_id = ?',
        (user_id, day, task_id),
    )
    row = cursor.fetchone()
    if row and row[0]:
        conn.close()
        return 0
    if row:
        cursor.execute(
            'UPDATE user_daily_tasks SET completed = 1, exp_awarded = ? WHERE user_id = ? AND day_utc = ? AND task_id = ?',
            (exp_amount, user_id, day, task_id),
        )
    else:
        cursor.execute(
            'INSERT INTO user_daily_tasks (user_id, day_utc, task_id, completed, exp_awarded) VALUES (?, ?, ?, 1, ?)',
            (user_id, day, task_id, exp_amount),
        )
    conn.commit()
    conn.close()
    add_exp(user_id, exp_amount)
    _maybe_complete_all_daily_tasks(user_id, day)
    return exp_amount


def _maybe_complete_all_daily_tasks(user_id: int, day: str):
    """Если все 3 задания дня выполнены — увеличиваем счётчик для достижения «Ежедневник»."""
    required = ("new_rating", "rate_daily_track", "add_favorite")
    conn = _connect()
    cursor = conn.cursor()
    ok = True
    for tid in required:
        cursor.execute(
            'SELECT completed FROM user_daily_tasks WHERE user_id = ? AND day_utc = ? AND task_id = ?',
            (user_id, day, tid),
        )
        r = cursor.fetchone()
        if not r or not r[0]:
            ok = False
            break
    if not ok:
        conn.close()
        return
    cursor.execute(
        'INSERT OR IGNORE INTO user_daily_all_completed (user_id, day_utc) VALUES (?, ?)',
        (user_id, day),
    )
    if cursor.rowcount > 0:
        cursor.execute(
            'INSERT INTO users (user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING',
            (user_id, get_user_nickname(user_id) or f'User_{user_id}'),
        )
        cursor.execute(
            'UPDATE users SET daily_tasks_all_count = COALESCE(daily_tasks_all_count, 0) + 1 WHERE user_id = ?',
            (user_id,),
        )
    conn.commit()
    conn.close()
    _check_achievements(user_id)


def mark_daily_favorite_task(user_id: int) -> int:
    """Вызывается при добавлении трека в плейлист (Mini App / бот)."""
    from utils import EXP_DAILY_TASK_FAVORITE
    return _try_award_daily_task(user_id, "add_favorite", EXP_DAILY_TASK_FAVORITE)


def _daily_track_id_for_gamification() -> Optional[str]:
    try:
        from yandex_music_service import get_daily_track
        t = get_daily_track()
        if not t:
            return None
        return str(t.get("id") or t.get("track_id") or "")
    except Exception:
        return None


def _after_review_gamification(user_id: int, track_id: str, was_new_track_rating: bool) -> dict:
    """Геймификация после сохранения оценки. Возвращает сводку для API."""
    out = {
        "streak": None,
        "streak_milestone_exp": 0,
        "daily_task_exp": 0,
        "referral_invitee_exp": 0,
        "referral_inviter_exp": 0,
    }
    if not was_new_track_rating:
        return out
    streak_info = _update_streak_for_user(user_id)
    out["streak"] = {"current": streak_info["current_streak"], "best": streak_info["best_streak"]}
    out["streak_milestone_exp"] = streak_info.get("milestone_exp_gained", 0)
    _check_achievements(user_id)

    from utils import EXP_DAILY_TASK_NEW_RATING, EXP_DAILY_TASK_DAILY_TRACK

    out["daily_task_exp"] += _try_award_daily_task(user_id, "new_rating", EXP_DAILY_TASK_NEW_RATING)
    daily_id = _daily_track_id_for_gamification()
    if daily_id and str(track_id) == str(daily_id):
        out["daily_task_exp"] += _try_award_daily_task(user_id, "rate_daily_track", EXP_DAILY_TASK_DAILY_TRACK)

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM reviews WHERE user_id = ?', (user_id,))
    total_reviews = cursor.fetchone()[0]
    if total_reviews != 1:
        conn.close()
        return out
    cursor.execute(
        'SELECT referrer_id, referral_welcome_exp_claimed, referral_inviter_bonus_paid FROM users WHERE user_id = ?',
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or not row[0]:
        return out
    referrer_id, welcome_done, inviter_done = int(row[0]), row[1] or 0, row[2] or 0
    from utils import EXP_REFERRAL_INVITEE_FIRST_REVIEW, EXP_REFERRAL_INVITER_FIRST_REVIEW

    if not welcome_done:
        add_exp(user_id, EXP_REFERRAL_INVITEE_FIRST_REVIEW)
        out["referral_invitee_exp"] = EXP_REFERRAL_INVITEE_FIRST_REVIEW
    if not inviter_done and referrer_id:
        add_exp(referrer_id, EXP_REFERRAL_INVITER_FIRST_REVIEW)
        out["referral_inviter_exp"] = EXP_REFERRAL_INVITER_FIRST_REVIEW
        try:
            from telegram_notify import schedule_notify_referral_first_review

            schedule_notify_referral_first_review(referrer_id, get_user_nickname(user_id) or "")
        except Exception:
            pass

    uconn = _connect()
    uc = uconn.cursor()
    if not welcome_done:
        uc.execute(
            'UPDATE users SET referral_welcome_exp_claimed = 1 WHERE user_id = ?',
            (user_id,),
        )
    if not inviter_done and referrer_id:
        uc.execute(
            'UPDATE users SET referral_inviter_bonus_paid = 1 WHERE user_id = ?',
            (user_id,),
        )
    uconn.commit()
    uconn.close()
    return out


def get_daily_tasks_status(user_id: int) -> list:
    """Состояние ежедневных заданий на сегодня (для API)."""
    day = _utc_today_str()
    meta = [
        {"id": "new_rating", "title": "Новая оценка", "description": "Оцени любой трек впервые сегодня", "exp": None},
        {"id": "rate_daily_track", "title": "Трек дня", "description": "Оцени сегодняшний трек дня", "exp": None},
        {"id": "add_favorite", "title": "В плейлист", "description": "Добавь любой трек в плейлист сегодня", "exp": None},
    ]
    from utils import EXP_DAILY_TASK_NEW_RATING, EXP_DAILY_TASK_DAILY_TRACK, EXP_DAILY_TASK_FAVORITE
    exp_map = {
        "new_rating": EXP_DAILY_TASK_NEW_RATING,
        "rate_daily_track": EXP_DAILY_TASK_DAILY_TRACK,
        "add_favorite": EXP_DAILY_TASK_FAVORITE,
    }
    conn = _connect()
    cursor = conn.cursor()
    out = []
    for m in meta:
        tid = m["id"]
        cursor.execute(
            'SELECT completed FROM user_daily_tasks WHERE user_id = ? AND day_utc = ? AND task_id = ?',
            (user_id, day, tid),
        )
        r = cursor.fetchone()
        done = bool(r and r[0])
        e = {**m, "completed": done, "exp_reward": exp_map.get(tid, 0)}
        out.append(e)
    conn.close()
    return out


def get_weekly_ratings_leaderboard(limit: int = 10) -> list:
    """Топ пользователей по числу оценок за текущую календарную неделю (UTC, с понедельника)."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = monday.strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT r.user_id, COUNT(*) as cnt, COALESCE(u.nickname, 'Игрок ' || r.user_id) as nick
        FROM reviews r
        LEFT JOIN users u ON u.user_id = r.user_id
        WHERE datetime(r.timestamp) >= datetime(?)
        GROUP BY r.user_id
        ORDER BY cnt DESC
        LIMIT ?
        ''',
        (week_start, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "reviews_count": r[1], "nickname": r[2]} for r in rows]


def _check_achievements(user_id: int):
    """Проверяет условия достижений и разблокирует подходящие (по уровню и количеству оценок)."""
    progress = get_user_progress(user_id)
    level = progress['level']
    streak = get_user_streak_data(user_id)
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM reviews WHERE user_id = ?', (user_id,))
    reviews_count = cursor.fetchone()[0]
    cursor.execute('SELECT COALESCE(daily_tasks_all_count, 0) FROM users WHERE user_id = ?', (user_id,))
    row_dc = cursor.fetchone()
    daily_all = row_dc[0] if row_dc else 0
    conn.close()
    unlocked = set(get_user_achievements(user_id))
    for ach in get_achievements_definitions():
        if ach['key'] in unlocked:
            continue
        ok = False
        if ach['condition_type'] == 'level' and level >= ach['condition_value']:
            ok = True
        if ach['condition_type'] == 'reviews_count' and reviews_count >= ach['condition_value']:
            ok = True
        if ach['condition_type'] == 'streak_days' and streak['current_streak'] >= ach['condition_value']:
            ok = True
        if ach['condition_type'] == 'daily_tasks_all' and daily_all >= ach['condition_value']:
            ok = True
        if ok:
            unlock_achievement(user_id, ach['key'])


def _parse_premium_until_iso(raw: Optional[str]):
    """Парсит premium_until из БД в aware UTC datetime или None."""
    if not raw or not str(raw).strip():
        return None
    from datetime import datetime, timezone
    try:
        s = str(raw).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def get_premium_status(user_id: int) -> dict:
    """
    Статус подписки Premium.
    active — сейчас действует; until — ISO окончания из БД (может быть в прошлом, если не продлевали).
    """
    from datetime import datetime, timezone
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT premium_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    raw = row[0] if row else None
    until_dt = _parse_premium_until_iso(raw)
    if not until_dt:
        return {"active": False, "until": None}
    now = datetime.now(timezone.utc)
    return {"active": until_dt > now, "until": raw}


def try_record_premium_payment_and_extend(
    user_id: int,
    telegram_charge_id: str,
    invoice_payload: str,
    total_amount: int,
    *,
    expected_payload: str,
    expected_amount: int,
    duration_days: int,
) -> tuple[bool, Optional[str]]:
    """
    Идемпотентная запись платежа Stars и продление premium_until.
    Возвращает (is_new_payment, premium_until_iso).
    При неверном payload/amount — (False, None).
    При дубликате charge_id — (False, текущий until из БД).
    """
    if not telegram_charge_id or invoice_payload != expected_payload or total_amount != expected_amount:
        return False, None
    if duration_days <= 0:
        return False, None

    from datetime import datetime, timedelta, timezone

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO premium_payments (telegram_charge_id, user_id, invoice_payload, total_amount)
        VALUES (?, ?, ?, ?)
        """,
        (telegram_charge_id, user_id, invoice_payload, total_amount),
    )
    inserted = cursor.rowcount > 0
    if not inserted:
        cursor.execute("SELECT premium_until FROM users WHERE user_id = ?", (user_id,))
        r2 = cursor.fetchone()
        conn.commit()
        conn.close()
        return False, (r2[0] if r2 else None)

    now = datetime.now(timezone.utc)
    cursor.execute("SELECT premium_until, nickname FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    base = now
    nick = f"User_{user_id}"
    if row:
        nick = row[1] or nick
        if row[0]:
            prev = _parse_premium_until_iso(row[0])
            if prev and prev > base:
                base = prev
    new_until = base + timedelta(days=duration_days)
    iso = new_until.isoformat()
    cursor.execute(
        "INSERT INTO users (user_id, nickname) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING",
        (user_id, nick),
    )
    cursor.execute("UPDATE users SET premium_until = ? WHERE user_id = ?", (iso, user_id))
    conn.commit()
    conn.close()
    return True, iso