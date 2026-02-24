# api_main.py — FastAPI-сервер для Telegram Mini App
import os
import sys

# Корень проекта для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

import config
from database import init_db
from telegram_validation import validate_init_data
from database import (
    get_user_progress,
    get_user_nickname,
    get_profile,
    get_leaderboard,
    save_review,
    get_last_reviews,
    get_favorites,
    add_favorite,
    remove_favorite,
    is_in_favorites,
    get_top_tracks_by_rating,
)
from yandex_music_service import get_daily_track, get_chart_tracks, search_tracks, get_track_by_id, get_playlist_tracks
from utils import CRITERIA, MAX_SCORE

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Music Bot Mini App API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_user_from_init_data(init_data: Optional[str] = None):
    if not init_data or not (init_data := init_data.strip()):
        raise HTTPException(status_code=401, detail="init_data_missing")
    if not config.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Server config error")
    user = validate_init_data(init_data, config.TELEGRAM_BOT_TOKEN)
    if not user:
        raise HTTPException(status_code=401, detail="init_data_invalid")
    return user


# --- Модели ---

class RatingPayload(BaseModel):
    track_id: str
    track_title: str
    track_artist: str
    rhymes: int
    rhythm: int
    style: int
    charisma: int
    vibe: int
    genre: Optional[str] = None
    review_text: Optional[str] = None


# --- Эндпоинты ---

@app.get("/tracks/daily")
def tracks_daily():
    """Трек дня."""
    track = get_daily_track()
    if not track:
        raise HTTPException(status_code=404, detail="Daily track not available")
    return track


@app.get("/tracks/chart")
def tracks_chart(limit: int = 20):
    """Чарт Яндекс.Музыки."""
    tracks = get_chart_tracks(limit=min(limit, 50))
    return {"tracks": tracks}


@app.get("/tracks/search")
def tracks_search(q: str = "", limit: int = 10):
    """Поиск треков."""
    if not q or len(q.strip()) == 0:
        return {"tracks": []}
    tracks = search_tracks(q.strip(), limit=min(limit, 20))
    return {"tracks": tracks}


@app.get("/tracks/playlist")
def tracks_playlist(url: str = "", limit: int = 50):
    """Треки из плейлиста Яндекс.Музыки по ссылке."""
    if not url or len(url.strip()) == 0:
        return {"tracks": []}
    tracks = get_playlist_tracks(url.strip(), limit=min(limit, 100))
    return {"tracks": tracks}


@app.get("/tracks/top")
def tracks_top(limit: int = 20):
    """Топ треков по среднему баллу сообщества. Всегда 200 и список (пустой при ошибке)."""
    try:
        tracks = get_top_tracks_by_rating(limit=min(limit, 50))
    except Exception:
        return {"tracks": []}
    from yandex_music_service import get_track_by_id
    out = []
    for t in tracks:
        tid = t.get("track_id")
        cover_url, track_url, genre = "", "", "—"
        if tid:
            try:
                full = get_track_by_id(tid)
                if full:
                    cover_url = full.get("cover_url") or ""
                    track_url = full.get("track_url") or ""
                    genre = full.get("genre") or "—"
            except Exception:
                pass
        out.append({
            "track_id": tid,
            "title": t.get("title") or "Без названия",
            "artist": t.get("artist") or "Неизвестен",
            "avg_score": t.get("avg_score", 0),
            "count": t.get("count", 0),
            "cover_url": cover_url,
            "track_url": track_url,
            "genre": genre,
        })
    return {"tracks": out}


@app.get("/tracks/{track_id}")
def track_by_id(track_id: str):
    """Трек по ID."""
    track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track


@app.get("/user/me")
def user_me(x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")):
    """Прогресс и профиль текущего пользователя (по initData)."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    user_id = int(user_id)
    progress = get_user_progress(user_id)
    profile = get_profile(user_id)
    nickname = get_user_nickname(user_id) or (profile.get("nickname") if profile else None)
    return {
        "user_id": user_id,
        "nickname": nickname or user.get("first_name", "Игрок"),
        "level": progress["level"],
        "exp": progress["exp"],
        "exp_to_next": 100 - (progress["exp"] % 100),
        "profile": profile,
    }


@app.get("/leaderboard")
def leaderboard(limit: int = 20):
    """Лидерборд по EXP."""
    leaders = get_leaderboard(limit=min(limit, 50))
    return {"leaders": leaders}


@app.get("/user/reviews")
def user_reviews(
    limit: int = 30,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Мои оценки (последние)."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    reviews = get_last_reviews(int(user_id), limit=min(limit, 50))
    return {"reviews": reviews}


@app.get("/user/favorites")
def user_favorites(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Моё избранное."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    favs = get_favorites(int(user_id), limit=100)
    return {"favorites": favs}


class FavoritePayload(BaseModel):
    track_id: str
    track_title: str
    track_artist: str


@app.post("/user/favorites")
def add_user_favorite(
    payload: FavoritePayload,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Добавить трек в избранное."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    add_favorite(
        int(user_id),
        payload.track_id,
        payload.track_title or "Без названия",
        payload.track_artist or "Неизвестен",
    )
    return {"ok": True}


@app.delete("/user/favorites/{track_id:path}")
def remove_user_favorite(
    track_id: str,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Убрать трек из избранного."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    remove_favorite(int(user_id), track_id)
    return {"ok": True}


@app.get("/user/favorites/check/{track_id:path}")
def check_favorite(
    track_id: str,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Проверить, в избранном ли трек."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    return {"in_favorites": is_in_favorites(int(user_id), track_id)}


@app.get("/criteria")
def criteria():
    """Критерии оценки для формы (названия и ключи)."""
    from utils import CRITERIA_NAMES
    return {
        "criteria": CRITERIA,
        "names": CRITERIA_NAMES,
        "max_score": MAX_SCORE,
    }


@app.post("/reviews")
def post_review(
    payload: RatingPayload,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Сохранить оценку трека. user_id берётся из валидного initData."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    user_id = int(user_id)

    ratings = {
        "rhymes": max(1, min(10, payload.rhymes)),
        "rhythm": max(1, min(10, payload.rhythm)),
        "style": max(1, min(10, payload.style)),
        "charisma": max(1, min(10, payload.charisma)),
        "vibe": max(1, min(10, payload.vibe)),
    }
    total = sum(ratings.values())

    save_review(
        user_id=user_id,
        track_id=payload.track_id,
        ratings=ratings,
        track_title=payload.track_title or "Без названия",
        track_artist=payload.track_artist or "Неизвестен",
        nickname=get_user_nickname(user_id) or user.get("first_name") or "Игрок",
        genre=payload.genre,
        review_text=payload.review_text,
    )
    return {
        "ok": True,
        "total": total,
        "exp_gained": 10,
    }


# Раздача статики Mini App (опционально: можно вынести на отдельный хост)
MINIAPP_DIR = os.path.join(os.path.dirname(__file__), "miniapp_static")


@app.get("/")
def miniapp_index():
    """Главная страница Mini App."""
    index_path = os.path.join(MINIAPP_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"app": "Music Bot Mini App API", "docs": "/docs"}


@app.get("/miniapp/{path:path}")
def miniapp_static(path: str):
    """Статика Mini App (js, css)."""
    full = os.path.join(MINIAPP_DIR, path)
    if not os.path.abspath(full).startswith(os.path.abspath(MINIAPP_DIR)):
        raise HTTPException(status_code=404)
    if os.path.isfile(full):
        return FileResponse(full)
    raise HTTPException(status_code=404)


def run_api(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_api(port=int(os.environ.get("MINIAPP_API_PORT", "8000")))
