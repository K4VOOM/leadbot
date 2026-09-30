**🇺🇦 [Українською](#технічна-документація) | 🇬🇧 [English](#technical-documentation)**

---

# Технічна документація

Цей файл доповнює [README.md](./README.md): тут — чому проєкт зроблений саме так, що вже перевірено наживо на кожному кроці, і на яких граблях уже наступали. Короткий опис фіч і команд запуску — у README, тут — глибина для тих, хто хоче зрозуміти рішення, а не тільки список можливостей.

## Ключові архітектурні рішення

- **Квіз як дані, не код.** Уся анкета описується YAML-конфігом (`configs/quiz.yaml`), движок (`app/quiz/engine.py`) лише читає й виконує його. Мета — підключати нового фріланс-клієнта заміною конфігу, а не переписуванням хендлерів.
- **Схема БД тільки через Alembic.** `Base.metadata.create_all()` у коді свідомо не використовується — щоб не розходитись зі станом міграцій і не ламати асинхронний engine (`create_all` вимагає синхронного з'єднання).
- **`ondelete=SET NULL` на `Lead.user_id`.** Ліди зберігаються навіть якщо юзера видалили з таблиці `users` — важливо для CRM-логіки, заявки не повинні зникати разом з юзером.
- **UTM зберігається один раз.** Перше джерело трафіку — істина в останній інстанції; повторні заходи через інший `/start`-параметр його не перезаписують (`get_or_create_user` навмисно не робить `on_conflict_do_update`).
- **`expire_on_commit=False` на сесіях.** Обов'язково для async SQLAlchemy — інакше звернення до атрибутів об'єкта після `commit()` спричиняє помилку lazy-load у async-контексті.
- **`repo.py` не комітить сам.** Функції доступу до даних лише формують і виконують запити; `commit`/`rollback` — відповідальність `DbSessionMiddleware`. Це дозволяє викликати кілька repo-функцій в одній транзакції з одного хендлера.
- **Сповіщення й зовнішні інтеграції не блокують збереження ліда.** `notify_manager` і `append_lead_to_sheet` обидва обгорнуті у власний `try/except` — якщо Telegram чи Google недоступні, лід все одно є в БД. Ці виклики навмисно незалежні один від одного.

## Відомі підводні камені (для себе на майбутнє)

- `naming_convention` для `MetaData` треба задавати з самого початку проєкту — додавання пізніше означає переписування вже застосованих міграцій.
- JSONB-поля (`Lead.answers`) SQLAlchemy не бачить як змінені при мутації `dict` на місці (`lead.answers["x"] = 1` не спрацює і не потрапить у UPDATE) — потрібен `MutableDict` або повне перезаписування поля новим об'єктом.
- Postgres читає `POSTGRES_USER`/`PASSWORD`/`DB` з `.env` тільки при **першій** ініціалізації порожнього volume. Зміна пароля пізніше в `.env` нічого не змінить у самій БД — потрібен `ALTER USER` вручну або `docker compose down -v` (це видалить дані).
- Група `docker` в Linux застосовується лише в нових сесіях/терміналах — після `usermod -aG docker $USER` потрібен повний релогін; `newgrp docker` рятує лише поточний термінал.
- У fish-шеллі активація venv — через `source .venv/bin/activate.fish`, а не звичайний `activate` (той написаний під bash/zsh і впаде з синтаксичною помилкою у fish).
- `chat_id` для каналів і супергруп у Bot API **завжди** з префіксом `-100` перед "видимим" числовим ID, який показує клієнт Telegram — пряме використання видимого ID дає `chat not found`.
- `scalar_one_or_none()` падає з `MultipleResultsFound`, якщо збігів більше одного — для перевірки "чи існує хоч один рядок" безпечніше `scalars().first()`.
- `lead.id` не існує, поки рядок не потрапив у БД. Якщо `id` потрібен одразу після `session.add(...)` (наприклад, для callback-кнопок), треба явний `await session.flush()` до коміту.
- Редагування Telegram-повідомлення з тим самим текстом і клавіатурою кидає `TelegramBadRequest: message is not modified` — це очікувана поведінка API, а не помилка коду, і її варто явно ігнорувати.
- Часті `edit_text` на одному повідомленні впираються в `TelegramRetryAfter` (flood control) — вартий уваги випадок, коли DB-транзакцію тоді краще відкотити, щоб стан у БД не розійшовся з тим, що бачить користувач.

## Історія розробки по кроках

Нижче — хронологічний журнал того, що було зроблено, перевірено і чому саме так, від підняття Docker до робочого MVP.

### Крок 0. Docker і Postgres
Docker + `docker-compose` плагін встановлені окремо (Arch Linux не ставить його разом з `docker`). Postgres 16 піднятий у контейнері, порт `127.0.0.1:5432` — тільки для локальної розробки. `docker-compose.yml` вимагає `POSTGRES_PASSWORD` явно (`:?` синтаксис), щоб не піднімався з порожнім паролем за замовчуванням.

### Крок 1. Конфіг (`app/config.py`)
`Settings(BaseSettings)` з `pydantic-settings`, читає `.env`. Шлях до `.env` будується від `Path(__file__).resolve().parent.parent`, а не як відносний рядок — тому конфіг працює однаково з термінала, з PyCharm, і незалежно від робочої директорії запуску. `extra="ignore"` — щоб змінні, потрібні лише для Docker Compose (`POSTGRES_USER` тощо), не ламали валідацію pydantic.

### Крок 2. Сесія БД (`app/db/session.py`)
`Base` з кастомним `naming_convention` (задано одразу, до першої міграції — інакше довелось би переписувати застосовані міграції). Async `engine` з `pool_pre_ping=True` (не падати на "мертвих" з'єднаннях після рестарту Postgres). `async_sessionmaker` з `expire_on_commit=False`.

### Крок 3. Моделі (`app/db/models.py`)
`User` і `Lead` через SQLAlchemy 2.0 стиль (`Mapped[...]`/`mapped_column`). `tg_id` — `BigInteger`, бо Telegram ID виходять за межі int32. `Lead.answers` — `JSONB`. `Lead.user_id` — `ForeignKey("users.id", ondelete="SET NULL")`, nullable.

### Крок 4. Alembic
Ініціалізований з `-t async` шаблоном. `env.py` імпортує `Base` і самі моделі (без цього `target_metadata` не бачить таблиць і autogenerate видає порожню міграцію), URL береться з `settings.database_url`, а не з `alembic.ini`. Перша міграція застосована, цикл `downgrade -1` → `upgrade head` перевірений в обидва боки.

### Крок 5. `get_or_create_user` і `/start` з UTM
`repo.py`: `INSERT ... ON CONFLICT (tg_id) DO NOTHING` + `SELECT` за `tg_id` — атомарна вставка без гонки. UTM з payload `/start fb-ads1` розбирається через `.split("-", 1)` (ліміт 1, щоб `google-ads-search` не розсипався на три частини). `echo_handler` видалений з `main.py`, бо він перехопив би всі майбутні повідомлення квізу.

### Крок 6. Движок квізу
`app/quiz/schema.py` — pydantic-моделі `BotSetting`, `Step` (з `Literal` для типу кроку), `Quiz`. `loader.py` читає й валідує `quiz.yaml` через `yaml.safe_load` + pydantic. Один FSM-стан `QuizStates.in_progress` замість окремого стану на кожне питання — прогрес тримається в `step_index`/`answers` у даних стану, а не в назві стану. `get_current_step(quiz, step_index)` повертає `None`, коли кроки закінчились — цей сигнал використовується і для показу питання, і для визначення кінця квізу.

### Крок 7. Клавіатури
`build_keyboard(step)` — reply-клавіатура з `step.options` плюс кнопка скасування; для кроків без опцій повертає `ReplyKeyboardRemove()` (а не `None`), бо `reply_markup=None` в Telegram означає "не чіпай", а не "прибери" — стара клавіатура лишилась би висіти на текстовому кроці. Скасування підтримує кілька варіантів написання через `F.text.lower().in_([...])`.

### Крок 8. Валідація відповідей
`validate_answer(step, text) -> str | None` через `match step.type:`. `choice` перевіряє входження в `options`, `email` — regex, `phone` — нормалізація (прибрати пробіли/дефіси/`+`/код країни `38`) і перевірка довжини. При невдалій валідації `step_index`/`answers` не змінюються.

### Крок 9. Дедуп лідів
`has_recent_lead(session, user_id, hours=24)` — перевіряє, чи є лід за останні 24 години. Використовує `.scalars().first()`, а не `.scalar_one_or_none()`, бо в юзера може бути декілька лідів. Підключено в `quiz_answer_handler` до створення нового `Lead`; `state.clear()` виконується незалежно від результату перевірки, щоб бот не "зависав" мовчки для юзера з недавнім лідом.

### Крок 10. Сповіщення менеджеру + рефакторинг
`format_lead_message(quiz, answers, status)` збирає текст питання з відповіддю для кожного кроку (в порядку `quiz.steps`), відповіді екрануються через `html.quote`. `notify_manager` обгорнута в `try/except` — падіння сповіщення не повинно ламати збереження ліда. Виправлено формат `manager_chat_id` (потрібен префікс `-100` для каналів). Валідація, побудова тексту й надсилання винесені з хендлера в `engine.py`, щоб `quiz_answer_handler` не був перевантажений.

### Крок 11. Керування статусом ліда
Три inline-кнопки під повідомленням менеджеру ("🆕 Нова" / "✅ Взяв у роботу" / "🔒 Закрито"), що не зникають після натискання — поточний статус завжди видно в тексті. `LeadAction(CallbackData, prefix="lead")` несе `lead_id` і `action`. `await session.flush()` після `session.add(lead)` — потрібен, щоб отримати `lead.id` до коміту транзакції (для кнопок). Хендлер у `manager.py` оновлює статус, перебудовує текст **з БД** (єдине джерело правди) і редагує повідомлення; ігнорує `message is not modified`, при `TelegramRetryAfter` робить `rollback`, щоб БД не розійшлась із тим, що бачить менеджер.

### Крок 12. Google Sheets
Сервісний акаунт Google Cloud (Sheets API + Drive API), ключ поза git у `secrets/`. Таблиця розшарена з правами Editor на `client_email` сервісного акаунта. Синхронна логіка `gspread` винесена в окрему функцію й викликається через `asyncio.to_thread(...)`, щоб не блокувати event loop бота на час мережевого запиту. Обгорнуто в `try/except` з логуванням, незалежно від `notify_manager`.

### Крок 13. Адмінка
Окремий роутер з фільтром по `admin_ids` з `.env`, підключений **першим** у `main.py` — щоб команди адміна мали пріоритет над будь-яким активним станом FSM користувача. `/stats` — кількість лідів усього і за сьогодні. `/export` — CSV у пам'яті (`io.StringIO`), кодування `utf-8-sig` для сумісності з Excel, надсилається як документ. `/broadcast` — окремий FSM-стан, розсилка з `asyncio.sleep(0.05)` між повідомленнями і `try/except (TelegramForbiddenError, TelegramBadRequest)` навколо кожного окремого надсилання, щоб один заблокований/неіснуючий чат не перервав розсилку для решти.

## Контекст: серія з 5 ботів для фрілансу

LeadBot — перший із п'яти пет-проєктів, задуманих для виходу на фріланс із Telegram-ботами:

1. Бот-магазин з оплатою і адмінкою
2. Бот запису на послуги (бронювання)
3. Бот платних підписок на закритий канал
4. **Лід-бот з квізом і CRM-інтеграцією ← цей проєкт**
5. AI-бот підтримки з базою знань (RAG)

Стек і рівень складності обрані навмисно "промисловими", а не мінімальними — щоб демонструвати реальний інженерний підхід (асинхронність, міграції, розділення відповідальності), а не просто working prototype.

**[⬆ Switch to English](#technical-documentation)**

---
---

# Technical Documentation

**🇺🇦 [Українською](#технічна-документація) | 🇬🇧 [English](#technical-documentation)**

This file complements [README.md](./README.md): it covers why the project is built the way it is, what has been verified live at each step, and which pitfalls were already hit. The short feature list and run commands live in the README; the depth for anyone who wants to understand the decisions, not just the feature list, lives here.

## Key architectural decisions

- **Quiz as data, not code.** The entire questionnaire is described by a YAML config (`configs/quiz.yaml`), and the engine (`app/quiz/engine.py`) only reads and executes it. The goal is to onboard a new freelance client by swapping a config, not by rewriting handlers.
- **Schema managed only through Alembic.** `Base.metadata.create_all()` is deliberately not used in the code — to avoid drifting from the migration state and to avoid breaking the async engine (`create_all` requires a synchronous connection).
- **`ondelete=SET NULL` on `Lead.user_id`.** Leads are kept even if the user is deleted from the `users` table — important for CRM logic, submitted leads shouldn't disappear along with the user.
- **UTM is stored once.** The first traffic source is treated as the source of truth; returning through a different `/start` parameter doesn't overwrite it (`get_or_create_user` deliberately skips `on_conflict_do_update`).
- **`expire_on_commit=False` on sessions.** Required for async SQLAlchemy — otherwise accessing object attributes after a `commit()` triggers a lazy-load error in an async context.
- **`repo.py` never commits by itself.** Data-access functions only build and execute queries; `commit`/`rollback` is `DbSessionMiddleware`'s job. This lets several repo functions run inside one transaction from a single handler.
- **Notifications and external integrations never block saving a lead.** Both `notify_manager` and `append_lead_to_sheet` are wrapped in their own `try/except` — if Telegram or Google is unreachable, the lead is still in the DB. The two calls are deliberately independent of each other.

## Known pitfalls (notes to self)

- `naming_convention` for `MetaData` needs to be set from the very start of the project — adding it later means rewriting migrations that were already applied.
- JSONB fields (`Lead.answers`) aren't picked up by SQLAlchemy when mutated in place (`lead.answers["x"] = 1` won't register and won't end up in the UPDATE) — needs `MutableDict` or a full field reassignment.
- Postgres only reads `POSTGRES_USER`/`PASSWORD`/`DB` from `.env` on the **first** initialization of an empty volume. Changing the password later in `.env` won't change anything in the actual DB — it needs a manual `ALTER USER` or `docker compose down -v` (which deletes the data).
- The `docker` group on Linux only applies in new sessions/terminals — after `usermod -aG docker $USER` a full re-login is needed; `newgrp docker` only fixes the current terminal.
- In the fish shell, activating a venv is done via `source .venv/bin/activate.fish`, not the regular `activate` (written for bash/zsh, and fails with a syntax error in fish).
- `chat_id` for channels and supergroups in the Bot API **always** needs a `-100` prefix in front of the "visible" numeric ID shown by the Telegram client — using the visible ID directly gives `chat not found`.
- `scalar_one_or_none()` raises `MultipleResultsFound` if there's more than one match — for checking "does at least one row exist", `scalars().first()` is safer.
- `lead.id` doesn't exist until the row has actually hit the database. If the `id` is needed right after `session.add(...)` (e.g. for callback buttons), an explicit `await session.flush()` is needed before the commit.
- Editing a Telegram message with the same text and keyboard raises `TelegramBadRequest: message is not modified` — this is expected API behavior, not a code bug, and it's worth explicitly ignoring.
- Frequent `edit_text` calls on the same message hit `TelegramRetryAfter` (flood control) — a case worth handling by rolling back the DB transaction so the DB state doesn't diverge from what the user actually sees.

## Development history, step by step

A chronological log of what was built, verified, and why, from bringing up Docker to a working MVP.

### Step 0. Docker and Postgres
Docker + the `docker-compose` plugin installed separately (Arch Linux doesn't bundle it with `docker`). Postgres 16 runs in a container, port `127.0.0.1:5432` — local development only. `docker-compose.yml` requires `POSTGRES_PASSWORD` explicitly (`:?` syntax) so it never comes up with an empty default password.

### Step 1. Config (`app/config.py`)
`Settings(BaseSettings)` from `pydantic-settings`, reads `.env`. The path to `.env` is built from `Path(__file__).resolve().parent.parent` rather than a relative string — so the config works the same from a terminal, from PyCharm, regardless of the working directory it's run from. `extra="ignore"` — so variables only needed by Docker Compose (`POSTGRES_USER`, etc.) don't break pydantic validation.

### Step 2. DB session (`app/db/session.py`)
`Base` with a custom `naming_convention` (set from the start, before the first migration — adding it later would mean rewriting already-applied migrations). Async `engine` with `pool_pre_ping=True` (avoid failing on "dead" connections after a Postgres restart). `async_sessionmaker` with `expire_on_commit=False`.

### Step 3. Models (`app/db/models.py`)
`User` and `Lead` in SQLAlchemy 2.0 style (`Mapped[...]`/`mapped_column`). `tg_id` — `BigInteger`, since Telegram IDs exceed int32 range. `Lead.answers` — `JSONB`. `Lead.user_id` — `ForeignKey("users.id", ondelete="SET NULL")`, nullable.

### Step 4. Alembic
Initialized with the `-t async` template. `env.py` imports `Base` and the models themselves (without this, `target_metadata` can't see the tables and autogenerate produces an empty migration), the URL comes from `settings.database_url`, not `alembic.ini`. The first migration was applied, and the `downgrade -1` → `upgrade head` cycle was verified both ways.

### Step 5. `get_or_create_user` and `/start` with UTM
`repo.py`: `INSERT ... ON CONFLICT (tg_id) DO NOTHING` + `SELECT` by `tg_id` — an atomic insert with no race condition. UTM from the `/start fb-ads1` payload is parsed via `.split("-", 1)` (limit 1, so `google-ads-search` doesn't split into three pieces). `echo_handler` was removed from `main.py`, since it would have intercepted every future quiz message.

### Step 6. Quiz engine
`app/quiz/schema.py` — pydantic models `BotSetting`, `Step` (with `Literal` for the step type), `Quiz`. `loader.py` reads and validates `quiz.yaml` via `yaml.safe_load` + pydantic. A single FSM state, `QuizStates.in_progress`, instead of a separate state per question — progress lives in `step_index`/`answers` in the state data, not in the state's name. `get_current_step(quiz, step_index)` returns `None` once the steps run out — this signal is used both to show the next question and to detect the end of the quiz.

### Step 7. Keyboards
`build_keyboard(step)` — a reply keyboard from `step.options` plus a cancel button; for steps with no options it returns `ReplyKeyboardRemove()` (not `None`), since `reply_markup=None` in Telegram means "leave it as is", not "remove it" — the old keyboard would have stayed visible on a text step. Cancellation supports several spellings via `F.text.lower().in_([...])`.

### Step 8. Answer validation
`validate_answer(step, text) -> str | None` via `match step.type:`. `choice` checks membership in `options`, `email` uses a regex, `phone` normalizes (stripping spaces/dashes/`+`/the `38` country code) and checks length. On failed validation, `step_index`/`answers` stay unchanged.

### Step 9. Lead dedup
`has_recent_lead(session, user_id, hours=24)` — checks for a lead within the last 24 hours. Uses `.scalars().first()` rather than `.scalar_one_or_none()`, since a user can have multiple leads. Wired in before creating a new `Lead` in `quiz_answer_handler`; `state.clear()` runs regardless of the check's result, so the bot doesn't silently hang for a user with a recent lead.

### Step 10. Manager notifications + refactor
`format_lead_message(quiz, answers, status)` builds text pairing each step's question with its answer (in `quiz.steps` order), answers are escaped via `html.quote`. `notify_manager` is wrapped in `try/except` — a failed notification shouldn't break saving the lead. Fixed the `manager_chat_id` format (channels need a `-100` prefix). Validation, text building, and sending were extracted from the handler into `engine.py`, so `quiz_answer_handler` isn't overloaded.

### Step 11. Lead status control
Three inline buttons under the manager's message ("🆕 New" / "✅ In progress" / "🔒 Closed") that don't disappear after a press — the current status is always visible in the text. `LeadAction(CallbackData, prefix="lead")` carries `lead_id` and `action`. `await session.flush()` after `session.add(lead)` — needed to get `lead.id` before the transaction commits (for the buttons). The handler in `manager.py` updates the status, rebuilds the text **from the DB** (the single source of truth), and edits the message; it ignores `message is not modified`, and on `TelegramRetryAfter` it issues a `rollback` so the DB doesn't diverge from what the manager sees.

### Step 12. Google Sheets
A Google Cloud service account (Sheets API + Drive API), key kept out of git under `secrets/`. The spreadsheet is shared with Editor access to the service account's `client_email`. The synchronous `gspread` logic is isolated in its own function and called via `asyncio.to_thread(...)`, so it doesn't block the bot's event loop during the network call. Wrapped in `try/except` with logging, independent of `notify_manager`.

### Step 13. Admin panel
A separate router filtered by `admin_ids` from `.env`, registered **first** in `main.py` — so admin commands take priority over any active FSM state a user might be in. `/stats` — total leads and today's count. `/export` — an in-memory CSV (`io.StringIO`), `utf-8-sig` encoding for Excel compatibility, sent as a document. `/broadcast` — a separate FSM state, sending with `asyncio.sleep(0.05)` between messages and `try/except (TelegramForbiddenError, TelegramBadRequest)` around each individual send, so one blocked or nonexistent chat doesn't interrupt the broadcast for everyone else.

## Context: a series of 5 bots for freelancing

LeadBot is the first of five pet projects planned for breaking into Telegram bot freelancing:

1. Storefront bot with payments and an admin panel
2. Booking bot for services
3. Paid subscription bot for a private channel
4. **Lead-gen bot with a quiz and CRM integration ← this project**
5. AI support bot with a knowledge base (RAG)

The stack and complexity level were deliberately chosen to be "production-grade" rather than minimal — to demonstrate a real engineering approach (async, migrations, separation of concerns), not just a working prototype.

**[⬆ Перемкнутись на українську](#технічна-документація)**