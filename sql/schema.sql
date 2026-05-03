-- =====================================================================
-- Marketplace analytics — schema
-- Final project, Data Analytics course
--
-- Запуск:
--   psql -U <user> -d <db> -f schema.sql
--
-- Скрипт идемпотентный: можно прогонять повторно.
-- =====================================================================


-- ---------------------------------------------------------------------
-- purchases — фактовая таблица
-- Одна строка = одна позиция чека (id заказа в API нет).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchases (
    id                    BIGSERIAL PRIMARY KEY,
    client_id             INT     NOT NULL,
    gender                CHAR(1) NOT NULL CHECK (gender IN ('M', 'F')),
    product_id            INT     NOT NULL,
    purchase_date         DATE    NOT NULL,
    purchase_time_seconds INT     NOT NULL,
    quantity              INT     NOT NULL,
    price_per_item        INT     NOT NULL,
    discount_per_item     INT     NOT NULL,
    total_price           INT     NOT NULL,

    -- Удобно для Metabase: сразу есть полный timestamp для группировок
    -- по часам, дням недели и т.п.
    purchase_timestamp    TIMESTAMP GENERATED ALWAYS AS (
        purchase_date + make_interval(secs => purchase_time_seconds)
    ) STORED
);

-- Индексы под три типа запросов:
--   (а) фильтр по периоду
--   (б) клиентская аналитика (RFM, когорты)
--   (в) товарная аналитика (ABC×XYZ)
-- Composite (col, purchase_date) покрывает и group-by, и фильтр по дате.
CREATE INDEX IF NOT EXISTS idx_purchases_date
    ON purchases (purchase_date);

CREATE INDEX IF NOT EXISTS idx_purchases_client_date
    ON purchases (client_id, purchase_date);

CREATE INDEX IF NOT EXISTS idx_purchases_product_date
    ON purchases (product_id, purchase_date);


-- ---------------------------------------------------------------------
-- load_log — журнал загрузок для бэкфилла
-- Одна строка = одна попытка загрузить одну дату.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS load_log (
    load_date     DATE      PRIMARY KEY,
    loaded_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    rows_loaded   INT       NOT NULL DEFAULT 0,
    status        TEXT      NOT NULL CHECK (status IN ('ok', 'empty', 'error')),
    error_message TEXT
);
-- 'ok'    — данные загружены
-- 'empty' — API вернул "Информация за более ранние периоды отсутствует"
--           или пустой массив; повторно дёргать не надо
-- 'error' — упало, можно ретраить


-- ---------------------------------------------------------------------
-- clients — VIEW поверх purchases
-- gender фиксирован у клиента, first/last_purchase_date считаются
-- агрегатами. Используется в RFM и когортах.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW clients AS
SELECT
    client_id,
    MIN(gender)        AS gender,
    MIN(purchase_date) AS first_purchase_date,
    MAX(purchase_date) AS last_purchase_date,
    COUNT(*)           AS line_count,
    SUM(total_price)   AS total_revenue
FROM purchases
GROUP BY client_id;
