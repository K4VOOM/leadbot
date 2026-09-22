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
├── app/
│   ├── main.py              # точка входу, запуск polling
│   ├── config.py            # Settings (pydantic-settings), читає .env
│   ├── db/
│   │   ├── session.py       # Base, async engine, async_sessionmaker
│   │   ├── models.py        # ORM-моделі: User, Lead
│   │   └── repo.py          # функції доступу до даних (у розробці)
│   └── handlers/            # роутери aiogram (ще не винесені з main.py)
├── configs/
│   └── quiz.yaml            # конфіг квізу (заплановано, ще не використовується кодом)
├── alembic/
│   ├── env.py                # налаштований на async engine + settings.database_url
│   └── versions/
│       └── 9bace4ced334_init.py   # початкова міграція: users, leads
├── docker-compose.yml        # сервіс db (postgres:16), loopback-порт, healthcheck
├── .env                       # секрети, НЕ в git
├── .env.example                # шаблон для .env
├── requirements.txt
└── alembic.ini
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

**Git**
- Репозиторій ініціалізований, `.env` і `.venv` не потрапляють у коміти
- `.env.example` з фейковими значеннями для нових розробників
- Комітиться поетапно, з осмисленими повідомленнями

### 🚧 У процесі

- `app/db/repo.py` — функція `get_or_create_user(session, tg_id, username, first_name, utm_source, utm_campaign) -> User`. Логіка: `INSERT ... ON CONFLICT (tg_id) DO NOTHING`, потім `SELECT` за `tg_id`. UTM для існуючого юзера **не перезаписується** — зберігається перше джерело трафіку.

### 📋 Заплановано (найближчі кроки)

1. **`get_or_create_user` в repo.py** — завершити й покрити базовим ручним тестом
2. **Middleware сесії** — `BaseMiddleware`, що на кожен апдейт відкриває сесію SQLAlchemy, кладе її в `data["session"]`, комітить/відкочує після хендлера; підключення через `dp.update.outer_middleware(...)`
3. **`/start` з UTM-мітками**:
   - Перенести хендлери з `main.py` у `app/handlers/start.py` через `Router()`
   - Прибрати `echo_handler` (заважатиме проходженню квізу)
   - Парсинг payload `/start fb-ads1` → `utm_source="fb"`, `utm_campaign="ads1"` через `CommandObject`
   - Обробка порожнього/некоректного payload
4. **Движок квізу** (`app/quiz/`):
   - `schema.py` — pydantic-моделі для `quiz.yaml` (кроки типу `choice`, `multi_choice`, `text`, `phone`, `email`)
   - `loader.py` — читання й валідація YAML
   - `engine.py` — логіка проходження: наступний крок, валідація відповіді
   - FSM з одним станом і `step_index` в даних, а не окремий стан на кожне питання
5. **Збереження ліда** — запис відповідей у `Lead.answers` (JSONB), дедуп (той самий `tg_id` не створює новий лід протягом 24 год)
6. **Сповіщення менеджеру** — повідомлення з відповідями + inline-кнопки "Взяв у роботу"/"Закрито", що міняють `Lead.status`
7. **Google Sheets інтеграція** — `gspread` (обгорнутий у `asyncio.to_thread`, щоб не блокував event loop), запис ліда з ретраєм, що не ламає основний потік при недоступності Google
8. **Адмінка в боті** — `/stats` (ліди за період з розбивкою по UTM), `/export` (CSV), `/broadcast` із сегментацією за відповідями квізу
9. **Розсилка** — rate limit ~20 повідомлень/сек, обробка `TelegramForbiddenError` (юзер заблокував бота → `subscribed=False`)

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