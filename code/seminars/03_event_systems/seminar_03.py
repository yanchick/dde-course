# %% [markdown]
# # Семинар 3 — Event-системы: Kafka и NATS ★
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Что делаем — работаем с Redpanda (Kafka API) напрямую через `aiokafka`:
# 1. Пишем и читаем топик, разбираем распределение станций по партициям (3.1).
# 2. Роняем `ingestion`, смотрим лаг группы `ingestion-bronze`, поднимаем (3.2).
# 3. Пишем идемпотентного консьюмера: дедуп по `readingId` (3.3).
# 4. Считаем tumbling window 60 с по станциям (3.4).
# 5. Сравниваем Kafka и NATS концептуально (3.5).
#
# Запуск:
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# docker compose --profile adv up -d
# uv run --project "$SPUTNIK_REPO" --with aiokafka --with httpx --with pandas \
#   python seminar_03.py
# ```

# %%
from __future__ import annotations

import asyncio
import inspect
import json
import os
import random
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.structs import TopicPartition

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

READINGS_TOPIC = "sensors.readings.v1"          # реальный топик стенда
PART_TOPIC = "sensors.seminar3.partitioned"      # учебный топик для 3.1
GROUP_ID = "ingestion-bronze"                    # группа ingestion
PARTITIONS = int(os.getenv("PARTITIONS", "3"))
SEED = int(os.getenv("SEED", "42"))
N_PERIODS = int(os.getenv("N_PERIODS", "30"))
INTERVAL_SEC = int(os.getenv("INTERVAL_SEC", "10"))
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "60"))
RUN_EXPERIMENT = os.getenv("RUN_EXPERIMENT") == "1"

STATIONS = [
    ("st_meteo-01", "pv_meteo", "TEMPERATURE"),
    ("st_meteo-02", "pv_meteo", "HUMIDITY"),
    ("st_air-01", "pv_air", "PM2_5"),
    ("st_air-02", "pv_air", "NOISE"),
    ("st_energy-01", "pv_energy", "ENERGY_KWH"),
    ("st_traffic-01", "pv_transport", "TRAFFIC_FLOW"),
]


# %% [markdown]
# ## 0. Стенд и Kafka-хелперы
#
# Семинар работает с профилем `adv`: нужна Redpanda (9092), `ingestion`
# (консьюмер) и `sensor-gateway`. Сначала — поиск репозитория (для
# `docker compose stop/start`) и проверка живости брокера.

# %%
def find_repo_root() -> Path:
    """Найти корень Sputnik-Mart по `docker-compose.yml` и папке `services`."""
    candidates: list[Path] = []
    if env := os.getenv("SPUTNIK_REPO"):
        candidates.append(Path(env))
    candidates.extend([Path.cwd(), *Path.cwd().parents])
    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if (path / "docker-compose.yml").is_file() and (path / "services").is_dir():
            return path
    raise RuntimeError("Не найден Sputnik-Mart. Укажите SPUTNIK_REPO=/путь/к/Sputnik-Mart")


def run_compose(root: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Выполнить `docker compose` в корне репозитория."""
    try:
        return subprocess.run(
            ["docker", "compose", "-f", str(root / "docker-compose.yml"), *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise RuntimeError("`docker compose` не найден в PATH") from error


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


async def kafka_alive(bootstrap: str = KAFKA_BOOTSTRAP, timeout: float = 5.0) -> bool:
    """Проверить, отвечает ли брокер (list_topics)."""
    async def _ping() -> bool:
        admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap)
        await admin.start()
        try:
            await admin.list_topics()
            return True
        finally:
            await admin.close()
    try:
        return await asyncio.wait_for(_ping(), timeout=timeout)
    except Exception:
        return False


def check_stack() -> dict[str, bool]:
    """Проверить доступность gateway и брокера Kafka."""
    return {
        "gateway": wait_http(f"{GATEWAY_URL}/healthz", timeout=15),
        "kafka": asyncio.run(kafka_alive()),
    }


# %% [markdown]
# ## 1. Данные и чтение/запись в Kafka
#
# Генерируем детерминированные чтения для 6 станций. Ключом сообщения всегда
# идёт `stationId` — так Kafka кладёт все записи одной станции в одну партицию
# и сохраняет порядок внутри неё.

# %%
def build_readings(
    prefix: str = "rd_sem3_",
    n_periods: int = N_PERIODS,
    interval_sec: int = INTERVAL_SEC,
    seed: int = SEED,
) -> list[dict[str, Any]]:
    """Детерминированные чтения: n_periods точек на станцию с шагом interval_sec."""
    rng = random.Random(seed)
    base = datetime(2026, 9, 1, tzinfo=UTC)
    readings: list[dict[str, Any]] = []
    for index in range(n_periods):
        measured = base + timedelta(seconds=interval_sec * index)
        for station_id, provider_id, metric in STATIONS:
            readings.append(
                {
                    "readingId": f"{prefix}{station_id}_{index:03d}",
                    "stationId": station_id,
                    "providerId": provider_id,
                    "metric": metric,
                    "value": round(rng.uniform(0.0, 100.0), 2),
                    "measuredAt": measured.isoformat(),
                }
            )
    return readings


def print_table(frame: pd.DataFrame) -> None:
    """Напечатать DataFrame без индекса (работает и вне Jupyter)."""
    if frame.empty:
        print("(пусто)")
    else:
        print(frame.to_string(index=False))


# %% [markdown]
# ## 2. Kafka-хелперы (produce / consume / lag)
#
# Это опора: функции ниже создают топик с заданным числом партиций, пишут
# сообщения с ключом `stationId`, читают их с партицией и offset, и считают лаг
# группы по разнице `end_offset - committed_offset`.

# %%
async def ensure_topic(topic: str, partitions: int, bootstrap: str = KAFKA_BOOTSTRAP) -> None:
    """Создать топик с N партиций, если его ещё нет (идемпотентно)."""
    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap)
    await admin.start()
    try:
        existing = await admin.list_topics()
        if topic in existing:
            return
        await admin.create_topics(
            [NewTopic(name=topic, num_partitions=partitions, replication_factor=1)]
        )
    finally:
        await admin.close()


async def produce_readings(topic: str, readings: list[dict[str, Any]], bootstrap: str = KAFKA_BOOTSTRAP) -> None:
    """Записать чтения в топик с ключом партиции = stationId."""
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
    )
    await producer.start()
    try:
        for reading in readings:
            await producer.send_and_wait(topic, key=reading["stationId"], value=reading)
    finally:
        await producer.stop()


async def topic_partitions(consumer: AIOKafkaConsumer, topic: str) -> list[int]:
    """Вернуть отсортированные партиции топика.

    В aiokafka < 0.14 ``partitions_for_topic`` был корутиной, в 0.14 стал
    синхронным. Поддерживаем оба варианта, чтобы семинар не зависел от версии.
    """
    partitions = consumer.partitions_for_topic(topic)
    if inspect.isawaitable(partitions):
        partitions = await partitions
    return sorted(partitions or [])


async def topic_end_offsets(topic: str, bootstrap: str = KAFKA_BOOTSTRAP) -> dict[TopicPartition, int]:
    """Снять текущие end-offset по партициям — границу «до» новой записи."""
    consumer = AIOKafkaConsumer(topic, bootstrap_servers=bootstrap, enable_auto_commit=False, group_id=None)
    await consumer.start()
    try:
        partitions = await topic_partitions(consumer, topic)
        return await consumer.end_offsets([TopicPartition(topic, p) for p in partitions])
    finally:
        await consumer.stop()


async def collect_records(
    topic: str,
    max_messages: int,
    bootstrap: str = KAFKA_BOOTSTRAP,
    start_offsets: dict[TopicPartition, int] | None = None,
) -> list[dict[str, Any]]:
    """Прочитать топик и вернуть записи с партицией, offset и ключом.

    С ``start_offsets`` читаем с переданных позиций, иначе — с начала топика.
    """
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        group_id=None,
        key_deserializer=lambda b: b.decode("utf-8"),
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    await consumer.start()
    records: list[dict[str, Any]] = []
    try:
        partitions = await topic_partitions(consumer, topic)
        # aiokafka: assign() и подписка на топик из конструктора взаимоисключающи,
        # поэтому сначала отписываемся и читаем вручную с начала.
        consumer.unsubscribe()
        tps = [TopicPartition(topic, p) for p in partitions]
        consumer.assign(tps)
        if start_offsets:
            for tp in tps:
                consumer.seek(tp, start_offsets.get(tp, 0))
        else:
            await consumer.seek_to_beginning()
        async for message in consumer:
            records.append(
                {
                    "station_id": message.key,
                    "partition": message.partition,
                    "offset": message.offset,
                    "readingId": message.value.get("readingId"),
                    "value": message.value.get("value"),
                    "measuredAt": message.value.get("measuredAt"),
                }
            )
            if len(records) >= max_messages:
                break
    finally:
        await consumer.stop()
    return records


async def produce_and_collect(
    topic: str,
    readings: list[dict[str, Any]],
    partitions: int = PARTITIONS,
    bootstrap: str = KAFKA_BOOTSTRAP,
) -> list[dict[str, Any]]:
    """Создать топик, записать чтения и прочитать их обратно с партициями."""
    await ensure_topic(topic, partitions, bootstrap)
    start_offsets = await topic_end_offsets(topic, bootstrap)
    await produce_readings(topic, readings, bootstrap)
    return await collect_records(topic, len(readings), bootstrap, start_offsets)


# %%
async def get_group_lag(topic: str, group_id: str, bootstrap: str = KAFKA_BOOTSTRAP) -> dict[str, Any]:
    """Считать лаг группы: ``end_offset - committed_offset`` по партициям."""
    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap)
    await admin.start()
    try:
        committed = await admin.list_consumer_group_offsets(group_id)
    finally:
        await admin.close()

    consumer = AIOKafkaConsumer(topic, bootstrap_servers=bootstrap, enable_auto_commit=False, group_id="seminar3-lag-probe")
    await consumer.start()
    try:
        tps = [TopicPartition(topic, p) for p in await topic_partitions(consumer, topic)]
        end = await consumer.end_offsets(tps)
    finally:
        await consumer.stop()

    per_partition: dict[int, dict[str, int]] = {}
    total = 0
    for tp in tps:
        committed_offset = committed.get(tp)
        committed_offset = committed_offset.offset if committed_offset is not None else 0
        lag = end.get(tp, 0) - committed_offset
        total += lag
        per_partition[tp.partition] = {
            "end": end.get(tp, 0),
            "committed": committed_offset,
            "lag": lag,
        }
    return {"total_lag": total, "per_partition": per_partition}


# %% [markdown]
# ## 3. Задание 3.1 — распределение станций по партициям
#
# В топике `sensors.seminar3.partitioned` 3 партиции, сообщения шли с ключом
# `stationId`. Заполните анализ: какая станция в какой партиции, все ли партиции
# задействованы и не нарушен ли порядок offset внутри партиции.

# %%
# TASK 3.1 — партиции
def analyze_partitions(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Разобрать распределение записей по партициям.

    `records` — список с ключами station_id, partition, offset, ...
    Верните словарь:
    {
      "station_partition": {station_id: partition},       # станция → партиция
      "used_partitions": [отсортированные номера партиций],
      "per_partition": {
          partition: {"count": int, "min_offset": int,
                       "max_offset": int, "ordered": bool},
      },
    }
    `ordered=True`, если offset внутри партиции идут подряд без пропусков.
    """
    # TODO (3.1): реализуйте разбор.
    # Подсказки:
    # - соберите station -> partition и partition -> list[offset];
    # - для каждой партиции: count, min, max, ordered = offsets == range(min, max+1).
    raise NotImplementedError("Задание 3.1: реализуйте analyze_partitions")


# %% [markdown]
# ## 4. Задание 3.2 — лаг consumer group
#
# Останавливаем `ingestion`, пишем N чтений в `sensors.readings.v1`, лаг растёт.
# Поднимаем `ingestion` — консьюмер дочитывает и коммитит, лаг падает до нуля.

# %%
# TASK 3.2 — лаг
def run_lag_recovery(
    root: Path,
    readings: list[dict[str, Any]],
    wait_after: float = 30.0,
) -> dict[str, Any]:
    """Остановить ingestion, создать лаг, поднять и дождаться его обнуления."""
    # TODO (3.2):
    # 1) run_compose(root, "stop", "ingestion");
    # 2) asyncio.run(produce_readings(READINGS_TOPIC, readings));
    # 3) lag_before = asyncio.run(get_group_lag(READINGS_TOPIC, GROUP_ID));
    # 4) run_compose(root, "start", "ingestion");
    # 5) в цикле до wait_after секунд: asyncio.run(get_group_lag(...)) и выход,
    #    когда total_lag == 0; сохранить lag_after.
    # 6) в finally обязательно run_compose(root, "start", "ingestion").
    # Верните {"lag_before": ..., "lag_after": ..., "produced": len(readings)}.
    raise NotImplementedError("Задание 3.2: реализуйте run_lag_recovery")


# %% [markdown]
# ## 5. Задание 3.3 — идемпотентный консьюмер
#
# At-least-once доставляет сообщения повторно. Консьюмер обязан дедуплицировать
# по `readingId`: первое вхождение оставляем, повторы помечаем.

# %%
# TASK 3.3 — дедуп
def dedup_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Разложить сообщения на уникальные и дубли по readingId.

    Верните {"kept": [уникальные], "duplicates": [повторные readingId]}.
    """
    # TODO (3.3): реализуйте дедуп по messages[i]["readingId"].
    raise NotImplementedError("Задание 3.3: реализуйте dedup_messages")


# %% [markdown]
# ## 6. Задание 3.4 — tumbling window 60 с
#
# Сгруппируйте чтения по (станция, окно 60 с) и посчитайте avg/min/max.
# Окно = ``floor(measuredAt / 60) * 60``. Сумма count по всем окнам должна
# равняться числу исходных записей.

# %%
# TASK 3.4 — окно
def tumbling_window(records: list[dict[str, Any]], window_seconds: int = WINDOW_SECONDS) -> list[dict[str, Any]]:
    """Посчитать avg/min/max по станциям внутри tumbling-окон.

    `records` — список с ключами station_id, value, measuredAt.
    Верните список {"station_id", "window_start", "count", "avg", "min", "max"}.
    """
    # TODO (3.4): сгруппируйте записи и агрегируйте.
    # Подсказка: window_start = int(ts.timestamp() // window_seconds) * window_seconds.
    raise NotImplementedError("Задание 3.4: реализуйте tumbling_window")


# %% [markdown]
# ## 7. Задание 3.5 — Kafka vs NATS
#
# В репозитории NATS нет (он в P2, см. ТЗ §7.3), поэтому сравнение — таблица.
# Заполните по 4 критериям: гарантия доставки, порядок, хранение, сценарий.

# %%
# TASK 3.5 — сравнение
KAFKA_NATS: dict[str, dict[str, str]] = {
    "Гарантия доставки": {"Kafka": "", "NATS": ""},
    "Порядок сообщений": {"Kafka": "", "NATS": ""},
    "Хранение / retention": {"Kafka": "", "NATS": ""},
    "Сценарий применения": {"Kafka": "", "NATS": ""},
}


# %% [markdown]
# ## 8. Эксперимент — убить брокер на 20 секунд
#
# Останавливаем `redpanda`, пробуем записать (продюсер падает/таймаутит),
# поднимаем и записываем снова. Обсудите, что дают `acks` и какие guarantee
# получаются на стороне продюсера и консьюмера.

# %%
async def try_produce(topic: str, reading: dict[str, Any], bootstrap: str = KAFKA_BOOTSTRAP, timeout: float = 8.0) -> bool:
    """Попытаться записать одно чтение; False при таймауте/ошибке."""
    async def _do() -> bool:
        producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap,
            key_serializer=lambda k: k.encode("utf-8"),
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )
        await producer.start()
        try:
            await producer.send_and_wait(topic, key=reading["stationId"], value=reading)
            return True
        finally:
            await producer.stop()
    try:
        return await asyncio.wait_for(_do(), timeout=timeout)
    except Exception:
        return False


async def wait_kafka(bootstrap: str = KAFKA_BOOTSTRAP, timeout: float = 60.0) -> bool:
    """Ждать, пока брокер снова не ответит на list_topics."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await kafka_alive(bootstrap, timeout=5):
            return True
        await asyncio.sleep(2)
    return False


def run_broker_experiment(root: Path) -> dict[str, Any]:
    """Остановить redpanda, проверить запись, поднять и записать снова."""
    reading: dict[str, Any] = {
        "readingId": "rd_sem3_exp",
        "stationId": "st_meteo-01",
        "providerId": "pv_meteo",
        "metric": "TEMPERATURE",
        "value": 1.0,
        "measuredAt": "2026-09-01T00:00:00+00:00",
    }
    # TODO (эксперимент):
    # 1) run_compose(root, "stop", "redpanda"); подождать 5 с;
    # 2) down_ok = asyncio.run(try_produce(READINGS_TOPIC, reading, timeout=8));
    # 3) run_compose(root, "start", "redpanda");
    # 4) recovered = asyncio.run(wait_kafka());
    # 5) up_ok = asyncio.run(try_produce(READINGS_TOPIC, reading, timeout=30)), если recovered.
    # 6) в finally поднять redpanda и дождаться wait_kafka; затем поднять
    #    ingestion (у него нет restart-политики, он упал вместе с брокером)
    #    и дождаться, пока лаг группы снова станет 0.
    # Верните {"produce_while_down": down_ok, "kafka_recovered": recovered,
    #          "produce_after_recovery": up_ok}.
    raise NotImplementedError("Эксперимент: реализуйте run_broker_experiment")


# %% [markdown]
# ## 9. Выводы
#
# Заполните коротко, своими словами. Проверка смотрит только на наличие
# содержательного ответа, но преподаватель спросит по существу.

# %%
# TASK — выводы
# TODO: ответьте своими словами, 1–3 предложения на пункт.
ANSWERS: dict[str, str] = {
    "1": "",  # Почему оплатам нельзя at-least-once?
    "2": "",  # Что такое offset и чем он отличается от acknowledgement?
    "3": "",  # Когда Kafka избыточен, а когда оправдан?
    "4": "",  # Где гарантируется порядок: по ключу в партиции или во всей теме?
    "5": "",  # Вывод по таблице Kafka/NATS — одно предложение.
}


# %% [markdown]
# ## 10. Прогон

# %%
root: Path | None = None
stack: dict[str, bool] = {}
records: list[dict[str, Any]] = []
partition_result: dict[str, Any] | None = None
lag_result: dict[str, Any] | None = None
dedup_result: dict[str, Any] | None = None
window_result: list[dict[str, Any]] | None = None
broker_result: dict[str, Any] | None = None
dedup_input: list[dict[str, Any]] = []

try:
    root = find_repo_root()
    print(f"Репозиторий: {root}")
except RuntimeError as error:
    print(f"{error}")

try:
    stack = check_stack()
    print("Стенд:", json.dumps(stack, ensure_ascii=False))
except Exception as error:
    print(f"Не удалось проверить стенд: {error}")

# %%
try:
    readings = build_readings()
    print(f"Сгенерировано чтений: {len(readings)}")
    records = asyncio.run(produce_and_collect(PART_TOPIC, readings))
    print(f"Прочитано из `{PART_TOPIC}`: {len(records)}")
    preview = pd.DataFrame(records)
    columns = [c for c in ("station_id", "partition", "offset", "readingId") if c in preview]
    print_table(preview[columns].head(12) if columns else preview)
except Exception as error:
    print(f"Не удалось поработать с Kafka (задание 3.1): {error}")

# %%
if records:
    try:
        partition_result = analyze_partitions(records)
        print("Распределение по партициям:")
        print(json.dumps(partition_result, ensure_ascii=False, indent=2))
    except NotImplementedError as error:
        print(f"Задание 3.1 не выполнено: {error}")

# %%
if root is not None:
    try:
        lag_readings = build_readings(prefix="rd_sem3_lag_", n_periods=5)
        lag_result = run_lag_recovery(root, lag_readings)
        print("Лаг:", json.dumps(lag_result, ensure_ascii=False, indent=2, default=str))
    except NotImplementedError as error:
        print(f"Задание 3.2 не выполнено: {error}")
    except Exception as error:
        print(f"Задание 3.2 не удалось: {error}")
else:
    print("Задание 3.2 пропущено: не найден репозиторий.")

# %%
dedup_input = [
    {"readingId": "rd_a"}, {"readingId": "rd_b"}, {"readingId": "rd_a"},
    {"readingId": "rd_c"}, {"readingId": "rd_b"}, {"readingId": "rd_b"},
]
try:
    dedup_result = dedup_messages(dedup_input)
    print("Дедуп:", json.dumps(dedup_result, ensure_ascii=False))
except NotImplementedError as error:
    print(f"Задание 3.3 не выполнено: {error}")

# %%
if records:
    try:
        window_result = tumbling_window(records)
        print(f"Окон: {len(window_result)}")
        print_table(pd.DataFrame(window_result).head(12))
    except NotImplementedError as error:
        print(f"Задание 3.4 не выполнено: {error}")

# %%
if RUN_EXPERIMENT and root is not None:
    try:
        broker_result = run_broker_experiment(root)
        print("Эксперимент (брокер):", json.dumps(broker_result, ensure_ascii=False))
    except NotImplementedError as error:
        print(f"Эксперимент не завершён: {error}")
else:
    print(
        "Эксперимент пропущен. Запустите с RUN_EXPERIMENT=1, когда стенд поднят "
        "и вы готовы остановить `redpanda`."
    )


# %% [markdown]
# ## 11. Проверки

# %%
def check_partitions(result: dict[str, Any], n_stations: int) -> None:
    """Проверить распределение станций по партициям."""
    sp = result["station_partition"]
    assert len(sp) == n_stations, f"станций {len(sp)}, ожидалось {n_stations}"
    assert len(result["used_partitions"]) >= 2, "задействовано < 2 партиций"
    for part, info in result["per_partition"].items():
        assert info["ordered"], f"в партиции {part} нарушен порядок (offset с пропусками)"


def check_lag(result: dict[str, Any]) -> None:
    """Проверить рост и обнуление лага."""
    assert result["lag_before"]["total_lag"] > 0, "лаг до подъёма должен быть > 0"
    assert result["lag_after"]["total_lag"] == 0, "лаг после подъёма должен стать 0"


def check_dedup(result: dict[str, Any], messages: list[dict[str, Any]]) -> None:
    """Проверить дедуп по readingId."""
    distinct = {m["readingId"] for m in messages}
    assert len(result["kept"]) == len(distinct), "kept != числу уникальных readingId"
    assert len(result["duplicates"]) == len(messages) - len(distinct), "не все дубли найдены"


def check_window(result: list[dict[str, Any]], n_records: int) -> None:
    """Проверить, что сумма окон равна числу записей."""
    total = sum(group["count"] for group in result)
    assert total == n_records, f"сумма count по окнам {total} != {n_records}"
    for group in result:
        assert group["count"] > 0, "пустое окно"
        assert group["min"] <= group["avg"] <= group["max"], "avg вне [min, max]"


def check_comparison(table: dict[str, dict[str, str]]) -> None:
    """Проверить заполненность таблицы Kafka/NATS."""
    for criterion, cells in table.items():
        assert cells.get("Kafka") and cells.get("NATS"), f"критерий {criterion!r} не заполнен"


def check_experiment(result: dict[str, Any]) -> None:
    """Проверить поведение продюсера при падении брокера."""
    assert result["produce_while_down"] is False, "пока брокер лежит, запись должна падать"
    assert result["kafka_recovered"] is True, "брокер не восстановился"
    assert result["produce_after_recovery"] is True, "после восстановления запись должна пройти"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    n_stations = len(STATIONS)
    n_records = len(records)

    checks: list[tuple[str, Any]] = []
    if partition_result is not None:
        checks.append(("3.1 партиции", lambda: check_partitions(partition_result, n_stations)))
    else:
        checks.append(("3.1 партиции", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if lag_result is not None:
        checks.append(("3.2 лаг", lambda: check_lag(lag_result)))
    else:
        checks.append(("3.2 лаг", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if dedup_result is not None:
        checks.append(("3.3 идемпотентность", lambda: check_dedup(dedup_result, dedup_input)))
    else:
        checks.append(("3.3 идемпотентность", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if window_result is not None:
        checks.append(("3.4 окно", lambda: check_window(window_result, n_records)))
    else:
        checks.append(("3.4 окно", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    checks.append(("3.5 сравнение", lambda: check_comparison(KAFKA_NATS)))
    if broker_result is not None:
        checks.append(("эксперимент", lambda: check_experiment(broker_result)))
    else:
        checks.append(("эксперимент", lambda: (_ for _ in ()).throw(AssertionError("не запущен (RUN_EXPERIMENT)"))))
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
