"""Точка входа для cron: грузит данные за вчерашний день.

Запуск: python -m src.daily_load
"""

from datetime import date, timedelta

from dotenv import load_dotenv
from loguru import logger

from src.loader import load_date


def main() -> None:
    """Загрузить вчерашний день."""
    load_dotenv()

    logger.add(
        "logs/daily_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        level="INFO",
    )

    yesterday = date.today() - timedelta(days=1)
    yesterday_str = yesterday.isoformat()

    logger.info("Daily load started for date={}", yesterday_str)
    load_date(yesterday_str)
    logger.info("Daily load finished for date={}", yesterday_str)


if __name__ == "__main__":
    main()