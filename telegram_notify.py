# telegram_notify.py — фоновые уведомления пользователям в Telegram (Bot API)
import threading
from typing import Optional

import requests

import config


def escape_html(s: Optional[str]) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> None:
    token = (config.TELEGRAM_BOT_TOKEN or "").strip()
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=6,
        )
    except Exception:
        pass


def _run_async(target, *args, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    t.start()


def schedule_notify_level_up(user_id: int, new_level: int) -> None:
    text = (
        f"🎉 <b>Новый уровень!</b>\n"
        f"Ты достиг <b>{new_level}</b> уровня. Продолжай оценивать треки!"
    )
    _run_async(_send_message, user_id, text)


def schedule_notify_streak_milestone(user_id: int, days: int, exp_bonus: int) -> None:
    text = (
        f"🔥 <b>Стрик {days} дней!</b>\n"
        f"Серия активна. Бонус: <b>+{exp_bonus} EXP</b>."
    )
    _run_async(_send_message, user_id, text)


def schedule_notify_referral_first_review(referrer_id: int, friend_nickname: str) -> None:
    name = escape_html((friend_nickname or "").strip() or "Друг")
    text = (
        f"👥 <b>Реферал активен!</b>\n"
        f"{name} поставил(а) первую оценку. "
        f"Тебе начислен бонус EXP в игре."
    )
    _run_async(_send_message, referrer_id, text)
