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
│   │   ├── repo.py              # get_or_create_user, has_recent_lead, set_lead_status
│   │   └── session.py           # Base, async engine, async_sessionmaker
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── manager.py           # callback-кнопки статусу ліда для менеджера
│   │   ├── quiz.py              # обробка відповідей квізу, рух по кроках
│   │   └── start.py             # /start: UTM, get_or_create_user, ініціалізація квізу
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── db.py                # DbSessionMiddleware: сесія на кожен апдейт
│   ├── quiz/
│   │   ├── __init__.py
│   │   ├── engine.py            # QuizStates, get_current_step, validate_answer, notify_manager
│   │   ├── keyboards.py         # reply-клавіатура квізу, LeadAction, inline-кнопки статусу
│   │   ├── loader.py            # load_quiz() — читання й валідація quiz.yaml
│   │   ├── schema.py            # pydantic-моделі BotSetting, Step, Quiz
│   │   └── sheets.py            # append_lead_to_sheet() — запис ліда в Google Sheets
│   ├── __init__.py
│   ├── config.py                # Settings (pydantic-settings), читає .env; тут же завантажується quiz
│   └── main.py                  # точка входу, запуск polling, підключення роутерів і middleware
├── configs/
│   └── quiz.yaml                 # конфіг квізу: кроки, привітання, текст завершення
├── secrets/
│   └── google_credentials.json   # ключ сервісного акаунта Google, НЕ в git
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

**Клавіатури для `choice`-кроків**
- `app/quiz/keyboards.py`: `build_keyboard(step)` — будує reply-клавіатуру з `step.options` (через `ReplyKeyboardBuilder`) плюс кнопку "❌Скасувати"; для кроків без `options` повертає `ReplyKeyboardRemove()`, щоб клавіатура не висіла на текстових питаннях
- Клавіатура підключена в обох місцях показу питання — в `start.py` (перше питання) і `quiz.py` (наступні питання)
- Окремий хендлер `cancel_quiz_handler` на точний текст кнопки (`F.text == "❌Скасувати"`), зареєстрований **до** `quiz_answer_handler` у файлі — порядок реєстрації в aiogram визначає, який хендлер перехопить повідомлення першим
- Перевірено на живому боті: клавіатура з'являється на `choice`-кроках, зникає на текстових, скасування коректно чистить стан і забирає клавіатуру

**Валідація відповідей**
- У `quiz_answer_handler` розбір за типом кроку через `match current_step.type:`
- `choice` — перевірка, що `message.text` дійсно є серед `step.options`, інакше повторний запит з клавіатурою
- `email` — перевірка формату через регулярний вираз
- `phone` — нормалізація (прибирання пробілів, дефісів, `+`, коду країни `38`) і перевірка довжини на 10 цифр
- `text`/`multi_choice` — без додаткової валідації поки що
- При невдалій валідації квіз **не рухається далі**: `step_index` і `answers` не змінюються, користувачу показується повідомлення з проханням повторити

**Дедуп лідів**
- `app/db/repo.py`: `has_recent_lead(session, user_id, hours=24)` — перевіряє, чи є в юзера лід, створений пізніше за поріг `now() - 24h`
- `.scalars().first()` замість `.scalar_one_or_none()` — бо в юзера цілком може бути кілька лідів, і `scalar_one_or_none` впав би з `MultipleResultsFound`
- Підключено в `quiz_answer_handler`: якщо в юзера вже є недавній лід, новий не створюється, натомість інше повідомлення ("вже залишали заявку нещодавно"); `state.clear()` виконується в обох випадках, щоб бот не "зависав" мовчки для юзера з недавнім лідом

**Сповіщення менеджеру**
- `app/quiz/engine.py`: `format_lead_message(quiz, answers, status)` збирає текст питання разом з відповіддю для кожного кроку квізу (в порядку `quiz.steps`, а не по ключах `answers`) і дописує жирним поточний статус; відповіді клієнта екрануються через `html.quote`, щоб довільний ввід не ламав HTML-розмітку
- `notify_manager(bot, quiz, answers, lead_id)` надсилає зібраний текст у `quiz.bot.manager_chat_id`, обгорнуто в `try/except`: якщо надсилання впаде (неправильний chat_id, бот не в чаті), лід усе одно зберігається — сповіщення не критичне для збереження даних
- Виправлено формат `manager_chat_id`: для каналів/супергруп Bot API вимагає префікс `-100` перед "видимим" ID з клієнта Telegram
- **Рефакторинг**: валідація (`validate_answer`), побудова тексту і надсилання (`notify_manager`) винесені з `quiz_answer_handler` в `app/quiz/engine.py` — хендлер більше не перевантажений, кожна функція відповідає за одну річ

**Керування статусом ліда**
- Під повідомленням три inline-кнопки: "🆕 Нова", "✅ Взяв у роботу", "🔒 Закрито". Кнопки не зникають після натискання, поточний статус завжди видно жирним в кінці повідомлення
- `LeadAction(CallbackData, prefix="lead")` несе `lead_id` і `action`, тож aiogram сам розпаковує `lead:5:in_work` без ручного `split`
- `app/handlers/manager.py`: хендлер на `LeadAction.filter()` оновлює статус через `set_lead_status`, перебудовує текст **з БД** (БД лишається єдиним джерелом правди) і редагує повідомлення
- `await session.flush()` у `quiz_answer_handler` після `session.add(lead)`: `lead.id` призначає база при INSERT, а він потрібен для кнопок ще до коміту транзакції
- Обробка крайніх випадків: повторне натискання тієї ж кнопки (`message is not modified`) ігнорується; при `TelegramRetryAfter` (flood control на редагуванні) робиться `rollback`, щоб БД не розійшлась з тим, що бачить менеджер
- Перевірено наживо: статуси змінюються, кнопки лишаються

**Google Sheets інтеграція**
- Сервісний акаунт Google Cloud (Sheets API + Drive API увімкнені), ключ у `secrets/google_credentials.json` (поза git, шлях через `BASE_DIR`, як і `.env`/`quiz.yaml`)
- Таблиця розшарена з правами Editor на `client_email` сервісного акаунта — без цього `gspread` не бачить таблицю навіть із дійсним ключем
- `app/quiz/sheets.py`: синхронна логіка (`gspread`) винесена в `_append_row_sync`, викликається через `await asyncio.to_thread(...)`, щоб не блокувати event loop бота на час мережевого запиту до Google
- `append_lead_to_sheet(quiz, answers)` обгорнута в `try/except` з логуванням — якщо Google недоступний, лід усе одно зберігається в БД і сповіщення менеджеру все одно йде, обидва виклики незалежні один від одного
- Рядок у таблиці будується в порядку `quiz.steps`, той самий підхід, що і в `format_lead_message`
- Перевірено наживо: одне проходження квізу одночасно створює лід у БД, надсилає сповіщення в канал і дописує рядок у Google-таблицю

**Git**
- Репозиторій ініціалізований, `.env`, `.venv` і `secrets/` не потрапляють у коміти
- `.env.example` з фейковими значеннями для нових розробників
- Комітиться поетапно, з осмисленими повідомленнями, після кожного перевіреного кроку

### 🚧 У процесі

- **Адмінка в боті** — `/stats` (ліди за період з розбивкою по UTM), `/export` (CSV), `/broadcast` із сегментацією за відповідями квізу

### 📋 Заплановано (найближчі кроки)

1. **Розсилка** — rate limit ~20 повідомлень/сек, обробка `TelegramForbiddenError` (юзер заблокував бота → `subscribed=False`)

### 🔮 На перспективу (не пріоритет)

- Тести на `repo.py` і `engine.py` (pytest + testcontainers або окрема тестова БД)
- CI (GitHub Actions): лінт + тести на push
- Деплой на VPS/Railway з `docker-compose.prod.yml`
- Другий приклад `quiz.yaml` під іншу нішу — для демонстрації в портфоліо, що шаблон легко переналаштувати під нового клієнта
- Rate limiting і захист від спаму на рівні хендлерів
- Реальний ретрай (кілька спроб з бекофом) для запису в Google Sheets — зараз лише одна спроба з try/except і логуванням

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
│   │   ├── repo.py              # get_or_create_user, has_recent_lead, set_lead_status
│   │   └── session.py           # Base, async engine, async_sessionmaker
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── manager.py           # callback buttons for the lead status (manager side)
│   │   ├── quiz.py              # quiz answer handling, step progression
│   │   └── start.py             # /start: UTM, get_or_create_user, quiz initialization
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── db.py                # DbSessionMiddleware: a session per update
│   ├── quiz/
│   │   ├── __init__.py
│   │   ├── engine.py            # QuizStates, get_current_step, validate_answer, notify_manager
│   │   ├── keyboards.py         # quiz reply keyboard, LeadAction, inline status buttons
│   │   ├── loader.py            # load_quiz() — reads and validates quiz.yaml
│   │   ├── schema.py            # pydantic models BotSetting, Step, Quiz
│   │   └── sheets.py            # append_lead_to_sheet() — writes a lead to Google Sheets
│   ├── __init__.py
│   ├── config.py                # Settings (pydantic-settings), reads .env; also loads quiz
│   └── main.py                  # entry point, starts polling, wires up routers and middleware
├── configs/
│   └── quiz.yaml                 # quiz config: steps, welcome message, finish message
├── secrets/
│   └── google_credentials.json   # Google service account key, NOT in git
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

**Keyboards for `choice` steps**
- `app/quiz/keyboards.py`: `build_keyboard(step)` — builds a reply keyboard from `step.options` (via `ReplyKeyboardBuilder`) plus a "❌ Cancel" button; for steps without `options` it returns `ReplyKeyboardRemove()`, so the keyboard doesn't linger on text questions
- The keyboard is wired in at both places a question is shown — `start.py` (the first question) and `quiz.py` (subsequent questions)
- A separate `cancel_quiz_handler` matching the exact button text (`F.text == "❌Скасувати"`), registered **before** `quiz_answer_handler` in the file — in aiogram, registration order determines which handler catches a message first
- Verified on the live bot: the keyboard appears on `choice` steps, disappears on text steps, and cancelling correctly clears the state and removes the keyboard

**Answer validation**
- In `quiz_answer_handler`, branching by step type via `match current_step.type:`
- `choice` — checks that `message.text` is actually among `step.options`, otherwise re-asks with the keyboard
- `email` — format check via a regular expression
- `phone` — normalization (stripping spaces, dashes, `+`, the `38` country code) and a length check for 10 digits
- `text`/`multi_choice` — no extra validation yet
- On failed validation the quiz **doesn't advance**: `step_index` and `answers` stay unchanged, the user gets a message asking them to try again

**Lead dedup**
- `app/db/repo.py`: `has_recent_lead(session, user_id, hours=24)` — checks whether the user has a lead created after the threshold `now() - 24h`
- Uses `.scalars().first()` instead of `.scalar_one_or_none()` — since a user can well have multiple leads, and `scalar_one_or_none` would raise `MultipleResultsFound`
- Wired into `quiz_answer_handler`: if the user already has a recent lead, a new one isn't created; instead a different message is shown ("you've already submitted a request recently"); `state.clear()` runs in both branches so the bot doesn't silently hang for a user with a recent lead

**Manager notifications**
- `app/quiz/engine.py`: `format_lead_message(quiz, answers, status)` builds text pairing each step's question with its answer (in `quiz.steps` order, not by `answers` keys) and appends the current status in bold; client answers are escaped via `html.quote` so arbitrary input can't break the HTML markup
- `notify_manager(bot, quiz, answers, lead_id)` sends the built text to `quiz.bot.manager_chat_id`, wrapped in `try/except`: if sending fails (wrong chat_id, bot not in the chat), the lead is still saved — the notification isn't critical to data persistence
- Fixed the `manager_chat_id` format: for channels/supergroups the Bot API requires a `-100` prefix in front of the "visible" ID shown in the Telegram client
- **Refactor**: validation (`validate_answer`), text building, and sending (`notify_manager`) were extracted out of `quiz_answer_handler` into `app/quiz/engine.py` — the handler is no longer overloaded, each function has a single responsibility

**Lead status control**
- Three inline buttons under the message: "🆕 New", "✅ In progress", "🔒 Closed". The buttons don't disappear after a press, and the current status is always visible in bold at the end of the message
- `LeadAction(CallbackData, prefix="lead")` carries `lead_id` and `action`, so aiogram unpacks `lead:5:in_work` itself, with no manual `split`
- `app/handlers/manager.py`: a handler on `LeadAction.filter()` updates the status via `set_lead_status`, rebuilds the text **from the DB** (the DB stays the single source of truth), and edits the message
- `await session.flush()` in `quiz_answer_handler` after `session.add(lead)`: `lead.id` is assigned by the database on INSERT, and the buttons need it before the transaction commits
- Edge cases: pressing the same button again (`message is not modified`) is ignored; on `TelegramRetryAfter` (flood control on edits) a `rollback` is issued so the DB doesn't diverge from what the manager sees
- Verified live: statuses change, buttons stay

**Google Sheets integration**
- A Google Cloud service account (Sheets API + Drive API enabled), key stored at `secrets/google_credentials.json` (outside git, path built via `BASE_DIR`, same as `.env`/`quiz.yaml`)
- The spreadsheet is shared with Editor access to the service account's `client_email` — without this `gspread` can't see the sheet even with a valid key
- `app/quiz/sheets.py`: the synchronous logic (`gspread`) is isolated in `_append_row_sync`, called via `await asyncio.to_thread(...)` so it doesn't block the bot's event loop during the network call to Google
- `append_lead_to_sheet(quiz, answers)` is wrapped in `try/except` with logging — if Google is unavailable, the lead is still saved to the DB and the manager notification still goes out, the two calls are independent
- The row is built in `quiz.steps` order, the same approach used for `format_lead_message`
- Verified live: a single quiz run creates a lead in the DB, notifies the channel, and appends a row to the Google sheet, all at once

**Git**
- Repository initialized, `.env`, `.venv`, and `secrets/` are not committed
- `.env.example` with placeholder values for new contributors
- Committed incrementally, with meaningful messages, after each verified step

### 🚧 In progress

- **In-bot admin panel** — `/stats` (leads over a period, broken down by UTM), `/export` (CSV), `/broadcast` with segmentation by quiz answers

### 📋 Planned (next steps)

1. **Broadcasts** — rate limit of ~20 messages/sec, handling `TelegramForbiddenError` (user blocked the bot → `subscribed=False`)

### 🔮 Down the line (not a priority)

- Tests for `repo.py` and `engine.py` (pytest + testcontainers or a separate test database)
- CI (GitHub Actions): lint + tests on push
- Deployment to a VPS/Railway with `docker-compose.prod.yml`
- A second `quiz.yaml` example for a different niche — for the portfolio, to show how quickly the template can be reconfigured for a new client
- Rate limiting and spam protection at the handler level
- Real retry logic (several attempts with backoff) for Google Sheets writes — currently just one attempt with try/except and logging

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