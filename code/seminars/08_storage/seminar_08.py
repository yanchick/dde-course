# %% [markdown]
# # Семинар 8 — Современные хранилища данных
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Одно и то же чтение живёт в трёх местах: в озере, в колоночной витрине и в
# документной коллекции. Семинар про то, почему это не дублирование, а разные
# инструменты:
# 1. Раскладываем события по слоям `bronze → silver → gold` — задание 8.1.
# 2. Пишем партицию идемпотентно: повторная загрузка не плодит объекты — 8.2.
# 3. Разбираем MergeTree: партиции, части, `ORDER BY` — задание 8.3.
# 4. Считаем, почему колонки читаются дешевле строк — задание 8.4.
# 5. Храним двух провайдеров с разной схемой без миграции — задание 8.5.
# 6. Эксперимент: потеряли партицию — что сломается и как починить.
#
# Задания отмечены `# TASK` и `TODO`: заполните тела функций и `ANSWERS`.
# Демо-ячейки, генератор событий и проверки менять не нужно.
#
# Запуск (Docker не нужен, все задания вычислительные):
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# uv run --project "$SPUTNIK_REPO" python seminar_08.py
# ```
#
# > [!note] MinIO и ClickHouse — опция
# > Скрипт читает настоящий DDL `infra/clickhouse/01_fact_readings.sql`, если
# > репозиторий найден, иначе использует встроенный снимок. Запись идёт в
# > локальный словарь-«озеро»: это тот же контракт ключей, что у MinIO, но без
# > сетевых таймаутов. Read-only пользователи ClickHouse/Mongo — backlog SRV-23.

# %%
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

SEED = int(os.getenv("SEED", "42"))
DAYS = int(os.getenv("DAYS", "2"))
STATIONS = int(os.getenv("STATIONS", "3"))
READINGS_PER_STATION = int(os.getenv("READINGS_PER_STATION", "4"))
START_DAY = date(2026, 9, 30)  # две даты специально попадают в разные месяцы

PROVIDERS: tuple[tuple[str, str, str], ...] = (
    ("pv_meteo", "ds_weather-stations", "TEMPERATURE"),
    ("pv_air", "ds_air-quality", "PM2_5"),
    ("pv_energy", "ds_energy-consumption", "ENERGY_KWH"),
    ("pv_transport", "ds_traffic-flow", "TRAFFIC_FLOW"),
    ("pv_market", "ds_retail-sales", "REVENUE"),
)

DDL_SNAPSHOT = """
CREATE TABLE IF NOT EXISTS sputnik.fact_readings
(
    reading_id   String,
    station_id   String,
    provider_id  String,
    metric       LowCardinality(String),
    value        Float64,
    unit         String,
    lat          Float64,
    lon          Float64,
    measured_at  DateTime64(3, 'UTC'),
    received_at  DateTime64(3, 'UTC'),
    dt           Date DEFAULT toDate(measured_at)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(dt)
ORDER BY (station_id, metric, measured_at);
"""

FIELDS: tuple[str, ...] = (
    "readingId",
    "stationId",
    "providerId",
    "metric",
    "value",
    "dt",
)


# %% [markdown]
# ## 1. Репозиторий, события и DDL
#
# Пять провайдеров × два дня × три станции × четыре чтения = 120 событий.
# Даты `2026-09-30` и `2026-10-01` дают две разные месячные партиции — на них
# видно, как MergeTree режет данные и что значит «потеряли партицию».

# %%
def find_repo_root() -> Path | None:
    """Найти корень Sputnik-Mart, если он есть рядом."""
    candidates: list[Path] = []
    if env := os.getenv("SPUTNIK_REPO"):
        candidates.append(Path(env))
    candidates.extend([Path.cwd(), *Path.cwd().parents])
    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if (path / "docker-compose.yml").is_file() and (path / "infra").is_dir():
            return path
    return None


def load_ddl() -> tuple[str, str]:
    """Прочитать DDL из репозитория или вернуть снимок."""
    root = find_repo_root()
    if root is not None:
        path = root / "infra" / "clickhouse" / "01_fact_readings.sql"
        if path.is_file():
            return path.read_text(encoding="utf-8"), "repo"
    return DDL_SNAPSHOT, "snapshot"


def build_events(
    days: int = DAYS, stations: int = STATIONS, per_station: int = READINGS_PER_STATION, seed: int = SEED
) -> list[dict[str, Any]]:
    """Детерминированные чтения пяти провайдеров за два дня."""
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    index = 0
    for day_offset in range(days):
        day = START_DAY + timedelta(days=day_offset)
        for provider, dataset, metric in PROVIDERS:
            for station_index in range(stations):
                station = f"st_{provider.removeprefix('pv_')}-{station_index + 1:02d}"
                for reading in range(per_station):
                    index += 1
                    value = round(10 + 3 * math.sin(index / 5) + rng.uniform(-0.2, 0.2), 4)
                    measured = datetime(
                        day.year, day.month, day.day, reading * 6, index % 60, tzinfo=UTC
                    )
                    events.append(
                        {
                            "readingId": f"rd_{index:05d}",
                            "stationId": station,
                            "providerId": provider,
                            "datasetId": dataset,
                            "metric": metric,
                            "value": value,
                            "unit": "C" if metric == "TEMPERATURE" else "unit",
                            "measuredAt": measured.isoformat(),
                            "receivedAt": (measured + timedelta(seconds=3)).isoformat(),
                            "dt": day.isoformat(),
                        }
                    )
    return events


def bronze_path(event: dict[str, Any]) -> str:
    return f"bronze/{event['providerId']}/{event['dt']}/readings.ndjson"


def silver_path(event: dict[str, Any]) -> str:
    return f"silver/{event['datasetId']}/{event['dt']}/readings.ndjson"


def gold_path(event: dict[str, Any]) -> str:
    return f"gold/fact_readings/{event['dt']}/part-0.ndjson"


EVENTS = build_events()
DDL_TEXT, DDL_SOURCE = load_ddl()
print(f"события: {len(EVENTS)}, дни: {sorted({e['dt'] for e in EVENTS})}")
print(f"DDL: {DDL_SOURCE}")


# %% [markdown]
# ## 2. Задание 8.1 — слои озера
#
# Один и тот же объект лежит по трём путям:
# - `bronze/{provider}/{dt}/` — как пришло от провайдера;
# - `silver/{dataset}/{dt}/` — после валидации, по датасету;
# - `gold/fact_readings/{dt}/` — витрина фактов для ClickHouse.
#
# Соберите `build_lake_layers(events)`: словарь
# `{"bronze": {path: rows}, "silver": ..., "gold": ...}`. В каждом пути —
# только свои строки, без пустых объектов. Проверка сверяет число партиций,
# строк и наличие `dt` в каждом ключе.

# %%
# TASK 8.1 — слои озера
def build_lake_layers(events: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Разложить события по bronze/silver/gold с партицией по дате."""
    # TODO (8.1): разложите события по трём слоям озера.
    # Подсказки:
    # - ключи путей дают bronze_path/silver_path/gold_path;
    # - в каждом слое словарь path → список строк, пустых партиций быть не должно;
    # - не мутируйте исходные события: складывайте копии.
    raise NotImplementedError("Задание 8.1: реализуйте build_lake_layers")


# %%
# Разложение по слоям выполняется в блоке «Прогон».


# %% [markdown]
# ## 3. Задание 8.2 — идемпотентная запись партиции
#
# Партиция — единица перезаписи. Если писать `append`, повторный запуск DAGа
# удвоит строки; если писать объект целиком, повтор безопасен. В MinIO это
# `put_object` по тому же ключу, в ClickHouse — `ReplacingMergeTree`/`INSERT`
# с дедупом, но принцип один: ключ детерминирован.
#
# Соберите `write_partition(store, path, rows)`: отсортируйте строки по
# `readingId`, сериализуйте в NDJSON, положите в `store[path]` (перезапись) и
# верните `{path, rows, bytes, checksum}`.

# %%
def checksum(rows: list[dict[str, Any]]) -> str:
    """Отпечаток набора строк, не зависящий от порядка."""
    body = "\n".join(
        sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows)
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


# %%
# TASK 8.2 — идемпотентная запись
def write_partition(
    store: dict[str, bytes], path: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Перезаписать объект партиции и вернуть его метаданные."""
    # TODO (8.2): запишите партицию идемпотентно.
    # Подсказки:
    # - пустой путь — ошибка;
    # - сортируйте строки по readingId, чтобы checksum не зависел от порядка;
    # - сериализуйте NDJSON (json.dumps sort_keys) и перезапишите store[path];
    # - верните {path, rows, bytes, checksum}.
    raise NotImplementedError("Задание 8.2: реализуйте write_partition")


# %%
# Запись партиций выполняется в блоке «Прогон».


# %% [markdown]
# ## 4. Задание 8.3 — MergeTree: партиции и части
#
# `PARTITION BY toYYYYMM(dt)` кладёт сентябрь и октябрь в разные партиции, а
# `ORDER BY (station_id, metric, measured_at)` задаёт сортировку внутри части —
# по ней работает индекс и слияние.
#
# Соберите `parse_merge_tree(ddl)` → `{engine, partition_by, order_by}` и
# `simulate_parts(rows)` → список
# `{partition, rows, min_dt, max_dt}`. Часть — это файл внутри партиции; после
# merge несколько частей становятся одной, но сумма строк не меняется.

# %%
# TASK 8.3 — разбор MergeTree и частей
def parse_merge_tree(ddl: str) -> dict[str, Any]:
    """Вытащить движок, выражение партиционирования и ключ сортировки."""
    # TODO (8.3): разберите DDL.
    # Подсказки:
    # - ENGINE = <имя>, PARTITION BY <выражение>, ORDER BY (<колонки>);
    # - order_by верните кортежем колонок без пробелов;
    # - если чего-то нет — ValueError.
    raise NotImplementedError("Задание 8.3: реализуйте parse_merge_tree")


def simulate_parts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Сгруппировать строки в месячные партиции."""
    # TODO (8.3): сгруппируйте строки по месяцу dt.
    # Подсказки:
    # - ключ партиции — первые 7 символов dt (YYYY-MM);
    # - верните список {partition, rows, min_dt, max_dt}, отсортированный;
    # - сумма rows обязана остаться равной числу строк.
    raise NotImplementedError("Задание 8.3: реализуйте simulate_parts")


# %%
# Разбор MergeTree выполняется в блоке «Прогон».


# %% [markdown]
# ## 5. Задание 8.4 — колонки против строк
#
# Строковое хранилище читает строку целиком: чтобы взять `value`, оно тянет и
# `stationId`, и `unit`, и остальные поля. Колоночное — только запрошенные
# колонки. На 120 строках разница не «в разы быстрее» на секундомере, зато
# видна в единицах чтения.
#
# Соберите `scan_cost(rows, columns, mode)` → `{values_read, bytes}` и
# `benchmark(rows, columns)` → стоимости для `row`/`column` и `speedup`.
# Считать байты как 8 байт на значение — достаточно для сравнения.

# %%
# TASK 8.4 — стоимость чтения
def scan_cost(rows: list[dict[str, Any]], columns: tuple[str, ...], mode: str) -> dict[str, int | str]:
    """Сколько значений/байт прочитает строковое или колоночное хранилище."""
    # TODO (8.4): посчитайте стоимость чтения.
    # Подсказки:
    # - mode только "row" или "column", columns — непустой кортеж из FIELDS;
    # - строковое читает все FIELDS, колоночное — только columns;
    # - values_read = len(rows) * ширина, bytes = values_read * 8;
    # - верните {mode, values_read, bytes}.
    raise NotImplementedError("Задание 8.4: реализуйте scan_cost")


def benchmark(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> dict[str, Any]:
    """Сравнить строковое и колоночное чтение на одном запросе."""
    # TODO (8.4): сравните два режима.
    # Подсказки:
    # - вызовите scan_cost для row и column;
    # - speedup = bytes(row) / bytes(column), округлите до 4 знаков;
    # - верните {row, column, speedup}.
    raise NotImplementedError("Задание 8.4: реализуйте benchmark")


# %%
# Бенчмарк выполняется в блоке «Прогон».


# %% [markdown]
# ## 6. Задание 8.5 — Mongo: две схемы без миграции
#
# `provider_meta` хранит метаданные провайдеров. У метео-провайдера поля лежат
# в `schema`, у качества воздуха — в списке `metrics`; у одного есть диапазон,
# у другого нет. В реляционной таблице это была бы миграция или NULL-колонки,
# в документной — просто два документа.
#
# Соберите `normalize_provider(doc)` → `{provider_id, metrics: {name: {unit,
# range}}, has_email}`. `query_metric(collection, provider_id, metric)` должна
# вернуть метрику или `None`, не падая на отсутствующем поле.

# %%
PROVIDER_DOCS: list[dict[str, Any]] = [
    {
        "providerId": "pv_meteo",
        "displayName": "Метео-сеть",
        "schema": {
            "TEMPERATURE": {"unit": "C", "range": [-50, 60]},
            "HUMIDITY": {"unit": "%", "range": [0, 100]},
        },
        "contact": {"email": "ops@meteo.example"},
    },
    {
        "providerId": "pv_air",
        "displayName": "Городской воздух",
        "metrics": [
            {"name": "PM2_5", "unit": "µg/m³"},
            {"name": "NOISE", "unit": "dB"},
        ],
        "contact": {"telegram": "@air_ops"},
    },
]


# %%
# TASK 8.5 — документная схема
def normalize_provider(doc: dict[str, Any]) -> dict[str, Any]:
    """Привести два разных документа к одному виду для чтения."""
    # TODO (8.5): приведите документ к единому виду.
    # Подсказки:
    # - providerId обязателен, иначе ValueError;
    # - метрики лежат либо в schema{name: {unit, range}}, либо в metrics[];
    # - верните {provider_id, metrics: {name: {unit, range}}, has_email};
    # - has_email зависит от contact.email.
    raise NotImplementedError("Задание 8.5: реализуйте normalize_provider")


def query_metric(
    collection: list[dict[str, Any]], provider_id: str, metric: str
) -> dict[str, Any] | None:
    """Найти метрику провайдера, не требуя одинаковой схемы документов."""
    # TODO (8.5): найдите метрику без миграции схемы.
    # Подсказки:
    # - ищите документ по providerId;
    # - нормализуйте его и верните metrics.get(metric);
    # - если провайдера или метрики нет — None, без исключения.
    raise NotImplementedError("Задание 8.5: реализуйте query_metric")


# %%
# NoSQL-документы разбираются в блоке «Прогон».


# %% [markdown]
# ## 7. Эксперимент — потеря партиции
#
# Удаляем объекты за `2026-10-01` из «озера». Витрина за этот день пустеет, но
# соседний день цел — это и есть партиционирование: сбой локализован. Затем
# перезаписываем партицию из исходных событий и сверяем отпечаток.
#
# Соберите `experiment_partition_loss(store, events, lost_dt)`: верните
# `{missing_rows, repaired_rows, checksum_before, checksum_after, restored}`.

# %%
# TASK — эксперимент с партицией
def experiment_partition_loss(
    store: dict[str, bytes], events: list[dict[str, Any]], lost_dt: str
) -> dict[str, Any]:
    """Удалить партицию, восстановить её и сверить отпечаток."""
    # TODO (эксперимент): смоделируйте потерю и восстановление партиции.
    # Подсказки:
    # - постройте слои и запомните checksum по bronze;
    # - удалите из store все ключи с "/{lost_dt}/", посчитав missing_rows;
    # - перезапишите эти партиции из bronze через write_partition;
    # - соберите строки из store и сравните checksum_before/after;
    # - верните {missing_rows, repaired_rows, checksum_before, checksum_after, restored}.
    raise NotImplementedError("Эксперимент: реализуйте experiment_partition_loss")


# %% [markdown]
# ## 8. Выводы
#
# Ответьте своими словами, 1–3 предложения на пункт. Проверка смотрит только
# на наличие содержательного ответа, но преподаватель спросит по существу.

# %%
# TODO (выводы): ответьте на пять вопросов своими словами, 1–3 предложения.
ANSWERS: dict[str, str] = {
    "1": "",
    "2": "",
    "3": "",
    "4": "",
    "5": "",
}


# %% [markdown]
# ## 9. Прогон

# %%
LAKE_RESULT: dict[str, dict[str, list[dict[str, Any]]]] = {}
STORE: dict[str, bytes] = {}
WRITE_RESULTS: list[dict[str, Any]] = []
SECOND_WRITE: list[dict[str, Any]] = []
MERGE_RESULT: dict[str, Any] | None = None
PART_RESULT: list[dict[str, Any]] = []
BENCH_RESULT: dict[str, Any] | None = None
NORMALIZED_RESULT: list[dict[str, Any]] = []
EXPERIMENT: dict[str, Any] = {}

# %%
try:
    LAKE_RESULT = build_lake_layers(EVENTS)
    print(
        "слои: "
        + ", ".join(
            f"{layer}={len(parts)} объектов/{sum(len(rows) for rows in parts.values())} строк"
            for layer, parts in LAKE_RESULT.items()
        )
    )
except NotImplementedError as error:
    print(f"Задание 8.1 не выполнено: {error}")
except Exception as error:
    print(f"Задание 8.1 не удалось: {error}")

# %%
if not LAKE_RESULT:
    print("Задание 8.2 пропущено: сначала выполните 8.1 (нет слоёв озера).")
else:
    try:
        WRITE_RESULTS = [
            write_partition(STORE, path, rows)
            for path, rows in sorted(LAKE_RESULT["bronze"].items())
        ]
        SECOND_WRITE = [
            write_partition(STORE, path, rows)
            for path, rows in sorted(LAKE_RESULT["bronze"].items())
        ]
        print(
            f"запись: объектов={len(STORE)}, строк={sum(item['rows'] for item in WRITE_RESULTS)}, "
            f"повтор идемпотентен={all(a['checksum'] == b['checksum'] for a, b in zip(WRITE_RESULTS, SECOND_WRITE, strict=True))}"
        )
    except NotImplementedError as error:
        print(f"Задание 8.2 не выполнено: {error}")
    except Exception as error:
        print(f"Задание 8.2 не удалось: {error}")

# %%
try:
    MERGE_RESULT = parse_merge_tree(DDL_TEXT)
    PART_RESULT = simulate_parts(EVENTS)
    print(
        f"MergeTree: {MERGE_RESULT['engine']} / {MERGE_RESULT['partition_by']} / "
        f"{', '.join(MERGE_RESULT['order_by'])}; частей={len(PART_RESULT)}"
    )
except NotImplementedError as error:
    print(f"Задание 8.3 не выполнено: {error}")
except Exception as error:
    print(f"Задание 8.3 не удалось: {error}")

# %%
try:
    BENCH_RESULT = benchmark(EVENTS, ("stationId", "value"))
    print(
        f"чтение: row={BENCH_RESULT['row']['bytes']} B, column={BENCH_RESULT['column']['bytes']} B, "
        f"speedup={BENCH_RESULT['speedup']}x"
    )
except NotImplementedError as error:
    print(f"Задание 8.4 не выполнено: {error}")
except Exception as error:
    print(f"Задание 8.4 не удалось: {error}")

# %%
try:
    NORMALIZED_RESULT = [normalize_provider(doc) for doc in PROVIDER_DOCS]
    print(
        "провайдеры: "
        + ", ".join(
            f"{item['provider_id']}={sorted(item['metrics'])}" for item in NORMALIZED_RESULT
        )
    )
    print(f"  PM2_5 у pv_air: {query_metric(PROVIDER_DOCS, 'pv_air', 'PM2_5')}")
except NotImplementedError as error:
    print(f"Задание 8.5 не выполнено: {error}")
except Exception as error:
    print(f"Задание 8.5 не удалось: {error}")

# %%
try:
    if not LAKE_RESULT:
        raise NotImplementedError("Эксперимент: сначала выполните задание 8.1")
    store = {}
    for path, rows in sorted(LAKE_RESULT["bronze"].items()):
        write_partition(store, path, rows)
    EXPERIMENT = experiment_partition_loss(store, EVENTS, "2026-10-01")
    print(
        f"потеря партиции: missing={EXPERIMENT['missing_rows']}, "
        f"repaired={EXPERIMENT['repaired_rows']}, restored={EXPERIMENT['restored']}"
    )
except NotImplementedError as error:
    print(f"Эксперимент не выполнен: {error}")
except Exception as error:
    print(f"Эксперимент не удался: {error}")


# %% [markdown]
# ## 10. Проверки

# %%
def check_layers(lake: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    """8.1: 10 bronze, 10 silver, 2 gold; 120 строк в каждом слое."""
    assert set(lake) == {"bronze", "silver", "gold"}, f"слои: {sorted(lake)}"
    assert len(lake["bronze"]) == 10, f"bronze партиций {len(lake['bronze'])}"
    assert len(lake["silver"]) == 10, f"silver партиций {len(lake['silver'])}"
    assert len(lake["gold"]) == 2, f"gold партиций {len(lake['gold'])}"
    for layer, partitions in lake.items():
        assert all(rows for rows in partitions.values()), f"пустая партиция в {layer}"
        assert all("/2026-09-30/" in path or "/2026-10-01/" in path for path in partitions), (
            f"в {layer} есть путь без даты"
        )
        assert sum(len(rows) for rows in partitions.values()) == 120, f"{layer}: не 120 строк"


def check_write(store: dict[str, bytes], results: list[dict[str, Any]]) -> None:
    """8.2: 120 строк, повтор не плодит объекты и не меняет checksum."""
    assert len(store) == 10, f"объектов {len(store)}, ожидалось 10"
    assert sum(item["rows"] for item in results) == 120, "записано не 120 строк"
    assert all(item["bytes"] > 0 for item in results), "есть пустой объект"
    assert len(results) == len(SECOND_WRITE), "разное число результатов"
    for first, second in zip(results, SECOND_WRITE, strict=True):
        assert first["checksum"] == second["checksum"], f"{first['path']}: checksum изменился"
        assert first["path"] == second["path"]
    body = store[results[0]["path"]].decode("utf-8")
    assert len(body.splitlines()) == results[0]["rows"], "число строк в объекте не совпало"


def check_merge(tree: dict[str, Any], parts: list[dict[str, Any]]) -> None:
    """8.3: MergeTree, месячные партиции, сумма строк та же."""
    assert tree["engine"] == "MergeTree", f"engine={tree['engine']}"
    assert tree["partition_by"] == "toYYYYMM(dt)", f"partition_by={tree['partition_by']}"
    assert tree["order_by"] == ("station_id", "metric", "measured_at"), (
        f"order_by={tree['order_by']}"
    )
    assert len(parts) == 2, f"партиций {len(parts)}, ожидалось 2"
    assert {part["partition"] for part in parts} == {"2026-09", "2026-10"}
    assert sum(part["rows"] for part in parts) == 120, "сумма строк по частям не 120"


def check_benchmark(result: dict[str, Any]) -> None:
    """8.4: колонки читают в 3 раза меньше при 6 полях и 2 колонках."""
    assert result["row"]["values_read"] == 720, f"row values={result['row']['values_read']}"
    assert result["column"]["values_read"] == 240, f"column values={result['column']['values_read']}"
    assert result["row"]["bytes"] == 5760, f"row bytes={result['row']['bytes']}"
    assert result["column"]["bytes"] == 1920, f"column bytes={result['column']['bytes']}"
    assert result["speedup"] == 3.0, f"speedup={result['speedup']}"


def check_nosql(collection: list[dict[str, Any]]) -> None:
    """8.5: два провайдера, разные схемы, запрос без миграции."""
    assert len(collection) == 2, f"провайдеров {len(collection)}"
    by_id = {item["provider_id"]: item for item in collection}
    assert set(by_id["pv_meteo"]["metrics"]) == {"TEMPERATURE", "HUMIDITY"}
    assert set(by_id["pv_air"]["metrics"]) == {"PM2_5", "NOISE"}
    assert by_id["pv_meteo"]["metrics"]["TEMPERATURE"]["range"] == [-50, 60]
    assert by_id["pv_air"]["metrics"]["PM2_5"]["range"] is None
    assert query_metric(PROVIDER_DOCS, "pv_air", "PM2_5")["unit"] == "µg/m³"
    assert query_metric(PROVIDER_DOCS, "pv_meteo", "OZONE") is None


def check_experiment(result: dict[str, Any]) -> None:
    """Эксперимент: потеряно и восстановлено 60 строк, отпечаток совпал."""
    assert result["missing_rows"] == 60, f"missing={result['missing_rows']}"
    assert result["repaired_rows"] == 60, f"repaired={result['repaired_rows']}"
    assert result["restored"] is True, "checksum после восстановления не совпал"
    assert result["checksum_before"] == result["checksum_after"]


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    checks: list[tuple[str, Callable[[], None]]] = []
    if LAKE_RESULT:
        checks.append(("8.1 слои", lambda: check_layers(LAKE_RESULT)))
    else:
        checks.append(("8.1 слои", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if STORE and WRITE_RESULTS:
        checks.append(("8.2 запись", lambda: check_write(STORE, WRITE_RESULTS)))
    else:
        checks.append(("8.2 запись", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if MERGE_RESULT is not None:
        checks.append(("8.3 MergeTree", lambda: check_merge(MERGE_RESULT, PART_RESULT)))
    else:
        checks.append(("8.3 MergeTree", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if BENCH_RESULT is not None:
        checks.append(("8.4 колонки", lambda: check_benchmark(BENCH_RESULT)))
    else:
        checks.append(("8.4 колонки", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if NORMALIZED_RESULT:
        checks.append(("8.5 Mongo", lambda: check_nosql(NORMALIZED_RESULT)))
    else:
        checks.append(("8.5 Mongo", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if EXPERIMENT:
        checks.append(("эксперимент", lambda: check_experiment(EXPERIMENT)))
    else:
        checks.append(("эксперимент", lambda: (_ for _ in ()).throw(AssertionError("не выполнен"))))
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
