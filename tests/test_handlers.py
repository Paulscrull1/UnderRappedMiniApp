"""Тесты обработчиков (логика, без реального Telegram)."""


def test_web_handler_normalize_ratings():
    """Нормализация оценок из Mini App: 5 критериев, значения 1–10."""
    from handlers.web_handler import _normalize_ratings
    from utils import CRITERIA
    r = _normalize_ratings({"rhymes": 3, "rhythm": 11, "style": 0})
    assert set(r.keys()) == set(CRITERIA)
    assert r["rhymes"] == 3
    assert r["rhythm"] == 10  # 11 → 10 (clip)
    assert r["style"] == 1   # 0 → 1 (clip min 1)
    r2 = _normalize_ratings({})
    assert all(1 <= r2[k] <= 10 for k in CRITERIA)


def test_build_card_caption():
    from handlers.track_card_handler import build_card_caption
    track = {"title": "Song", "artist": "Band", "genre": "Rock"}
    cap = build_card_caption(track)
    assert "Song" in cap
    assert "Band" in cap
    assert "Rock" in cap


def test_download_key():
    from handlers.track_card_handler import _download_key
    k = _download_key(123, "t:a")
    assert k == (123, "t:a")
