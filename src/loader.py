"""Оркестратор загрузки одной даты.

Логика: если в load_log уже есть запись со статусом 'ok' или 'empty',
ничего не делаем (skip). Иначе — идём в API, потом в БД.
"""

from loguru import logger

from src import api_client, db


def load_date(date: str, force: bool = False) -> None:
    """Загрузить данные за указанную дату.

    Args:
        date: дата 'YYYY-MM-DD'.
        force: если True, грузим даже если уже было 'ok' или 'empty'.
    """
    if not force:
        existing_status = db.get_load_status(date)
        if existing_status in ("ok", "empty"):
            logger.info(
                "date={} already loaded with status={}, skip",
                date,
                existing_status,
            )
            return

    rows, status = api_client.fetch_day(date)

    if status == "empty":
        db.mark_empty(date)
        logger.info("date={} marked as empty", date)
        return

    if status == "error":
        logger.error("date={} fetch failed, will retry next time", date)
        return

    db.load_day(date, rows)
    logger.info("date={} loaded {} rows", date, len(rows))