# HR Goals AI — Модуль оценки и генерации целей

AI-модуль для автоматической оценки и генерации целей сотрудников нефтегазовой компании по методологии SMART.
Разработан для хакатона ТОО «КМГ-Кумколь».

---

## Стек технологий

| Слой | Технология |
|------|-----------|
| LLM | Anthropic Claude Sonnet 4 (по умолчанию) или Azure OpenAI (`gpt-4o`, `gpt-4o-mini`) |
| Эмбеддинги | `BAAI/bge-m3` (локально) или Azure `text-embedding-3-large` |
| Векторная БД | ChromaDB (embedded, persistent) |
| Backend | FastAPI + SQLAlchemy 2.0 async + asyncpg |
| Frontend | React 18 + Vite + Tailwind CSS + Recharts |
| База данных | PostgreSQL 16 |
| Контейнеризация | Docker + docker-compose |

---

## Требования

- [Docker](https://docs.docker.com/get-docker/) и Docker Compose v2+
- Один из ключей:
  - Anthropic (`ANTHROPIC_API_KEY=sk-ant-...`) **или**
  - Azure OpenAI (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`)
- (опционально) токен HuggingFace (`HF_TOKEN`) для скачивания `BAAI/bge-m3`

Для **локального запуска без Docker** дополнительно нужны Python 3.11+, Node.js 20+, PostgreSQL 16.

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

Заполнить `.env` по сценарию:

```env
# Вариант Anthropic (по умолчанию)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Вариант Azure OpenAI (используется на демо)
LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<name>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
```

> **Нет облачных ключей?** Можно оставить `LLM_PROVIDER=anthropic` и не вызывать эндпоинты генерации/оценки (UI будет работать в режиме справочника + RAG). Для полноценного сценария требуется один из ключей.

`HACKATHON_DATA_DIR` указывает на папку с CSV (по умолчанию `./hackathon_db`, она уже в репозитории). Backend при первом запуске автоматически импортирует данные из этой папки.

### 3. Запустить

```bash
docker compose up --build -d
```

> ⏳ **Первый запуск** тянет зависимости, скачивает модель эмбеддингов и загружает 160 документов в ChromaDB. С качёнными образами повторные старты занимают <30 секунд.

### 4. Открыть в браузере

| Сервис | URL |
|--------|-----|
| Фронтенд | http://localhost:5174 |
| API (Swagger) | http://localhost:8010/docs |
| Backend health | http://localhost:8010/health |

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
# Заполнить ключи, указать локальный DATABASE_URL и HACKATHON_DATA_DIR:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hr_goals
# HACKATHON_DATA_DIR=../hackathon_db

# Запустить PostgreSQL (отдельно, например через Docker)
docker run -d --name pg16 \
  -e POSTGRES_DB=hr_goals \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5433:5432 \
  postgres:16

# Запустить backend (автоматически создаст таблицы и заполнит данными)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> При старте backend проверяет таблицу `employees`. Если она пуста, автоматически запускается `scripts.import_hackathon_data.import_data` с путём `HACKATHON_DATA_DIR`. Это гарантирует, что при любом клонировании репозитория достаточно положить папку `hackathon_db` рядом с проектом или пробросить её в контейнер.

### Frontend

```bash
cd frontend

npm install
npm run dev
```

---

## Импорт реальных данных hackathon_db

1. Убедитесь, что локальная PostgreSQL поднята (или контейнер `ai_for_hr-postgres-1` работает), а `DATABASE_URL` указывает на нужную базу.
2. Проверьте, что `hackathon_db/` находится рядом с проектом (или передайте кастомный путь через `HACKATHON_DATA_DIR` / `--data-dir`).
3. Активируйте виртуальное окружение backend и выполните:

```bash
cd backend
python -m scripts.import_hackathon_data --data-dir ../../hackathon_db
# опции:
#   --skip-truncate      импорт без очистки таблиц
#   --limit-goals 500    загрузить ограниченное число целей (для отладки)
```

Скрипт очистит таблицы (`departments`, `employees`, `documents`, `goals`, `goal_events`, `goal_reviews`, `kpi_timeseries`) и наполнит их значениями из CSV.

4. После загрузки нужно переиндексировать документы для ChromaDB:

```bash
python -m scripts.index_documents --force
```

5. Проверьте, что данные загрузились:

```sql
SELECT COUNT(*) FROM goals;
SELECT COUNT(*) FROM goal_events;
SELECT COUNT(*) FROM documents;
```

Теперь backend и RAG используют реальные данные хакатона. При следующем `docker compose up` проверка `employees` покажет >0 и импорт повторно запускаться не будет.
Если нужно обновить датасет, повторите шаги 3–4.

---

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `ANTHROPIC_API_KEY` | Ключ Anthropic API (используется при `LLM_PROVIDER=anthropic`) | — |
| `DATABASE_URL` | Строка подключения к PostgreSQL | `postgresql+asyncpg://postgres:postgres@localhost:5432/hr_goals` |
| `CHROMA_PERSIST_DIR` | Папка для хранения ChromaDB | `./chroma_data` |
| `HACKATHON_DATA_DIR` | Путь к каталогу с CSV `hackathon_db` | `../hackathon_db` |
| `EMBEDDING_MODEL` | Идентификатор эмбеддингов (используется для названия коллекции) | `BAAI/bge-m3` |
| `LLM_PROVIDER` | Провайдер LLM: `anthropic` (по умолчанию) или `azure_openai` | `anthropic` |
| `LLM_MODEL` | ID модели (`claude-sonnet-4-20250514` или имя Azure deployment) | `claude-sonnet-4-20250514` |
| `LLM_TEMPERATURE_EVAL` | Температура для оценки (детерминизм) | `0` |
| `LLM_TEMPERATURE_GEN` | Температура для генерации | `0.3` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `AZURE_OPENAI_API_KEY` | (опционально) ключ Azure OpenAI | — |
| `AZURE_OPENAI_ENDPOINT` | (опционально) endpoint Azure OpenAI `https://<name>.openai.azure.com/` | — |
| `AZURE_OPENAI_API_VERSION` | Версия API Azure | `2024-02-01` |
| `AZURE_OPENAI_DEPLOYMENT` | Имя deployment в Azure (например, `gpt-4o-mini`) | — |

> ⚙️ **Выбор моделей:**  
> - Для локального режима без облачных ключей оставьте `LLM_PROVIDER=anthropic`, не вызывайте генерацию/оценку и используйте RAG/аналитику.  
> - Для демонстрации на Azure задайте `LLM_PROVIDER=azure_openai`, `AZURE_OPENAI_*` и `AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large`.  
> - Для более лёгкого embeddings можно экспортировать `EMBEDDING_MODEL=intfloat/multilingual-e5-small` перед сборкой (`EMBEDDING_MODEL=intfloat/multilingual-e5-small docker compose up --build`). Каждой модели соответствует собственная коллекция Chroma (`documents_<model>`).

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
│       │   ├── llm_client.py    # Обёртка над Anthropic/Azure OpenAI + кэш
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

## Реализация функциональных требований

| # | Требование | Backend | UI |
|---|-----------|---------|-----|
| **F-09** | Генерация целей по должности, подразделению и ВНД | `core/generator.py` + `core/rag.py` + `api/v1/generator.py` | Страница «Генератор целей» — выбрать сотрудника → «Сгенерировать цели» |
| **F-10** | Привязка каждой цели к ВНД (источник + цитата) | `core/generator.py`: поля `source_document`, `source_quote` в промпте и схеме | В карточке цели — кликабельный блок «Источник ВНД» раскрывает цитату |
| **F-11** | Настройка контекста генерации (фокус-приоритеты) | `api/v1/generator.py`: поле `focus_priorities` в запросе | Страница «Генератор» — поле «Фокус-приоритеты» (опционально) |
| **F-12** | Генерация в SMART-формате с self-check | `core/generator.py`: `_self_check_goal()` — прогоняет каждую цель через evaluator, до 2 retry переформулировки | В карточке цели — SMART-индекс и бейдж «Требует проверки» если < 0.63 |
| **F-13** | Интерфейс выбора целей (принять / отклонить) | — | Страница «Генератор» — кнопки «Принять» / «Отклонить» на каждой карточке; отклонённые затемняются |
| **F-14** | Каскадирование: цели на основе целей руководителя | `api/v1/generator.py`: загрузка целей руководителя через `manager_id`; `core/generator.py`: передаются в промпт и детектируются через similarity | В карточке цели — фиолетовый блок «Каскадировано от: [Имя]» с цитатой цели руководителя |
| **F-15** | История сгенерированных и оценённых целей | БД: таблицы `goal_events`, `goal_reviews` хранят полную историю | Страница «История» — раздельно показывает историю оценок и генераций из localStorage |
| **F-16** | Предупреждение если целей < 3 или > 5 | `api/v1/evaluator.py`: batch evaluate проверяет количество | В batch evaluate и в строке сводки под карточками генератора |
| **F-17** | Стратегическая связка (уровень + источник) | `core/evaluator.py`: `evaluate_strategic_link()` — отдельный LLM-вызов, возвращает уровень/источник/цитату | В «Оценке цели» — блок «Стратегическая связка» с уровнем (бейдж), источником ВНД и цитатой |
| **F-18** | Контроль суммы весов = 100% | `core/generator.py`: нормализация весов; `api/v1/evaluator.py`: batch предупреждение | В генераторе — строка «Сумма весов X%» (зелёная если ~100%, красная если отклонение) |
| **F-19** | Классификация типа цели + переформулировка activity | `core/evaluator.py`: LLM классифицирует тип; `core/generator.py`: self-check переформулирует activity-цели | В оценщике и карточках генератора — цветной бейдж Impact / Output / Activity |
| **F-20** | Проверка достижимости по историческим данным | `services/goal_service.py`: `get_similar_goals()` ищет похожие цели в БД; `api/v1/evaluator.py`: считает % rejected | В «Оценке цели» — оранжевый блок «Достижимость» если >50% похожих целей в подразделении отклонялись |
| **F-21** | Проверка дублирования внутри набора | `core/generator.py`: попарная проверка similarity между сгенерированными целями (Jaccard) | В генераторе — предупреждение «Возможное дублирование: цель #X и цель #Y» в строке warnings |
| **F-22** | Дашборд зрелости целеполагания (maturity index) | `core/analytics_engine.py`: `compute_maturity_index()`; `api/v1/analytics.py` | Страница «Аналитика» — Maturity Index, heatmap по критериям SMART × департамент, bar chart, тренды |

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

**Медленный первый запуск / много места**
Это ожидаемо — см. раздел «Быстрый старт». После первой сборки повторный запуск занимает < 30 сек, качество приложения не меняется.

**Ошибка `ANTHROPIC_API_KEY`**
Убедиться, что файл `.env` создан из `.env.example` и ключ указан корректно (начинается с `sk-ant-`).

**Порт занят**
Если порты 5432, 8000 или 5173 заняты — изменить маппинг в `docker-compose.yml` (левая часть `"host:container"`).
