# HR Goals AI — Модуль оценки и генерации целей

AI-модуль для автоматической оценки и генерации целей сотрудников нефтегазовой компании по методологии SMART.
Разработан для хакатона ТОО «КМГ-Кумколь».

---

## Стек технологий

| Слой | Технология |
|------|-----------|
| LLM | Claude Sonnet (`claude-sonnet-4-20250514`) через Anthropic API |
| Эмбеддинги | `BAAI/bge-m3` (sentence-transformers) |
| Векторная БД | ChromaDB (embedded, persistent) |
| Backend | FastAPI + SQLAlchemy 2.0 async + asyncpg |
| Frontend | React 18 + Vite + Tailwind CSS + Recharts |
| База данных | PostgreSQL 16 |
| Контейнеризация | Docker + docker-compose |

---

## Требования

- [Docker](https://docs.docker.com/get-docker/) и Docker Compose (v2+)
- Ключ Anthropic API (`sk-ant-...`)

Для **локального запуска без Docker** дополнительно:
- Python 3.11+
- Node.js 20+
- PostgreSQL 16

---

## Быстрый старт (Docker)

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd ai_for_hr
```

### 2. Создать файл `.env`

```bash
cp .env.example .env
```

Открыть `.env` и вставить ключ Anthropic:

```env
ANTHROPIC_API_KEY=sk-ant-ваш-ключ-здесь
```

Остальные переменные для Docker менять не нужно.

### 3. Запустить

```bash
docker-compose up --build
```

> Первый запуск занимает **5–10 минут**: сборка образов, загрузка модели `BAAI/bge-m3` (~2 ГБ), инициализация БД и индексирование 160 ВНД-документов.
> Повторные запуски — менее 30 секунд.

### 4. Открыть в браузере

| Сервис | URL |
|--------|-----|
| Фронтенд | http://localhost:5173 |
| API (Swagger) | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/health |

---

## Локальный запуск без Docker

### Backend

```bash
cd backend

# Создать виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Установить зависимости
pip install -e .

# Создать .env (в корне проекта)
cp ../.env.example ../.env
# Заполнить ANTHROPIC_API_KEY и указать локальный DATABASE_URL:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hr_goals

# Запустить PostgreSQL (отдельно, например через Docker)
docker run -d --name pg16 \
  -e POSTGRES_DB=hr_goals \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16

# Запустить backend (автоматически создаст таблицы и заполнит данными)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend

npm install
npm run dev
```

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `ANTHROPIC_API_KEY` | **Обязательно.** Ключ Anthropic API | — |
| `DATABASE_URL` | Строка подключения к PostgreSQL | `postgresql+asyncpg://postgres:postgres@localhost:5432/hr_goals` |
| `CHROMA_PERSIST_DIR` | Папка для хранения ChromaDB | `./chroma_data` |
| `BGE_MODEL_NAME` | Модель эмбеддингов | `BAAI/bge-m3` |
| `LLM_MODEL` | ID модели Claude | `claude-sonnet-4-20250514` |
| `LLM_TEMPERATURE_EVAL` | Температура для оценки (детерминизм) | `0` |
| `LLM_TEMPERATURE_GEN` | Температура для генерации | `0.3` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

---

## Структура проекта

```
ai_for_hr/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── app/
│       ├── main.py              # FastAPI + автозапуск seed и индексирования
│       ├── config.py            # Настройки (pydantic-settings)
│       ├── database.py          # Async SQLAlchemy engine
│       ├── api/v1/              # Эндпоинты: evaluator, generator, analytics, documents, goals, employees
│       ├── core/
│       │   ├── prompts.py       # Все промпты (SMART-оценка, генерация, связка)
│       │   ├── evaluator.py     # Логика SMART-оценки (нормализация 0.0–1.0)
│       │   ├── generator.py     # Логика генерации целей
│       │   ├── rag.py           # RAG-пайплайн
│       │   ├── schemas.py       # Pydantic-модели ответов
│       │   ├── llm_client.py    # Обёртка над Anthropic API + кэш
│       │   └── analytics_engine.py
│       ├── models/              # SQLAlchemy ORM-модели
│       └── services/            # ChromaDB, document indexer, goal service
│   ├── scripts/
│   │   ├── seed_database.py     # Генерация синтетических данных
│   │   ├── index_documents.py   # Индексирование ВНД в ChromaDB
│   │   └── eval_prompts.py      # A/B тестирование промптов
│   └── data/
│       └── calibration/         # Эталонные оценки и RAG-тесты
└── frontend/
    └── src/
        ├── pages/               # GoalEvaluator, GoalGenerator, Analytics, DocumentBrowser
        └── components/          # SmartRadarChart, GoalCard, BeforeAfter, DepartmentHeatmap
```

---

## API эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| `POST` | `/api/v1/evaluate` | Оценка одной цели (SMART + тип + стратег. связка) |
| `POST` | `/api/v1/evaluate/batch` | Пакетная оценка набора целей сотрудника |
| `POST` | `/api/v1/reformulate` | Переформулировка слабой цели (before/after) |
| `POST` | `/api/v1/generate` | Генерация 3–5 целей для сотрудника |
| `POST` | `/api/v1/documents/search` | Семантический поиск по ВНД |
| `GET` | `/api/v1/analytics/dashboard` | Сводный дашборд по всем департаментам |
| `GET` | `/api/v1/analytics/department/{id}` | Детали по департаменту |
| `GET` | `/api/v1/analytics/trends` | Тренды по кварталам |
| `GET` | `/api/v1/employees` | Список сотрудников (с поиском) |
| `GET` | `/api/v1/employees/{id}` | Профиль сотрудника |
| `GET` | `/api/v1/employees/{id}/goals` | Цели сотрудника |
| `GET` | `/api/v1/departments` | Список департаментов |
| `GET` | `/api/v1/kpi/{department_id}` | KPI департамента |
| `GET` | `/health` | Healthcheck |

Интерактивная документация Swagger: http://localhost:8000/docs

---

## Формат ответа оценки (`POST /api/v1/evaluate`)

```json
{
  "goal_id": null,
  "goal_text": "Снизить текучесть персонала в добывающем подразделении с 18% до 12% к концу Q2 2025",
  "smart_scores": {
    "specific": 0.75,
    "measurable": 1.0,
    "achievable": 0.75,
    "relevant": 1.0,
    "time_bound": 1.0
  },
  "smart_index": 0.9,
  "recommendations": [
    "S (Конкретность): ...",
    "A (Достижимость): ..."
  ],
  "improved_goal": null,
  "smart_detail": { ... },
  "strategic_link": {
    "link_level": "стратегическая",
    "source_name": "Стратегия развития человеческого капитала 2025–2027",
    "confidence": 0.92,
    ...
  }
}
```

Оценки `smart_scores` — шкала **0.0–1.0** (соответствует 1–5 нормализованным через `(score-1)/4`).

---

## Ручное управление данными

### Пересоздать базу данных и данные

```bash
# Остановить backend, затем:
cd backend
python scripts/seed_database.py
```

### Переиндексировать документы в ChromaDB

```bash
cd backend
python scripts/index_documents.py
```

### A/B тест промптов

```bash
cd backend
python scripts/eval_prompts.py
```

Выводит Pearson correlation и MAE между версиями промптов на калибровочном датасете (`data/calibration/expert_markup.json`).

---

## Остановка и очистка

```bash
# Остановить контейнеры
docker-compose down

# Остановить и удалить тома (сбросить все данные)
docker-compose down -v
```

---

## Возможные проблемы

**Backend не запускается — ошибка подключения к БД**
PostgreSQL ещё не готов. Backend автоматически ждёт healthcheck. Если ошибка сохраняется — проверить `docker-compose logs postgres`.

**Медленный первый запуск**
Загрузка модели `BAAI/bge-m3` (~2 ГБ) происходит при первой сборке образа. При повторном `docker-compose up` модель берётся из кэша Docker.

**Ошибка `ANTHROPIC_API_KEY`**
Убедиться, что файл `.env` создан из `.env.example` и ключ указан корректно (начинается с `sk-ant-`).

**Порт занят**
Если порты 5432, 8000 или 5173 заняты — изменить маппинг в `docker-compose.yml` (левая часть `"host:container"`).
