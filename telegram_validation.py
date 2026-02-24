# telegram_validation.py
# Валидация initData от Telegram Mini App (HMAC-SHA256)
import hmac
import hashlib
import json
from urllib.parse import parse_qsl

# Максимальный возраст initData (секунды) — защита от replay (7 дней для учёта сдвига времени)
INIT_DATA_MAX_AGE = 604800  # 7 дней


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = INIT_DATA_MAX_AGE):
    """
    Проверяет подпись initData и опционально возраст auth_date.
    Возвращает dict с данными user (id, first_name, ...) или None при ошибке.

    Алгоритм Telegram (core.telegram.org):
    - data_check_string = все поля кроме hash, отсортированы по ключу, key=value через \\n
    - secret_key = HMAC_SHA256(key="WebAppData", message=bot_token)
    - computed_hash = HMAC_SHA256(key=secret_key, message=data_check_string).hex()
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True)
        received_hash = None
        auth_date = None
        check_pairs = []
        user_json = None
        for k, v in pairs:
            if k == "hash":
                received_hash = v
            elif k == "auth_date":
                auth_date = int(v) if v.isdigit() else None
                check_pairs.append((k, v))
            elif k == "user":
                user_json = v
                check_pairs.append((k, v))
            else:
                check_pairs.append((k, v))

        if not received_hash or not check_pairs:
            return None

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_pairs))
        # В документации: secret_key = HMAC(WebAppData как ключ, bot_token как сообщение)
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256,
        ).digest()
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return None

        if max_age_seconds and auth_date:
            import time
            if abs(time.time() - auth_date) > max_age_seconds:
                return None

        if user_json:
            user = json.loads(user_json)
            return user
        return {}
    except Exception:
        return None
