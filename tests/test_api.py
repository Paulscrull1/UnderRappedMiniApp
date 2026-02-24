"""Тесты API Mini App (FastAPI): публичные эндпоинты и формат ответов."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(temp_db):
    """Клиент FastAPI с подставленной тестовой БД."""
    import database
    import api_main
    return TestClient(api_main.app)


def test_criteria_returns_200_and_structure(client):
    """GET /criteria доступен без авторизации, возвращает критерии и max_score."""
    r = client.get("/criteria")
    assert r.status_code == 200
    data = r.json()
    assert "criteria" in data
    assert "names" in data
    assert data.get("max_score") == 50
    assert len(data["criteria"]) == 5


def test_tracks_chart_returns_200(client):
    """GET /tracks/chart возвращает список треков (может быть пустой без токена)."""
    r = client.get("/tracks/chart?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert "tracks" in data
    assert isinstance(data["tracks"], list)


def test_tracks_search_empty_returns_empty(client):
    """GET /tracks/search без q возвращает пустой список."""
    r = client.get("/tracks/search")
    assert r.status_code == 200
    assert r.json() == {"tracks": []}


def test_tracks_playlist_empty_url_returns_empty(client):
    """GET /tracks/playlist без url возвращает пустой список."""
    r = client.get("/tracks/playlist")
    assert r.status_code == 200
    assert r.json() == {"tracks": []}


def test_user_me_requires_init_data(client):
    """GET /user/me без X-Telegram-Init-Data возвращает 401."""
    r = client.get("/user/me")
    assert r.status_code == 401


def test_leaderboard_returns_200(client):
    """GET /leaderboard доступен без авторизации."""
    r = client.get("/leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert "leaders" in data
    assert isinstance(data["leaders"], list)


def test_root_serves_index_or_json(client):
    """GET / отдаёт index.html или JSON при отсутствии файла."""
    r = client.get("/")
    assert r.status_code == 200
    # Если есть miniapp_static/index.html — отдаётся HTML
    if "text/html" in r.headers.get("content-type", ""):
        assert b"<!DOCTYPE html>" in r.content or b"<html" in r.content
    else:
        assert "app" in r.json() or "docs" in r.json()
