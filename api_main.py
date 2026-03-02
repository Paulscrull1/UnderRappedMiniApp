# api_main.py — FastAPI-сервер для Telegram Mini App
import os
import sys

# Корень проекта для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

api = APIRouter()

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
    get_achievements_definitions,
    get_user_achievements,
    save_user_nickname,
    update_profile_description,
    update_profile_avatar_emoji,
    update_profile_avatar_url,
    clear_profile_avatar_custom,
    set_pinned_track,
    clear_pinned_track,
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


class ProfileUpdatePayload(BaseModel):
    nickname: Optional[str] = None
    description: Optional[str] = None
    avatar_emoji: Optional[str] = None
    pinned_track_id: Optional[str] = None
    pinned_track_title: Optional[str] = None
    pinned_track_artist: Optional[str] = None


# --- Эндпоинты (все под /api, чтобы не было 404 за прокси/туннелями) ---

@api.get("/config")
def app_config():
    """Публичный конфиг для фронта: bot_username для ссылок «Поделиться»."""
    return {"bot_username": (config.BOT_USERNAME or "").strip() or None}


@api.get("/tracks/daily")
def tracks_daily():
    """Трек дня."""
    track = get_daily_track()
    if not track:
        raise HTTPException(status_code=404, detail="Daily track not available")
    return track


@api.get("/tracks/chart")
def tracks_chart(limit: int = 20):
    """Чарт Яндекс.Музыки."""
    tracks = get_chart_tracks(limit=min(limit, 50))
    return {"tracks": tracks}


@api.get("/tracks/search")
def tracks_search(q: str = "", limit: int = 10):
    """Поиск треков."""
    if not q or len(q.strip()) == 0:
        return {"tracks": []}
    tracks = search_tracks(q.strip(), limit=min(limit, 20))
    return {"tracks": tracks}


@api.get("/tracks/playlist")
def tracks_playlist(url: str = "", limit: int = 50):
    """Треки из плейлиста Яндекс.Музыки по ссылке."""
    if not url or len(url.strip()) == 0:
        return {"tracks": []}
    tracks = get_playlist_tracks(url.strip(), limit=min(limit, 100))
    return {"tracks": tracks}


@api.get("/tracks/top")
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


@api.get("/tracks/{track_id}")
def track_by_id(track_id: str):
    """Трек по ID."""
    track = get_track_by_id(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track


@api.get("/user/me")
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
    unlocked_keys = set(get_user_achievements(user_id))
    achievements = []
    for a in get_achievements_definitions():
        achievements.append({
            "key": a["key"],
            "name_ru": a["name_ru"],
            "description_ru": a["description_ru"],
            "icon": a["icon"],
            "unlocked": a["key"] in unlocked_keys,
        })
    return {
        "user_id": user_id,
        "nickname": nickname or user.get("first_name", "Игрок"),
        "level": progress["level"],
        "exp": progress["exp"],
        "exp_to_next": 100 - (progress["exp"] % 100),
        "profile": profile,
        "achievements": achievements,
    }


@api.get("/leaderboard")
def leaderboard(limit: int = 20):
    """Лидерборд по EXP (в каждом элементе есть description — статус из профиля)."""
    leaders = get_leaderboard(limit=min(limit, 50))
    for row in leaders:
        row.setdefault("description", (row.get("description") or "").strip())
    return {"leaders": leaders}


@api.get("/user/reviews")
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


@api.get("/user/favorites")
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


@api.post("/user/favorites")
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


@api.delete("/user/favorites/{track_id:path}")
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


@api.get("/user/favorites/check/{track_id:path}")
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


ALLOWED_PROFILE_KEYS = frozenset(
    {"nickname", "description", "avatar_emoji", "pinned_track_id", "pinned_track_title", "pinned_track_artist"}
)


def _apply_profile_update(user_id: int, user: dict, body: dict):
    """Обновляет только те поля, ключи которых реально есть в теле запроса (сырой JSON).
    Аватар меняется только если клиент явно передал avatar_emoji в запросе."""
    data = {k: body[k] for k in body if k in ALLOWED_PROFILE_KEYS}
    if "nickname" in data and (str(data["nickname"] or "").strip()):
        save_user_nickname(user_id, str(data["nickname"]).strip()[:50])
    if "description" in data:
        update_profile_description(user_id, str(data["description"]) if data["description"] is not None else "")
    if "avatar_emoji" in data:
        val = str(data["avatar_emoji"] or "").strip()
        if val == "":
            clear_profile_avatar_custom(user_id)
        else:
            update_profile_avatar_emoji(user_id, val)
    if "pinned_track_id" in data:
        pid = str(data["pinned_track_id"] or "").strip()
        if pid == "":
            clear_pinned_track(user_id)
        else:
            save_user_nickname(user_id, get_user_nickname(user_id) or user.get("first_name") or "Игрок")
            set_pinned_track(
                user_id,
                pid,
                (str(data.get("pinned_track_title") or "").strip())[:200],
                (str(data.get("pinned_track_artist") or "").strip())[:200],
            )


async def _profile_update_body(request: Request):
    """Читаем тело как JSON-объект; только переданные ключи попадут в _apply_profile_update."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    return body


def _apply_profile_save_only(user_id: int, user: dict, body: dict):
    """Обновляет только статус (description), никнейм и закреплённый трек. Аватар не трогается никогда."""
    if "nickname" in body and (str(body.get("nickname") or "").strip()):
        save_user_nickname(user_id, str(body["nickname"]).strip()[:50])
    if "description" in body:
        update_profile_description(user_id, str(body["description"]) if body["description"] is not None else "")
    if "pinned_track_id" in body:
        pid = str(body.get("pinned_track_id") or "").strip()
        if pid == "":
            clear_pinned_track(user_id)
        else:
            save_user_nickname(user_id, get_user_nickname(user_id) or user.get("first_name") or "Игрок")
            set_pinned_track(
                user_id,
                pid,
                (str(body.get("pinned_track_title") or "").strip())[:200],
                (str(body.get("pinned_track_artist") or "").strip())[:200],
            )


@api.post("/user/profile/nickname")
async def post_profile_nickname(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Обновить только никнейм. Остальное не трогаем."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(body, dict) or "nickname" not in body:
        raise HTTPException(status_code=400, detail="Body must be { \"nickname\": \"...\" }")
    uid = int(user_id)
    val = str(body.get("nickname") or "").strip()[:50]
    if not val:
        raise HTTPException(status_code=400, detail="nickname cannot be empty")
    save_user_nickname(uid, val)
    return {"ok": True}


@api.post("/user/profile/status")
async def post_profile_status(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Обновить только статус (description). Остальное не трогаем."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    uid = int(user_id)
    if "description" in body:
        desc = str(body["description"]) if body["description"] is not None else ""
        update_profile_description(uid, desc)
    return {"ok": True}


@api.post("/user/profile/pinned")
async def post_profile_pinned(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Обновить только закреплённый трек. Аватар и статус не трогаем."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    uid = int(user_id)
    pid = str(body.get("pinned_track_id") or "").strip()
    if pid == "":
        clear_pinned_track(uid)
    else:
        save_user_nickname(uid, get_user_nickname(uid) or user.get("first_name") or "Игрок")
        set_pinned_track(
            uid,
            pid,
            (str(body.get("pinned_track_title") or "").strip())[:200],
            (str(body.get("pinned_track_artist") or "").strip())[:200],
        )
    return {"ok": True}


@api.patch("/user/profile")
async def patch_profile(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Обновить профиль (PATCH)."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    body = await _profile_update_body(request)
    _apply_profile_update(int(user_id), user, body)
    return {"ok": True}


@api.post("/user/profile")
async def post_profile(
    request: Request,
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Обновить профиль (POST) — для эмодзи/сброса аватара и т.д. Для сохранения статуса/ника/трека используйте POST /user/profile/save."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    body = await _profile_update_body(request)
    _apply_profile_update(int(user_id), user, body)
    return {"ok": True}


AVATARS_DIR = os.path.join(os.path.dirname(__file__), "avatars")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@api.post("/user/profile/avatar")
async def upload_profile_avatar(
    file: UploadFile = File(...),
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    """Загрузить картинку как аватар (из галереи)."""
    user = _get_user_from_init_data(x_telegram_init_data)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not in init data")
    user_id = int(user_id)
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Только изображения: JPEG, PNG, GIF, WebP")
    os.makedirs(AVATARS_DIR, exist_ok=True)
    ext = ".jpg" if "jpeg" in ct or "jpg" in ct else ".png" if "png" in ct else ".gif" if "gif" in ct else ".webp"
    filename = f"{user_id}{ext}"
    path = os.path.join(AVATARS_DIR, filename)
    try:
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Файл не более 5 МБ")
        with open(path, "wb") as f:
            f.write(contents)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка сохранения файла")
    avatar_url = f"/avatars/{filename}"
    update_profile_avatar_url(user_id, avatar_url)
    return {"ok": True, "avatar_url": avatar_url}


@api.get("/avatars/{filename:path}")
def get_avatar(filename: str):
    """Раздача загруженных аватарок."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404)
    path = os.path.join(AVATARS_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)


@api.get("/achievements")
def list_achievements():
    """Список всех достижений (к чему стремиться). Без авторизации."""
    out = []
    for a in get_achievements_definitions():
        out.append({
            "key": a["key"],
            "name_ru": a["name_ru"],
            "description_ru": a["description_ru"],
            "icon": a["icon"],
            "condition_type": a["condition_type"],
            "condition_value": a["condition_value"],
        })
    return {"achievements": out}


@api.get("/criteria")
def criteria():
    """Критерии оценки для формы (названия и ключи)."""
    from utils import CRITERIA_NAMES
    return {
        "criteria": CRITERIA,
        "names": CRITERIA_NAMES,
        "max_score": MAX_SCORE,
    }


@api.post("/reviews")
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

    unlocked_before = set(get_user_achievements(user_id))
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
    unlocked_after = set(get_user_achievements(user_id))
    new_achievement = (unlocked_after - unlocked_before).pop() if (unlocked_after - unlocked_before) else None
    ach_detail = None
    if new_achievement:
        for a in get_achievements_definitions():
            if a["key"] == new_achievement:
                ach_detail = {"key": a["key"], "name_ru": a["name_ru"], "icon": a["icon"]}
                break
    return {
        "ok": True,
        "total": total,
        "exp_gained": 10,
        "achievement_unlocked": ach_detail,
    }


app.include_router(api, prefix="/api")

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
