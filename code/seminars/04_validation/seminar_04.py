# %% [markdown]
# # Семинар 4 — Продвинутая очистка и валидация
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Что делаем — прогоняем данные через валидацию `bronze → silver`:
# 1. Пишем Pandera-схему (диапазон, не-null, enum) — задание 4.1.
# 2. Прогоняем `clean_readings` из репозитория — опора.
# 3. Пишем 2 Great-Expectations-ожидания — задание 4.2.
# 4. Разбираем DLQ по причинам — задание 4.3.
# 5. Ловим выброс PM2.5 через z-score — задание 4.4.
# 6. Сверяем `qualityScore` API с `report.json` — задание 4.5.
#
# Запуск:
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# docker compose --profile adv up -d
# uv run --project "$SPUTNIK_REPO" --with httpx python seminar_04.py
# ```
#
# `pandera`, `great_expectations` и `boto3` приходят из зависимостей
# репозитория (`sputnik-validation`, `sputnik-db`), поэтому отдельно их
# добавлять не нужно.

# %%
from __future__ import annotations

import json
import math
import os
import random
import statistics
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import pandera.pandas as pa

try:
    import boto3  # для записи report.json в MinIO
except ImportError:  # pragma: no cover - зависимость опциональна
    boto3 = None

from sim.dirty import DirtyConfig, contaminate
from sim.sensors import build_stations, generate_readings
from validation.quality_report import (
    report_for_dataset,
    report_key,
    report_payload,
    run_great_expectations,
)
from validation.validator import QualityMetrics, clean_readings

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "sputnik")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "sputnik123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lake")
MINIO_REGION = os.getenv("MINIO_REGION", "us-east-1")

SEED = int(os.getenv("SEED", "42"))
DATASET_ID = "ds_weather-stations"
PERIODS = int(os.getenv("PERIODS", "24"))
SPIKE_INDEX = int(os.getenv("SPIKE_INDEX", "30"))
SPIKE_FACTOR = float(os.getenv("SPIKE_FACTOR", "10.0"))
Z_THRESHOLD = float(os.getenv("Z_THRESHOLD", "3.0"))


# %% [markdown]
# ## 1. Данные: чистые и грязные чтения
#
# Чистые чтения генерируем через `sim.sensors`, загрязняем через `sim.dirty`
# (пропуски, дубли, выбросы) и явно добавляем три битые записи без `stationId`,
# чтобы в DLQ гарантированно попали все три причины.

# %%
def build_clean_records(periods: int = PERIODS, seed: int = SEED) -> list[dict[str, Any]]:
    """Детерминированные валидные чтения (6 станций × periods точек)."""
    return generate_readings(seed=seed, periods=periods, stations=build_stations())


def build_dirty_records(clean: list[dict[str, Any]], seed: int = SEED) -> list[dict[str, Any]]:
    """Загрязнённые чтения + три битые записи без `stationId` (SCHEMA_MISMATCH)."""
    contaminated = contaminate(
        clean,
        seed=seed,
        config=DirtyConfig(missing=0.08, duplicate=0.05, outlier=0.02, broken=0.0),
    )
    broken: list[dict[str, Any]] = []
    for index in range(3):
        record = dict(clean[index])
        record.pop("stationId", None)
        record["readingId"] = f"rd_sem4_broken_{index}"
        broken.append(record)
    return [*contaminated, *broken]


def defect_examples(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Найти по одному примеру каждого дефекта в загрязнённых записях."""
    counts = Counter(r.get("readingId") for r in records)
    missing = next((r for r in records if r.get("value") is None), None)
    broken = next((r for r in records if "stationId" not in r), None)
    duplicate = next((rid for rid, count in counts.items() if count and count > 1), None)
    return {
        "missing_value": missing,
        "broken_schema": broken,
        "duplicate_readingId": duplicate,
    }


def quarantine_as_dlq(quarantine: list[Any]) -> list[dict[str, Any]]:
    """Преобразовать карантин `clean_readings` в записи DLQ `{readingId, reason, raw}`."""
    return [
        {
            "readingId": row.raw.get("reading_id"),
            "reason": row.reason.value,
            "raw": row.raw,
        }
        for row in quarantine
    ]


def print_table(frame: pd.DataFrame) -> None:
    """Напечатать DataFrame без индекса (работает и вне Jupyter)."""
    if frame.empty:
        print("(пусто)")
    else:
        print(frame.to_string(index=False))


# %% [markdown]
# ## 2. Задание 4.1 — Pandera-схема
#
# Соберите схему с **тремя** проверками:
# - диапазон значения `value` (для `TEMPERATURE` — `[-90, 60]`);
# - не-null у `reading_id`;
# - enum у `metric` (список допустимых метрик).

# %%
CLEAN_DF = pd.DataFrame(
    [
        {"reading_id": "rd_c1", "metric": "TEMPERATURE", "value": 18.5},
        {"reading_id": "rd_c2", "metric": "TEMPERATURE", "value": 22.0},
    ]
)
DIRTY_DF = pd.DataFrame(
    [
        {"reading_id": "rd_d1", "metric": "TEMPERATURE", "value": 999.0},  # вне диапазона
        {"reading_id": "rd_d2", "metric": "TEMPERATURE", "value": None},   # null
        {"reading_id": None, "metric": "TEMPERATURE", "value": 18.5},      # null reading_id
        {"reading_id": "rd_d4", "metric": "INVALID", "value": 18.5},       # не enum
    ]
)


# %%
# TASK 4.1 — Pandera-схема
def build_reading_schema() -> Any:
    """Вернуть Pandera-схему с 3 проверками: диапазон, не-null, enum."""
    # TODO (4.1): верните pa.DataFrameSchema({...}).
    # Подсказки:
    # - reading_id: pa.Column(str, nullable=False);
    # - metric: pa.Column(str, checks=pa.Check.isin([...]), nullable=False);
    # - value: pa.Column(float, checks=pa.Check.in_range(-90.0, 60.0), nullable=False).
    raise NotImplementedError("Задание 4.1: реализуйте build_reading_schema")


def validate_with_schema(schema: Any, frame: pd.DataFrame) -> bool:
    """True, если фрейм проходит схему (без исключения)."""
    try:
        schema.validate(frame, lazy=True)
        return True
    except Exception:
        return False


# %% [markdown]
# ## 3. Опора: `clean_readings` → серебро, метрики и карантин
#
# Функция репозитория убирает пропуски, дубли и выбросы, восстанавливает
# пропуски ряда и возвращает `CleanBatch` (фрейм + карантин + метрики).

# %%
def run_pipeline(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Прогнать clean_readings и вернуть сводку по silver/карантину/метрикам."""
    batch = clean_readings(records)
    return {
        "silver_rows": len(batch.frame),
        "quarantine": len(batch.quarantine),
        "weather_score": round(batch.metrics_by_dataset.get(DATASET_ID, QualityMetrics()).quality_score, 4),
    }


# %% [markdown]
# ## 4. Задание 4.2 — два Great-Expectations ожидания
#
# Прогоните фрейм через GE с двумя ожиданиями: `value` не-null и `value` в
# диапазоне `[-90, 60]`. Верните `{"success": bool, "results": [...]}`.

# %%
# TASK 4.2 — Great Expectations
def run_ge_checks(frame: pd.DataFrame) -> dict[str, Any]:
    """Прогнать 2 GE-ожидания (value не-null и в диапазоне) по фрейму."""
    # TODO (4.2): используйте great_expectations:
    # 1) import great_expectations as gx;
    # 2) context = gx.get_context(mode="ephemeral");
    # 3) data_source = context.data_sources.add_pandas("demo");
    # 4) asset = data_source.add_dataframe_asset(name="readings");
    # 5) batch_definition = asset.add_batch_definition_whole_dataframe("batch");
    # 6) batch = batch_definition.get_batch(batch_parameters={"dataframe": frame});
    # 7) suite = context.suites.add(gx.ExpectationSuite(name="demo_suite"));
    # 8) suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="value"));
    # 9) suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="value", min_value=-90, max_value=60));
    # 10) result = batch.validate(suite).
    # Верните {"success": result.success, "results": [...]} (оберните в try/except,
    #       чтобы при отсутствии GE вернуть {"available": False}).
    raise NotImplementedError("Задание 4.2: реализуйте run_ge_checks")


# %% [markdown]
# ## 5. Задание 4.3 — разбор DLQ
#
# Сгруппируйте записи DLQ по причине отбраковки и верните `{reason: count}`.

# %%
# TASK 4.3 — DLQ
def parse_dlq(dlq_records: list[dict[str, Any]]) -> dict[str, int]:
    """Сгруппировать записи DLQ по `reason`: {причина: количество}."""
    # TODO (4.3): верните dict(Counter(r["reason"] for r in dlq_records)).
    raise NotImplementedError("Задание 4.3: реализуйте parse_dlq")


# %% [markdown]
# ## 6. Задание 4.4 — выброс PM2.5 через z-score
#
# В сезонном ряду PM2.5 есть суточная волна и один внедрённый выброс (умножаем
# значение на `SPIKE_FACTOR`). Найдите его по z-score, не помечая сезонный пик.

# %%
def build_pm25_series(
    n: int = 48,
    seed: int = SEED,
    spike_index: int = SPIKE_INDEX,
    spike_factor: float = SPIKE_FACTOR,
) -> list[float]:
    """Сезонный ряд PM2.5 (суточная волна + шум) с одним внедрённым выбросом."""
    rng = random.Random(seed)
    values = [
        round(35.0 + 15.0 * math.sin(2 * math.pi * index / 24.0) + rng.gauss(0.0, 1.0), 2)
        for index in range(n)
    ]
    values[spike_index] = round(values[spike_index] * spike_factor, 2)
    return values


def seasonal_peak_index(values: list[float], exclude: int) -> int:
    """Индекс сезонного максимума (без учёта внедрённого выброса)."""
    return max((index for index in range(len(values)) if index != exclude), key=values.__getitem__)


# %%
# TASK 4.4 — аномалии
def detect_anomalies(values: list[float], threshold: float = Z_THRESHOLD) -> list[int]:
    """Вернуть индексы, где |z-score| > threshold."""
    # TODO (4.4): среднее и ст. отклонение через statistics.mean/stdev;
    # z = (x - mean) / std; вернуть [i for i, x in enumerate(values) if abs(z_i) > threshold].
    raise NotImplementedError("Задание 4.4: реализуйте detect_anomalies")


# %% [markdown]
# ## 7. Задание 4.5 — сверка `qualityScore` API с `report.json`
#
# Соберите отчёт локально (`report_for_dataset`), запишите `report.json` в MinIO
# и сравните с тем, что отдаёт Quality API через gateway.

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


def write_report_to_minio(reports: dict[str, Any], dt: date) -> str:
    """Записать `report.json` в MinIO и вернуть ключ объекта."""
    s3 = minio_client()
    key = report_key(dt)
    body = json.dumps(report_payload(dt, reports), ensure_ascii=False, indent=2)
    s3.put_object(
        Bucket=MINIO_BUCKET, Key=key, Body=body.encode("utf-8"), ContentType="application/json"
    )
    return key


def get_quality_api_score(dataset_id: str) -> float:
    """Прочитать `qualityScore` датасета из Quality API (через gateway)."""
    response = httpx.get(f"{GATEWAY_URL}/api/v1/quality/{dataset_id}", timeout=20)
    response.raise_for_status()
    return float(response.json()["qualityScore"])


# %%
# TASK 4.5 — сверка
def reconcile_quality(metrics: Any, dataset_id: str, dt: date) -> dict[str, Any]:
    """Сверить qualityScore API с локальным report.json."""
    # TODO (4.5):
    # 1) report = report_for_dataset(metrics, dataset_id, dt);
    # 2) write_report_to_minio({dataset_id: report}, dt);
    # 3) api_score = get_quality_api_score(dataset_id);
    # 4) верните {"report_score": report["quality_score"], "api_score": api_score,
    #             "delta": abs(api_score - report["quality_score"])}.
    raise NotImplementedError("Задание 4.5: реализуйте reconcile_quality")


# %% [markdown]
# ## 8. Эксперимент — переименовать поле в bronze
#
# Если в bronze поле переименовано (`stationId` → `station_v2`), валидация
# воспринимает запись как неконформную и не пишет её в silver. Проверьте это и
# подумайте: останавливать пайплайн целиком или пропускать битый батч?

# %%
# TASK — эксперимент
def rename_field_experiment(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Переименовать stationId→station_v2 и показать, что silver не обновляется."""
    # TODO:
    # 1) переименуйте поле в КОПИИ записей (не мутируя исходные):
    #    renamed = []
    #    for r in records:
    #        c = dict(r)
    #        if "stationId" in c:
    #            c["station_v2"] = c.pop("stationId")
    #        renamed.append(c)
    # 2) clean_batch = clean_readings(records); renamed_batch = clean_readings(renamed);
    # 3) верните {"clean_rows": len(clean_batch.frame),
    #             "renamed_rows": len(renamed_batch.frame),
    #             "reasons": sorted({q.reason.value for q in renamed_batch.quarantine})}.
    raise NotImplementedError("Эксперимент: реализуйте rename_field_experiment")


# %% [markdown]
# ## 9. Выводы
#
# Заполните коротко, своими словами. Проверка смотрит только на наличие
# содержательного ответа, но преподаватель спросит по существу.

# %%
# TASK — выводы
# TODO: ответьте своими словами, 1–3 предложения на пункт.
ANSWERS: dict[str, str] = {
    "1": "",  # Для каких дефектов DLQ, а для каких — починка на лету?
    "2": "",  # Останавливать пайплайн целиком или пропускать битый батч?
    "3": "",  # Почему z-score на сезонных данных даёт ложные срабатывания?
    "4": "",  # Почему qualityScore API обязан совпадать с report.json?
    "5": "",  # Когда нужен Great Expectations, а хватает ли Pandera?
}


# %% [markdown]
# ## 10. Прогон

# %%
clean_records: list[dict[str, Any]] = []
dirty_records: list[dict[str, Any]] = []
clean_summary: dict[str, Any] | None = None
dirty_summary: dict[str, Any] | None = None
recovered_summary: dict[str, Any] | None = None
schema: Any | None = None
schema_clean: bool | None = None
schema_dirty: bool | None = None
ge_clean: dict[str, Any] | None = None
ge_dirty: dict[str, Any] | None = None
dlq_counts: dict[str, int] | None = None
pm25_values: list[float] = []
anomalies: list[int] | None = None
seasonal_peak: int | None = None
reconcile: dict[str, Any] | None = None
experiment: dict[str, Any] | None = None

# %%
try:
    clean_records = build_clean_records()
    dirty_records = build_dirty_records(clean_records)
    print(f"Чистых чтений: {len(clean_records)}, грязных: {len(dirty_records)}")
    examples = defect_examples(dirty_records)
    print("Примеры дефектов:")
    print("  missing value:", json.dumps(examples["missing_value"], ensure_ascii=False, default=str))
    print("  broken schema (нет stationId):", json.dumps(examples["broken_schema"], ensure_ascii=False, default=str))
    print("  duplicate readingId:", examples["duplicate_readingId"])
except Exception as error:
    print(f"Не удалось сгенерировать данные: {error}")

# %%
if clean_records:
    try:
        clean_summary = run_pipeline(clean_records)
        dirty_summary = run_pipeline(dirty_records)
        recovered_summary = run_pipeline(clean_records)
        print("clean    :", json.dumps(clean_summary, ensure_ascii=False))
        print("dirty    :", json.dumps(dirty_summary, ensure_ascii=False))
        print("recovered:", json.dumps(recovered_summary, ensure_ascii=False))
    except Exception as error:
        print(f"Не удалось прогнать clean_readings: {error}")

# %%
try:
    schema = build_reading_schema()
    schema_clean = validate_with_schema(schema, CLEAN_DF)
    schema_dirty = validate_with_schema(schema, DIRTY_DF)
    print(f"Pandera: clean={schema_clean}, dirty={schema_dirty}")
except NotImplementedError as error:
    print(f"Задание 4.1 не выполнено: {error}")

# %%
try:
    ge_clean = run_ge_checks(CLEAN_DF)
    ge_dirty = run_ge_checks(DIRTY_DF)
    print(f"GE: clean={ge_clean.get('success')}, dirty={ge_dirty.get('success')}")
except NotImplementedError as error:
    print(f"Задание 4.2 не выполнено: {error}")

# %%
if dirty_records:
    try:
        batch = clean_readings(dirty_records)
        dlq_counts = parse_dlq(quarantine_as_dlq(batch.quarantine))
        print("DLQ по причинам:", json.dumps(dlq_counts, ensure_ascii=False))
    except NotImplementedError as error:
        print(f"Задание 4.3 не выполнено: {error}")

# %%
try:
    pm25_values = build_pm25_series()
    anomalies = detect_anomalies(pm25_values)
    seasonal_peak = seasonal_peak_index(pm25_values, SPIKE_INDEX)
    print(f"PM2.5: точек={len(pm25_values)}, выбросы={anomalies}, сезонный пик={seasonal_peak}")
except NotImplementedError as error:
    print(f"Задание 4.4 не выполнено: {error}")

# %%
if dirty_records:
    try:
        metrics = clean_readings(dirty_records).metrics_by_dataset[DATASET_ID]
        reconcile = reconcile_quality(metrics, DATASET_ID, date.today())
        print("Сверка:", json.dumps(reconcile, ensure_ascii=False))
    except NotImplementedError as error:
        print(f"Задание 4.5 не выполнено: {error}")
    except Exception as error:
        print(f"Задание 4.5 не удалось: {error}")

# %%
if clean_records:
    try:
        experiment = rename_field_experiment(clean_records)
        print("Эксперимент (переименование поля):", json.dumps(experiment, ensure_ascii=False))
    except NotImplementedError as error:
        print(f"Эксперимент не завершён: {error}")


# %% [markdown]
# ## 11. Проверки

# %%
def check_schema(schema: Any, clean_ok: bool, dirty_ok: bool) -> None:
    """Проверить Pandera-схему на чистом и грязном фрейме."""
    assert schema is not None, "схема не собрана"
    assert clean_ok is True, "чистый фрейм должен проходить схему"
    assert dirty_ok is False, "грязный фрейм должен отклоняться"


def check_ge(clean: dict[str, Any], dirty: dict[str, Any]) -> None:
    """Проверить GE-ожидания: чистое проходит, грязное — нет."""
    assert clean.get("success") is True, "GE: чистый фрейм должен проходить"
    assert dirty.get("success") is False, "GE: грязный фрейм должен падать"


def check_dlq(counts: dict[str, int]) -> None:
    """Проверить разбор DLQ: ≥5 записей и ≥3 причины."""
    total = sum(counts.values())
    assert total >= 5, f"записей в DLQ {total}, ожидалось >= 5"
    assert len(counts) >= 3, f"причин {len(counts)}, ожидалось >= 3"


def check_anomalies(anomalies: list[int], spike: int, peak: int) -> None:
    """Проверить, что внедрённый выброс найден, а сезонный пик — нет."""
    assert spike in anomalies, "внедрённый выброс не найден"
    assert peak not in anomalies, "сезонный пик ложно помечен как выброс"


def check_reconcile(result: dict[str, Any]) -> None:
    """Проверить сверку qualityScore API и отчёта."""
    assert result["delta"] < 0.05, f"расхождение {result['delta']} >= 0.05"


def check_experiment(result: dict[str, Any]) -> None:
    """Проверить, что переименование поля ломает silver."""
    assert result["clean_rows"] > 0, "чистые данные должны давать silver"
    assert result["renamed_rows"] == 0, "после переименования silver должен быть пуст"
    assert "SCHEMA_MISMATCH" in result["reasons"], "ожидалась причина SCHEMA_MISMATCH"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    checks: list[tuple[str, Any]] = []
    if schema is not None:
        checks.append(("4.1 схема", lambda: check_schema(schema, schema_clean, schema_dirty)))
    else:
        checks.append(("4.1 схема", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if ge_clean is not None and ge_dirty is not None:
        checks.append(("4.2 GE", lambda: check_ge(ge_clean, ge_dirty)))
    else:
        checks.append(("4.2 GE", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if dlq_counts is not None:
        checks.append(("4.3 DLQ", lambda: check_dlq(dlq_counts)))
    else:
        checks.append(("4.3 DLQ", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if anomalies is not None and seasonal_peak is not None:
        checks.append(("4.4 аномалии", lambda: check_anomalies(anomalies, SPIKE_INDEX, seasonal_peak)))
    else:
        checks.append(("4.4 аномалии", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if reconcile is not None:
        checks.append(("4.5 сверка", lambda: check_reconcile(reconcile)))
    else:
        checks.append(("4.5 сверка", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if experiment is not None:
        checks.append(("эксперимент", lambda: check_experiment(experiment)))
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
