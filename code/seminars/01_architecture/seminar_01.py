# %% [markdown]
# # Семинар 1 — Архитектура систем обработки данных
#
# **Версия студента.** Профиль `base`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Что делаем:
# 1. Проверяем стенд через `docker compose ps`.
# 2. Входим демо-покупателем и читаем каталог.
# 3. Собираем карту сервисов (задание 1.1).
# 4. Прослеживаем `X-Request-Id` через gateway и `catalog` (задание 1.2).
# 5. Роняем `catalog` и объясняем ошибку (задание 1.3).
#
# Запуск:
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# docker compose --profile base up -d
# uv run --project "$SPUTNIK_REPO" --with httpx --with pandas python seminar_01.py
# ```

# %%
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000").rstrip("/")
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8001").rstrip("/")
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "buyer@sputnik.demo")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo")
PROFILE = os.getenv("PROFILE", "base")
REQUEST_ID = "req_seminar_01_demo"
RUN_EXPERIMENT = os.getenv("RUN_EXPERIMENT") == "1"


# %% [markdown]
# ## 1. Где лежит репозиторий
#
# Скрипт не зависит от текущей папки: путь берётся из `SPUTNIK_REPO`, а если
# переменная не задана — ищется вверх по дереву от текущей директории.

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
    raise RuntimeError(
        "Не найден Sputnik-Mart. Укажите SPUTNIK_REPO=/путь/к/Sputnik-Mart"
    )


def run_compose(root: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
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


def compose_ps(root: Path, profile: str = PROFILE) -> list[dict[str, Any]]:
    """Вернуть `docker compose ps` как список словарей."""
    process = run_compose(root, "--profile", profile, "ps", "--format", "json")
    if process.returncode != 0:
        print(process.stderr.strip() or "docker compose ps завершился с ошибкой")
        return []
    raw = process.stdout.strip()
    if not raw:
        return []
    try:
        if raw.startswith("["):
            data = json.loads(raw)
        else:
            data = [json.loads(line) for line in raw.splitlines() if line.strip()]
    except json.JSONDecodeError:
        print("Не удалось разобрать JSON от `docker compose ps`; используется пустой список")
        return []
    return data if isinstance(data, list) else [data]


def _ports_of(item: dict[str, Any]) -> list[int]:
    """Достать опубликованные порты из Publishers или строки Ports."""
    ports: set[int] = set()
    for publisher in item.get("Publishers") or []:
        port = publisher.get("PublishedPort")
        if port:
            ports.add(int(port))
    if not ports:
        for match in re.finditer(r"(?:0\.0\.0\.0:|\[::\]:)?(\d+)->", str(item.get("Ports") or "")):
            ports.add(int(match.group(1)))
    return sorted(ports)


def service_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Нормализовать вывод compose ps: сервис, состояние, здоровье, порты."""
    rows = []
    for item in items:
        rows.append(
            {
                "service": item.get("Service") or item.get("Name") or "?",
                "state": item.get("State") or "?",
                "health": item.get("Health") or "—",
                "ports": _ports_of(item),
            }
        )
    return sorted(rows, key=lambda row: row["service"])


# %% [markdown]
# ## 2. Карта сервисов (задание 1.1)
#
# Заполните роль и хранилище для каждого сервиса по `docker-compose.yml`,
# README и паспортам сервисов. Порт берётся из живого `docker compose ps`,
# а не из головы.

# %%
# TASK 1.1 — карта сервисов
# TODO: заполните role и storage. Подсказка — README репозитория,
# `docker-compose.yml` и папки `services/*`.
SERVICE_CATALOG: dict[str, dict[str, str]] = {
    "api-gateway": {"role": "", "storage": ""},
    "catalog": {"role": "", "storage": ""},
    "identity": {"role": "", "storage": ""},
    "order": {"role": "", "storage": ""},
    "review": {"role": "", "storage": ""},
    "delivery": {"role": "", "storage": ""},
    "web-vitrina": {"role": "", "storage": ""},
    "sensor-gateway": {"role": "", "storage": ""},
    "quality": {"role": "", "storage": ""},
}


def build_service_map(
    rows: list[dict[str, Any]],
    catalog: dict[str, dict[str, str]] | None = None,
) -> pd.DataFrame:
    """Соединить живое состояние compose с ролями и хранилищами.

    Ожидаемые колонки: service, port, state, health, role, storage.
    """
    # TODO (1.1): соберите DataFrame по образцу:
    #   by_service = {row["service"]: row for row in rows}
    #   для каждого service из catalog возьмите live = by_service.get(...)
    #   port = ", ".join(...) или "—"
    #   верните pd.DataFrame(records)
    raise NotImplementedError("Задание 1.1: заполните SERVICE_CATALOG и build_service_map")


def print_table(frame: pd.DataFrame) -> None:
    """Напечатать DataFrame без индекса (работает и вне Jupyter)."""
    if frame.empty:
        print("(пусто)")
    else:
        print(frame.to_string(index=False))


# %% [markdown]
# ## 3. Вход и каталог
#
# Вход — `POST /api/v1/auth/login` с демо-аккаунтом. Дальше все запросы идут
# через gateway с Bearer-токеном.

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
    """Прочитать страницу каталога через gateway."""
    response = client.get(
        "/api/v1/datasets",
        params={"page": page, "pageSize": page_size},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


# %% [markdown]
# ## 4. Сквозной `requestId` (задание 1.2)
#
# Отправляем один и тот же `X-Request-Id` в трёх запросах:
# 1. через gateway с токеном;
# 2. напрямую в `catalog` с токеном;
# 3. через gateway без токена — получаем конверт ошибки.
#
# Во всех трёх ответах идентификатор должен совпасть с отправленным.

# %%
# TASK 1.2 — сквозной requestId
def trace_request(
    client: httpx.Client,
    token: str,
    request_id: str = REQUEST_ID,
) -> dict[str, Any]:
    """Проследить requestId через gateway, catalog и конверт ошибки."""
    # TODO (1.2):
    # 1) GET /api/v1/datasets через client с Bearer и X-Request-Id;
    # 2) GET /api/v1/datasets напрямую в CATALOG_URL с теми же заголовками;
    # 3) GET /api/v1/datasets без токена — отдельным httpx.Client без Authorization.
    # Верните словарь с ключами:
    # gateway_status, gateway_request_id, catalog_status, catalog_request_id,
    # error_status, error_code, error_request_id.
    raise NotImplementedError("Задание 1.2: реализуйте trace_request")



# %% [markdown]
# ## 5. Диагноз по ошибке (задание 1.3)
#
# Когда upstream недоступен, gateway возвращает `5xx` с единым конвертом.
# Задача — по пути и коду ответа назвать сервис и причину.

# %%
# TASK 1.3 — диагноз по ошибке
def diagnose(path: str, status_code: int, payload: dict[str, Any] | None) -> dict[str, str]:
    """Определить сервис и причину по ответу gateway."""
    # TODO (1.3): разберите конверт ошибки.
    # Подсказки:
    # - 401 без токена — это gateway, запрос не дошёл до данных;
    # - 5xx на /api/v1/datasets — недоступен catalog;
    # - 403 — нет прав на датасет (order/delivery).
    # Верните {"service": ..., "reason": ...}.
    raise NotImplementedError("Задание 1.3: реализуйте diagnose")


# %% [markdown]
# ## 6. Эксперимент: роняем `catalog`
#
# Останавливаем контейнер, ждём, отправляем запрос, затем обязательно поднимаем
# обратно и ждём `healthz`. По умолчанию эксперимент выключен:
# `RUN_EXPERIMENT=1`.

# %%
def wait_health(url: str, timeout: int = 30) -> bool:
    """Дождаться `200` от health-эндпоинта."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def experiment_catalog_down(
    root: Path,
    client: httpx.Client,
    token: str,
) -> dict[str, Any]:
    """Остановить catalog, получить ошибку, поднять сервис обратно."""
    # TODO (1.3): реализуйте по шагам.
    # 1) run_compose(root, "stop", "catalog"); проверьте returncode.
    # 2) подождите 2 секунды и отправьте GET /api/v1/datasets через client
    #    с Bearer и X-Request-Id; сохраните status, payload, request_id.
    # 3) в finally обязательно run_compose(root, "start", "catalog")
    #    и wait_health(f"{CATALOG_URL}/healthz").
    # Верните словарь с ключами status, payload, request_id, restored.
    raise NotImplementedError("Задание 1.3: реализуйте experiment_catalog_down")


# %% [markdown]
# ## 7. Выводы
#
# Заполните коротко, своими словами. Проверка смотрит только на наличие
# содержательного ответа, но преподаватель спросит по существу.

# %%
# TASK — выводы
# TODO: ответьте своими словами, 1–3 предложения на пункт.
ANSWERS: dict[str, str] = {
    "1": "",  # Где граница между Lake и потоком?
    "2": "",  # Что продолжает работать, если ClickHouse недоступен?
    "3": "",  # Зачем нужен gateway, если сервисы и так доступны?
    "4": "",  # Почему 500 теряет requestId, а 401 — нет?
}


# %% [markdown]
# ## 8. Прогон

# %%
root: Path | None = None
stack_items: list[dict[str, Any]] = []
service_map: pd.DataFrame | None = None
trace: dict[str, Any] | None = None
experiment: dict[str, Any] | None = None
diagnosis: dict[str, str] | None = None
api: httpx.Client | None = None
token: str | None = None

try:
    root = find_repo_root()
    print(f"Репозиторий: {root}")
    stack_items = service_rows(compose_ps(root))
    print(f"Сервисов в профиле `{PROFILE}`: {len(stack_items)}")
    print_table(
        pd.DataFrame(
            [
                {
                    "service": row["service"],
                    "state": row["state"],
                    "health": row["health"],
                    "ports": ", ".join(map(str, row["ports"])) or "—",
                }
                for row in stack_items
            ]
        )
    )
except Exception as error:  # стенд может быть не поднят
    print(f"Не удалось проверить стенд: {error}")

# %%
try:
    token = login()
    api = httpx.Client(
        base_url=GATEWAY_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    page = catalog_page(api)
    print("Покупатель вошёл, токен получен.")
    print("Пагинация:", json.dumps(page.get("pagination", {}), ensure_ascii=False))
    preview = pd.DataFrame(page.get("data", []))
    columns = [column for column in ("datasetId", "name", "category", "qualityScore") if column in preview]
    print_table(preview[columns] if columns else preview)
except Exception as error:
    print(f"Не удалось войти или прочитать каталог: {error}")

# %%
if stack_items:
    try:
        service_map = build_service_map(stack_items)
        print_table(service_map)
    except NotImplementedError as error:
        print(f"Задание 1.1 не выполнено: {error}")
else:
    print("Задание 1.1 пропущено: нет данных `docker compose ps`.")

# %%
if api is not None and token is not None:
    try:
        trace = trace_request(api, token)
        print(json.dumps(trace, ensure_ascii=False, indent=2))
    except NotImplementedError as error:
        print(f"Задание 1.2 не выполнено: {error}")
else:
    print("Задание 1.2 пропущено: нет токена.")

# %%
if RUN_EXPERIMENT and root is not None and api is not None and token is not None:
    experiment = experiment_catalog_down(root, api, token)
    print(json.dumps(experiment, ensure_ascii=False, indent=2, default=str))
    diagnosis = diagnose("/api/v1/datasets", experiment.get("status", 0), experiment.get("payload"))
    print("Диагноз:", json.dumps(diagnosis, ensure_ascii=False))
else:
    print(
        "Эксперимент пропущен. Запустите с RUN_EXPERIMENT=1, когда стенд поднят "
        "и вы готовы остановить `catalog`."
    )


# %% [markdown]
# ## 9. Проверки

# %%
def check_service_map(frame: pd.DataFrame) -> None:
    """Проверить карту сервисов."""
    required = {"service", "port", "state", "health", "role", "storage"}
    missing = required - set(frame.columns)
    assert not missing, f"нет колонок: {sorted(missing)}"
    assert (frame["role"].str.len() > 3).all(), "у всех сервисов должна быть роль"
    expected_ports = {
        "api-gateway": "8000",
        "catalog": "8001",
        "identity": "8002",
        "order": "8003",
        "review": "8004",
        "delivery": "8005",
        "sensor-gateway": "8006",
        "web-vitrina": "8050",
    }
    for service, port in expected_ports.items():
        row = frame[frame["service"] == service]
        assert not row.empty, f"нет сервиса {service}"
        if row.iloc[0]["state"] == "не запущен":
            continue  # в профиле base sensor-gateway ещё не поднят
        assert port in str(row.iloc[0]["port"]), f"{service}: ожидался порт {port}"


def check_trace(trace: dict[str, Any]) -> None:
    """Проверить сквозной requestId."""
    assert trace["gateway_status"] == 200, "gateway должен отдать 200"
    assert trace["catalog_status"] == 200, "catalog должен отдать 200"
    assert trace["error_status"] == 401, "без токена ожидается 401"
    assert trace["error_code"] == "UNAUTHORIZED", "ожидается код UNAUTHORIZED"
    values = {
        trace["gateway_request_id"],
        trace["catalog_request_id"],
        trace["error_request_id"],
    }
    assert values == {REQUEST_ID}, f"requestId не совпал: {values}"


def check_diagnosis(diagnosis: dict[str, str]) -> None:
    """Проверить диагноз эксперимента."""
    assert diagnosis.get("service") == "catalog", "ожидался catalog"
    assert diagnosis.get("reason"), "нужна причина"


def check_experiment(experiment: dict[str, Any]) -> None:
    """Проверить, что ошибка получена, а сервис восстановлен."""
    assert experiment.get("status", 0) >= 500, "ожидался 5xx от gateway"
    assert experiment.get("restored") is True, "catalog не восстановился"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    checks: list[tuple[str, Any]] = []
    if service_map is not None:
        checks.append(("1.1 карта сервисов", lambda: check_service_map(service_map)))
    else:
        checks.append(("1.1 карта сервисов", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if trace is not None:
        checks.append(("1.2 requestId", lambda: check_trace(trace)))
    else:
        checks.append(("1.2 requestId", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))
    if diagnosis is not None:
        checks.append(("1.3 диагноз", lambda: check_diagnosis(diagnosis)))
    else:
        checks.append(("1.3 диагноз", lambda: (_ for _ in ()).throw(AssertionError("эксперимент не запущен"))))
    if experiment is not None:
        checks.append(("эксперимент", lambda: check_experiment(experiment)))
    else:
        checks.append(("эксперимент", lambda: (_ for _ in ()).throw(AssertionError("эксперимент не запущен"))))
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
