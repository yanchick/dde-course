# %% [markdown]
# # Семинар 9 — Мониторинг, тестирование, DevOps, GDPR
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# «Пайплайн зелёный» и «данные свежие» — не одно и то же. Семинар про то, как
# отличить работающий сервис от работающего пайплайна и как это защитить
# тестами и гейтами:
# 1. Читаем метрики лага и свежести, находим окно деградации — задание 9.1.
# 2. Пишем тесты, которые ловят регресс на пустых данных — задание 9.2.
# 3. Воспроизводим `429` и разбираем `Retry-After` и backoff — задание 9.3.
# 4. Читаем CI-гейты и ловим ломающую схему — задание 9.4.
# 5. Сканируем выгрузку на PII и маскируем её — задание 9.5.
# 6. Эксперимент: отключаем маскирование — CI обязан покраснеть.
#
# Задания отмечены `# TASK` и `TODO`: заполните тела функций и `ANSWERS`.
# Демо-ячейки, генератор метрик и проверки менять не нужно.
#
# Запуск (Docker и Prometheus не нужны, все задания вычислительные):
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# uv run --project "$SPUTNIK_REPO" python seminar_09.py
# ```
#
# > [!note] Живые Prometheus/Grafana — опция, а не требование
# > Скрипт читает `.github/workflows/ci.yml` из репозитория, если он найден,
# > иначе работает по встроенному снимку. Метрики — детерминированная серия
# > тех же имён (`sputnik_consumer_lag`, `sputnik_data_freshness_seconds`),
# > что отдаёт Prometheus. Прокинуть `RATE_LIMIT_*` в compose — backlog
# > SRV-26, поэтому `429` моделируется без живого gateway.

# %%
from __future__ import annotations

import json
import math
import os
import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

SEED = int(os.getenv("SEED", "42"))
MINUTES = int(os.getenv("MINUTES", "180"))
LAG_THRESHOLD = int(os.getenv("LAG_THRESHOLD", "500"))
FRESHNESS_SLA = int(os.getenv("FRESHNESS_SLA", "300"))
DEGRADATION_START = int(os.getenv("DEGRADATION_START", "60"))
DEGRADATION_END = int(os.getenv("DEGRADATION_END", "90"))
START_AT = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)

# Снимок CI: используется, если репозиторий рядом не найден.
CI_SNAPSHOT = """name: ci
on: [push, pull_request]
jobs:
  lint:
  unit:
  coverage:
  contract:
  contract-lint:
  image-build:
  release-gate:
"""

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


# %% [markdown]
# ## 1. Репозиторий и метрики
#
# 180 минут жизни пайплайна. Лаг consumer group `ingestion-bronze` обычно
# 25–40 событий; в окне 60–89 минут провайдер ускорился, а консьюмер не успел —
# лаг вырос примерно до 780, свежесть вышла за SLA 300 секунд, `qualityScore`
# просел. Всё остальное время система здорова.
#
# Метрики те же, что в `infra/grafana`: `sputnik_consumer_lag`,
# `sputnik_data_freshness_seconds`, `sputnik_quality_score`.

# %%
def find_repo_root() -> Path | None:
    """Найти корень Sputnik-Mart, если он есть рядом."""
    candidates: list[Path] = []
    if env := os.getenv("SPUTNIK_REPO"):
        candidates.append(Path(env))
    candidates.extend([Path.cwd(), *Path.cwd().parents])
    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if (path / "docker-compose.yml").is_file() and (path / ".github").is_dir():
            return path
    return None


def load_ci_source() -> tuple[str, str]:
    """Прочитать CI из репозитория или вернуть снимок."""
    root = find_repo_root()
    if root is not None:
        path = root / ".github" / "workflows" / "ci.yml"
        if path.is_file():
            return path.read_text(encoding="utf-8"), "repo"
    return CI_SNAPSHOT, "snapshot"


def build_metrics(minutes: int = MINUTES, seed: int = SEED) -> list[dict[str, Any]]:
    """Детерминированная серия лага, свежести и качества по минутам."""
    rng = random.Random(seed)
    series: list[dict[str, Any]] = []
    for minute in range(minutes):
        base = 25 + round(10 * math.sin(minute / 6)) + rng.randint(0, 3)
        degraded = DEGRADATION_START <= minute < DEGRADATION_END
        lag = base + (750 if degraded else 0)
        freshness = 35 + lag + rng.randint(0, 5)
        quality = round(max(0.0, 0.99 - lag / 6000), 4)
        series.append(
            {
                "minute": minute,
                "at": (START_AT + timedelta(minutes=minute)).isoformat(),
                "lag": lag,
                "freshness_seconds": freshness,
                "quality_score": quality,
            }
        )
    return series


# %%
METRICS = build_metrics()
CI_TEXT, CI_SOURCE = load_ci_source()
print(f"метрики: {len(METRICS)} минут, окно {DEGRADATION_START}–{DEGRADATION_END - 1}")
print(f"CI: {CI_SOURCE}")


# %% [markdown]
# ## 2. Задание 9.1 — окно деградации
#
# Метрика — это ряд, а не одно число. `max(lag)` сам по себе ничего не говорит:
# важно, **когда** и **как долго** лаг был выше порога. Непрерывный отрезок, где
# `lag > threshold`, — окно деградации; именно его показывают на графике и
# привязывают к алерту.
#
# Соберите `analyze_lag(series, threshold)`: верните `max_lag`, `max_minute`,
# список окон `{start, end, minutes}` (индексы минут включительно),
# `degraded_minutes` и `samples_over`. Пустая серия — ошибка.

# %%
# TASK 9.1 — окно деградации
def analyze_lag(
    series: list[dict[str, Any]], threshold: int = LAG_THRESHOLD
) -> dict[str, Any]:
    """Найти непрерывные окна, где лаг выше порога."""
    # TODO (9.1): найдите окна деградации.
    # Подсказки:
    # - пустая серия и отрицательный threshold — ValueError;
    # - идите по минутам и запоминайте начало непрерывного отрезка lag > threshold;
    # - окно закрывается на первой минуте, где условие нарушено;
    # - верните max_lag, max_minute, windows [{start, end, minutes}],
    #   degraded_minutes и samples_over.
    raise NotImplementedError("Задание 9.1: реализуйте analyze_lag")


# %% [markdown]
# ## 3. Задание 9.2 — тесты, которые ловят регресс
#
# Тест «на нормальных данных» обычно зелёный и бесполезный. Ценность теста —
# в границах: пустой вход, одно значение, ноль, максимум, отрицательное
# значение. Чтобы это проверить, мы не спорим о покрытии, а запускаем набор
# тестов против **мутантов** — намеренно сломанных версий функции. Хороший
# набор обязан убить каждого мутанта.
#
# `summarize_readings` — проверяемая функция: `{count, avg, min, max}`, на
# пустом списке `count=0`, остальные поля `None`.
#
# Соберите `build_test_cases()`: ≥4 кейса вида `{name, rows}`, среди них
# обязательно пустой. Затем `run_suite(cases, func)` прогоняет кейсы и
# сравнивает результат с корректной функцией.

# %%
def summarize_readings(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Count/avg/min/max по value; пустой вход — не исключение."""
    values = [float(row["value"]) for row in rows]
    if not values:
        return {"count": 0, "avg": None, "min": None, "max": None}
    return {
        "count": len(values),
        "avg": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }


def _mutant_empty_crash(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Мутант: падает на пустом входе."""
    values = [float(row["value"]) for row in rows]
    return {
        "count": len(values),
        "avg": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }


def _mutant_swapped(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Мутант: перепутаны min и max."""
    result = summarize_readings(rows)
    return {**result, "min": result["max"], "max": result["min"]}


def _mutant_ignores_zero(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Мутант: выбрасывает нулевые значения."""
    kept = [row for row in rows if float(row["value"]) != 0.0]
    return summarize_readings(kept)


MUTANTS: dict[str, Callable[[list[dict[str, Any]]], dict[str, Any]]] = {
    "empty_crash": _mutant_empty_crash,
    "swapped": _mutant_swapped,
    "ignores_zero": _mutant_ignores_zero,
}


# %%
# TASK 9.2 — набор тестов
def build_test_cases() -> list[dict[str, Any]]:
    """Кейсы, покрывающие границы: пусто, одно значение, ноль, максимум."""
    # TODO (9.2): соберите набор кейсов.
    # Подсказки:
    # - минимум 4 кейса, у каждого name и rows;
    # - обязательно пустой rows — он ловит деление на ноль;
    # - добавьте ноль, одно значение и максимум, чтобы убить мутантов
    #   ignores_zero, swapped и empty_crash.
    raise NotImplementedError("Задание 9.2: реализуйте build_test_cases")


def run_suite(
    cases: list[dict[str, Any]],
    func: Callable[[list[dict[str, Any]]], dict[str, Any]] = summarize_readings,
) -> dict[str, Any]:
    """Прогнать кейсы; PASS, если результат совпал с корректной функцией."""
    results: list[dict[str, Any]] = []
    for case in cases:
        expected = summarize_readings(case["rows"])
        try:
            actual = func(case["rows"])
        except Exception as error:
            results.append({"name": case["name"], "passed": False, "error": repr(error)})
            continue
        results.append({"name": case["name"], "passed": actual == expected, "error": None})
    passed = sum(1 for item in results if item["passed"])
    return {"total": len(results), "passed": passed, "failed": len(results) - passed, "results": results}


# %% [markdown]
# ## 4. Задание 9.3 — `429` и backoff
#
# `429 Too Many Requests` — не ошибка данных, а сигнал «сбавь темп». Клиент
# обязан подождать и повторить. `Retry-After` задаёт минимальную паузу, а
# экспоненциальный backoff — страховку, если заголовка нет. Без верхней
# границы backoff превращается в «уснуть на час».
#
# Соберите `call_with_retry(call, max_attempts, base_delay, max_delay)`:
# вызывайте `call()`, пока не `200`; на `429` ждите
# `min(max_delay, max(Retry-After, base_delay·2^(attempt−1)))`; на прочих
# статусах — сразу отказ. Верните `{ok, attempts, delays, body}`.

# %%
def scripted_call(outcomes: list[dict[str, Any]]) -> Callable[[], dict[str, Any]]:
    """Клиент, который отдаёт заранее заданные ответы по порядку."""
    queue = list(outcomes)

    def call() -> dict[str, Any]:
        return queue.pop(0) if queue else {"status": 500, "body": "script exhausted"}

    return call


# %%
# TASK 9.3 — повторы с backoff
def parse_retry_after(response: dict[str, Any]) -> float:
    """Разобрать Retry-After в секундах; мусор — 0."""
    try:
        return max(0.0, float(response.get("retry_after", 0)))
    except (TypeError, ValueError):
        return 0.0


def call_with_retry(
    call: Callable[[], dict[str, Any]],
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 8.0,
) -> dict[str, Any]:
    """Повторять 429 с уважением к Retry-After и потолком задержки."""
    # TODO (9.3): реализуйте повторы с backoff.
    # Подсказки:
    # - проверьте 0 < base_delay <= max_delay и max_attempts > 0;
    # - 200 — успех, любой другой статус кроме 429 — сразу отказ;
    # - на 429 пауза = min(max_delay, max(Retry-After, base_delay·2^(attempt−1)));
    # - после последней попытки верните ok=False, attempts=max_attempts.
    raise NotImplementedError("Задание 9.3: реализуйте call_with_retry")


# %% [markdown]
# ## 5. Задание 9.4 — CI-гейты и ломающая схема
#
# CI — это не «зелёная галочка», а набор гейтов: lint, unit, coverage ≥80,
# contract, contract-lint, image-build, release-gate. `release-gate` идёт
# последним и пропускает только всё остальное.
#
# Соберите `parse_ci_jobs(text)` — порядок job'ов из блока `jobs:`;
# `ci_verdict(results, jobs)` — `{exit_code, failed, passed}` (первый
# упавший job останавливает сборку); `schema_gate(old_fields, new_fields)` —
# `{ok, removed, added}`, где удалённое обязательное поле ломает контракт,
# а добавленное — нет.

# %%
# TASK 9.4 — CI и схема
def parse_ci_jobs(text: str) -> list[str]:
    """Порядок job'ов из блока jobs:."""
    # TODO (9.4): вытащите job'ы в порядке объявления.
    # Подсказки:
    # - начните после строки `jobs:`;
    # - job — строка с отступом ровно в два пробела и двоеточием в конце;
    # - на первом ключе верхнего уровня блок заканчивается.
    raise NotImplementedError("Задание 9.4: реализуйте parse_ci_jobs")


def ci_verdict(results: dict[str, bool], jobs: list[str]) -> dict[str, Any]:
    """Первый упавший job останавливает сборку."""
    # TODO (9.4): посчитайте вердикт CI.
    # Подсказки:
    # - идите по jobs по порядку;
    # - отсутствующий или False job — exit_code=1, failed=job;
    # - верните {exit_code, failed, passed} с уже пройденными job'ами.
    raise NotImplementedError("Задание 9.4: реализуйте ci_verdict")


def schema_gate(old_fields: tuple[str, ...], new_fields: tuple[str, ...]) -> dict[str, Any]:
    """Удаление поля ломает контракт, добавление — нет."""
    # TODO (9.4): сравните обязательные поля.
    # Подсказки:
    # - removed = old − new, added = new − old (отсортируйте);
    # - ok=True только если removed пуст.
    raise NotImplementedError("Задание 9.4: реализуйте schema_gate")


# %% [markdown]
# ## 6. Задание 9.5 — PII в выгрузке
#
# GDPR и 152-ФЗ начинаются не в юридическом отделе, а в `sanitize_export`.
# Выгрузка не должна содержать email и телефоны, но обязана сохранять
# `userId`: иначе аналитика теряет связь событий.
#
# Соберите `find_pii(rows)` → `{emails, phones, count}` и
# `sanitize_export(rows)` → `{rows, findings_before, findings_after,
# kept_user_id}`. Маска — `***@***` для email и `***` для телефона.

# %%
EXPORT_ROWS: list[dict[str, Any]] = [
    {"userId": "u_0001", "datasetId": "ds_weather-stations", "email": "ivan.petrov@example.com", "phone": "+7 916 123-45-67", "text": "Отлично, спасибо"},
    {"userId": "u_0002", "datasetId": "ds_air-quality", "email": "anna.smirnova@example.com", "phone": "+7 925 555-12-34", "text": "Данные грязные"},
    {"userId": "u_0003", "datasetId": "ds_energy-consumption", "email": "no-reply@example.org", "phone": "", "text": "Нормально"},
    {"userId": "u_0004", "datasetId": "ds_traffic-flow", "email": "ops@example.net", "phone": "", "text": "Работает"},
    {"userId": "u_0005", "datasetId": "ds_retail-sales", "email": "", "phone": "", "text": "Без контактов"},
    {"userId": "u_0006", "datasetId": "ds_weather-stations", "email": "buyer@sputnik.demo", "phone": "", "text": "Скачал"},
    {"userId": "u_0007", "datasetId": "ds_air-quality", "email": "", "phone": "+7 911 222-33-44", "text": "Проверяю"},
    {"userId": "u_0008", "datasetId": "ds_traffic-flow", "email": "analyst@sputnik.demo", "phone": "", "text": "Беру в отчёт"},
    {"userId": "u_0009", "datasetId": "ds_energy-consumption", "email": "", "phone": "+7 921 444-55-66", "text": "Позже"},
    {"userId": "u_0010", "datasetId": "ds_retail-sales", "email": "", "phone": "", "text": "Спасибо"},
]


# %%
# TASK 9.5 — поиск и маскирование PII
def find_pii(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Найти email и телефоны в строковых полях."""
    # TODO (9.5): найдите PII в строках выгрузки.
    # Подсказки:
    # - просмотрите все строковые значения всех полей;
    # - используйте EMAIL_RE и PHONE_RE;
    # - верните уникальные emails/phones (отсортированные) и count.
    raise NotImplementedError("Задание 9.5: реализуйте find_pii")


def sanitize_export(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Заменить PII маской, сохранив userId и остальные поля."""
    # TODO (9.5): замаскируйте выгрузку.
    # Подсказки:
    # - в каждой строке замените email на ***@***, телефон на ***;
    # - не мутируйте исходные строки;
    # - посчитайте находки до и после через find_pii;
    # - kept_user_id — у всех строк остался непустой userId.
    raise NotImplementedError("Задание 9.5: реализуйте sanitize_export")


# %% [markdown]
# ## 7. Эксперимент — отключаем маскирование
#
# Представьте, что кто-то «оптимизировал» экспорт и вернул строки как есть.
# Сканер PII обязан это поймать, а CI-гейт — заблокировать сборку. Если гейт
# пропускает утечку, проблема не в GDPR, а в тестах.
#
# Соберите `experiment_pii_gate(rows)`: `{unguarded_findings,
# guarded_findings, ci_blocks_unmasked, ci_passes_masked}`.

# %%
# TASK — эксперимент с PII-гейтом
def experiment_pii_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Проверить, что гейт блокирует грязную выгрузку и пропускает чистую."""
    # TODO (эксперимент): смоделируйте CI-гейт PII.
    # Подсказки:
    # - без маски посчитайте находки на rows;
    # - с маской вызовите sanitize_export и возьмите findings_after;
    # - гейт блокирует, если находок > 0, и пропускает, если 0.
    raise NotImplementedError("Эксперимент: реализуйте experiment_pii_gate")


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
LAG_REPORT: dict[str, Any] | None = None
TEST_CASES: list[dict[str, Any]] = []
TEST_SUITE: dict[str, Any] | None = None
MUTANT_RESULTS: dict[str, dict[str, Any]] = {}
RETRY_OK: dict[str, Any] | None = None
RETRY_EXHAUSTED: dict[str, Any] | None = None
CI_JOBS: list[str] = []
CI_RESULT: dict[str, Any] | None = None
SCHEMA_OK: dict[str, Any] | None = None
SCHEMA_BROKEN: dict[str, Any] | None = None
PII_SCAN: dict[str, Any] | None = None
EXPORT_RESULT: dict[str, Any] | None = None
EXPERIMENT: dict[str, Any] = {}

# %%
try:
    LAG_REPORT = analyze_lag(METRICS)
    print(
        f"лаг: max={LAG_REPORT['max_lag']} на минуте {LAG_REPORT['max_minute']}, "
        f"окон={len(LAG_REPORT['windows'])}, деградация={LAG_REPORT['degraded_minutes']} мин"
    )
    for window in LAG_REPORT["windows"]:
        print(f"  окно {window['start']}–{window['end']} ({window['minutes']} мин)")
    over_sla = [row for row in METRICS if row["freshness_seconds"] > FRESHNESS_SLA]
    print(f"  свежесть выше SLA: {len(over_sla)} минут, минимум quality={min(row['quality_score'] for row in METRICS):.4f}")
except NotImplementedError as error:
    print(f"Задание 9.1 не выполнено: {error}")
except Exception as error:
    print(f"Задание 9.1 не удалось: {error}")

# %%
try:
    TEST_CASES = build_test_cases()
    TEST_SUITE = run_suite(TEST_CASES)
    MUTANT_RESULTS = {name: run_suite(TEST_CASES, mutant) for name, mutant in MUTANTS.items()}
    print(
        f"тесты: кейсов={TEST_SUITE['total']}, прошло={TEST_SUITE['passed']}, "
        f"провалено={TEST_SUITE['failed']}"
    )
    killed = [name for name, result in MUTANT_RESULTS.items() if result["failed"] > 0]
    print(f"  мутантов убито: {len(killed)}/{len(MUTANTS)} — {', '.join(killed)}")
except NotImplementedError as error:
    print(f"Задание 9.2 не выполнено: {error}")
except Exception as error:
    print(f"Задание 9.2 не удалось: {error}")

# %%
try:
    RETRY_OK = call_with_retry(
        scripted_call(
            [
                {"status": 429, "retry_after": 1, "body": "slow down"},
                {"status": 429, "retry_after": 2, "body": "slow down"},
                {"status": 200, "body": "ok"},
            ]
        )
    )
    RETRY_EXHAUSTED = call_with_retry(
        scripted_call([{"status": 429, "retry_after": 0, "body": "slow down"}] * 10)
    )
    print(
        f"429: ok={RETRY_OK['ok']}, попыток={RETRY_OK['attempts']}, "
        f"задержки={RETRY_OK['delays']}"
    )
    print(
        f"  исчерпание: ok={RETRY_EXHAUSTED['ok']}, попыток={RETRY_EXHAUSTED['attempts']}, "
        f"задержки={RETRY_EXHAUSTED['delays']}"
    )
except NotImplementedError as error:
    print(f"Задание 9.3 не выполнено: {error}")
except Exception as error:
    print(f"Задание 9.3 не удалось: {error}")

# %%
try:
    CI_JOBS = parse_ci_jobs(CI_TEXT)
    CI_RESULT = ci_verdict({job: job != "unit" for job in CI_JOBS}, CI_JOBS)
    SCHEMA_OK = schema_gate(("readingId", "stationId", "value"), ("readingId", "stationId", "value", "unit"))
    SCHEMA_BROKEN = schema_gate(("readingId", "stationId", "value"), ("readingId", "station_id", "value"))
    print(f"CI: jobs={CI_JOBS}")
    print(f"  с упавшим unit: exit={CI_RESULT['exit_code']}, failed={CI_RESULT['failed']}")
    print(f"  схема +unit: ok={SCHEMA_OK['ok']}; переименование: ok={SCHEMA_BROKEN['ok']}, removed={SCHEMA_BROKEN['removed']}")
except NotImplementedError as error:
    print(f"Задание 9.4 не выполнено: {error}")
except Exception as error:
    print(f"Задание 9.4 не удалось: {error}")

# %%
try:
    PII_SCAN = find_pii(EXPORT_ROWS)
    EXPORT_RESULT = sanitize_export(EXPORT_ROWS)
    print(
        f"PII: до={PII_SCAN['count']} (email={len(PII_SCAN['emails'])}, "
        f"тел={len(PII_SCAN['phones'])}), после={EXPORT_RESULT['findings_after']}, "
        f"userId сохранён={EXPORT_RESULT['kept_user_id']}"
    )
except NotImplementedError as error:
    print(f"Задание 9.5 не выполнено: {error}")
except Exception as error:
    print(f"Задание 9.5 не удалось: {error}")

# %%
try:
    EXPERIMENT = experiment_pii_gate(EXPORT_ROWS)
    print(
        f"эксперимент: без маски найдено={EXPERIMENT['unguarded_findings']}, "
        f"гейт блокирует={EXPERIMENT['ci_blocks_unmasked']}; "
        f"с маской найдено={EXPERIMENT['guarded_findings']}, "
        f"гейт пропускает={EXPERIMENT['ci_passes_masked']}"
    )
except NotImplementedError as error:
    print(f"Эксперимент не выполнен: {error}")
except Exception as error:
    print(f"Эксперимент не удался: {error}")


# %% [markdown]
# ## 10. Проверки

# %%
def check_lag(report: dict[str, Any]) -> None:
    """9.1: одно окно 60–89, 30 минут, пик выше порога, свежесть нарушена."""
    assert len(report["windows"]) == 1, f"окон {len(report['windows'])}, ожидалось одно"
    window = report["windows"][0]
    assert window["start"] == DEGRADATION_START, f"начало окна {window['start']}"
    assert window["end"] == DEGRADATION_END - 1, f"конец окна {window['end']}"
    assert window["minutes"] == DEGRADATION_END - DEGRADATION_START
    assert report["degraded_minutes"] == DEGRADATION_END - DEGRADATION_START
    assert report["max_lag"] > LAG_THRESHOLD, f"max_lag={report['max_lag']}"
    assert report["max_minute"] == window["start"] + max(
        range(window["minutes"]), key=lambda offset: METRICS[window["start"] + offset]["lag"]
    ), "max_minute не совпал с пиком внутри окна"
    assert report["samples_over"] == report["degraded_minutes"]
    assert any(row["freshness_seconds"] > FRESHNESS_SLA for row in METRICS), "SLA не нарушен"


def check_tests(cases: list[dict[str, Any]], suite: dict[str, Any], mutants: dict[str, dict[str, Any]]) -> None:
    """9.2: ≥4 кейса, пустой есть, набор зелёный и убивает всех мутантов."""
    assert len(cases) >= 4, f"кейсов {len(cases)}, нужно >= 4"
    assert any(not case["rows"] for case in cases), "нет кейса с пустым входом"
    assert suite["failed"] == 0, f"корректная функция провалила {suite['failed']} кейсов"
    assert suite["passed"] == len(cases), "прошли не все кейсы"
    for name, result in mutants.items():
        assert result["failed"] > 0, f"мутант {name!r} выжил: тесты его не поймали"


def check_retry(ok_run: dict[str, Any], exhausted: dict[str, Any]) -> None:
    """9.3: две паузы по Retry-After, успех с третьей попытки, потолок backoff."""
    assert ok_run["ok"] is True, "успешный сценарий не завершился"
    assert ok_run["attempts"] == 3, f"попыток {ok_run['attempts']}, ожидалось 3"
    assert ok_run["delays"] == [1.0, 2.0], f"задержки {ok_run['delays']}"
    assert exhausted["ok"] is False, "исчерпание попыток должно быть отказом"
    assert exhausted["attempts"] == 5, f"попыток {exhausted['attempts']}"
    assert exhausted["delays"] == [1.0, 2.0, 4.0, 8.0], f"задержки {exhausted['delays']}"
    assert all(delay <= 8.0 for delay in exhausted["delays"]), "backoff вышел за потолок"


def check_ci(jobs: list[str], result: dict[str, Any], good: dict[str, Any], broken: dict[str, Any]) -> None:
    """9.4: семь job'ов, падение останавливает сборку, схема ловится."""
    expected = ["lint", "unit", "coverage", "contract", "contract-lint", "image-build", "release-gate"]
    assert jobs == expected, f"jobs={jobs}"
    assert result["exit_code"] == 1, f"exit_code={result['exit_code']}"
    assert result["failed"] == "unit", f"failed={result['failed']}"
    assert result["passed"] == ["lint"], f"passed={result['passed']}"
    assert good["ok"] is True and not good["removed"], "добавление поля не должно ломать схему"
    assert broken["ok"] is False, "переименование поля должно ломать схему"
    assert broken["removed"] == ["stationId"], f"removed={broken['removed']}"


def check_pii(scan: dict[str, Any], export: dict[str, Any]) -> None:
    """9.5: 10 находок до, 0 после, userId сохранён."""
    assert scan["count"] == 10, f"находок {scan['count']}, ожидалось 10"
    assert len(scan["emails"]) == 6, f"email {len(scan['emails'])}, ожидалось 6"
    assert len(scan["phones"]) == 4, f"телефонов {len(scan['phones'])}, ожидалось 4"
    assert export["findings_after"] == 0, "после маскирования остались находки"
    assert export["kept_user_id"] is True, "потерян userId"
    assert all("@" not in row["email"] or row["email"] == "***@***" for row in export["rows"])
    assert len(export["rows"]) == len(EXPORT_ROWS), "потеряны строки выгрузки"


def check_experiment(result: dict[str, Any]) -> None:
    """Эксперимент: гейт блокирует грязную выгрузку и пропускает чистую."""
    assert result["unguarded_findings"] == 10, f"без маски найдено {result['unguarded_findings']}"
    assert result["guarded_findings"] == 0, "после маски остались находки"
    assert result["ci_blocks_unmasked"] is True, "гейт пропустил утечку"
    assert result["ci_passes_masked"] is True, "гейт забраковал чистую выгрузку"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    checks: list[tuple[str, Callable[[], None]]] = []
    if LAG_REPORT is not None:
        checks.append(("9.1 лаг", lambda: check_lag(LAG_REPORT)))
    else:
        checks.append(("9.1 лаг", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if TEST_SUITE is not None and TEST_CASES and MUTANT_RESULTS:
        checks.append(("9.2 тесты", lambda: check_tests(TEST_CASES, TEST_SUITE, MUTANT_RESULTS)))
    else:
        checks.append(("9.2 тесты", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if RETRY_OK is not None and RETRY_EXHAUSTED is not None:
        checks.append(("9.3 429", lambda: check_retry(RETRY_OK, RETRY_EXHAUSTED)))
    else:
        checks.append(("9.3 429", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if CI_RESULT is not None and SCHEMA_OK is not None and SCHEMA_BROKEN is not None:
        checks.append(("9.4 CI", lambda: check_ci(CI_JOBS, CI_RESULT, SCHEMA_OK, SCHEMA_BROKEN)))
    else:
        checks.append(("9.4 CI", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if PII_SCAN is not None and EXPORT_RESULT is not None:
        checks.append(("9.5 PII", lambda: check_pii(PII_SCAN, EXPORT_RESULT)))
    else:
        checks.append(("9.5 PII", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
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
