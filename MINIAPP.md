# Telegram Mini App — Музыкальная игра

Мини-приложение для прокачки за счёт прослушивания и оценки треков.

## Что сделано

- **API (FastAPI):** `api_main.py` — эндпоинты трек дня, чарт, поиск, профиль/EXP, лидерборд, сохранение оценки. Валидация `initData` Telegram.
- **Фронтенд:** `miniapp_static/index.html` — трек дня, форма оценки (5 критериев 1–10), лидерборд, отображение уровня/EXP.
- **Бот:** кнопка «🎮 Играть» в главном меню (если задан `MINI_APP_URL`). Обработчик `web_handler` принимает оценки из Mini App (формат приведён к 5 критериям, балл до 50).

## Запуск

### 1. Зависимости

```bash
pip install -r requirements.txt
```

### 2. Переменные окружения

В `.env` или окружении:

- `TELEGRAM_BOT_TOKEN` — токен бота
- `YANDEX_MUSIC_TOKEN` — токен Яндекс.Музыки (для трека дня и чарта)
- `MINI_APP_URL` — **HTTPS**-URL, по которому открывается Mini App (обязательно для кнопки «Играть»)

### 3. Запуск API (и раздача Mini App)

```bash
# Порт по умолчанию 8000
python api_main.py

# Или через uvicorn
uvicorn api_main:app --host 0.0.0.0 --port 8000
```

Главная страница `https://your-host/` отдаёт `miniapp_static/index.html`. Документация API: `https://your-host/docs`.

### 4. Доступ по HTTPS (для Telegram)

Telegram открывает Mini App только по **HTTPS**. Бесплатные варианты без платной подписки:

#### Вариант A: Cloudflare Tunnel (рекомендуется)

Бесплатно, без регистрации. Нужно установить `cloudflared` один раз.

1. Скачай [cloudflared](https://github.com/cloudflare/cloudflared/releases) для Windows (файл `cloudflared-windows-amd64.exe`), переименуй в `cloudflared.exe` и положи в папку из PATH или в папку проекта.
2. Запусти API: `python api_main.py` (порт 8000).
3. В **другом** терминале выполни:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   Если соединение обрывается (ошибки QUIC/timeout), попробуй принудительно HTTP/2:
   ```bash
   cloudflared tunnel --url http://localhost:8000 --protocol http2
   ```
4. В выводе появится строка вида `https://xxxx-xxxx.trycloudflare.com` — это твой HTTPS-URL. Пропиши его в `.env` как `MINI_APP_URL=...` и в BotFather (Menu Button / Configure Mini App).

При каждом новом запуске туннеля URL может меняться — тогда обновляй `MINI_APP_URL` и при необходимости настройки бота.

**Если в Mini App показывается «Cloudflare Tunnel Error»:**

1. **Туннель не запущен или URL устарел.** Сервис trycloudflare выдаёт **новый URL при каждом запуске** cloudflared. Старый адрес перестаёт работать.
2. Убедись, что **API запущен**: в одном терминале `python api_main.py` (должен слушать порт 8000).
3. В **втором** терминале запусти туннель:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   или из папки проекта: `.\cloudflared.exe tunnel --url http://localhost:8000`
4. В выводе cloudflared скопируй строку вида `https://xxxx-xxxx.trycloudflare.com`.
5. Пропиши этот URL в `.env`: `MINI_APP_URL=https://новый-url.trycloudflare.com`
6. В [BotFather](https://t.me/BotFather) → твой бот → Menu Button → Configure Mini App — укажи тот же URL.
7. Перезапусти бота (`python main.py`) и снова открой Mini App из Telegram.

Если туннель рвётся (ошибки QUIC/timeout), попробуй: `cloudflared tunnel --url http://localhost:8000 --protocol http2`

#### Вариант B: localtunnel (через Node.js)

Если установлен Node.js:

```bash
npx localtunnel --port 8000
```

Выдаст URL вида `https://something.loca.lt`. Иногда при первом заходе показывается страница «Click to continue» — для Telegram Mini App может быть неудобно; лучше пробовать Cloudflare.

#### Вариант C: Продакшен

Размести приложение на хостинге с HTTPS (VPS + nginx, Railway, Render и т.п.) — тогда URL постоянный и не зависит от туннеля.

### 5. Бот

Запуск бота как раньше:

```bash
python main.py
```

Если `MINI_APP_URL` задан, в главном меню появится кнопка «🎮 Играть», открывающая Mini App.

## Поведение Mini App

1. Пользователь нажимает «Играть» в боте → открывается веб-страница по `MINI_APP_URL`.
2. Страница запрашивает у API трек дня, критерии оценки и (с заголовком `X-Telegram-Init-Data`) данные пользователя (уровень, EXP).
3. Пользователь переходит по ссылке «Слушать в Яндексе», слушает трек, выставляет оценки по 5 критериям (слайдеры 1–10) и нажимает «Отправить оценку».
4. API проверяет `initData`, сохраняет оценку в БД и начисляет EXP. В интерфейсе отображается «+10 EXP» и обновлённый уровень.

Оценки из Mini App и из бота (кнопки в чате) пишутся в одну БД и влияют на один и тот же прогресс пользователя.
