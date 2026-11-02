# %% [markdown]
# # Семинар 7 — ETL/ELT и оркестрация
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Пайплайн уже работает, но «работает» и «работает правильно» — разные вещи.
# Семинар про то, чем управляет оркестратор и как это проверить:
# 1. Читаем DAGи репозитория и собираем карту задач — задание 7.1.
# 2. Доказываем идемпотентность загрузки числами — задание 7.2.
# 3. Настраиваем сенсор свежести: ждать, а не падать — задание 7.3.
# 4. Сравниваем ETL и ELT на одном объёме — задание 7.4.
# 5. Разбираем лог падения: retry или terminal — задание 7.5.
# 6. Эксперимент: backfill с чекпоинта не должен менять результат.
#
# Задания отмечены `# TASK` и `TODO`: заполните тела функций и `ANSWERS`.
# Демо-ячейки, генератор событий и проверки менять не нужно.
#
# Запуск (Docker и Airflow не нужны, все задания вычислительные):
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# uv run --project "$SPUTNIK_REPO" python seminar_07.py
# ```
#
# > [!note] Живой Airflow — опция, а не требование
# > Скрипт читает `dags/*.py` из репозитория, если он найден, иначе работает
# > по встроенному снимку тех же DAGов. Управление DAGом из кода — backlog
# > SRV-19 (`scripts/airflow_client.py`); без него семинар всё равно
# > воспроизводим.

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
DAYS = int(os.getenv("DAYS", "3"))
BATCHES_PER_DAY = int(os.getenv("BATCHES_PER_DAY", "4"))
STATIONS_PER_STATION = int(os.getenv("READINGS_PER_STATION", "8"))
SLA_SECONDS = int(os.getenv("SLA_SECONDS", "600"))
SENSOR_TIMEOUT_SECONDS = int(os.getenv("SENSOR_TIMEOUT_SECONDS", "1800"))
START_DAY = date(2026, 9, 1)

STATIONS: tuple[tuple[str, str], ...] = (
    ("st_meteo-01", "TEMPERATURE"),
    ("st_air-01", "PM2_5"),
    ("st_energy-01", "ENERGY_KWH"),
)

# Снимок DAGов: используется, если репозиторий рядом не найден.
# В живом репозитории тот же разбор идёт по `dags/*.py`.
DAG_SNAPSHOT: dict[str, str] = {
    "ingest_readings": '''
dag_id="ingest_readings"
schedule="@hourly"
catchup=False
retries=3
wait_for_bronze >> pull_bronze >> validate >> silver >> transform >> load_gold
''',
    "deliver_subscription": '''
dag_id="deliver_subscription"
schedule="@continuous"
catchup=False
retries=3
wait_for_subscription >> select_fresh
''',
    "refresh_quality": '''
dag_id="refresh_quality"
schedule="@hourly"
catchup=False
retries=3
freshness >> recalculate
''',
    "sync_provider_exports": '''
dag_id="sync_provider_exports"
schedule="@daily"
catchup=False
retries=3
wait_for_files >> sync_exports
''',
    "retention_pii": '''
dag_id="retention_pii"
schedule="@daily"
catchup=False
retries=3
delete_expired_pii
''',
}


# %% [markdown]
# ## 1. Репозиторий и события
#
# Оркестратор управляет не «файлами», а партициями и ключами. Поэтому сначала
# готовим детерминированный поток чтений: 3 дня × 4 батча × 3 станции × 8
# значений = 288 событий и 4 намеренных дубля (повторная доставка из Kafka).

# %%
def find_repo_root() -> Path | None:
    """Найти корень Sputnik-Mart, если он есть рядом."""
    candidates: list[Path] = []
    if env := os.getenv("SPUTNIK_REPO"):
        candidates.append(Path(env))
    candidates.extend([Path.cwd(), *Path.cwd().parents])
    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if (path / "docker-compose.yml").is_file() and (path / "dags").is_dir():
            return path
    return None


def load_dag_sources() -> tuple[dict[str, str], str]:
    """Прочитать `dags/*.py` или вернуть встроенный снимок."""
    root = find_repo_root()
    if root is None:
        return dict(DAG_SNAPSHOT), "snapshot"
    sources: dict[str, str] = {}
    for path in sorted((root / "dags").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if DAG_ID_RE.search(text):
            sources[path.stem] = text
    return (sources, "repo") if sources else (dict(DAG_SNAPSHOT), "snapshot")


def build_events(
    days: int = DAYS, batches: int = BATCHES_PER_DAY, seed: int = SEED
) -> list[dict[str, Any]]:
    """События чтений: детерминированные значения и 4 повторные доставки."""
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    index = 0
    for day_offset in range(days):
        day = START_DAY + timedelta(days=day_offset)
        for batch in range(batches):
            hour = batch * 6
            for station, metric in STATIONS:
                for _ in range(STATIONS_PER_STATION):
                    index += 1
                    value = round(20 + 5 * math.sin(index / 7) + rng.uniform(-0.5, 0.5), 4)
                    measured = datetime(day.year, day.month, day.day, hour, index % 60, tzinfo=UTC)
                    events.append(
                        {
                            "readingId": f"rd_{index:05d}",
                            "stationId": station,
                            "providerId": "pv_meteo" if station.startswith("st_meteo") else "pv_demo",
                            "metric": metric,
                            "value": value,
                            "measuredAt": measured.isoformat(),
                            "receivedAt": (measured + timedelta(seconds=5)).isoformat(),
                            "dt": day.isoformat(),
                        }
                    )

    # At-least-once: те же readingId приходят ещё раз, позже и с тем же value.
    for duplicate in events[:4]:
        copy = dict(duplicate)
        copy["receivedAt"] = (
            datetime.fromisoformat(duplicate["receivedAt"]) + timedelta(seconds=30)
        ).isoformat()
        events.append(copy)
    rng.shuffle(events)
    return events


def digest(rows: list[dict[str, Any]]) -> str:
    """Стабильный отпечаток набора строк (порядок не важен)."""
    normalized = sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows)
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()[:16]


# %%
EVENTS = build_events()
print(f"события: {len(EVENTS)}, уникальных readingId: {len({e['readingId'] for e in EVENTS})}")
print(f"дни: {sorted({e['dt'] for e in EVENTS})}")


# %% [markdown]
# ## 2. Задание 7.1 — карта DAGов
#
# `parse_dag_source` уже разбирает исходник: `dag_id`, `schedule`, `catchup`,
# `retries` и цепочки `a >> b >> c`. Одна строка без `>>` — DAG из одной
# задачи (`retention_pii`).
#
# Соберите `build_dag_map`: по словарю исходников вернуть
# `{source, dags, total_tasks, ingest_order}`. В `dags` для каждого DAGа —
# `schedule`, `catchup`, `retries`, `tasks` (порядок как в цепочке).
# Проверка сверяет состав и порядок, а не форматирование исходников.

# %%
DAG_ID_RE = re.compile(r'dag_id\s*=\s*["\']([^"\']+)["\']')
SCHEDULE_RE = re.compile(r'schedule\s*=\s*["\']([^"\']+)["\']')
CATCHUP_RE = re.compile(r"catchup\s*=\s*(True|False)")
RETRIES_RE = re.compile(r'"retries"\s*:\s*(\d+)|retries\s*=\s*(\d+)')
TASK_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:>>\s*([A-Za-z_][A-Za-z0-9_]*)\s*)+$")
BARE_TASK_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TASK_ID_RE = re.compile(r'task_id\s*=\s*["\']([^"\']+)["\']')


def parse_dag_source(name: str, text: str) -> dict[str, Any]:
    """Разобрать один DAG: метаданные и цепочку задач."""
    dag_match = DAG_ID_RE.search(text)
    dag_id = dag_match.group(1) if dag_match else name
    schedule_match = SCHEDULE_RE.search(text)
    catchup_match = CATCHUP_RE.search(text)
    retries_match = RETRIES_RE.search(text)
    retries = int(next(group for group in retries_match.groups() if group)) if retries_match else 0

    tasks: list[str] = []
    declared = TASK_ID_RE.findall(text)
    if declared:
        tasks = declared
    else:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" in stripped:
                continue
            if ">>" in stripped:
                for part in stripped.split(">>"):
                    task = part.strip().split()[0] if part.strip() else ""
                    if task and TASK_RE.match(f"x >> {task}"):
                        tasks.append(task)
            elif BARE_TASK_RE.fullmatch(stripped):
                tasks.append(stripped)

    # Убираем повторы, сохраняя порядок, и отбрасываем слова, похожие на код.
    seen: set[str] = set()
    ordered = [task for task in tasks if not (task in seen or seen.add(task))]
    return {
        "dag_id": dag_id,
        "schedule": schedule_match.group(1) if schedule_match else "unknown",
        "catchup": catchup_match.group(1) == "True" if catchup_match else False,
        "retries": retries,
        "tasks": ordered,
    }


# %%
# TASK 7.1 — карта DAGов
def build_dag_map(sources: dict[str, str]) -> dict[str, Any]:
    """Собрать карту DAGов: метаданные, число задач и порядок ingest."""
    # TODO (7.1): соберите карту DAGов из исходников.
    # Подсказки:
    # - пройдите sources и разберите каждый через parse_dag_source;
    # - проверьте, что задач нет только у пустого DAGа, и dag_id не дублируется;
    # - в dags положите schedule/catchup/retries/tasks;
    # - верните source ("repo", если найден корень, иначе "snapshot"),
    #   dags, total_tasks и ingest_order (задачи ingest_readings).
    raise NotImplementedError("Задание 7.1: реализуйте build_dag_map")


# %% [markdown]
# ## 3. Задание 7.2 — идемпотентность загрузки
#
# ClickHouse пишет gold через `ReplacingMergeTree`: повторная строка с тем же
# ключом `(reading_id)` заменяет предыдущую по `received_at`. Kafka даёт
# at-least-once, поэтому дубли — норма, а не сбой.
#
# Соберите `upsert_events`: хранилище — словарь `readingId → row`. Для каждого
# события выберите строку с более поздним `receivedAt`; верните
# `{received, upserted, total}`. Повторный прогон того же батча не должен
# увеличивать `total`.

# %%
# TASK 7.2 — идемпотентная загрузка
def upsert_events(
    store: dict[str, dict[str, Any]], events: list[dict[str, Any]]
) -> dict[str, int]:
    """Upsert по readingId: побеждает более поздний receivedAt."""
    # TODO (7.2): реализуйте идемпотентный upsert.
    # Подсказки:
    # - store — словарь readingId → строка, менять его на месте;
    # - если ключа нет или receivedAt события не раньше текущего — замените;
    # - верните {received, upserted, total}.
    raise NotImplementedError("Задание 7.2: реализуйте upsert_events")


# %%
# Загрузка выполняется в блоке «Прогон»: студенческая версия не должна
# падать на импорте, пока задание не выполнено.


# %% [markdown]
# ## 4. Задание 7.3 — сенсор свежести
#
# `PythonSensor` в `ingest_readings` ждёт появления bronze. Если провайдер
# задерживается, DAG не должен падать сразу: он остаётся `running`, пока не
# истечёт таймаут. Это разные состояния, и путать их дорого: `failed` будит
# дежурного, `running` — нет.
#
# Соберите `sensor_decision(age_seconds, sla_seconds, timeout_seconds)`:
# `ready`, пока данные не старше SLA; `wait`, пока не истёк таймаут; `fail`
# после таймаута. Верните `{state, action, age_seconds, reason}`.

# %%
# TASK 7.3 — решение сенсора
def sensor_decision(
    age_seconds: float,
    sla_seconds: int = SLA_SECONDS,
    timeout_seconds: int = SENSOR_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Готово / ждать / упасть по возрасту данных."""
    # TODO (7.3): решите, что делать при данном возрасте данных.
    # Подсказки:
    # - проверьте 0 < sla_seconds < timeout_seconds;
    # - age ≤ SLA → ready/run; age < timeout → wait/reschedule;
    # - иначе → fail/alert;
    # - верните {state, action, age_seconds, reason}.
    raise NotImplementedError("Задание 7.3: реализуйте sensor_decision")


# %% [markdown]
# ## 5. Задание 7.4 — ETL против ELT
#
# На одном и том же наборе событий:
# - **ETL** — вычитать все строки в Python, посчитать агрегат, загрузить его;
# - **ELT** — загрузить сырьё в хранилище и агрегировать там, вернув клиенту
#   только результат.
#
# Результат обязан совпасть. Разница — в том, сколько строк пересекло границу
# «клиент ↔ хранилище»: считаем `client_rows`, а не секунды (таймеры шумят).
#
# Соберите `run_etl` и `run_elt`: обе возвращают
# `{rows, client_rows, digest}`. `rows` — агрегаты по `(dt, stationId)` с
# `count`, `sum`, `avg`, `min`, `max`.

# %%
def aggregate_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Агрегат по (dt, stationId): count/sum/avg/min/max."""
    buckets: dict[tuple[str, str], list[float]] = {}
    for event in events:
        key = (str(event["dt"]), str(event["stationId"]))
        buckets.setdefault(key, []).append(float(event["value"]))
    rows = [
        {
            "dt": dt,
            "stationId": station,
            "count": len(values),
            "sum": round(sum(values), 6),
            "avg": round(sum(values) / len(values), 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
        }
        for (dt, station), values in sorted(buckets.items())
    ]
    return rows


# %%
# TASK 7.4 — ETL и ELT
def run_etl(events: list[dict[str, Any]]) -> dict[str, Any]:
    """ETL: трансформация в клиенте, затем загрузка агрегатов."""
    # TODO (7.4): реализуйте ETL.
    # Подсказки:
    # - трансформируйте события в (dt, stationId, value);
    # - агрегируйте через aggregate_rows;
    # - client_rows — сколько строк пересекло границу «клиент ↔ хранилище»:
    #   трансформированные плюс загруженные агрегаты;
    # - верните {rows, client_rows, digest}.
    raise NotImplementedError("Задание 7.4: реализуйте run_etl")


def run_elt(events: list[dict[str, Any]]) -> dict[str, Any]:
    """ELT: сырьё загружается bulk, агрегат считает хранилище."""
    # TODO (7.4): реализуйте ELT.
    # Подсказки:
    # - «загрузите» сырьё как есть, агрегируйте через aggregate_rows;
    # - client_rows — только возвращённые агрегаты;
    # - digest обязан совпасть с run_etl.
    raise NotImplementedError("Задание 7.4: реализуйте run_elt")


# %%
# Сравнение ETL/ELT выполняется в блоке «Прогон».


# %% [markdown]
# ## 6. Задание 7.5 — разбор падения
#
# `retries=3` и exponential backoff спасают только от **временных** ошибок.
# Повторять `SchemaMismatch` или `401` бессмысленно: через 30 секунд схема не
# изменится, а токен сам не появится.
#
# Соберите `classify_failure(message)`: `retry` для сетевых ошибок, таймаутов,
# `429` и `5xx`; `terminal` для схемы, типов, `4xx` (кроме `429`) и нарушения
# ограничений. Верните `{action, code, reason}`.

# %%
FAILURES: tuple[tuple[str, str], ...] = (
    ("ConnectionError: postgres:5432 refused", "retry"),
    ("TimeoutError: broker did not respond in 30s", "retry"),
    ("HTTP 503 Service Unavailable from clickhouse", "retry"),
    ("HTTP 429 Too Many Requests, Retry-After: 2", "retry"),
    ("SchemaMismatch: column station_v2 is unknown", "terminal"),
    ("HTTP 401 Unauthorized: token expired", "terminal"),
)


# %%
# TASK 7.5 — классификация ошибки
def classify_failure(message: str) -> dict[str, str]:
    """Временная ошибка → retry, детерминированная → terminal."""
    # TODO (7.5): классифицируйте ошибку по тексту.
    # Подсказки:
    # - сначала проверяйте terminal: схема, типы, 4xx (кроме 429), auth;
    # - затем retry: сеть, таймаут, 429, 5xx, блокировки;
    # - верните {action, code, reason}; code — transient_error,
    #   permanent_error или unknown_error.
    raise NotImplementedError("Задание 7.5: реализуйте classify_failure")


# %%
# Разбор лога выполняется в блоке «Прогон».


# %% [markdown]
# ## 7. Эксперимент — backfill с чекпоинта
#
# Полный пересчёт трёх дней и дозагрузка с чекпоинта (первый день уже в gold)
# обязаны дать одинаковый отпечаток. Но второй прогон должен обработать меньше
# строк — иначе чекпоинт бесполезен.
#
# Соберите `backfill(events, checkpoint_day, store, full)`: `full=True` —
# прогнать все дни, `False` — только дни после `checkpoint_day`. Верните
# `{digest, processed, total}`. `store` — тот же upsert-склад, что в 7.2.

# %%
# TASK — эксперимент с backfill
def backfill(
    events: list[dict[str, Any]],
    checkpoint_day: str,
    store: dict[str, dict[str, Any]],
    full: bool = False,
) -> dict[str, Any]:
    """Пересчитать все дни или только дни после чекпоинта."""
    # TODO (эксперимент): реализуйте backfill.
    # Подсказки:
    # - при full=True берите все события, иначе только dt > checkpoint_day;
    # - прогоните выборку через upsert_events в тот же store;
    # - digest считайте по отсортированным строкам store;
    # - верните {digest, processed, total}.
    raise NotImplementedError("Эксперимент: реализуйте backfill")


# %%
# Эксперимент с backfill выполняется в блоке «Прогон».


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
DAG_SOURCES: dict[str, str] = {}
DAG_MAP: dict[str, Any] | None = None
GOLD: dict[str, dict[str, Any]] = {}
FIRST_LOAD: dict[str, int] | None = None
SECOND_LOAD: dict[str, int] | None = None
ETL: dict[str, Any] | None = None
ELT: dict[str, Any] | None = None
TRIAGE_RESULT: list[dict[str, str]] = []
EXPERIMENT: dict[str, Any] = {}

# %%
try:
    DAG_SOURCES, source_kind = load_dag_sources()
    DAG_MAP = build_dag_map(DAG_SOURCES)
    print(f"DAGи: {len(DAG_MAP['dags'])} из {source_kind}, задач всего {DAG_MAP['total_tasks']}")
    for dag_id, dag in DAG_MAP["dags"].items():
        print(f"  {dag_id:24} {dag['schedule']:11} retries={dag['retries']} tasks={len(dag['tasks'])}")
except NotImplementedError as error:
    print(f"Задание 7.1 не выполнено: {error}")
except Exception as error:
    print(f"Задание 7.1 не удалось: {error}")

# %%
try:
    FIRST_LOAD = upsert_events(GOLD, EVENTS)
    SECOND_LOAD = upsert_events(GOLD, EVENTS)
    print(
        f"идемпотентность: received={FIRST_LOAD['received']}, total={FIRST_LOAD['total']}, "
        f"повтор total={SECOND_LOAD['total']}"
    )
except NotImplementedError as error:
    print(f"Задание 7.2 не выполнено: {error}")
except Exception as error:
    print(f"Задание 7.2 не удалось: {error}")

# %%
try:
    scenario = [(120, "ready"), (900, "wait"), (2400, "fail")]
    for age, expected in scenario:
        decision = sensor_decision(age)
        print(f"  age={age:5}s → {decision['state']:5} ({decision['action']})")
except NotImplementedError as error:
    print(f"Задание 7.3 не выполнено: {error}")
except Exception as error:
    print(f"Задание 7.3 не удалось: {error}")

# %%
try:
    ETL, ELT = run_etl(EVENTS), run_elt(EVENTS)
    print(
        f"ETL/ELT: ETL client_rows={ETL['client_rows']}, ELT client_rows={ELT['client_rows']}, "
        f"строк агрегата={len(ELT['rows'])}, совпало={ETL['digest'] == ELT['digest']}"
    )
except NotImplementedError as error:
    print(f"Задание 7.4 не выполнено: {error}")
except Exception as error:
    print(f"Задание 7.4 не удалось: {error}")

# %%
try:
    TRIAGE_RESULT = [{"message": message, **classify_failure(message)} for message, _ in FAILURES]
    for item in TRIAGE_RESULT:
        print(f"  {item['action']:8} {item['code']:15} | {item['message']}")
except NotImplementedError as error:
    print(f"Задание 7.5 не выполнено: {error}")
except Exception as error:
    print(f"Задание 7.5 не удалось: {error}")

# %%
try:
    full_store: dict[str, dict[str, Any]] = {}
    full_run = backfill(EVENTS, "2026-09-01", full_store, full=True)
    resume_store: dict[str, dict[str, Any]] = {}
    upsert_events(resume_store, [event for event in EVENTS if str(event["dt"]) == "2026-09-01"])
    resume_run = backfill(EVENTS, "2026-09-01", resume_store, full=False)
    EXPERIMENT = {"full": full_run, "resume": resume_run}
    print(
        f"backfill: full={full_run['processed']} строк ({full_run['digest']}), "
        f"resume={resume_run['processed']} строк ({resume_run['digest']})"
    )
except NotImplementedError as error:
    print(f"Эксперимент не выполнен: {error}")
except Exception as error:
    print(f"Эксперимент не удался: {error}")


# %% [markdown]
# ## 10. Проверки

# %%
def check_dag_map(dag_map: dict[str, Any]) -> None:
    """7.1: пять DAGов, ingest из шести задач, retries и catchup как в репо."""
    dags = dag_map["dags"]
    assert len(dags) == 5, f"DAGов {len(dags)}, ожидалось 5"
    assert dag_map["total_tasks"] == 13, f"задач {dag_map['total_tasks']}, ожидалось 13"
    ingest = dags["ingest_readings"]
    assert ingest["tasks"] == [
        "wait_for_bronze",
        "pull_bronze",
        "validate",
        "silver",
        "transform",
        "load_gold",
    ], f"порядок ingest: {ingest['tasks']}"
    assert ingest["retries"] == 3, f"retries={ingest['retries']}"
    assert ingest["catchup"] is False, "catchup должен быть False"
    assert ingest["schedule"] == "@hourly", f"schedule={ingest['schedule']}"
    assert dags["retention_pii"]["tasks"] == ["delete_expired_pii"], "у retention_pii одна задача"
    assert all(dag["tasks"] for dag in dags.values()), "есть DAG без задач"


def check_idempotency(first: dict[str, int], second: dict[str, int], store: dict[str, Any]) -> None:
    """7.2: 292 события, 288 уникальных, повтор не меняет total."""
    assert first["received"] == 292, f"received={first['received']}, ожидалось 292"
    assert first["total"] == 288, f"total={first['total']}, ожидалось 288"
    assert second["total"] == first["total"], "повторный прогон изменил total"
    assert len(store) == 288, f"в store {len(store)} строк"
    latest = max(store.values(), key=lambda row: row["receivedAt"])
    assert latest["receivedAt"] > latest["measuredAt"], "нет более позднего receivedAt"


def check_sensor() -> None:
    """7.3: ready / wait / fail, задержка не равна падению."""
    ready = sensor_decision(120)
    wait = sensor_decision(900)
    failed = sensor_decision(2400)
    assert ready["state"] == "ready" and ready["action"] == "run"
    assert wait["state"] == "wait" and wait["action"] == "reschedule"
    assert failed["state"] == "fail" and failed["action"] == "alert"
    assert wait["state"] != failed["state"], "задержка должна быть wait, не fail"
    assert sensor_decision(SLA_SECONDS)["state"] == "ready", "граница SLA включительно"


def check_etl_elt(etl: dict[str, Any], elt: dict[str, Any]) -> None:
    """7.4: результаты равны, ELT тянет в клиент меньше строк."""
    assert etl["digest"] == elt["digest"], "результаты ETL и ELT различаются"
    assert len(etl["rows"]) == 9, f"агрегатов {len(etl['rows'])}, ожидалось 3 дня × 3 станции"
    assert elt["client_rows"] < etl["client_rows"], "ELT не снизил число строк в клиенте"
    assert etl["client_rows"] - elt["client_rows"] == 292, "разница должна быть 292 строки"


def check_triage(triage: list[dict[str, str]]) -> None:
    """7.5: хотя бы по две retry и terminal, решения совпадают с ожиданием."""
    assert len(triage) == len(FAILURES), f"разобрано {len(triage)} из {len(FAILURES)}"
    expected = {message: action for message, action in FAILURES}
    for item in triage:
        assert item["action"] == expected[item["message"]], (
            f"{item['message']!r} → {item['action']}, ожидалось {expected[item['message']]}"
        )
    assert sum(1 for item in triage if item["action"] == "retry") >= 2
    assert sum(1 for item in triage if item["action"] == "terminal") >= 2


def check_experiment(experiment: dict[str, Any]) -> None:
    """Эксперимент: тот же digest, меньше обработанных строк."""
    full, resume = experiment["full"], experiment["resume"]
    assert full["digest"] == resume["digest"], "digest полного и resume-прогона различаются"
    assert resume["processed"] < full["processed"], "resume не сэкономил строки"
    assert full["total"] == resume["total"] == 288, "total после backfill не 288"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    checks: list[tuple[str, Callable[[], None]]] = []
    if DAG_MAP is not None:
        checks.append(("7.1 DAGи", lambda: check_dag_map(DAG_MAP)))
    else:
        checks.append(("7.1 DAGи", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if FIRST_LOAD is not None and SECOND_LOAD is not None:
        checks.append(("7.2 идемпотентность", lambda: check_idempotency(FIRST_LOAD, SECOND_LOAD, GOLD)))
    else:
        checks.append(("7.2 идемпотентность", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    checks.append(("7.3 сенсор", check_sensor))
    if ETL is not None and ELT is not None:
        checks.append(("7.4 ETL/ELT", lambda: check_etl_elt(ETL, ELT)))
    else:
        checks.append(("7.4 ETL/ELT", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if TRIAGE_RESULT:
        checks.append(("7.5 разбор", lambda: check_triage(TRIAGE_RESULT)))
    else:
        checks.append(("7.5 разбор", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
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
