# soundcloud_service.py
# Поиск и получение треков SoundCloud в едином формате (id, title, artist, cover_url, genre, track_url, source).
import requests

from soundcloud_token import get_token

_API_BASE = "https://api.soundcloud.com"
TRACK_ID_PREFIX = "sc_"


def _auth_headers():
    token = get_token()
    if not token:
        return None
    return {"Accept": "application/json", "Authorization": f"OAuth {token}"}


def _sc_id_from_track_id(track_id):
    """Из нашего id 'sc_123456' возвращает числовой 123456."""
    if not track_id:
        return None
    s = str(track_id).strip()
    if s.startswith(TRACK_ID_PREFIX):
        try:
            return int(s[len(TRACK_ID_PREFIX) :])
        except ValueError:
            return None
    return None


def _to_track_dict(item):
    """Преобразует объект трека API в единый словарь для бота."""
    if not item or not isinstance(item, dict):
        return None
    tid = item.get("id")
    if tid is None:
        return None
    our_id = f"{TRACK_ID_PREFIX}{tid}"
    title = (item.get("title") or "").strip() or "Без названия"
    user = item.get("user") or {}
    artist = (user.get("full_name") or user.get("username") or "").strip() or "Неизвестен"
    cover_url = (item.get("artwork_url") or "").strip() or ""
    genre = (item.get("genre") or "").strip() or "—"
    track_url = (item.get("permalink_url") or "").strip() or ""
    if not track_url:
        track_url = f"https://soundcloud.com/search?q={artist}+{title}"
    return {
        "id": our_id,
        "title": title,
        "artist": artist,
        "cover_url": cover_url,
        "genre": genre,
        "track_url": track_url,
        "source": "soundcloud",
    }


def search_tracks(query, limit=10):
    """
    Поиск треков по запросу. Возвращает список словарей в едином формате.
    Только треки с доступным воспроизведением (playable или preview).
    """
    headers = _auth_headers()
    if not headers:
        return []
    try:
        resp = requests.get(
            f"{_API_BASE}/tracks",
            params={"q": query, "access": "playable,preview", "limit": min(limit, 50)},
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not isinstance(data, list):
            return []
        out = []
        for item in data[:limit]:
            d = _to_track_dict(item)
            if d:
                out.append(d)
        return out
    except Exception as e:
        print(f"soundcloud_service search_tracks error: {e}")
        return []


def get_track_by_id(track_id):
    """
    По нашему track_id (sc_123456) возвращает словарь трека или None.
    """
    sc_id = _sc_id_from_track_id(track_id)
    if sc_id is None:
        return None
    headers = _auth_headers()
    if not headers:
        return None
    try:
        resp = requests.get(
            f"{_API_BASE}/tracks/{sc_id}",
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        return _to_track_dict(resp.json())
    except Exception as e:
        print(f"soundcloud_service get_track_by_id error: {e}")
        return None


def download_track_bytes(track_id):
    """
    Скачивает трек как MP3. Возвращает (bytes, title, performer) или (None, None, None).
    Пробует /tracks/{id}/streams (http_mp3_128_url), при отсутствии — stream_url из объекта трека.
    """
    track = get_track_by_id(track_id)
    if not track:
        return None, None, None
    title = track.get("title") or "Track"
    performer = track.get("artist") or "Unknown"
    sc_id = _sc_id_from_track_id(track_id)
    if sc_id is None:
        return None, None, None
    headers = _auth_headers()
    if not headers:
        return None, None, None
    stream_url = None
    try:
        resp = requests.get(
            f"{_API_BASE}/tracks/{sc_id}/streams",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                stream_url = data.get("http_mp3_128_url") or data.get("preview_mp3_128_url")
        if not stream_url:
            track_resp = requests.get(
                f"{_API_BASE}/tracks/{sc_id}",
                headers=headers,
                timeout=10,
            )
            if track_resp.status_code == 200:
                tr = track_resp.json()
                if isinstance(tr, dict):
                    stream_url = tr.get("stream_url")
            if stream_url and not stream_url.startswith("http"):
                stream_url = (stream_url[:2] == "//" and "https:" + stream_url) or (stream_url.startswith("/") and _API_BASE.rstrip("/") + stream_url) or None
        if not stream_url:
            return None, None, None
        # Прямой URL с CDN может не требовать OAuth; stream_url с API — требует
        stream_resp = requests.get(stream_url, headers=headers, timeout=60, stream=True)
        stream_resp.raise_for_status()
        audio_bytes = stream_resp.content
        if not audio_bytes or len(audio_bytes) < 1024:
            return None, None, None
        return audio_bytes, title, performer
    except Exception as e:
        print(f"soundcloud_service download_track_bytes error: {e}")
        return None, None, None
