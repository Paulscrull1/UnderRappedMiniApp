# soundcloud_token.py
# Один токен на всё приложение: получаем по Client Credentials, храним и обновляем по refresh_token.
# Лимиты SoundCloud: 50 токенов/12ч на приложение, 30/1ч на IP — поэтому переиспользуем один токен.
import time
import threading
import requests

import config

_TOKEN_URL = "https://secure.soundcloud.com/oauth/token"
_CACHE = {}
_LOCK = threading.Lock()
# Обновлять за N секунд до истечения, чтобы не получить 401 в момент запроса
_REFRESH_BEFORE_EXPIRY = 120


def _now():
    return int(time.time())


def _request_token(grant_type, **extra_data):
    """Запрос токена: client_credentials или refresh_token."""
    if not config.SOUNDCLOUD_CLIENT_ID or not config.SOUNDCLOUD_CLIENT_SECRET:
        return None

    data = {"grant_type": grant_type}
    auth = (config.SOUNDCLOUD_CLIENT_ID, config.SOUNDCLOUD_CLIENT_SECRET)
    if grant_type == "client_credentials":
        # Только Basic auth и grant_type
        pass
    else:
        # refresh_token: в теле передаём client_id, client_secret, refresh_token
        data["client_id"] = config.SOUNDCLOUD_CLIENT_ID
        data["client_secret"] = config.SOUNDCLOUD_CLIENT_SECRET
        data["refresh_token"] = extra_data.get("refresh_token", "")

    resp = requests.post(
        _TOKEN_URL,
        auth=auth if grant_type == "client_credentials" else None,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


def _is_expired(expires_at):
    return _now() >= (expires_at - _REFRESH_BEFORE_EXPIRY)


def get_token():
    """
    Возвращает валидный access_token для заголовка Authorization.
    Один раз получает по Client Credentials, далее обновляет по refresh_token.
    Без ключей в config возвращает None.
    """
    if not config.SOUNDCLOUD_CLIENT_ID or not config.SOUNDCLOUD_CLIENT_SECRET:
        return None

    with _LOCK:
        access = _CACHE.get("access_token")
        expires_at = _CACHE.get("expires_at", 0)
        refresh = _CACHE.get("refresh_token")

        if access and not _is_expired(expires_at):
            return access

        # Нужен новый токен: refresh или первый запрос
        if refresh:
            body = _request_token("refresh_token", refresh_token=refresh)
        else:
            body = _request_token("client_credentials")

        if not body or "access_token" not in body:
            # Сбрасываем кэш, чтобы при следующем вызове попробовать client_credentials снова
            _CACHE.clear()
            return None

        expires_in = int(body.get("expires_in", 3600))
        _CACHE["access_token"] = body["access_token"]
        _CACHE["expires_at"] = _now() + expires_in
        if body.get("refresh_token"):
            _CACHE["refresh_token"] = body["refresh_token"]

        return _CACHE["access_token"]
