# music_providers.py
# Единая точка доступа к трекам: роутинг по track_id (Яндекс vs SoundCloud) и объединённый поиск.
from yandex_music_service import search_tracks as yandex_search, get_track_by_id as yandex_get_track
from soundcloud_service import (
    TRACK_ID_PREFIX,
    search_tracks as soundcloud_search,
    get_track_by_id as soundcloud_get_track,
)


def _is_soundcloud_id(track_id):
    return track_id and str(track_id).strip().startswith(TRACK_ID_PREFIX)


def get_track_by_id(track_id):
    """
    Возвращает словарь трека по id из любого источника.
    track_id вида 'sc_123' → SoundCloud, иначе → Яндекс.Музыка.
    """
    if not track_id:
        return None
    if _is_soundcloud_id(track_id):
        return soundcloud_get_track(track_id)
    return yandex_get_track(track_id)


def search_tracks(query, limit=10, sources=("yandex", "soundcloud")):
    """
    Поиск по всем включённым источникам. Объединяет результаты:
    сначала Яндекс (до half), затем SoundCloud (до half), всего до limit.
    Каждый трек в едином формате с полем source при необходимости.
    """
    if not query or not (q := str(query).strip()):
        return []
    cap = min(limit, 50)
    half = max(1, cap // 2)
    out = []
    if "yandex" in sources:
        for t in yandex_search(q, limit=half):
            if t and t.get("id"):
                out.append({**t, "source": t.get("source") or "yandex"})
    if "soundcloud" in sources:
        for t in soundcloud_search(q, limit=half):
            if t and t.get("id"):
                out.append(t)
    return out[:cap]
