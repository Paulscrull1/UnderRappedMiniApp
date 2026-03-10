# config.py
# Токены только из переменных окружения или .env (никогда не хранить в коде)
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
YANDEX_MUSIC_TOKEN = os.environ.get("YANDEX_MUSIC_TOKEN", "")
# Опционально: ID чата/канала для хранения аудио. Создай канал, добавь бота как админа,
# перешли любое сообщение из канала боту @userinfobot или @getidsbot — получишь ID (например -1001234567890).
# Тогда «Мои скачанные» копирует треки оттуда, а сообщение пользователю удаляется при «Назад в меню».
STORAGE_CHAT_ID = os.environ.get("STORAGE_CHAT_ID", "").strip() or None

# URL Mini App (HTTPS). Для разработки: ngrok или другой туннель.
MINI_APP_URL = os.environ.get("MINI_APP_URL", "").strip() or None

# Username бота без @ (для ссылок «Поделиться»). Добавь в .env: BOT_USERNAME=YourBotUsername
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").strip() or None

# SoundCloud API (для поиска и карточек треков). Один токен на всё приложение, обновляется по refresh_token.
SOUNDCLOUD_CLIENT_ID = os.environ.get("SOUNDCLOUD_CLIENT_ID", "").strip() or None
SOUNDCLOUD_CLIENT_SECRET = os.environ.get("SOUNDCLOUD_CLIENT_SECRET", "").strip() or None