# Marketplace Analytics

Дипломный проект курса Data Analytics. Полная аналитическая цепочка для онлайн-маркетплейса формата Ozon: ежедневная загрузка данных из API, хранение в PostgreSQL, BI-дашборд в Metabase и два аналитических исследования по итогам собранных данных.

## Стек

- Python 3.10+ (requests, psycopg2-binary, pandas, loguru, python-dotenv)
- PostgreSQL 16
- Docker
- Metabase (последний образ)
- cron (Ubuntu 22.04)
- Jupyter / matplotlib / seaborn — для исследовательских ноутбуков

## Архитектура

```
+-------------+       +------------------+       +-------------+       +------------+
|             |       |                  |       |             |       |            |
|  Marketplace+------>+  daily_load.py   +------>+ PostgreSQL  +<------+  Metabase  |
|     API     |       |  (Python loader) |       |   (Docker)  |       |  (Docker)  |
|             |       |                  |       |             |       |            |
+-------------+       +--------+---------+       +-------------+       +-----+------+
                               ^                                              |
                               |                                              |
                          +----+----+                                    +----v----+
                          |  cron   |                                    | Браузер |
                          |  07:00  |                                    | (BI UI) |
                          +---------+                                    +---------+
```

API маркетплейса отдаёт покупки за день. Скрипт `daily_load` забирает данные за указанную дату и идемпотентно складывает их в Postgres. Ежедневный запуск настроен через cron на VPS. Metabase подключён к той же БД и используется для дашборда и ad-hoc запросов.

## Структура репозитория

```
.
├── src/                       # Код загрузчика
│   ├── api_client.py          # Обёртка над API (пагинация, ретраи)
│   ├── db.py                  # Подключение и запись в Postgres
│   ├── loader.py              # Логика загрузки одной даты
│   ├── daily_load.py          # Точка входа для cron (вчерашняя дата)
│   └── backfill.py            # Загрузка диапазона дат (для первичной заливки)
├── sql/
│   └── schema.sql             # DDL: purchases, load_log, view clients
├── notebooks/
│   ├── api_recon.ipynb                # Этап 1: разведка API
│   ├── 01_assortment_research.ipynb   # Исследование 1: ассортимент
│   └── 02_ltv_research.ipynb          # Исследование 2: клиенты и LTV
├── reports/                   # PDF-выгрузки исследований
├── requirements.txt
├── .env.example               # Шаблон переменных окружения
└── README.md
```

## Схема БД

Три объекта в схеме `public`:

- **`purchases`** — основная таблица фактов: `purchase_id` (PK), `purchase_date`, `client_id`, `product_id`, `product_name`, `category`, `price`, `quantity`, `total_amount`. На колонках `purchase_date` и `client_id` построены индексы для быстрых группировок и оконных запросов.
- **`load_log`** — журнал загрузок: `load_date` (PK), `loaded_at`, `rows_loaded`, `status` (`ok` / `empty` / `error`), `error_message`. Используется для контроля целостности и идемпотентности (повторный запуск на уже загруженную дату пропускается).
- **`clients`** (view) — производное представление поверх `purchases` с агрегатами по клиенту: дата первой и последней покупки, число заказов, суммарный LTV. Используется в исследовании 2 и в Metabase.

DDL целиком — в `sql/schema.sql`.

## Локальный запуск

Воспроизводимый запуск загрузчика на своей машине. Требуется Python 3.10+ и Docker.

```bash
# 1. Склонировать репозиторий
git clone https://github.com/palpitova/marketplace-analytics.git
cd marketplace-analytics

# 2. Создать виртуальное окружение и поставить зависимости
python3 -m venv venv
source venv/bin/activate   # для Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Поднять Postgres в Docker
docker run -d --name marketplace-pg \
  -e POSTGRES_DB=marketplace \
  -e POSTGRES_USER=marketplace_user \
  -e POSTGRES_PASSWORD=<свой_пароль> \
  -p 5432:5432 \
  postgres:16

# 4. Применить схему
docker exec -i marketplace-pg psql -U marketplace_user -d marketplace < sql/schema.sql

# 5. Скопировать шаблон .env и заполнить значения
cp .env.example .env
# отредактировать .env: DATABASE_URL, API_BASE_URL, API_TOKEN

# 6. Тестовый запуск загрузки за вчерашний день
python -m src.daily_load
```

После запуска данные за вчерашнюю дату появятся в `purchases`, а в `load_log` — запись со статусом `ok`.

## Развёртывание на сервере

Проект развёрнут на VPS (Ubuntu 22.04, reg.ru). Postgres и Metabase крутятся в Docker, общаются через bridge-сеть. Порт Postgres биндится только на `127.0.0.1` — снаружи база недоступна, подключение возможно только через SSH-туннель. Metabase открыт публично на порту 3000.

Ежедневная загрузка настроена в `crontab` пользователя проекта:

```
0 7 * * * cd /home/marketplace/marketplace-analytics && \
  /home/marketplace/marketplace-analytics/venv/bin/python -m src.daily_load \
  >> /home/marketplace/marketplace-analytics/cron.log 2>&1
```

Логи запусков пишутся в `cron.log`, статус каждой загрузки дублируется в таблице `load_log`. Параметры подключения к серверу и БД переданы преподавателю в отдельном файле сдачи.

## Исследования

Два аналитических исследования по итогам собранных данных. Полные PDF-версии лежат в `reports/`, исходники — в `notebooks/`.

**1. Ассортиментная матрица (ABC × XYZ)** — классификация товаров одновременно по вкладу в выручку (ABC) и по стабильности продаж (XYZ). Цель — выделить устойчивое ядро ассортимента и кандидатов на ротацию. Ноутбук `notebooks/01_assortment_research.ipynb`, отчёт `reports/Ассортиментная матрица маркетплейса.pdf`.

**2. Клиенты и LTV (RFM + когортный анализ)** — RFM-сегментация клиентской базы и когортный анализ удержания по неделям первой покупки. Цель — понять структуру базы, выделить сегменты для удержания и оценить устойчивость когорт. Ноутбук `notebooks/02_ltv_research.ipynb`, отчёт `reports/Клиенты и LTV маркетплейса.pdf`.

Оба исследования опираются на одну и ту же БД, заполняемую ежедневной загрузкой из API.

## Автор

Дарья Политова, дипломный проект курса Data Analytics, 2026.
