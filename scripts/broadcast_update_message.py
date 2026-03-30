#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Разовая рассылка пользователям бота (запуск вручную).

Запуск из корня проекта или из папки scripts/ — путь к БД и .env берутся от корня репозитория.

  python scripts/broadcast_update_message.py
  cd scripts && python broadcast_update_message.py

  python scripts/broadcast_update_message.py --dry-run
  python scripts/broadcast_update_message.py --yes   # без подтверждения y/N

Нужны TELEGRAM_BOT_TOKEN и (при другом пути) переменная MUSIC_BOT_DB — как у основного бота.
"""
from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import config  # noqa: E402
from database import DATABASE_PATH  # noqa: E402


def resolved_database_path() -> Path:
    """Путь к SQLite: абсолютный как есть, относительный — от корня проекта (не от cwd)."""
    p = Path(DATABASE_PATH)
    if p.is_absolute():
        return p.resolve()
    return (ROOT / p).resolve()

from telegram import Bot
from telegram.error import Forbidden, TelegramError

BROADCAST_TEXT = (
    "Забыли сказать, удобнее всего, пользоваться приложением через Mini App. "
    "Для этого нажми Кнопку играть, или кнопку Mini App"
    " И не забудь включить VP*, Роскомпозор не дремлет!"
)

# Пауза между отправками (сек.), чтобы не упираться в лимиты Telegram
SEND_DELAY_SEC = 0.06


def collect_recipient_ids(db_path: str | Path) -> list[int]:
    """Все уникальные положительные user_id из таблиц, где они встречаются."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ids: set[int] = set()
    sources = [
        ("users", "user_id"),
        ("reviews", "user_id"),
        ("user_favorites", "user_id"),
        ("user_progress", "user_id"),
        ("user_downloads", "user_id"),
    ]
    for table, col in sources:
        try:
            for row in cur.execute(f"SELECT DISTINCT {col} AS u FROM {table} WHERE {col} IS NOT NULL"):
                uid = row["u"]
                if uid is None:
                    continue
                try:
                    i = int(uid)
                except (TypeError, ValueError):
                    continue
                if i > 0:
                    ids.add(i)
        except sqlite3.OperationalError:
            pass
    conn.close()
    return sorted(ids)


async def run_broadcast(recipients: list[int], *, dry_run: bool) -> None:
    token = (config.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        print("Ошибка: не задан TELEGRAM_BOT_TOKEN (.env или окружение).")
        sys.exit(1)

    bot = Bot(token)
    ok = 0
    failed: list[tuple[int, str]] = []

    async with bot:
        for uid in recipients:
            if dry_run:
                print(f"[dry-run] отправил бы: chat_id={uid}")
                ok += 1
                continue
            try:
                await bot.send_message(chat_id=uid, text=BROADCAST_TEXT)
                ok += 1
                print(f"OK {uid}")
            except Forbidden:
                failed.append((uid, "бот заблокирован или пользователь недоступен"))
                print(f"SKIP {uid}: Forbidden")
            except TelegramError as e:
                failed.append((uid, str(e)))
                print(f"ERR {uid}: {e}")
            await asyncio.sleep(SEND_DELAY_SEC)

    print(f"\nИтого: успешно {ok}, ошибок/пропусков {len(failed)}")
    if failed and not dry_run:
        for uid, reason in failed[:30]:
            print(f"  — {uid}: {reason}")
        if len(failed) > 30:
            print(f"  … и ещё {len(failed) - 30}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Рассылка текста об обновлении пользователям из БД.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только показать chat_id, без отправки",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="не спрашивать подтверждение в консоли",
    )
    args = parser.parse_args()

    db_path = resolved_database_path()
    if not db_path.is_file():
        print(f"Ошибка: файл БД не найден: {db_path}")
        sys.exit(1)

    recipients = collect_recipient_ids(db_path)
    print(f"База: {db_path}")
    print(f"Уникальных получателей: {len(recipients)}")
    print(f"Текст сообщения:\n{BROADCAST_TEXT}\n")

    if not recipients:
        print("Некому отправлять — в БД нет user_id.")
        sys.exit(0)

    if args.dry_run:
        asyncio.run(run_broadcast(recipients, dry_run=True))
        return

    if not args.yes:
        ans = input(f"Отправить сообщение {len(recipients)} пользователям? [y/N]: ").strip().lower()
        if ans not in ("y", "yes", "д", "да"):
            print("Отменено.")
            sys.exit(0)

    asyncio.run(run_broadcast(recipients, dry_run=False))


if __name__ == "__main__":
    main()
