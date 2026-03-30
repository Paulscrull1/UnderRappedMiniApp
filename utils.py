# utils.py
import hashlib

# Хранение состояния пользователей
user_states = {}

# Критерии оценки
CRITERIA = ["rhymes", "rhythm", "style", "charisma", "vibe"]

# Человекочитаемые названия критериев
CRITERIA_NAMES = {
    "rhymes": "Рифмы/образы",
    "rhythm": "Структура/ритмика",
    "style": "Реализация стиля",
    "charisma": "Индивидуальность/харизма",
    "vibe": "Атмосфера/вайб",
}

# Максимальный балл (5 критериев × 10)
MAX_SCORE = 50

# Начисление EXP за действия
EXP_FOR_RATING = 10
EXP_FOR_REVIEW = 15
EXP_FOR_FAVORITE = 5
# Реферал: бонус пригласившему при привязке ref (бот /start ref_)
EXP_FOR_REFERRAL_LINK = 100
# Устаревшее имя — оставлено для совместимости импортов
EXP_FOR_REFERRAL = EXP_FOR_REFERRAL_LINK
# Приглашённый: первая оценка трека; пригласивший: когда приглашённый сделал первую оценку
EXP_REFERRAL_INVITEE_FIRST_REVIEW = 500
EXP_REFERRAL_INVITER_FIRST_REVIEW = 200

# Стрик: одноразовая награда при первом достижении вехи (текущий стрик дней)
EXP_STREAK_MILESTONE = {3: 50, 7: 120, 14: 200, 30: 500}

# Ежедневные задания (UTC), EXP один раз за день за каждое задание
EXP_DAILY_TASK_NEW_RATING = 25
EXP_DAILY_TASK_DAILY_TRACK = 40
EXP_DAILY_TASK_FAVORITE = 15

# Глобальное хранилище для сопоставления хэш → track_id
hash_to_track_id = {}


def level_progress_bar(level: int, exp: int, width: int = 10) -> str:
    """
    Строка прогресс-бара уровня: [████░░░░░░] 40 EXP до 2 уровня.
    exp — текущий EXP, level — текущий уровень; до следующего: (level * 100) - exp.
    """
    exp_in_level = exp % 100  # EXP в рамках текущего уровня (0..99)
    exp_to_next = 100 - exp_in_level
    if exp_to_next == 100 and exp > 0:
        exp_to_next = 100  # на границе уровня
    filled = (exp_in_level * width) // 100
    bar = "█" * filled + "░" * (width - filled)
    next_lvl = level + 1
    return f"[{bar}] {exp_to_next} EXP до {next_lvl} уровня"


def hash_id(track_id: str) -> str:
    """
    Создаёт короткий (10 символов) MD5-хэш из любого track_id.
    Используется для безопасной передачи в callback_data,
    чтобы не превысить лимит Telegram в 64 байта.
    """
    return hashlib.md5(track_id.encode('utf-8')).hexdigest()[:10]