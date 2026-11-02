# %% [markdown]
# # Семинар 5 — Сложная предобработка и трансформация
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Путь данных: `bronze → silver → gold`. Silver уже очищен в семинаре 4;
# здесь собираем gold и учимся не протекать будущим:
# 1. Строим признаки витрины продаж (rolling 7 дней, конверсия, средний чек) — задание 5.1.
# 2. Считаем лаги, скользящее среднее и суточные sin/cos для ряда — задание 5.2.
# 3. Сравниваем baseline, ручной AR(1) и прогноз репозитория — задание 5.3.
# 4. Оцениваем лексиконную тональность на 30 отзывах — задание 5.4 (бонус 5.5 — по желанию).
# 5. Проверяем инкрементальный пересчёт витрины — эксперимент.
#
# Запуск (ClickHouse и Airflow не нужны, все задания вычислительные):
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# uv run --project "$SPUTNIK_REPO" python seminar_05.py
# ```
#
# `pandas` и `numpy` приходят из зависимостей репозитория, отдельно их
# добавлять не нужно.

# %%
from __future__ import annotations

import hashlib
import json
import math
import os
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sim.sensors import build_stations, generate_readings

# forecast_series понадобится в задании 5.3 — импорт оставлен заранее.
from transform.gold_readings import forecast_series, hourly_aggregates  # noqa: F401
from transform.gold_sales import build_sales_rows
from transform.gold_sentiment import score_text
from validation.validator import clean_readings

SEED = int(os.getenv("SEED", "42"))
PERIODS = int(os.getenv("PERIODS", "48"))
TRAIN_HOURS = int(os.getenv("TRAIN_HOURS", "36"))
FORECAST_HORIZON = int(os.getenv("FORECAST_HORIZON", "12"))
ROLLING = int(os.getenv("ROLLING", "24"))
BONUS_DIR = Path(os.getenv("BONUS_DIR", "./_out/images"))

DATASETS: tuple[str, ...] = (
    "ds_weather-stations",
    "ds_air-quality",
    "ds_energy-consumption",
    "ds_traffic-flow",
    "ds_retail-sales",
)
START_DAY = date(2026, 9, 1)
SERIES_STATION = "st_meteo-01"
SERIES_METRIC = "TEMPERATURE"
FORECAST_STATION = "st_air-02"
FORECAST_METRIC = "NOISE"
FEATURE_COLUMNS: tuple[str, ...] = (
    "orders_7d",
    "downloads_7d",
    "conversion_7d",
    "avg_amount_7d",
)


# %% [markdown]
# ## 1. Данные: silver и часовые агрегаты
#
# `clean_readings` уже отработал в семинаре 4: получаем silver-фрейм, а из него —
# часовые агрегаты `hourly_aggregates` (это и есть будущая основа gold-витрины).

# %%
def build_silver(periods: int = PERIODS, seed: int = SEED) -> pd.DataFrame:
    """Детерминированный silver-фрейм из 6 станций × periods точек."""
    records = generate_readings(seed=seed, periods=periods, stations=build_stations())
    return clean_readings(records).frame


def print_table(frame: pd.DataFrame) -> None:
    """Напечатать DataFrame без индекса (работает и вне Jupyter)."""
    if frame.empty:
        print("(пусто)")
    else:
        print(frame.to_string(index=False))


def sparkline(values: list[float]) -> str:
    """Компактный график ряда символами Unicode."""
    if not values:
        return ""
    low, high = min(values), max(values)
    if high == low:
        return "▄" * len(values)
    levels = "▁▂▃▄▅▆▇█"
    scale = len(levels) - 1
    return "".join(levels[int((value - low) / (high - low) * scale)] for value in values)


# %%
SILVER: pd.DataFrame = build_silver()
HOURLY: pd.DataFrame = hourly_aggregates(SILVER)

print(f"silver: {SILVER.shape[0]} строк × {SILVER.shape[1]} колонок, станций: {SILVER['station_id'].nunique()}")
print("первые 8 строк часовых агрегатов:")
print_table(HOURLY.head(8))

# %%
_weather = (
    HOURLY[(HOURLY["station_id"] == SERIES_STATION) & (HOURLY["metric"] == SERIES_METRIC)]
    .sort_values("hour")["avg_value"]
    .tolist()
)
print(f"{SERIES_STATION} {SERIES_METRIC}: {len(_weather)} точек")
print(sparkline(_weather))


# %% [markdown]
# ## 2. Задание 5.1 — признаки витрины продаж
#
# События commerce детерминированы: 5 датасетов × 14 дней. `build_sales_rows`
# репозитория сворачивает их в дневную витрину `mart_sales_daily`.
#
# Соберите `build_dataset_features`: для каждого датасета и дня — четыре
# признака по окну из `window` дней **включая текущий**:
# - `orders_7d`, `downloads_7d` — суммы;
# - `conversion_7d = downloads_7d / orders_7d` (`0`, если заказов нет);
# - `avg_amount_7d = gross_7d / orders_7d` (`0`, если заказов нет).
#
# Плюс колонки `dt`, `dataset_id`, `max_event_dt` и `feature_time`
# (конец дня `23:59:59 UTC`). Будущие дни в окно попадать не должны.

# %%
def _event_time(day: date, rng: random.Random) -> str:
    """Случайная минута внутри дня в ISO UTC."""
    moment = datetime(day.year, day.month, day.day, rng.randrange(24), rng.randrange(60), tzinfo=UTC)
    return moment.isoformat()


def build_commerce_events(days: int = 14, seed: int = SEED) -> dict[str, list[dict[str, Any]]]:
    """Детерминированные commerce-события: заказы, скачивания, подписки, клики."""
    rng = random.Random(seed)
    orders: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []
    subscriptions: list[dict[str, Any]] = []
    clicks: list[dict[str, Any]] = []

    for day_index in range(days):
        day = START_DAY + timedelta(days=day_index)
        for dataset_id in DATASETS:
            count_orders = rng.randint(0, 5)
            count_downloads = rng.randint(0, 8)
            count_clicks = rng.randint(0, 25)
            # Гарантируем хотя бы одно событие, иначе день не попадёт в витрину.
            if count_orders == count_downloads == count_clicks == 0:
                count_clicks = 1
            for _ in range(count_orders):
                orders.append(
                    {
                        "datasetId": dataset_id,
                        "at": _event_time(day, rng),
                        "amount": round(rng.uniform(500.0, 5000.0), 2),
                    }
                )
            for _ in range(count_downloads):
                downloads.append({"datasetId": dataset_id, "at": _event_time(day, rng)})
            for _ in range(count_clicks):
                clicks.append({"datasetId": dataset_id, "at": _event_time(day, rng)})
            if rng.random() < 0.25:
                subscriptions.append({"datasetId": dataset_id, "at": _event_time(day, rng)})

    return {
        "orders": orders,
        "downloads": downloads,
        "subscriptions": subscriptions,
        "clicks": clicks,
    }


def build_sales_mart(events: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    """Свернуть события в дневную витрину репозитория (DataFrame)."""
    rows = build_sales_rows(
        events["orders"],
        events["downloads"],
        subscriptions=events["subscriptions"],
        clicks=events["clicks"],
    )
    return pd.DataFrame(
        rows,
        columns=["dt", "dataset_id", "orders", "downloads", "clicks", "gross_amount"],
    )


# %%
# TASK 5.1 — признаки витрины продаж
def build_dataset_features(mart: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Признаки по окну `window` дней на каждый датасет и день (без будущего)."""
    # TODO (5.1): верните DataFrame с колонками dt, dataset_id, четырьмя
    # признаками и max_event_dt/feature_time.
    # Подсказки:
    # - приведите dt к дате и отсортируйте по (dataset_id, dt);
    # - для каждой строки берите срез [position - window + 1 : position + 1]
    #   (только прошлое и текущий день);
    # - conversion_7d и avg_amount_7d равны 0, когда сумма заказов = 0;
    # - max_event_dt — самый поздний день окна, feature_time — конец текущего дня.
    raise NotImplementedError("Задание 5.1: реализуйте build_dataset_features")


# %% [markdown]
# ## 3. Задание 5.2 — признаки временного ряда
#
# Ряд — часовая температура `st_meteo-01`. Соберите `add_series_features`:
# - `lag_1`, `lag_7` — только прошлые значения (`shift`);
# - `rolling_24` — среднее текущего и до 23 прошлых (`min_periods=1`);
# - `hour_of_day`, `sin_hour = sin(2π·hour/24)`, `cos_hour = cos(2π·hour/24)`.
#
# Лаги и окно считаются назад: строка дня `t` не должна видеть `t+1`.

# %%
def build_series(
    silver: pd.DataFrame,
    station: str = SERIES_STATION,
    metric: str = SERIES_METRIC,
) -> list[tuple[datetime, float]]:
    """Отсортированный ряд (время, значение) по станции и метрике."""
    subset = silver[(silver["station_id"] == station) & (silver["metric"] == metric)]
    subset = subset.sort_values("measured_at")
    return [
        (pd.Timestamp(row.measured_at).to_pydatetime(), float(row.value))
        for row in subset.itertuples()
    ]


# %%
# TASK 5.2 — признаки ряда
def add_series_features(
    points: list[tuple[datetime, float]], rolling: int = ROLLING
) -> pd.DataFrame:
    """Лаги, скользящее среднее и суточные sin/cos без будущих значений."""
    # TODO (5.2): соберите DataFrame с колонками hour, value, lag_1, lag_7,
    # rolling_24, hour_of_day, sin_hour, cos_hour.
    # Подсказки:
    # - lag_1 и lag_7 — это shift(1) и shift(7) по value;
    # - rolling_24 — rolling(window=rolling, min_periods=1).mean();
    # - hour_of_day — час из hour, sin/cos — от 2π·hour_of_day/24.
    raise NotImplementedError("Задание 5.2: реализуйте add_series_features")


# %% [markdown]
# ## 4. Задание 5.3 — прогноз: baseline, AR(1) и модель репозитория
#
# Делим ряд на train/test (36 + 12 часов). Три прогноза:
# - **baseline** — повтор последнего значения train (persistence);
# - **AR(1)** — вручную подобранная модель `x[t] = a·x[t-1] + b`. Это
#   AR-часть ARIMA(1,0,0): без дифференцирования (`d=0`) и скользящего
#   среднего (`q=0`). Параметры `(a, b)` — МНК по парам соседних точек;
# - **repo** — `forecast_series` репозитория (линейный тренд + суточные sin/cos).
#
# Сравниваем MAE на одном и том же тестовом окне.
#
# > Ряд для проверки — `st_air-02 / NOISE`. На `TEMPERATURE` окно 36/12
# > попадает на смену суточной фазы: AR(1) без сезонности проигрывает
# > persistence, и это честный результат, а не баг. Для проверки нужен ряд,
# > где AR(1) действительно лучше baseline.

# %%
def split_series(
    frame: pd.DataFrame, train_hours: int = TRAIN_HOURS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Разделить ряд на train и test по числу часов."""
    if train_hours <= 0 or train_hours >= len(frame):
        raise ValueError(f"train_hours={train_hours} вне диапазона 1..{len(frame) - 1}")
    return frame.iloc[:train_hours].copy(), frame.iloc[train_hours:].copy()


def baseline_forecast(values: list[float], horizon: int) -> list[float]:
    """Persistence: повторить последнее значение train `horizon` раз."""
    if not values:
        raise ValueError("пустой train: baseline невозможен")
    return [float(values[-1])] * horizon


def fit_ar1(values: list[float]) -> tuple[float, float]:
    """МНК-оценка AR(1): x[t] = a·x[t-1] + b."""
    if len(values) < 3:
        raise ValueError("для AR(1) нужно минимум 3 точки")
    previous = np.asarray(values[:-1], dtype=float)
    current = np.asarray(values[1:], dtype=float)
    design = np.column_stack([previous, np.ones_like(previous)])
    coefficients, *_ = np.linalg.lstsq(design, current, rcond=None)
    return float(coefficients[0]), float(coefficients[1])


def forecast_ar1(values: list[float], horizon: int) -> list[float]:
    """Итеративный прогноз AR(1) на `horizon` шагов."""
    slope, intercept = fit_ar1(values)
    last = float(values[-1])
    predictions: list[float] = []
    for _ in range(horizon):
        last = slope * last + intercept
        predictions.append(last)
    return predictions


# %%
# TASK 5.3 — оценка прогнозов
def evaluate_forecasts(
    series_frame: pd.DataFrame,
    silver_train: pd.DataFrame,
    station: str,
    metric: str,
    train_hours: int = TRAIN_HOURS,
    horizon: int = FORECAST_HORIZON,
) -> dict[str, Any]:
    """MAE baseline, AR(1) и прогноза репозитория на общем тестовом окне."""
    # TODO (5.3): разделите ряд через split_series, посчитайте три прогноза
    # и MAE по фактическим значениям теста.
    # Подсказки:
    # - baseline = baseline_forecast(train_values, horizon);
    # - ar1 = forecast_ar1(train_values, horizon);
    # - repo = forecast_series(silver_train, horizon_hours=horizon);
    # - сопоставьте прогноз репозитория с тестом по часу (station/metric/час);
    # - верните n_test, mae_baseline, mae_ar1, mae_repo и 2–3 примера
    #   {hour, actual, baseline, ar1, repo}.
    raise NotImplementedError("Задание 5.3: реализуйте evaluate_forecasts")


# %% [markdown]
# ## 5. Задание 5.4 — лексиконная тональность
#
# `score_text` репозитория — детерминированный лексикон: считает вхождения
# основ слов и возвращает `(positive − negative) / total` в `[-1, 1]`.
# Порог: `> 0.1` — positive, `< −0.1` — negative, иначе neutral.
#
# В наборе 30 отзывов и несколько специально трудных случаев: отрицание
# («не понравилось», «не рекомендую»), смешанные отзывы, сарказм и формы
# «ошибок»/«ошибка», которые лексикон не различает. Соберите
# `evaluate_sentiment` и объясните, где лексикон ошибается.

# %%
REVIEWS: list[dict[str, str]] = [
    {"id": "r01", "text": "Отличный набор данных, всё работает.", "label": "positive"},
    {"id": "r02", "text": "Очень полезный датасет, рекомендую.", "label": "positive"},
    {"id": "r03", "text": "Данные точные и качественные.", "label": "positive"},
    {"id": "r04", "text": "Удобная структура, быстро разобрался.", "label": "positive"},
    {"id": "r05", "text": "Супер, всё понравилось.", "label": "positive"},
    {"id": "r06", "text": "Хорошее качество и понятная документация.", "label": "positive"},
    {"id": "r07", "text": "Быстро, данные актуальные.", "label": "positive"},
    {"id": "r08", "text": "Полезно, рекомендую коллегам.", "label": "positive"},
    {"id": "r09", "text": "Отлично, ошибок не нашёл.", "label": "positive"},
    {"id": "r10", "text": "Great dataset, very useful.", "label": "positive"},
    {"id": "r11", "text": "Ужасное качество, много ошибок.", "label": "negative"},
    {"id": "r12", "text": "Данные неточные, постоянно врут.", "label": "negative"},
    {"id": "r13", "text": "Очень медленно, выгрузка занимает часы.", "label": "negative"},
    {"id": "r14", "text": "Плохая документация, ничего не понятно.", "label": "negative"},
    {"id": "r15", "text": "Слишком дорого для такого качества.", "label": "negative"},
    {"id": "r16", "text": "Сложно разобраться, всё запутано.", "label": "negative"},
    {"id": "r17", "text": "Разочарован, половина полей пустая.", "label": "negative"},
    {"id": "r18", "text": "Не рекомендую, много пропусков.", "label": "negative"},
    {"id": "r19", "text": "Не понравилось: данные грязные.", "label": "negative"},
    {"id": "r20", "text": "Ужасно, но в целом полезно.", "label": "negative"},
    {"id": "r21", "text": "Датасет как датасет, ничего особенного.", "label": "neutral"},
    {"id": "r22", "text": "Скачал, посмотрю позже.", "label": "neutral"},
    {"id": "r23", "text": "Информация о погоде за сентябрь.", "label": "neutral"},
    {"id": "r24", "text": "Цена средняя, качество среднее.", "label": "neutral"},
    {"id": "r25", "text": "Обновление раз в сутки.", "label": "neutral"},
    {"id": "r26", "text": "Есть описание полей и примеры.", "label": "neutral"},
    {"id": "r27", "text": "Не плохо, но и не хорошо.", "label": "neutral"},
    {"id": "r28", "text": "Данные хорошие, но половина пропусков.", "label": "negative"},
    {"id": "r29", "text": "Отличная работа, снова всё сломалось.", "label": "negative"},
    {"id": "r30", "text": "Ошибок нет, всё отлично.", "label": "positive"},
]


def predict_sentiment(text: str) -> str:
    """Класс тональности по порогам лексиконного score."""
    score = score_text(text)
    if score > 0.1:
        return "positive"
    if score < -0.1:
        return "negative"
    return "neutral"


# %%
# TASK 5.4 — оценка тональности
def evaluate_sentiment(reviews: list[dict[str, str]]) -> dict[str, Any]:
    """Accuracy, ошибки и разбивка по истинным меткам."""
    # TODO (5.4): пройдите по отзывам, сравните predict_sentiment(text) с label.
    # Подсказки:
    # - считайте correct и total;
    # - собирайте errors как {id, text, expected, predicted, score};
    # - by_label — {метка: {correct, total}} по истинным меткам;
    # - accuracy = correct / total.
    raise NotImplementedError("Задание 5.4: реализуйте evaluate_sentiment")


# %% [markdown]
# ## 6. Задание 5.5 — бонус P2: 50 PGM-картинок
#
# Не входит в 7 проверок. Сгенерируйте 50 детерминированных grayscale-картинок
# `32×32` в формате **PGM P2** (ASCII): градиент + круг. Прочитайте их обратно
# и убедитесь, что файлов 50, размер `32×32`, а значения нормированы в `[0, 1]`.
#
# Формат: первая строка `P2`, затем `width height`, затем `maxval`, затем
# `width·height` целых чисел.

# %%
# TASK 5.5 — бонус PGM P2
def write_pgm_images(
    directory: Path = BONUS_DIR, count: int = 50, size: int = 32
) -> list[Path]:
    """Записать `count` детерминированных PGM P2-картинок `size×size`."""
    # TODO (5.5, бонус): создайте папку и запишите count файлов .pgm.
    # Подсказки:
    # - формат P2: строка "P2", затем "width height", затем "255",
    #   затем width·height целых значений через пробел;
    # - значение = градиент по (x, y), внутри круга — 255;
    # - параметры круга и градиента зависят от index, чтобы картинки различались;
    # - верните список путей.
    raise NotImplementedError("Задание 5.5: реализуйте write_pgm_images")


def read_pgm(path: Path) -> tuple[int, int, list[list[float]]]:
    """Прочитать PGM P2 и вернуть (width, height, матрица в [0, 1])."""
    tokens = Path(path).read_text(encoding="ascii").split()
    if len(tokens) < 4 or tokens[0] != "P2":
        raise ValueError(f"{path}: ожидался формат P2")
    width, height, max_value = (int(token) for token in tokens[1:4])
    values = [int(token) for token in tokens[4:]]
    if len(values) != width * height or max_value <= 0:
        raise ValueError(f"{path}: повреждённые данные PGM")
    matrix = [
        [values[y * width + x] / max_value for x in range(width)] for y in range(height)
    ]
    return width, height, matrix


def verify_bonus_images(directory: Path = BONUS_DIR, count: int = 50) -> dict[str, Any]:
    """Проверить число файлов, размер и диапазон значений."""
    paths = sorted(Path(directory).glob("*.pgm"))
    sizes: set[tuple[int, int]] = set()
    low, high = 1.0, 0.0
    for path in paths:
        width, height, matrix = read_pgm(path)
        sizes.add((width, height))
        for row in matrix:
            low = min(low, min(row))
            high = max(high, max(row))
    return {
        "files": len(paths),
        "expected_files": count,
        "sizes": sorted(sizes),
        "min": low,
        "max": high,
    }


# %% [markdown]
# ## 7. Эксперимент — инкрементальный пересчёт витрины
#
# Пересчитываем признаки для последнего дня двумя способами: по всей истории и
# только по последним 7 дням. Если окно признаков — ровно 7 дней, результаты
# обязаны совпасть: старые дни уже не влияют на `orders_7d`.
#
# Зачем это обсуждать: pandas пересчитывает весь фрейм в памяти. На миллиардах
# событий «пересчитать всё» дорого; ClickHouse считает агрегаты по окну
# инкрементально (MergeTree + `AggregatingMergeTree`/материализованные
# представления), а Airflow запускает только партиции затронутых дней.
# Живое сравнение с ClickHouse в этом семинаре не требуется: эксперимент
# чисто вычислительный.

# %%
# TASK — эксперимент
def experiment_incremental(mart: pd.DataFrame) -> dict[str, Any]:
    """Сравнить признаки последнего дня при полном и оконном пересчёте."""
    # TODO: посчитайте признаки по всей витрине и только по последним 7 дням.
    # Подсказки:
    # - full = build_dataset_features(mart), возьмите последний dt;
    # - window_mart = mart[dt >= последний_день - 6 дней];
    # - сравните признаки последнего дня по dataset_id с допуском 1e-9;
    # - верните day, full_rows, window_rows, equal, mismatches.
    raise NotImplementedError("Эксперимент: реализуйте experiment_incremental")


# %% [markdown]
# ## 8. Выводы
#
# Ответьте своими словами, 1–3 предложения на пункт. Проверка смотрит только
# на наличие содержательного ответа, но преподаватель спросит по существу.

# %%
# TODO: ответьте своими словами, 1–3 предложения на пункт.
ANSWERS: dict[str, str] = {
    "1": "",  # Где живут признаки: silver, gold или feature store? Почему?
    "2": "",  # Почему окно не должно видеть будущие дни?
    "3": "",  # Зачем считать baseline до ARIMA?
    "4": "",  # Два ограничения лексиконной тональности.
    "5": "",  # Что даёт инкрементальный пересчёт и когда он ломается?
}


# %% [markdown]
# ## 9. Прогон

# %%
EVENTS: dict[str, list[dict[str, Any]]] = {"orders": [], "downloads": [], "subscriptions": [], "clicks": []}
MART: pd.DataFrame = pd.DataFrame()
FEATURES: pd.DataFrame = pd.DataFrame()
SERIES: list[tuple[datetime, float]] = []
SERIES_FEATURES: pd.DataFrame = pd.DataFrame()
FORECAST_EVAL: dict[str, Any] | None = None
SENTIMENT_EVAL: dict[str, Any] | None = None
BONUS_SUMMARY: dict[str, Any] | None = None
EXPERIMENT: dict[str, Any] | None = None
DIGEST_ONE: str | None = None
DIGEST_TWO: str | None = None
REPRO_OK: bool = False

# %%
try:
    EVENTS = build_commerce_events()
    MART = build_sales_mart(EVENTS)
    print(
        f"события: заказов={len(EVENTS['orders'])}, скачиваний={len(EVENTS['downloads'])}, "
        f"подписок={len(EVENTS['subscriptions'])}, кликов={len(EVENTS['clicks'])}"
    )
    print(f"витрина продаж: {len(MART)} строк × {MART.shape[1]} колонок")
    print_table(MART.head(5))
except Exception as error:
    print(f"Не удалось собрать витрину: {error}")

# %%
try:
    FEATURES = build_dataset_features(MART)
    print(f"признаки: {len(FEATURES)} строк")
    print_table(FEATURES.head(7))
except NotImplementedError as error:
    print(f"Задание 5.1 не выполнено: {error}")
except Exception as error:
    print(f"Задание 5.1 не удалось: {error}")

# %%
try:
    SERIES = build_series(SILVER)
    SERIES_FEATURES = add_series_features(SERIES)
    print(f"ряд {SERIES_STATION}/{SERIES_METRIC}: {len(SERIES_FEATURES)} строк")
    print_table(SERIES_FEATURES.head(9))
except NotImplementedError as error:
    print(f"Задание 5.2 не выполнено: {error}")
except Exception as error:
    print(f"Задание 5.2 не удалось: {error}")

# %%
try:
    _noise_points = build_series(SILVER, station=FORECAST_STATION, metric=FORECAST_METRIC)
    _noise_features = add_series_features(_noise_points)
except NotImplementedError as error:
    _noise_features = None
    print(f"Задание 5.3 не выполнено: сначала выполните 5.2 ({error})")

if _noise_features is not None:
    try:
        _train_until = _noise_features["hour"].iloc[TRAIN_HOURS - 1]
        _silver_train = SILVER[
            (SILVER["station_id"] == FORECAST_STATION)
            & (SILVER["metric"] == FORECAST_METRIC)
            & (SILVER["measured_at"] <= _train_until)
        ]
        FORECAST_EVAL = evaluate_forecasts(
            _noise_features,
            _silver_train,
            FORECAST_STATION,
            FORECAST_METRIC,
            train_hours=TRAIN_HOURS,
            horizon=FORECAST_HORIZON,
        )
        print(f"прогноз {FORECAST_STATION}/{FORECAST_METRIC}, тест={FORECAST_EVAL['n_test']} ч:")
        print(
            f"  MAE baseline={FORECAST_EVAL['mae_baseline']:.4f}, "
            f"AR(1)={FORECAST_EVAL['mae_ar1']:.4f}, repo={FORECAST_EVAL['mae_repo']:.4f}"
        )
        print("  примеры:", json.dumps(FORECAST_EVAL["examples"][:2], ensure_ascii=False))
    except NotImplementedError as error:
        print(f"Задание 5.3 не выполнено: {error}")
    except Exception as error:
        print(f"Задание 5.3 не удалось: {error}")

# %%
try:
    SENTIMENT_EVAL = evaluate_sentiment(REVIEWS)
    print(
        f"тональность: accuracy={SENTIMENT_EVAL['accuracy']:.4f}, "
        f"верно={SENTIMENT_EVAL['correct']}/{SENTIMENT_EVAL['total']}, "
        f"ошибок={len(SENTIMENT_EVAL['errors'])}"
    )
    for item in SENTIMENT_EVAL["errors"][:4]:
        print(
            f"  {item['id']}: {item['expected']} → {item['predicted']} "
            f"(score={item['score']}): {item['text']}"
        )
except NotImplementedError as error:
    print(f"Задание 5.4 не выполнено: {error}")
except Exception as error:
    print(f"Задание 5.4 не удалось: {error}")

# %%
try:
    write_pgm_images()
    BONUS_SUMMARY = verify_bonus_images()
    print("бонус PGM:", json.dumps(BONUS_SUMMARY, ensure_ascii=False))
except NotImplementedError as error:
    print(f"Задание 5.5 (бонус) не выполнено: {error}")
except Exception as error:
    print(f"Задание 5.5 (бонус) не удалось: {error}")

# %%
try:
    EXPERIMENT = experiment_incremental(MART)
    print("эксперимент:", json.dumps(EXPERIMENT, ensure_ascii=False))
except NotImplementedError as error:
    print(f"Эксперимент не выполнен: {error}")
except Exception as error:
    print(f"Эксперимент не удался: {error}")

# %%
def features_digest(mart: pd.DataFrame) -> str:
    """sha256 от округлённых признаков (детерминизм прогона)."""
    frame = build_dataset_features(mart)
    payload: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        clean: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (float, np.floating)):
                clean[key] = round(float(value), 6)
            elif hasattr(value, "isoformat"):
                clean[key] = value.isoformat()
            else:
                clean[key] = value
        payload.append(clean)
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


try:
    DIGEST_ONE = features_digest(MART)
    DIGEST_TWO = features_digest(build_sales_mart(build_commerce_events()))
    REPRO_OK = DIGEST_ONE == DIGEST_TWO
    print(f"digest #1: {DIGEST_ONE}")
    print(f"digest #2: {DIGEST_TWO}")
    if REPRO_OK:
        print("REPRO_OK")
except NotImplementedError as error:
    print(f"Воспроизводимость не проверена: {error}")
except Exception as error:
    print(f"Воспроизводимость не удалась: {error}")


# %% [markdown]
# ## 10. Проверки

# %%
def check_features(features: pd.DataFrame, mart: pd.DataFrame) -> None:
    """5.1: 70 строк, нет NaN, окно не смотрит в будущее."""
    assert len(features) == 70, f"строк {len(features)}, ожидалось 70"
    assert not features[list(FEATURE_COLUMNS)].isna().any().any(), "в признаках есть NaN"
    assert (features["max_event_dt"] <= features["dt"]).all(), "max_event_dt в будущем"
    assert (features["feature_time"].dt.date == features["dt"]).all(), "feature_time не того дня"
    assert len(mart) == 70, f"в витрине {len(mart)} строк, ожидалось 70"

    for dataset_id, group in features.groupby("dataset_id"):
        group = group.sort_values("dt")
        first = group.iloc[0]
        day_orders = float(
            mart[(mart["dataset_id"] == dataset_id) & (mart["dt"] == first["dt"])]["orders"].sum()
        )
        assert first["orders_7d"] == day_orders, (
            f"{dataset_id}: первый день orders_7d={first['orders_7d']} != orders={day_orders}"
        )


def check_series(series: pd.DataFrame) -> None:
    """5.2: 48 строк, лаги и rolling без будущего, sin/cos в диапазоне."""
    assert len(series) == 48, f"строк {len(series)}, ожидалось 48"
    assert series["lag_7"].isna().sum() == 7, "lag_7 должен иметь ровно 7 null"
    values = series["value"].tolist()
    for index in range(1, len(series)):
        assert series["lag_1"].iloc[index] == values[index - 1], f"lag_1[{index}] не прошлое"
    expected_last = float(np.mean(values[-24:]))
    assert abs(float(series["rolling_24"].iloc[-1]) - expected_last) < 1e-9, "rolling_24 неверен"
    assert series["sin_hour"].between(-1.0, 1.0).all(), "sin_hour вне [-1, 1]"
    assert series["cos_hour"].between(-1.0, 1.0).all(), "cos_hour вне [-1, 1]"
    assert series["hour_of_day"].between(0, 23).all(), "hour_of_day вне 0..23"


def check_forecast(result: dict[str, Any]) -> None:
    """5.3: AR(1) и repo лучше baseline, все MAE конечны."""
    assert result["n_test"] == 12, f"n_test={result['n_test']}, ожидалось 12"
    assert result["mae_ar1"] < result["mae_baseline"], "AR(1) не лучше baseline"
    assert result["mae_repo"] < result["mae_baseline"], "repo не лучше baseline"
    for key in ("mae_baseline", "mae_ar1", "mae_repo"):
        assert math.isfinite(float(result[key])), f"{key} не конечно"


def check_sentiment(result: dict[str, Any]) -> None:
    """5.4: accuracy 0.60–0.90 и хотя бы 3 содержательные ошибки."""
    accuracy = float(result["accuracy"])
    errors = result["errors"]
    assert 0.60 <= accuracy <= 0.90, f"accuracy={accuracy:.4f} вне [0.60, 0.90]"
    assert len(errors) >= 3, f"ошибок {len(errors)}, ожидалось >= 3"
    assert len(errors) == result["total"] - result["correct"], "ошибки не сходятся с correct"
    for item in errors:
        assert item["expected"] != item["predicted"], "в ошибках метка совпала с прогнозом"


def check_repro(digest_one: str | None, digest_two: str | None, ok: bool) -> None:
    """Воспроизводимость: два одинаковых digest."""
    assert digest_one and digest_two, "digest не посчитан"
    assert ok and digest_one == digest_two, "digest-ы различаются"


def check_experiment(result: dict[str, Any]) -> None:
    """Эксперимент: оконный пересчёт совпал и прочитал меньше строк."""
    assert result["equal"] is True, "оконный пересчёт не совпал с полным"
    assert result["window_rows"] < result["full_rows"], "окно не меньше полного прогона"
    assert result["window_rows"] == 35, f"window_rows={result['window_rows']}, ожидалось 35"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    checks: list[tuple[str, Any]] = []

    if not FEATURES.empty and not MART.empty:
        checks.append(("5.1 признаки", lambda: check_features(FEATURES, MART)))
    else:
        checks.append(("5.1 признаки", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))

    if not SERIES_FEATURES.empty:
        checks.append(("5.2 ряд", lambda: check_series(SERIES_FEATURES)))
    else:
        checks.append(("5.2 ряд", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))

    if FORECAST_EVAL is not None:
        checks.append(("5.3 прогноз", lambda: check_forecast(FORECAST_EVAL)))
    else:
        checks.append(("5.3 прогноз", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))

    if SENTIMENT_EVAL is not None:
        checks.append(("5.4 тональность", lambda: check_sentiment(SENTIMENT_EVAL)))
    else:
        checks.append(("5.4 тональность", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))

    checks.append(("воспроизводимость", lambda: check_repro(DIGEST_ONE, DIGEST_TWO, REPRO_OK)))

    if EXPERIMENT is not None:
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
