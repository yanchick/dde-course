# %% [markdown]
# # Семинар 2 — Продвинутый сбор данных
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Что делаем — собираем один датасет тремя способами и публикуем его в стенд:
# 1. REST-каталог через gateway (задание 2.1 — пагинация).
# 2. Scrapy-паук по локальному «сайту конкурента» (задание 2.2 — селекторы).
# 3. Партнёрский CSV, читаем чанками (задание 2.3 — память).
# 4. Отправляем чтения в `sensor-gateway` (задание 2.4 — публикация).
# 5. Повторный батч → проверяем дедуп по `readingId` (задание 2.5).
#
# Запуск:
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# docker compose --profile adv up -d
# uv run --project "$SPUTNIK_REPO" \
#   --with httpx --with pandas --with boto3 --with scrapy \
#   python seminar_02.py
# ```

# %%
from __future__ import annotations

import functools
import http.server
import json
import os
import random
import tempfile
import threading
import time
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

try:
    import boto3  # для чтения bronze из MinIO
except ImportError:  # pragma: no cover - зависимость опциональна
    boto3 = None

try:
    import scrapy  # для задания 2.2
    from scrapy.crawler import CrawlerProcess
except ImportError:  # pragma: no cover - зависимость опциональна
    scrapy = None
    CrawlerProcess = None

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")
SENSOR_GATEWAY_URL = os.getenv("SENSOR_GATEWAY_URL", "http://localhost:8006").rstrip("/")
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "buyer@sputnik.demo")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "sputnik")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "sputnik123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lake")
MINIO_REGION = os.getenv("MINIO_REGION", "us-east-1")

SEED = int(os.getenv("SEED", "42"))
READING_PREFIX = "rd_sem2_"
N_CSV_ROWS = int(os.getenv("N_CSV_ROWS", "200_000"))
MEMORY_LIMIT_MB = float(os.getenv("MEMORY_LIMIT_MB", "50"))
MOCK_CARDS = 24


# %% [markdown]
# ## 0. Проверка стенда
#
# Семинар работает только с профилем `adv`: нужны `sensor-gateway` (приём
# чтений), `ingestion` (дедуп → bronze) и MinIO (озеро). Перед заданиями
# убедимся, что ключевые сервисы отвечают.

# %%
def wait_http(url: str, timeout: float = 60.0) -> bool:
    """Ждать, пока эндпоинт не начнёт отвечать 2xx."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def check_stack() -> dict[str, bool]:
    """Проверить доступность gateway и sensor-gateway."""
    return {
        "gateway": wait_http(f"{GATEWAY_URL}/healthz", timeout=15),
        "sensor_gateway": wait_http(f"{SENSOR_GATEWAY_URL}/healthz", timeout=15),
    }


# %% [markdown]
# ## 1. REST-каталог: вход и пагинация
#
# Каталог отдаёт `GET /api/v1/datasets` с метаданными пагинации
# `{page, pageSize, total, totalPages, hasMore}`. Сначала — вход демо-покупателем
# и одна страница как опора.

# %%
def login() -> str:
    """Войти демо-покупателем и вернуть accessToken."""
    response = httpx.post(
        f"{GATEWAY_URL}/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["accessToken"]


def catalog_page(client: httpx.Client, page: int = 1, page_size: int = 5) -> dict[str, Any]:
    """Прочитать одну страницу каталога через gateway."""
    response = client.get(
        "/api/v1/datasets",
        params={"page": page, "pageSize": page_size},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


# %% [markdown]
# ## 2. Задание 2.1 — пагинация до конца
#
# Соберите **все** датасеты, перебирая страницы, пока `pagination.hasMore` не
# станет `False`. Проверка: записей ровно `pagination.total` и ни один
# `datasetId` не повторяется.

# %%
# TASK 2.1 — пагинация
def collect_all_datasets(client: httpx.Client, page_size: int = 2) -> list[dict[str, Any]]:
    """Собрать все датасеты каталога, листая страницы до `hasMore=False`."""
    # TODO (2.1): реализуйте цикл пагинации.
    # Подсказки:
    # - page = 1; бесконечный цикл;
    # - payload = catalog_page(client, page, page_size);
    # - rows.extend(payload["data"]);
    # - если не payload["pagination"]["hasMore"] — выход;
    # - page += 1.
    # Верните rows.
    raise NotImplementedError("Задание 2.1: реализуйте collect_all_datasets")


def print_table(frame: pd.DataFrame) -> None:
    """Напечатать DataFrame без индекса (работает и вне Jupyter)."""
    if frame.empty:
        print("(пусто)")
    else:
        print(frame.to_string(index=False))


# %% [markdown]
# ## 3. Задание 2.2 — Scrapy-паук по локальному моку
#
# Скрейпить живой сайт нельзя: только локальный мок. Сначала генерируем
# «сайт конкурента» из 24 карточек и поднимаем локальный HTTP-сервер, затем
# паук собирает карточки. Вам нужно дописать **два CSS-селектора**:
# название (`NAME_SELECTOR`) и цену (`PRICE_SELECTOR`).

# %%
_MOCK_NAMES = [
    "Погода по городам", "Качество воздуха онлайн", "Потребление энергии",
    "Транспортный поток", "Розничные продажи", "Метеорадар", "Шум города",
    "PM2.5 по районам", "Электросети", "Пробки в реальном времени",
    "Продажи супермаркетов", "Влажность и осадки", "Пыльца растений",
    "Геоаналитика", "Потребление воды", "Парковки", "Цены на топливо",
    "Движение общественного транспорта", "Качество связи", "Теплосети",
    "Экологические сводки", "Грузоперевозки", "Аналитика торговых точек",
    "Микроклимат офисов",
]
_MOCK_CATEGORIES = ["WEATHER", "AIR_QUALITY", "ENERGY", "TRANSPORT", "COMMERCE"]


def make_mock_site(target_dir: Path, n_cards: int = MOCK_CARDS, seed: int = SEED) -> Path:
    """Сгенерировать локальный «сайт конкурента» и вернуть путь к index.html."""
    rng = random.Random(seed)
    cards: list[str] = []
    for index in range(n_cards):
        name = _MOCK_NAMES[index % len(_MOCK_NAMES)]
        price = round(rng.uniform(100.0, 5000.0), 2)
        category = _MOCK_CATEGORIES[index % len(_MOCK_CATEGORIES)]
        cards.append(
            "  <div class=\"product-card\">\n"
            f"    <h3 class=\"name\">{name}</h3>\n"
            f"    <span class=\"price\">{price}</span>\n"
            f"    <span class=\"category\">{category}</span>\n"
            "  </div>"
        )
    html = (
        "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">"
        "<title>Конкурент «Данные 24»</title></head>\n<body>\n"
        "<h1>Каталог конкурента</h1>\n"
        + "\n".join(cards)
        + "\n</body></html>\n"
    )
    path = target_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def serve_directory(root: Path, port: int = 0) -> tuple[Any, str]:
    """Поднять локальный HTTP-сервер для папки и вернуть `(server, base_url)`."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, actual_port = server.server_address
    return server, f"http://{host}:{actual_port}"


# %%
# TASK 2.2 — селекторы паука
class CompetitorSpider(scrapy.Spider if scrapy else object):
    """Паук по локальному «сайту конкурента» (карточки датасетов)."""

    name = "competitor"

    CARDS_SELECTOR = "div.product-card"       # дано: контейнер карточки
    NAME_SELECTOR = ""                         # TODO (2.2): название датасета
    PRICE_SELECTOR = ""                        # TODO (2.2): цена
    CATEGORY_SELECTOR = "span.category::text"  # дано: категория

    def __init__(self, start_url: str | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url] if start_url else []


def run_spider(start_url: str) -> list[dict[str, Any]]:
    """Запустить паука и вернуть список карточек `{name, price, category}`."""
    if scrapy is None:
        raise RuntimeError(
            "Scrapy не установлен. Установите: uv run --project \"$SPUTNIK_REPO\" "
            "--with scrapy python seminar_02.py"
        )
    items: list[dict[str, Any]] = []

    class CollectorSpider(CompetitorSpider):
        def parse(self, response: Any, **kwargs: Any) -> None:  # noqa: D102
            if not self.NAME_SELECTOR or not self.PRICE_SELECTOR:
                # До выполнения 2.2 селекторы пусты: не отдаём Scrapy пустой CSS,
                # иначе он печатает SelectorSyntaxError и пугает студента.
                return
            for card in response.css(self.CARDS_SELECTOR):
                items.append(
                    {
                        "name": (card.css(self.NAME_SELECTOR).get() or "").strip(),
                        "price": (card.css(self.PRICE_SELECTOR).get() or "").strip(),
                        "category": (card.css(self.CATEGORY_SELECTOR).get() or "").strip(),
                    }
                )

    process = CrawlerProcess(
        settings={"LOG_LEVEL": "ERROR", "ROBOTSTXT_OBEY": False, "HTTPERROR_ALLOW_ALL": True}
    )
    process.crawl(CollectorSpider, start_url=start_url)
    process.start()
    return items


# %% [markdown]
# ## 4. Задание 2.3 — партнёрский CSV чанками
#
# Партнёр отдаёт выгрузку CSV. Читать её целиком в память нельзя: считаем строки
# чанками и замеряем пик памяти через `tracemalloc`.

# %%
def generate_partner_csv(path: Path, n_rows: int = N_CSV_ROWS, seed: int = SEED) -> Path:
    """Детерминированно сгенерировать CSV выгрузку партнёра (n_rows строк)."""
    rng = random.Random(seed)
    base = datetime(2026, 9, 1, tzinfo=UTC)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("stationId,metric,value,measuredAt\n")
        for index in range(n_rows):
            handle.write(
                f"st_partner_{index % 6},TEMPERATURE,{rng.uniform(-20, 30):.2f},"
                f"{(base + timedelta(minutes=index)).isoformat()}\n"
            )
    return path


# %%
# TASK 2.3 — чтение чанками
def count_rows_chunked(path: Path, chunksize: int = 20_000) -> dict[str, Any]:
    """Посчитать строки CSV чанками и замерить пик памяти в МБ."""
    # TODO (2.3): читайте pd.read_csv(path, chunksize=chunksize), суммируйте
    # len(chunk); память замеряйте через tracemalloc.start()/get_traced_memory().
    # Верните {"rows": total, "peak_mb": peak / (1024*1024)}.
    raise NotImplementedError("Задание 2.3: реализуйте count_rows_chunked")


# %% [markdown]
# ## 5. Задание 2.4 — публикация чтений в sensor-gateway
#
# Чтение — это JSON-объект с `readingId, stationId, providerId, metric, value,
# unit, geo, measuredAt`. `receivedAt` проставляет только шлюз. Отправляем батч
# из 10 валидных чтений + 1 битая запись (без `stationId`) и смотрим
# `accepted/dead`.

# %%
def build_readings(n: int = 10, seed: int = SEED) -> list[dict[str, Any]]:
    """Сгенерировать n валидных чтений метеостанции (TEMPERATURE)."""
    rng = random.Random(seed)
    base = datetime(2026, 9, 1, tzinfo=UTC)
    readings: list[dict[str, Any]] = []
    for index in range(n):
        readings.append(
            {
                "readingId": f"{READING_PREFIX}{index:04d}",
                "stationId": "st_meteo-01",
                "providerId": "pv_meteo",
                "metric": "TEMPERATURE",
                "value": round(rng.uniform(-20.0, 30.0), 2),
                "unit": "C",
                "geo": {"lat": 59.93, "lon": 30.31},
                "measuredAt": (base + timedelta(minutes=index)).isoformat(),
            }
        )
    return readings


def broken_record() -> dict[str, Any]:
    """Битая запись: нет обязательного `stationId` (→ SCHEMA_MISMATCH)."""
    return {
        "readingId": f"{READING_PREFIX}broken",
        "providerId": "pv_meteo",
        "metric": "TEMPERATURE",
        "value": 21.5,
        "unit": "C",
        "measuredAt": "2026-09-01T00:00:00+00:00",
    }


def build_batch(n: int = 10, seed: int = SEED) -> list[dict[str, Any]]:
    """Батч для публикации: n валидных чтений + 1 битая запись."""
    return [*build_readings(n, seed), broken_record()]


# %%
# TASK 2.4 — публикация
def publish_readings(readings: list[dict[str, Any]]) -> dict[str, Any]:
    """Отправить список чтений в sensor-gateway и вернуть ответ JSON."""
    # TODO (2.4): httpx.post(f"{SENSOR_GATEWAY_URL}/api/v1/readings", json=readings).
    # Шлюз принимает объект или массив и возвращает {"accepted": N, "dead": M}.
    # Верните response.json().
    raise NotImplementedError("Задание 2.4: реализуйте publish_readings")


# %% [markdown]
# ## 6. Чтение bronze из MinIO
#
# `ingestion` читает `sensors.readings.v1`, дедуплицирует по `readingId` (Redis,
# TTL 24 ч) и пишет сырой слой `lake/bronze/{provider}/{dt}/part-*.ndjson`.
# Ниже — хелперы для проверки `receivedAt` и дедупа.

# %%
def minio_client() -> Any:
    """Создать boto3 S3-клиент для локального MinIO."""
    if boto3 is None:
        raise RuntimeError("boto3 не установлен: добавьте --with boto3")
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=MINIO_REGION,
    )


def bronze_readings(client: Any, reading_prefix: str = READING_PREFIX) -> list[dict[str, Any]]:
    """Собрать из bronze все чтения с `readingId` по префиксу."""
    out: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=MINIO_BUCKET, Prefix="bronze/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".ndjson"):
                continue
            body = client.get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read().decode("utf-8")
            for line in body.splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if str(record.get("readingId", "")).startswith(reading_prefix):
                    out.append(record)
    return out


def bronze_counts(client: Any, reading_prefix: str = READING_PREFIX) -> dict[str, int]:
    """Число строк и уникальных `readingId` в bronze по префиксу."""
    rows = bronze_readings(client, reading_prefix)
    return {"total": len(rows), "distinct": len({r["readingId"] for r in rows})}


def wait_bronze(client: Any, expected: int, timeout: float = 90.0) -> list[dict[str, Any]]:
    """Ждать, пока в bronze появится `expected` чтений с нашим префиксом."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = bronze_readings(client)
        if len(rows) >= expected:
            return rows
        time.sleep(2)
    return bronze_readings(client)


def check_received_at(readings: list[dict[str, Any]]) -> bool:
    """True, если у всех чтений `receivedAt >= measuredAt`."""
    for record in readings:
        if "receivedAt" not in record:
            return False
        received = datetime.fromisoformat(record["receivedAt"])
        measured = datetime.fromisoformat(record["measuredAt"])
        if received < measured:
            return False
    return True


# %% [markdown]
# ## 7. Задание 2.5 — дедуп по readingId
#
# Повторная отправка того же батча не должна плодить строки: `ingestion`
# увидит те же `readingId` и отправит их в DLQ с причиной `DUPLICATE`, а bronze
# не изменится.

# %%
# TASK 2.5 — дедуп
def verify_dedup(client: Any, batch: list[dict[str, Any]], wait_seconds: float = 6.0) -> dict[str, Any]:
    """Повторно отправить батч и сравнить счётчики bronze до/после."""
    # TODO (2.5):
    # 1) before = bronze_counts(client);
    # 2) publish_readings(batch) — повторная отправка;
    # 3) time.sleep(wait_seconds) — дать ingestion обработать;
    # 4) after = bronze_counts(client).
    # Верните {"before": before, "after": after, "resend": <ответ повторной отправки>}.
    raise NotImplementedError("Задание 2.5: реализуйте verify_dedup")


# %% [markdown]
# ## 8. Эксперимент — куда падает битое значение
#
# Отправляем две заведомо битые записи: `value: "abc"` (строка вместо числа) и
# `value: 999` (выход за границы TEMPERATURE `[-90, 60]`). Обе уходят в DLQ, но
# по разным причинам. Вопрос для обсуждения: где должна стоять проверка — у
# источника, на шлюзе или в озере?

# %%
# TASK — классификация причины отбраковки
def classify_reason(record: dict[str, Any]) -> str:
    """Вернуть причину DLQ для битой записи по правилам шлюза.

    Одна из: ``NULL_VALUE``, ``OUT_OF_RANGE``, ``SCHEMA_MISMATCH``.
    """
    # TODO: реализуйте правила.
    # Подсказки (метрика TEMPERATURE, границы [-90, 60]):
    # - value is None                    -> NULL_VALUE
    # - значение вне границ метрики      -> OUT_OF_RANGE
    # - не тот тип / отсутствует поле    -> SCHEMA_MISMATCH
    raise NotImplementedError("Эксперимент: реализуйте classify_reason")


def dirty_readings() -> list[dict[str, Any]]:
    """Две битые записи для эксперимента."""
    base: dict[str, Any] = {
        "stationId": "st_meteo-01",
        "providerId": "pv_meteo",
        "metric": "TEMPERATURE",
        "unit": "C",
        "measuredAt": "2026-09-01T00:00:00+00:00",
    }
    return [
        {**base, "readingId": f"{READING_PREFIX}dirty_1", "value": "abc"},
        {**base, "readingId": f"{READING_PREFIX}dirty_2", "value": 999},
    ]


# %% [markdown]
# ## 9. Выводы
#
# Заполните коротко, своими словами. Проверка смотрит только на наличие
# содержательного ответа, но преподаватель спросит по существу.

# %%
# TASK — выводы
# TODO: ответьте своими словами, 1–3 предложения на пункт.
ANSWERS: dict[str, str] = {
    "1": "",  # Как не сломать API партнёра при сборе его данных?
    "2": "",  # Что делать с дублями, если они всё же пришли?
    "3": "",  # Почему чтение чанками не всегда быстрее, чем целиком?
    "4": "",  # Где должна стоять проверка валидности: источник, шлюз или озеро?
}


# %% [markdown]
# ## 10. Прогон

# %%
stack: dict[str, bool] = {}
all_datasets: list[dict[str, Any]] | None = None
cards: list[dict[str, Any]] | None = None
chunked: dict[str, Any] | None = None
publish_result: dict[str, Any] | None = None
accepted_rows: list[dict[str, Any]] = []
dedup: dict[str, Any] | None = None
dirty_result: dict[str, Any] | None = None
api: httpx.Client | None = None
token: str | None = None

try:
    stack = check_stack()
    print("Стенд:", json.dumps(stack, ensure_ascii=False))
except Exception as error:
    print(f"Не удалось проверить стенд: {error}")

# %%
try:
    token = login()
    api = httpx.Client(
        base_url=GATEWAY_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    page = catalog_page(api, page_size=5)
    print("Покупатель вошёл, токен получен.")
    print("Пагинация:", json.dumps(page.get("pagination", {}), ensure_ascii=False))
    preview = pd.DataFrame(page.get("data", []))
    columns = [c for c in ("datasetId", "name", "category", "qualityScore") if c in preview]
    print_table(preview[columns] if columns else preview)
except Exception as error:
    print(f"Не удалось войти или прочитать каталог: {error}")

# %%
if api is not None:
    try:
        all_datasets = collect_all_datasets(api)
        print(f"Собрано датасетов: {len(all_datasets)}")
        frame = pd.DataFrame(all_datasets)
        columns = [c for c in ("datasetId", "name", "category") if c in frame]
        print_table(frame[columns] if columns else frame)
    except NotImplementedError as error:
        print(f"Задание 2.1 не выполнено: {error}")
else:
    print("Задание 2.1 пропущено: нет токена.")

# %%
try:
    with tempfile.TemporaryDirectory(prefix="mock_site_") as tmp:
        site_dir = Path(tmp)
        make_mock_site(site_dir)
        server, base_url = serve_directory(site_dir)
        try:
            cards = run_spider(base_url)
            print(f"Карточек собрано: {len(cards)}")
            print_table(pd.DataFrame(cards).head(5))
        finally:
            server.shutdown()
except RuntimeError as error:
    print(f"Задание 2.2 не выполнено: {error}")

# %%
try:
    with tempfile.TemporaryDirectory(prefix="partner_csv_") as tmp:
        csv_path = Path(tmp) / "partner.csv"
        generate_partner_csv(csv_path)
        chunked = count_rows_chunked(csv_path)
        print(f"Строк: {chunked['rows']}, пик памяти: {chunked['peak_mb']:.2f} МБ")
except NotImplementedError as error:
    print(f"Задание 2.3 не выполнено: {error}")

# %%
batch = build_batch()
try:
    publish_result = publish_readings(batch)
    print("Публикация:", json.dumps(publish_result, ensure_ascii=False))
except NotImplementedError as error:
    print(f"Задание 2.4 не выполнено: {error}")

# %%
if publish_result is not None:
    try:
        client = minio_client()
        accepted_rows = wait_bronze(client, expected=10)
        print(f"В bronze найдено чтений с префиксом `{READING_PREFIX}`: {len(accepted_rows)}")
        print("receivedAt >= measuredAt:", check_received_at(accepted_rows))
    except Exception as error:
        print(f"Проверка receivedAt не удалась: {error}")

# %%
if publish_result is not None:
    try:
        client = minio_client()
        dedup = verify_dedup(client, batch)
        print("Дедуп:", json.dumps(dedup, ensure_ascii=False))
    except NotImplementedError as error:
        print(f"Задание 2.5 не выполнено: {error}")
    except Exception as error:
        print(f"Проверка дедупа не удалась: {error}")

# %%
try:
    dirty_result = publish_readings(dirty_readings())
    print("Грязный батч:", json.dumps(dirty_result, ensure_ascii=False))
    print("classify_reason('abc'):", classify_reason(dirty_readings()[0]))
    print("classify_reason(999):", classify_reason(dirty_readings()[1]))
except NotImplementedError as error:
    print(f"Эксперимент не завершён: {error}")


# %% [markdown]
# ## 11. Проверки

# %%
def check_pagination(rows: list[dict[str, Any]], total: int) -> None:
    """Проверить полноту и уникальность собранного каталога."""
    assert len(rows) == total, f"собрано {len(rows)}, ожидалось {total}"
    ids = [r["datasetId"] for r in rows]
    assert len(set(ids)) == len(ids), "есть повторяющиеся datasetId"


def check_selectors(cards: list[dict[str, Any]]) -> None:
    """Проверить, что паук собрал карточки с корректной ценой."""
    assert len(cards) >= 20, f"карточек {len(cards)}, ожидалось >= 20"
    for card in cards:
        assert card.get("name"), "у карточки нет названия"
        assert float(card["price"]) > 0, f"некорректная цена: {card['price']!r}"


def check_chunked(result: dict[str, Any]) -> None:
    """Проверить подсчёт строк и пик памяти."""
    assert result["rows"] == N_CSV_ROWS, f"строк {result['rows']}, ожидалось {N_CSV_ROWS}"
    assert result["peak_mb"] < MEMORY_LIMIT_MB, (
        f"пик памяти {result['peak_mb']:.2f} МБ выше порога {MEMORY_LIMIT_MB} МБ"
    )


def check_publish(result: dict[str, Any], received_ok: bool) -> None:
    """Проверить accepted/dead и receivedAt >= measuredAt."""
    assert result.get("accepted") == 10, f"accepted {result.get('accepted')}, ожидалось 10"
    assert result.get("dead") == 1, f"dead {result.get('dead')}, ожидалось 1"
    assert received_ok, "receivedAt < measuredAt хотя бы у одного чтения"


def check_dedup(dedup: dict[str, Any]) -> None:
    """Проверить, что повторная отправка не изменила bronze."""
    before = dedup.get("before", {})
    after = dedup.get("after", {})
    assert before.get("distinct", 0) > 0, "до повторной отправки в bronze пусто"
    assert after["total"] == before["total"], (
        f"строк стало {after['total']}, было {before['total']} — дедуп не сработал"
    )
    assert after["distinct"] == before["distinct"], "появились новые readingId"


def check_experiment(dirty: dict[str, Any] | None) -> None:
    """Проверить классификацию причин и отбраковку грязного батча."""
    assert classify_reason(dirty_readings()[0]) == "SCHEMA_MISMATCH", (
        "'abc' должно классифицироваться как SCHEMA_MISMATCH"
    )
    assert classify_reason(dirty_readings()[1]) == "OUT_OF_RANGE", (
        "999 должно классифицироваться как OUT_OF_RANGE"
    )
    assert classify_reason({"value": None, "metric": "TEMPERATURE"}) == "NULL_VALUE", (
        "None должно классифицироваться как NULL_VALUE"
    )
    if dirty is not None:
        assert dirty.get("dead") == 2, f"грязный батч: dead {dirty.get('dead')}, ожидалось 2"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    received_ok = bool(accepted_rows) and check_received_at(accepted_rows)
    total = len(all_datasets) if all_datasets is not None else 0

    checks: list[tuple[str, Any]] = []
    if all_datasets is not None:
        checks.append(("2.1 пагинация", lambda: check_pagination(all_datasets, total)))
    else:
        checks.append(("2.1 пагинация", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if cards is not None:
        checks.append(("2.2 селекторы", lambda: check_selectors(cards)))
    else:
        checks.append(("2.2 селекторы", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if chunked is not None:
        checks.append(("2.3 чанки", lambda: check_chunked(chunked)))
    else:
        checks.append(("2.3 чанки", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if publish_result is not None:
        checks.append(("2.4 публикация", lambda: check_publish(publish_result, received_ok)))
    else:
        checks.append(("2.4 публикация", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if dedup is not None:
        checks.append(("2.5 дедуп", lambda: check_dedup(dedup)))
    else:
        checks.append(("2.5 дедуп", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    checks.append(("эксперимент", lambda: check_experiment(dirty_result)))
    if all(str(value).strip() for value in ANSWERS.values()):
        checks.append(("выводы", lambda: None))
    else:
        checks.append(("выводы", lambda: (_ for _ in ()).throw(AssertionError("заполните ANSWERS"))))

    failures = 0
    for name, check in checks:
        try:
            check()
        except Exception as error:
            failures += 1
            print(f"FAIL  {name}: {error}")
        else:
            print(f"PASS  {name}")
    print(f"\nИтог: {len(checks) - failures}/{len(checks)} проверок пройдено")


run_checks()
