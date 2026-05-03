"""Точка входа для бэкфилла исторических данных.

Запуск: python -m src.backfill --from YYYY-MM-DD --to YYYY-MM-DD
"""

import argparse
import time
from datetime import date, timedelta

from dotenv import load_dotenv
from loguru import logger

from src.loader import load_date


SLEEP_BETWEEN_DAYS_SEC = 0.5
PROGRESS_EVERY_N_DAYS = 10


def parse_date(text: str) -> date:
    """Распарсить дату из строки 'YYYY-MM-DD'."""
    return date.fromisoformat(text)


def main() -> None:
    """Прогнать бэкфилл по диапазону дат."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="Backfill marketplace data")
    parser.add_argument("--from", dest="date_from", required=True, type=parse_date)
    parser.add_argument("--to", dest="date_to", required=True, type=parse_date)
    args = parser.parse_args()

    if args.date_from > args.date_to:
        raise SystemExit("--from must be <= --to")

    total_days = (args.date_to - args.date_from).days + 1
    logger.info(
        "Backfill started: from={} to={} total_days={}",
        args.date_from,
        args.date_to,
        total_days,
    )

    current = args.date_from
    processed = 0
    while current <= args.date_to:
        load_date(current.isoformat())
        processed += 1

        if processed % PROGRESS_EVERY_N_DAYS == 0:
            logger.info(
                "Progress: {}/{} days ({:.1f}%)",
                processed,
                total_days,
                100 * processed / total_days,
            )

        current += timedelta(days=1)
        if current <= args.date_to:
            time.sleep(SLEEP_BETWEEN_DAYS_SEC)

    logger.info("Backfill finished: processed {} days", processed)


if __name__ == "__main__":
    main()