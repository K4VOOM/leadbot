**🇺🇦 [Українською](#leadbot--telegram-бот-для-збору-лідів) | 🇬🇧 [English](#leadbot--telegram-lead-generation-bot)**

---

# LeadBot — Telegram-бот для збору лідів

Telegram-бот на aiogram 3 для проведення квізу, збору заявок (лідів) і передачі їх менеджеру. Квіз описується конфігом (YAML), а не хардкодиться в коді — це головна ідея проєкту: під нового клієнта на фрілансі можна підключити нову анкету без переписування логіки.

Пет-проєкт для портфоліо на фріланс. Стек обраний навмисно як "промисловий" рівень складності, а не мінімальний MVP.

## Стек

- **Python 3.14**
- **aiogram 3** — Telegram Bot API framework
- **PostgreSQL 16** — основна БД (у Docker)
- **SQLAlchemy 2.0 (async)** — ORM, стиль `Mapped[...]` / `mapped_column`
- **asyncpg** — асинхронний драйвер Postgres
- **Alembic** (async template) — міграції схеми БД
- **pydantic-settings** — конфіг з `.env`
- **Docker Compose** — локальний Postgres

Плановий, але ще не підключений стек:
- **Redis** — для FSM aiogram і кешу
- **Google Sheets (gspread)** — вивантаження лідів
- **APScheduler / Celery** — розсилки, нагадування

## Структура проєкту

```
leadbot/
├── alembic/
│   ├── env.py                    # налаштований на async engine + settings.database_url
│   └── versions/
│       └── 9bace4ced334_init.py       # початкова міграція: users, leads
├── app/
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py            # ORM-моделі: User, Lead
│   │   ├── repo.py              # get_or_create_user з on_conflict_do_nothing
│   │   └── session.py           # Base, async engine, async_sessionmaker
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── quiz.py              # обробка відповідей квізу, рух по кроках
│   │   └── start.py             # /start: UTM, get_or_create_user, ініціалізація квізу
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── db.py                # DbSessionMiddleware: сесія на кожен апдейт
│   ├── quiz/
│   │   ├── __init__.py
│   │   ├── engine.py            # QuizStates, get_current_step()
│   │   ├── loader.py            # load_quiz() — читання й валідація quiz.yaml
│   │   └── schema.py            # pydantic-моделі BotSetting, Step, Quiz
│   ├── __init__.py
│   ├── config.py                # Settings (pydantic-settings), читає .env; тут же завантажується quiz
│   └── main.py                  # точка входу, запуск polling, підключення роутерів і middleware
├── configs/
│   └── quiz.yaml                 # конфіг квізу: кроки, привітання, текст завершення
├── .env                            # секрети, НЕ в git
├── .env.example                     # шаблон для .env
├── .gitignore
├── alembic.ini
├── docker-compose.yml             # сервіс db (postgres:16), loopback-порт, healthcheck
└── requirements.txt
```

## Поточний стан (станом на сьогодні)

### ✅ Готово

**Інфраструктура**
- Docker + Docker Compose встановлені та налаштовані (Arch/CachyOS, потрібен був плагін `docker-compose` окремим пакетом і додавання користувача в групу `docker`)
- Postgres 16 піднятий у контейнері, порт відкритий тільки на `127.0.0.1` (безпечно для локальної розробки)
- Healthcheck на контейнері БД (`pg_isready`), `start_period: 10s`
- `docker-compose.yml` з `name: leadbot`, обов'язковим `POSTGRES_PASSWORD` через `.env` (`:?` синтаксис — падає, якщо не задано)
- PyCharm Docker Compose integration підключена й працює (Services tab, запуск сервісу прямо з IDE)

**Конфігурація**
- `app/config.py`: клас `Settings(BaseSettings)` з полями `bot_token`, `database_url`
- Шлях до `.env` будується від `Path(__file__).resolve().parent.parent`, тому конфіг працює незалежно від робочої директорії запуску
- `extra="ignore"` в `SettingsConfigDict`, щоб зайві змінні compose (`POSTGRES_USER` тощо) не ламали валідацію

**Шар БД**
- `app/db/session.py`: `Base` з кастомним `naming_convention` (`ix_`, `uq_`, `ck_`, `fk_`, `pk_` — узгоджені імена constraints для читабельних міграцій), async `engine` з `pool_pre_ping=True`, `async_sessionmaker` з `expire_on_commit=False`
- `app/db/models.py`:
  - `User`: `tg_id` (BigInteger, unique, indexed), `username`, `first_name`, `utm_source`, `utm_campaign`, `subscribed` (bool, default True), `created_at` (timezone-aware, server-side default)
  - `Lead`: `user_id` (FK на `users.id`, `ondelete=SET NULL`, nullable), `answers` (JSONB), `status` (default `"new"`), `created_at`
  - `relationship` в обидва боки (`User.leads` ↔ `Lead.user`)
- З'єднання з реальною БД перевірено (`SELECT 1` через async engine — працює)

**Міграції**
- Alembic ініціалізований з `-t async` шаблоном
- `env.py` налаштований: імпортує `Base` і моделі, `target_metadata = Base.metadata`, engine будується з `settings.database_url` (а не з `alembic.ini`)
- Перша міграція (`init`) згенерована і застосована: таблиці `users`, `leads`, `alembic_version` створені в БД
- Цикл `downgrade -1` → `upgrade head` перевірено, працює в обидва боки

**Шар доступу до даних**
- `app/db/repo.py`: функція `get_or_create_user(session, tg_id, username, first_name, utm_source, utm_campaign) -> User`. Логіка: `INSERT ... ON CONFLICT (tg_id) DO NOTHING`, потім `SELECT` за `tg_id`. UTM для існуючого юзера **не перезаписується** — зберігається перше джерело трафіку.
- Перевірено вручну через Python-консоль PyCharm: повторний виклик з тим самим `tg_id` не створює новий рядок і не перезаписує `username`/UTM

**Middleware**
- `app/middlewares/db.py`: `DbSessionMiddleware` — на кожен апдейт відкриває сесію SQLAlchemy, кладе в `data["session"]`, комітить після хендлера, робить rollback і прокидає виняток далі при помилці; підключений через `dp.update.outer_middleware(...)`
- Перевірено вручну: сесія доступна в хендлері, транзакція комітиться без винятків

**`/start` з UTM-мітками**
- Хендлер винесений у `app/handlers/start.py` через `Router()`, `echo_handler` прибраний з `main.py`
- Парсинг payload `/start fb-ads1` → `utm_source="fb"`, `utm_campaign="ads1"` через `CommandObject.args.split("-", 1)`, з обробкою порожнього payload і payload без дефіса
- Перевірено через psql: UTM зберігається правильно і не перезаписується при повторному `/start` з іншим payload

**Движок квізу (початок)**
- `app/quiz/schema.py`: pydantic-моделі `BotSetting`, `Step` (з `Literal` для типу кроку), `Quiz`
- `app/quiz/loader.py`: `load_quiz()` читає й валідує `configs/quiz.yaml` через `yaml.safe_load` + pydantic
- `app/quiz/engine.py`: `QuizStates` (один FSM-стан `in_progress`), `get_current_step(quiz, step_index)` — повертає поточний крок або `None`, якщо кроки закінчились
- Конфіг квізу завантажується один раз при старті (`quiz = load_quiz(QUIZ_PATH)` в `config.py`, на рівні модуля — Python кешує імпорт, тому файл читається рівно один раз)
- `/start` тепер ще й ініціалізує квіз: виставляє `step_index=0`, `answers={}`, стан `QuizStates.in_progress`, показує привітання і перше питання

**Обробка відповідей квізу**
- `app/handlers/quiz.py`: окремий хендлер на фільтр стану `QuizStates.in_progress`, реагує на будь-яке повідомлення користувача під час проходження квізу
- Логіка: зберігає відповідь у `answers[крок.id]`, збільшує `step_index`, показує наступне питання; на останньому кроці показує `quiz.bot.finish` і скидає стан
- Перевірено в реальному боті: питання приходять по порядку, після завершення бот більше не реагує на повідомлення (`is not handled` у логах — стан скинутий коректно)

**Збереження ліда в БД**
- По завершенню квізу створюється `Lead` з накопиченими `answers` (JSONB) і прив'язкою до `user.id` (через повторний виклик `get_or_create_user` за `tg_id`, який повертає вже існуючого юзера)
- `session.add(lead)` перед `state.clear()` — якщо збереження впаде, стан юзера не скидається, і відповіді не губляться
- Перевірено через psql: рядок у `leads` містить усі відповіді квізу, правильний `user_id`, `status="new"` і заповнений `created_at` (обидва — Python-side/server-side дефолти, нічого не передавалось вручну)

**Git**
- Репозиторій ініціалізований, `.env` і `.venv` не потрапляють у коміти
- `.env.example` з фейковими значеннями для нових розробників
- Комітиться поетапно, з осмисленими повідомленнями, після кожного перевіреного кроку

### 🚧 У процесі

- **Клавіатури для кроків типу `choice`/`multi_choice`** — побудова inline/reply-клавіатури з `options` кроку, замість очікування довільного тексту

### 📋 Заплановано (найближчі кроки)

1. **Валідація відповідей** — формат для `phone`/`email`, перевірка що вибір належить `options`
2. **Дедуп лідів** — той самий `tg_id` не створює новий лід протягом 24 год
3. **Сповіщення менеджеру** — повідомлення з відповідями + inline-кнопки "Взяв у роботу"/"Закрито", що міняють `Lead.status`
4. **Google Sheets інтеграція** — `gspread` (обгорнутий у `asyncio.to_thread`, щоб не блокував event loop), запис ліда з ретраєм, що не ламає основний потік при недоступності Google
5. **Адмінка в боті** — `/stats` (ліди за період з розбивкою по UTM), `/export` (CSV), `/broadcast` із сегментацією за відповідями квізу
7. **Розсилка** — rate limit ~20 повідомлень/сек, обробка `TelegramForbiddenError` (юзер заблокував бота → `subscribed=False`)

### 🔮 На перспективу (не пріоритет)

- Тести на `repo.py` і `engine.py` (pytest + testcontainers або окрема тестова БД)
- CI (GitHub Actions): лінт + тести на push
- Деплой на VPS/Railway з `docker-compose.prod.yml`
- Другий приклад `quiz.yaml` під іншу нішу — для демонстрації в портфоліо, що шаблон легко переналаштувати під нового клієнта
- Rate limiting і захист від спаму на рівні хендлерів

## Ключові архітектурні рішення

- **Квіз як дані, не код.** Уся анкета описується YAML-конфігом, движок читає й виконує його. Мета — підключати нового клієнта фріланс-заміною конфігу, а не переписуванням хендлерів.
- **Схема БД тільки через Alembic.** `Base.metadata.create_all()` у коді свідомо не використовується — щоб не розходитись зі станом міграцій і не ламати асинхронний engine (create_all вимагає синхронного з'єднання).
- **`ondelete=SET NULL` на `Lead.user_id`.** Ліди зберігаються навіть якщо юзера видалили з таблиці `users` — важливо для CRM-логіки, заявки не повинні зникати.
- **UTM зберігається один раз.** Перше джерело трафіку — істина в останній інстанції, повторні заходи через інший `/start`-параметр його не перезаписують.
- **`expire_on_commit=False` на сесіях.** Обов'язково для async SQLAlchemy — інакше звернення до атрибутів об'єкта після commit спричиняє помилку lazy-load у async-контексті.

## Відомі підводні камені (для себе на майбутнє)

- `naming_convention` треба задавати з самого початку — додавання пізніше означає переписування вже застосованих міграцій
- JSONB-поля (`Lead.answers`) SQLAlchemy не бачить як змінені при мутації `dict` на місці (`lead.answers["x"] = 1` не спрацює) — потрібен `MutableDict` або повне перезаписування поля
- Postgres читає `POSTGRES_USER`/`PASSWORD`/`DB` з `.env` тільки при першій ініціалізації порожнього volume — зміна пароля пізніше вимагає `ALTER USER` або `docker compose down -v`
- Група `docker` в Linux застосовується лише в нових сесіях/терміналах — після `usermod -aG docker` потрібен релогін, `newgrp` рятує лише поточний термінал
- В fish-шеллі активація venv — через `source .venv/bin/activate.fish`, а не звичайний `activate`

## Запуск локально

```bash
# 1. Підняти Postgres
docker compose up -d

# 2. Встановити залежності
python -m venv .venv
source .venv/bin/activate  # або .venv/bin/activate.fish для fish
pip install -r requirements.txt

# 3. Налаштувати .env (скопіювати з .env.example і заповнити)
cp .env.example .env

# 4. Застосувати міграції
alembic upgrade head

# 5. Запустити бота
python -m app.main
```

## Мета проєкту

Це перший з п'яти пет-проєктів для виходу на фріланс з Telegram-ботами:
1. Бот-магазин з оплатою і адмінкою
2. Бот запису на послуги (бронювання)
3. Бот платних підписок на закритий канал
4. **Лід-бот з квізом і CRM-інтеграцією ← цей проєкт**
5. AI-бот підтримки з базою знань (RAG)

Для портфоліо: живий демо-бот + другий `quiz.yaml` під іншу нішу, щоб наочно показати швидкість кастомізації під нового клієнта.

**[⬆ Перемкнутись на English](#leadbot--telegram-lead-generation-bot)**

---
---

# LeadBot — Telegram lead-generation bot

**🇺🇦 [Українською](#leadbot--telegram-бот-для-збору-лідів) | 🇬🇧 [English](#leadbot--telegram-lead-generation-bot)**

A Telegram bot built on aiogram 3 that runs a quiz, collects leads, and forwards them to a manager. The quiz is defined by a config file (YAML) rather than hardcoded in the code — that's the core idea of the project: onboarding a new freelance client should mean swapping a config, not rewriting logic.

A portfolio pet project for going freelance. The stack is deliberately chosen at a "production-grade" level of complexity rather than a minimal MVP.

## Stack

- **Python 3.14**
- **aiogram 3** — Telegram Bot API framework
- **PostgreSQL 16** — main database (in Docker)
- **SQLAlchemy 2.0 (async)** — ORM, `Mapped[...]` / `mapped_column` style
- **asyncpg** — async Postgres driver
- **Alembic** (async template) — database schema migrations
- **pydantic-settings** — config from `.env`
- **Docker Compose** — local Postgres

Planned but not yet wired in:
- **Redis** — for aiogram FSM and caching
- **Google Sheets (gspread)** — lead export
- **APScheduler / Celery** — broadcasts, reminders

## Project structure

```
leadbot/
├── alembic/
│   ├── env.py                    # configured for async engine + settings.database_url
│   └── versions/
│       └── 9bace4ced334_init.py       # initial migration: users, leads
├── app/
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py            # ORM models: User, Lead
│   │   ├── repo.py              # get_or_create_user with on_conflict_do_nothing
│   │   └── session.py           # Base, async engine, async_sessionmaker
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── quiz.py              # quiz answer handling, step progression
│   │   └── start.py             # /start: UTM, get_or_create_user, quiz initialization
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── db.py                # DbSessionMiddleware: a session per update
│   ├── quiz/
│   │   ├── __init__.py
│   │   ├── engine.py            # QuizStates, get_current_step()
│   │   ├── loader.py            # load_quiz() — reads and validates quiz.yaml
│   │   └── schema.py            # pydantic models BotSetting, Step, Quiz
│   ├── __init__.py
│   ├── config.py                # Settings (pydantic-settings), reads .env; also loads quiz
│   └── main.py                  # entry point, starts polling, wires up routers and middleware
├── configs/
│   └── quiz.yaml                 # quiz config: steps, welcome message, finish message
├── .env                            # secrets, NOT in git
├── .env.example                     # template for .env
├── .gitignore
├── alembic.ini
├── docker-compose.yml             # db service (postgres:16), loopback port, healthcheck
└── requirements.txt
```

## Current state (as of today)

### ✅ Done

**Infrastructure**
- Docker + Docker Compose installed and configured (Arch/CachyOS required the `docker-compose` plugin as a separate package, plus adding the user to the `docker` group)
- Postgres 16 running in a container, port exposed only on `127.0.0.1` (safe for local development)
- Healthcheck on the DB container (`pg_isready`), `start_period: 10s`
- `docker-compose.yml` with `name: leadbot`, mandatory `POSTGRES_PASSWORD` via `.env` (`:?` syntax — fails fast if not set)
- PyCharm Docker Compose integration connected and working (Services tab, running the service directly from the IDE)

**Configuration**
- `app/config.py`: a `Settings(BaseSettings)` class with `bot_token` and `database_url` fields
- The path to `.env` is built from `Path(__file__).resolve().parent.parent`, so the config works regardless of the working directory it's run from
- `extra="ignore"` in `SettingsConfigDict`, so extra compose variables (`POSTGRES_USER`, etc.) don't break validation

**Database layer**
- `app/db/session.py`: `Base` with a custom `naming_convention` (`ix_`, `uq_`, `ck_`, `fk_`, `pk_` — consistent constraint names for readable migrations), async `engine` with `pool_pre_ping=True`, `async_sessionmaker` with `expire_on_commit=False`
- `app/db/models.py`:
  - `User`: `tg_id` (BigInteger, unique, indexed), `username`, `first_name`, `utm_source`, `utm_campaign`, `subscribed` (bool, default True), `created_at` (timezone-aware, server-side default)
  - `Lead`: `user_id` (FK to `users.id`, `ondelete=SET NULL`, nullable), `answers` (JSONB), `status` (default `"new"`), `created_at`
  - `relationship` on both sides (`User.leads` ↔ `Lead.user`)
- Connection to the real database verified (`SELECT 1` through the async engine — works)

**Migrations**
- Alembic initialized with the `-t async` template
- `env.py` configured: imports `Base` and the models, `target_metadata = Base.metadata`, the engine is built from `settings.database_url` (not from `alembic.ini`)
- The first migration (`init`) generated and applied: `users`, `leads`, `alembic_version` tables created in the database
- The `downgrade -1` → `upgrade head` cycle verified, works both ways

**Data access layer**
- `app/db/repo.py`: the `get_or_create_user(session, tg_id, username, first_name, utm_source, utm_campaign) -> User` function. Logic: `INSERT ... ON CONFLICT (tg_id) DO NOTHING`, then `SELECT` by `tg_id`. UTM fields for an existing user are **not overwritten** — the first traffic source is kept.
- Manually verified via the PyCharm Python console: calling it again with the same `tg_id` doesn't create a new row and doesn't overwrite `username`/UTM

**Middleware**
- `app/middlewares/db.py`: `DbSessionMiddleware` — opens a SQLAlchemy session per update, puts it in `data["session"]`, commits after the handler runs, rolls back and re-raises on error; wired in via `dp.update.outer_middleware(...)`
- Manually verified: the session is available inside the handler, the transaction commits with no exceptions

**`/start` with UTM tags**
- The handler was moved into `app/handlers/start.py` via `Router()`, `echo_handler` removed from `main.py`
- Payload parsing `/start fb-ads1` → `utm_source="fb"`, `utm_campaign="ads1"` via `CommandObject.args.split("-", 1)`, handling empty payloads and payloads without a dash
- Verified via psql: UTM is stored correctly and isn't overwritten on a repeat `/start` with a different payload

**Quiz engine (started)**
- `app/quiz/schema.py`: pydantic models `BotSetting`, `Step` (with `Literal` for the step type), `Quiz`
- `app/quiz/loader.py`: `load_quiz()` reads and validates `configs/quiz.yaml` via `yaml.safe_load` + pydantic
- `app/quiz/engine.py`: `QuizStates` (a single FSM state, `in_progress`), `get_current_step(quiz, step_index)` — returns the current step or `None` once the steps run out
- The quiz config is loaded once at startup (`quiz = load_quiz(QUIZ_PATH)` in `config.py`, at module level — Python caches the import, so the file is read exactly once)
- `/start` now also initializes the quiz: sets `step_index=0`, `answers={}`, state `QuizStates.in_progress`, shows the welcome message and the first question

**Quiz answer handling**
- `app/handlers/quiz.py`: a separate handler filtered on state `QuizStates.in_progress`, reacting to any user message while the quiz is in progress
- Logic: stores the answer in `answers[step.id]`, increments `step_index`, shows the next question; on the last step shows `quiz.bot.finish` and clears the state
- Verified on the live bot: questions arrive in order, and after finishing the bot no longer reacts to messages (`is not handled` in the logs — the state was cleared correctly)

**Saving a lead to the database**
- Once the quiz finishes, a `Lead` is created with the accumulated `answers` (JSONB) linked to `user.id` (via another call to `get_or_create_user` by `tg_id`, which returns the already-existing user)
- `session.add(lead)` happens before `state.clear()` — if saving fails, the user's state isn't cleared and the answers aren't lost
- Verified via psql: the row in `leads` contains all quiz answers, the correct `user_id`, `status="new"`, and a populated `created_at` (both are Python-side/server-side defaults, nothing passed manually)

**Git**
- Repository initialized, `.env` and `.venv` are not committed
- `.env.example` with placeholder values for new contributors
- Committed incrementally, with meaningful messages, after each verified step

### 🚧 In progress

- **Keyboards for `choice`/`multi_choice` steps** — building an inline/reply keyboard from the step's `options`, instead of waiting for free-form text

### 📋 Planned (next steps)

1. **Answer validation** — format checks for `phone`/`email`, checking that a choice is among `options`
2. **Lead dedup** — the same `tg_id` doesn't create a new lead within 24 hours
3. **Manager notifications** — a message with the answers + inline buttons "In progress"/"Closed" that update `Lead.status`
4. **Google Sheets integration** — `gspread` (wrapped in `asyncio.to_thread` so it doesn't block the event loop), writing a lead with retries that don't break the main flow if Google is unavailable
5. **In-bot admin panel** — `/stats` (leads over a period, broken down by UTM), `/export` (CSV), `/broadcast` with segmentation by quiz answers
3. **Lead dedup** — the same `tg_id` doesn't create a new lead within 24 hours
4. **Manager notifications** — a message with the answers + inline buttons "In progress"/"Closed" that update `Lead.status`
5. **Google Sheets integration** — `gspread` (wrapped in `asyncio.to_thread` so it doesn't block the event loop), writing a lead with retries that don't break the main flow if Google is unavailable
6. **In-bot admin panel** — `/stats` (leads over a period, broken down by UTM), `/export` (CSV), `/broadcast` with segmentation by quiz answers
7. **Broadcasts** — rate limit of ~20 messages/sec, handling `TelegramForbiddenError` (user blocked the bot → `subscribed=False`)

### 🔮 Down the line (not a priority)

- Tests for `repo.py` and `engine.py` (pytest + testcontainers or a separate test database)
- CI (GitHub Actions): lint + tests on push
- Deployment to a VPS/Railway with `docker-compose.prod.yml`
- A second `quiz.yaml` example for a different niche — for the portfolio, to show how quickly the template can be reconfigured for a new client
- Rate limiting and spam protection at the handler level

## Key architectural decisions

- **Quiz as data, not code.** The entire questionnaire is described by a YAML config, and the engine reads and executes it. The goal is to onboard a new freelance client by swapping a config, not by rewriting handlers.
- **Schema managed only through Alembic.** `Base.metadata.create_all()` is deliberately not used in the code — to avoid drifting from the migration state and to avoid breaking the async engine (create_all requires a synchronous connection).
- **`ondelete=SET NULL` on `Lead.user_id`.** Leads are kept even if the user is deleted from the `users` table — important for CRM logic, submitted leads shouldn't disappear.
- **UTM is stored once.** The first traffic source is treated as the source of truth; returning through a different `/start` parameter doesn't overwrite it.
- **`expire_on_commit=False` on sessions.** Required for async SQLAlchemy — otherwise accessing object attributes after a commit triggers a lazy-load error in an async context.

## Known pitfalls (notes to self)

- `naming_convention` needs to be set from the very start — adding it later means rewriting migrations that were already applied
- JSONB fields (`Lead.answers`) aren't picked up by SQLAlchemy when mutated in place (`lead.answers["x"] = 1` won't work) — needs `MutableDict` or a full field reassignment
- Postgres only reads `POSTGRES_USER`/`PASSWORD`/`DB` from `.env` on the first initialization of an empty volume — changing the password later requires `ALTER USER` or `docker compose down -v`
- The `docker` group on Linux only applies in new sessions/terminals — after `usermod -aG docker` you need to re-login; `newgrp` only fixes the current terminal
- In the fish shell, activating a venv is done via `source .venv/bin/activate.fish`, not the regular `activate`

## Running locally

```bash
# 1. Start Postgres
docker compose up -d

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate  # or .venv/bin/activate.fish for fish
pip install -r requirements.txt

# 3. Set up .env (copy from .env.example and fill in)
cp .env.example .env

# 4. Apply migrations
alembic upgrade head

# 5. Run the bot
python -m app.main
```

## Project goal

This is the first of five Telegram bot pet projects for going freelance:
1. Storefront bot with payments and an admin panel
2. Booking bot for services
3. Paid subscription bot for a private channel
4. **Lead-gen bot with a quiz and CRM integration ← this project**
5. AI support bot with a knowledge base (RAG)

For the portfolio: a live demo bot + a second `quiz.yaml` for a different niche, to visibly demonstrate how fast the template can be customized for a new client.

**[⬆ Switch to Ukrainian](#leadbot--telegram-бот-для-збору-лідів)**