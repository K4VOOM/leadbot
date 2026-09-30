**🇺🇦 [Українською](#leadbot--telegram-бот-для-збору-лідів) | 🇬🇧 [English](#leadbot--telegram-lead-generation-bot)**

---

# LeadBot — Telegram-бот для збору лідів

Telegram-бот на aiogram 3 для проведення квізу, збору заявок (лідів) і передачі їх менеджеру. Квіз описується YAML-конфігом, а не хардкодиться в коді — це основна ідея проєкту: новий клієнт або нова анкетна ніша підключаються через конфіг, без переписування логіки.

Проєкт уже є функціональним MVP: є користувачі, ліди, квіз, UTM-метки, менеджерські статуси, адмін-команди, Google Sheets і PostgreSQL.

## Стек

- Python 3.11+
- aiogram 3
- SQLAlchemy 2 + asyncpg
- PostgreSQL 16
- Alembic
- Pydantic + pydantic-settings
- PyYAML
- gspread
- Docker Compose

## Структура проєкту

```text
leadbot/
├── app/
│   ├── db/
│   │   ├── models.py
│   │   ├── repo.py
│   │   ├── session.py
│   │   └── __init__.py
│   ├── handlers/
│   │   ├── admin.py
│   │   ├── manager.py
│   │   ├── quiz.py
│   │   ├── start.py
│   │   └── __init__.py
│   ├── middlewares/
│   │   └── db.py
│   ├── quiz/
│   │   ├── engine.py
│   │   ├── keyboards.py
│   │   ├── loader.py
│   │   ├── schema.py
│   │   ├── sheets.py
│   │   └── __init__.py
│   ├── config.py
│   ├── main.py
│   └── __init__.py
├── alembic/
│   ├── env.py
│   └── versions/
├── configs/
│   └── quiz.yaml
├── .env
├── .env.example
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
├── secrets/
│   └── google_credentials.json
├── .gitignore
└── README.md
```

## Поточний стан

### ✅ Реалізовано

- запуск Telegram-бота через aiogram 3
- `/start` з підтримкою UTM у форматі `source-campaign`
- читання й валідація квізу з `configs/quiz.yaml`
- створення/пошук користувача в PostgreSQL
- збереження ліда з відповідями у таблиці `leads`
- перевірка повторної заявки за останні 24 години
- валідація для `choice`, `email`, `phone`, `text`
- скасування квізу через кнопку або текст
- надсилання менеджеру повідомлення з inline-статусами
- редагування статусу ліда через кнопки
- адмін-команди `/stats`, `/export`, `/broadcast`
- міграції через Alembic
- запис лідів у Google Sheets з логуванням помилок

### 🔧 Конфігурація

Основні параметри читаються з `.env` через `pydantic-settings`.

```env
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=[123456789, 987654321]

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/leadbot_db
POSTGRES_USER=user
POSTGRES_PASSWORD=change_me
POSTGRES_DB=leadbot_db
```

`app/config.py` завантажує `.env` від кореня проєкту і ігнорує зайві змінні, які приходять від Docker Compose.

### 📄 Конфіг квізу

```yaml
bot:
  welcome: "Привіт! Відповідь на 5 питань, і ми підберемо вам рішення 🙌"
  finish: "Дякуємо! Менеджер зв'яжеться з вами протягом години."
  manager_chat_id: -1001234567890

steps:
  - id: type
    text: "Що вас цікавить?"
    type: choice
    options: ["Квартира", "Будинок", "Комерція"]

  - id: phone
    text: "Залиште номер телефону"
    type: phone
```

Підтримувані типи кроків:

- `choice`
- `multi_choice`
- `text`
- `phone`
- `email`

## База даних

Модель даних має дві основні таблиці:

- `users`
  - `tg_id`
  - `username`
  - `first_name`
  - `utm_source`
  - `utm_campaign`
  - `subscribed`
  - `created_at`
- `leads`
  - `user_id`
  - `answers`
  - `status`
  - `created_at`

Статуси ліда:

- `new`
- `in_work`
- `closed`

## Адмін-функціонал

Адміністратори задаються через `ADMIN_IDS` у `.env`.

- `/stats` — лічильник лідів загалом та за сьогодні
- `/export` — CSV-експорт всіх лідів
- `/broadcast` — розсилка тексту всім підписаним користувачам

## Запуск локально

```bash
# 1. Запустити PostgreSQL
cd /path/to/project
docker compose up -d db

# 2. Встановити залежності
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Скопіювати .env
cp .env.example .env
# виправити значення у .env

# 4. Застосувати міграції
alembic upgrade head

# 5. Запустити бота
python -m app.main
```

## Примітки

- `.env` і `secrets/google_credentials.json` не додаються до git
- для Google Sheets потрібен сервісний акаунт і спільний доступ до таблиці
- `config.py` читає `.env` від кореня проєкту, тому запуск робочий незалежно від поточної директорії

**[⬆ Перемкнутись на English](#leadbot--telegram-lead-generation-bot)**

---
---

# LeadBot — Telegram lead-generation bot

**🇺🇦 [Українською](#leadbot--telegram-бот-для-збору-лідів) | 🇬🇧 [English](#leadbot--telegram-lead-generation-bot)**

A Telegram bot built with aiogram 3 that runs a quiz, collects leads, and forwards them to a manager. The questionnaire is defined in YAML instead of being hardcoded in Python — the project is designed so a new client or niche can be plugged in via configuration without rewriting business logic.

The project is already a working MVP: it includes users, leads, UTM tracking, manager statuses, admin commands, PostgreSQL storage, and Google Sheets export.

## Stack

- Python 3.11+
- aiogram 3
- SQLAlchemy 2 + asyncpg
- PostgreSQL 16
- Alembic
- Pydantic + pydantic-settings
- PyYAML
- gspread
- Docker Compose

## Project structure

```text
leadbot/
├── app/
│   ├── db/
│   │   ├── models.py
│   │   ├── repo.py
│   │   ├── session.py
│   │   └── __init__.py
│   ├── handlers/
│   │   ├── admin.py
│   │   ├── manager.py
│   │   ├── quiz.py
│   │   ├── start.py
│   │   └── __init__.py
│   ├── middlewares/
│   │   └── db.py
│   ├── quiz/
│   │   ├── engine.py
│   │   ├── keyboards.py
│   │   ├── loader.py
│   │   ├── schema.py
│   │   ├── sheets.py
│   │   └── __init__.py
│   ├── config.py
│   ├── main.py
│   └── __init__.py
├── alembic/
│   ├── env.py
│   └── versions/
├── configs/
│   └── quiz.yaml
├── .env
├── .env.example
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
├── secrets/
│   └── google_credentials.json
├── .gitignore
└── README.md
```

## Current state

### ✅ Implemented

- Telegram bot startup via aiogram 3
- `/start` with UTM support in `source-campaign` format
- quiz parsing and validation from `configs/quiz.yaml`
- creating/fetching a user in PostgreSQL
- storing leads with answers in the `leads` table
- duplicate lead protection for the last 24 hours
- validation for `choice`, `email`, `phone`, and `text`
- quiz cancellation via button or message text
- manager notifications with inline status actions
- lead status updates through callback buttons
- admin commands `/stats`, `/export`, and `/broadcast`
- Alembic migrations
- writing leads to Google Sheets with error logging

### 🔧 Configuration

Most settings are loaded from `.env` using `pydantic-settings`.

```env
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=[123456789, 987654321]

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/leadbot_db
POSTGRES_USER=user
POSTGRES_PASSWORD=change_me
POSTGRES_DB=leadbot_db
```

`app/config.py` loads `.env` from the project root and ignores extra variables coming from Docker Compose.

### 📄 Quiz config example

```yaml
bot:
  welcome: "Hello! Answer 5 questions and we'll find the best solution for you 🙌"
  finish: "Thank you! A manager will contact you within an hour."
  manager_chat_id: -1001234567890

steps:
  - id: type
    text: "What are you interested in?"
    type: choice
    options: ["Apartment", "House", "Commercial"]

  - id: phone
    text: "Leave your phone number"
    type: phone
```

Supported step types:

- `choice`
- `multi_choice`
- `text`
- `phone`
- `email`

## Database

The data model contains two main tables:

- `users`
  - `tg_id`
  - `username`
  - `first_name`
  - `utm_source`
  - `utm_campaign`
  - `subscribed`
  - `created_at`
- `leads`
  - `user_id`
  - `answers`
  - `status`
  - `created_at`

Lead statuses:

- `new`
- `in_work`
- `closed`

## Admin functionality

Admins are configured via `ADMIN_IDS` in `.env`.

- `/stats` — total and today's lead count
- `/export` — CSV export of all leads
- `/broadcast` — sends a text message to all subscribed users

## Running locally

```bash
# 1. Start PostgreSQL
docker compose up -d db

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Copy env settings
cp .env.example .env
# fill in the real values

# 4. Apply migrations
alembic upgrade head

# 5. Run the bot
python -m app.main
```

## Notes

- `.env` and `secrets/google_credentials.json` are not committed to git
- Google Sheets requires a service account and shared access to the spreadsheet
- `app/config.py` resolves `.env` from the project root, so it works regardless of the current working directory

**[⬆ Switch to Ukrainian](#leadbot--telegram-бот-для-збору-лідів)**
