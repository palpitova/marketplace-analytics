"""Работа с PostgreSQL: соединение и загрузка данных за один день."""

import os
from typing import List, Dict, Optional

import psycopg2
import psycopg2.extras
from loguru import logger


PURCHASES_COLUMNS = (
    "client_id",
    "gender",
    "product_id",
    "purchase_date",
    "purchase_time_seconds",
    "quantity",
    "price_per_item",
    "discount_per_item",
    "total_price",
)


def get_connection():
    """Открыть соединение к PostgreSQL по DATABASE_URL."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


def _row_to_tuple(row: Dict, date: str) -> tuple:
    """Преобразовать запись из API в кортеж под порядок PURCHASES_COLUMNS."""
    return (
        row["client_id"],
        row["gender"],
        row["product_id"],
        date,
        row["purchase_time_as_seconds_from_midnight"],
        row["quantity"],
        row["price_per_item"],
        row["discount_per_item"],
        row["total_price"],
    )


def load_day(date: str, rows: List[Dict]) -> int:
    """Загрузить данные за день в одной транзакции.

    Сначала удаляем все строки за эту дату (чтобы перезапуск был
    идемпотентным), потом батчем вставляем новые. На execute_values
    переходим вместо cursor.executemany ради скорости.

    Args:
        date: дата 'YYYY-MM-DD'.
        rows: список словарей, как пришли из API.

    Returns:
        Количество вставленных строк.
    """
    insert_sql = (
        "INSERT INTO purchases (" + ", ".join(PURCHASES_COLUMNS) + ") VALUES %s"
    )
    log_upsert_sql = """
        INSERT INTO load_log (load_date, loaded_at, rows_loaded, status, error_message)
        VALUES (%s, NOW(), %s, 'ok', NULL)
        ON CONFLICT (load_date) DO UPDATE SET
            loaded_at = EXCLUDED.loaded_at,
            rows_loaded = EXCLUDED.rows_loaded,
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message
    """

    conn = get_connection()
    try:
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM purchases WHERE purchase_date = %s",
                        (date,),
                    )
                    if rows:
                        values = [_row_to_tuple(r, date) for r in rows]
                        psycopg2.extras.execute_values(
                            cur, insert_sql, values, page_size=1000
                        )
                    cur.execute(log_upsert_sql, (date, len(rows)))
            logger.info("DB load_day date={} inserted={}", date, len(rows))
            return len(rows)
        except Exception as exc:
            logger.exception("DB load_day failed for date={}", date)
            _write_error_log(conn, date, str(exc))
            raise
    finally:
        conn.close()


def _write_error_log(conn, date: str, message: str) -> None:
    """Записать в load_log статус 'error' отдельной транзакцией."""
    sql = """
        INSERT INTO load_log (load_date, loaded_at, rows_loaded, status, error_message)
        VALUES (%s, NOW(), 0, 'error', %s)
        ON CONFLICT (load_date) DO UPDATE SET
            loaded_at = EXCLUDED.loaded_at,
            rows_loaded = EXCLUDED.rows_loaded,
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message
    """
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, (date, message[:1000]))
    except Exception:
        logger.exception("Failed to write error to load_log for date={}", date)


def mark_empty(date: str) -> None:
    """Пометить дату как 'empty' в load_log (повторно дёргать не нужно)."""
    sql = """
        INSERT INTO load_log (load_date, loaded_at, rows_loaded, status, error_message)
        VALUES (%s, NOW(), 0, 'empty', NULL)
        ON CONFLICT (load_date) DO UPDATE SET
            loaded_at = EXCLUDED.loaded_at,
            rows_loaded = EXCLUDED.rows_loaded,
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, (date,))
        logger.info("DB mark_empty date={}", date)
    finally:
        conn.close()


def get_load_status(date: str) -> Optional[str]:
    """Узнать текущий статус даты в load_log. Возвращает None, если не загружали."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM load_log WHERE load_date = %s",
                (date,),
            )
            result = cur.fetchone()
            return result[0] if result else None
    finally:
        conn.close()