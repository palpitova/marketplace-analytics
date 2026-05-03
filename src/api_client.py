"""Клиент к API маркетплейса.

Тонкость: на запрос «слишком старой» или несуществующей даты API отвечает
не пустым JSON-массивом, а текстом «Информация за более ранние периоды
отсутствует». Поэтому JSON парсим в try/except и пустой день узнаём
именно по JSONDecodeError.
"""

import os
import time
import json
from typing import Tuple, List, Dict, Optional

import requests
from loguru import logger


RETRY_DELAYS_SEC = (1, 2, 4)
REQUEST_TIMEOUT_SEC = 30


def fetch_day(date: str) -> Tuple[List[Dict], str]:
    """Скачать данные за один день.

    Args:
        date: дата в формате 'YYYY-MM-DD'.

    Returns:
        (rows, status), где status — один из:
        - 'ok'    — данные пришли, в rows список словарей;
        - 'empty' — день за пределами доступной истории, rows = [];
        - 'error' — все ретраи провалились, rows = [].
    """
    base_url = os.environ["API_BASE_URL"]
    params = {"date": date}

    started_at = time.monotonic()
    last_error: Optional[Exception] = None

    for attempt, delay in enumerate([0, *RETRY_DELAYS_SEC]):
        if delay:
            time.sleep(delay)
        try:
            response = requests.get(
                base_url,
                params=params,
                timeout=REQUEST_TIMEOUT_SEC,
            )
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "API request failed (attempt {}): {}", attempt + 1, exc
            )
            continue

        if 500 <= response.status_code < 600:
            last_error = RuntimeError("HTTP " + str(response.status_code))
            logger.warning(
                "API returned {} (attempt {})",
                response.status_code,
                attempt + 1,
            )
            continue
        if response.status_code != 200:
            logger.error(
                "API returned {} for date={}: {}",
                response.status_code,
                date,
                response.text[:200],
            )
            return [], "error"

        try:
            payload = response.json()
        except json.JSONDecodeError:
            elapsed = time.monotonic() - started_at
            logger.info(
                "date={} status=empty rows=0 elapsed={:.2f}s",
                date,
                elapsed,
            )
            return [], "empty"

        if not isinstance(payload, list):
            logger.error("Unexpected payload type for date={}: {}", date, type(payload))
            return [], "error"

        elapsed = time.monotonic() - started_at
        logger.info(
            "date={} status=ok rows={} elapsed={:.2f}s",
            date,
            len(payload),
            elapsed,
        )
        return payload, "ok"

    logger.error("All retries failed for date={}: {}", date, last_error)
    return [], "error"