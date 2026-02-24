# database.py
import os
import sqlite3

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

    # Таблица пользователей: никнейм, профиль (аватар, описание, закреплённый трек)
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
    Сохраняет или обновляет никнейм пользователя
    """
    if not nickname or len(nickname.strip()) == 0:
        return
    nickname = nickname.strip()[:50]  # Ограничение длины

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, nickname)
        VALUES (?, ?)
    ''', (user_id, nickname))
    conn.commit()
    conn.close()


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
        'SELECT nickname, avatar_file_id, description, pinned_track_id, pinned_track_title, pinned_track_artist '
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


def save_review(user_id, track_id, ratings, track_title, track_artist, nickname, genre=None, review_text=None):
    """
    Сохраняет оценку трека и начисляет EXP.
    """
    total = sum(ratings.values())

    # Используем постоянный ник из БД, если есть; иначе — переданный
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

    from utils import EXP_FOR_RATING
    add_exp(user_id, EXP_FOR_RATING)


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
    Лидерборд по EXP: user_id, nickname, exp, level.
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.user_id, COALESCE(u.nickname, 'Пользователь ' || p.user_id), p.exp
        FROM user_progress p
        LEFT JOIN users u ON u.user_id = p.user_id
        ORDER BY p.exp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {'user_id': r[0], 'nickname': r[1] or f'User_{r[0]}', 'exp': r[2], 'level': 1 + r[2] // 100}
        for r in rows
    ]