---
title: "Семинар 1 — Архитектура систем обработки данных"
description: "План занятия, задания и порядок сдачи: Архитектура систем обработки данных."
---

# Семинар 1 — Архитектура систем обработки данных

**Связанная лекция:** [Архитектура систем обработки данных](../lectures/01-architecture.md)

## Цель

Понять, из каких сервисов состоит стенд, где проходит граница между фасадом и
пайплайном, и как один `requestId` связывает запрос через несколько сервисов.

## Результаты

- Студент читает `docker-compose.yml` и находит сервис по порту и хранилищу.
- Объясняет роль `api-gateway` и разницу профилей `base`/`adv`.
- Прослеживает `X-Request-Id` через gateway и прямой вызов сервиса.
- По ответу об ошибке определяет, какой сервис недоступен.

## Тайминг

| Блок      | Мин | Что                                    |
| --------- | --- | -------------------------------------- |
| Вход      | 5   | проверка стенда, у кого красный статус |
| Разбор    | 15  | две нити, профили, gateway             |
| Демо      | 15  | логин, каталог, `requestId`            |
| Работа    | 40  | задания 1.1–1.3                        |
| Дебрифинг | 10  | эксперимент и вопросы                  |
| Сдача     | 5   | `make check-nb 01` или `run_checks()`  |

## Задания

1. **1.1 Карта сервисов.** Заполнить роль и хранилище для 9 сервисов, сверить
   порты с `docker compose ps`.
2. **1.2 Трейс.** Отправить запрос с `X-Request-Id`, увидеть его в ответе
   gateway, в прямом ответе `catalog` и в конверте ошибки `401`.
3. **1.3 Диагноз.** Остановить `catalog`, получить `5xx`, определить сервис и
   причину, поднять обратно.

## Эксперимент

Остановить `catalog` при живом `base`: фасад и каталог деградируют, но
`identity`/`order`/`delivery` продолжают работать. Gateway отдаёт `500`
`INTERNAL_ERROR` с единым конвертом, но **без `requestId`** — это дефект OBS-5.
Сравните с `401`, где `requestId` есть, и объясните разницу в порядке
middleware.

!!! warning "Безопасность"
    Эксперимент останавливает контейнер. Запускайте только с `RUN_EXPERIMENT=1`
    и только на своём локальном стенде. Скрипт сам поднимает `catalog` обратно.


## Как запускать

### Подготовка стенда

```bash
git clone https://github.com/yanchick/Sputnik-Mart.git ~/Sputnik-Mart
cd ~/Sputnik-Mart
cp .env.example .env
uv sync --all-packages --dev
docker compose --profile base up -d
docker compose ps
```

Дождитесь, пока `api-gateway`, `catalog`, `identity`, `order`, `review`,
`delivery`, `quality`, `web-vitrina` будут в состоянии `running`, а `seed` и
`migrate` — `exited (0)`.

### Запуск из терминала

```bash
export SPUTNIK_REPO=~/Sputnik-Mart
cd "code/seminars/01_architecture"

# студенческая версия (ожидаемо часть проверок FAIL до выполнения заданий)
uv run --project "$SPUTNIK_REPO" python seminar_01.py

```

Если `uv` не находит зависимости, добавьте их явно:

```bash
uv run --project "$SPUTNIK_REPO" --with httpx --with pandas python seminar_01.py
```

### Запуск в JupyterLab

```bash
cd ~/Sputnik-Mart
uv run jupyter lab
```

Откройте `seminar_01.py` как notebook (JupyterLab понимает percent-format) или
скопируйте файл в `notebooks/` репозитория. Выполняйте ячейки сверху вниз.

### Переменные окружения

| Переменная       | По умолчанию            | Зачем                        |
| ---------------- | ----------------------- | ---------------------------- |
| `SPUTNIK_REPO`   | поиск вверх по дереву   | путь к Sputnik-Mart          |
| `GATEWAY_URL`    | `http://localhost:8000` | gateway                      |
| `CATALOG_URL`    | `http://localhost:8001` | прямой вызов catalog         |
| `DEMO_EMAIL`     | `buyer@sputnik.demo`    | демо-покупатель              |
| `DEMO_PASSWORD`  | `demo`                  | пароль                       |
| `PROFILE`        | `base`                  | профиль compose              |
| `RUN_EXPERIMENT` | выключен                | включает остановку `catalog` |

### Ожидаемый результат

1. Таблица сервисов: 9 строк, порты 8000–8006 и 8050, состояния `running`.
2. Превью каталога: 5 датасетов, пагинация `{page: 1, pageSize: 5, total: 5, ...}`.
3. `trace`:
   ```json
   {
     "gateway_status": 200,
     "gateway_request_id": "req_seminar_01_demo",
     "catalog_status": 200,
     "catalog_request_id": "req_seminar_01_demo",
     "error_status": 401,
     "error_code": "UNAUTHORIZED",
     "error_request_id": "req_seminar_01_demo"
   }
   ```
4. Эксперимент (с `RUN_EXPERIMENT=1`): `status` 500, `restored: true`, а
   `request_id` пустой — это ожидаемый дефект OBS-5. На `401` `requestId` есть,
   на `500` — теряется. Обсудите, в каком порядке стоят middleware.
5. `Итог: 5/5 проверок пройдено`.

!!! note "Про `requestId` в логах"
    Сервисы возвращают `X-Request-Id` в заголовках и в конверте ошибки, но
    per-request логирование в репозитории пока не добавлено (см. ТЗ §3.7,
    OBS-4). Поэтому задание проверяет заголовки, а не `docker compose logs`.


### Если что-то не работает

| Симптом                                                 | Что делать                                                                                                                                  |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `Не найден Sputnik-Mart`                                | `export SPUTNIK_REPO=/путь/к/Sputnik-Mart`                                                                                                  |
| `docker compose не найден`                              | установить Docker Compose v2                                                                                                                |
| `401` при логине                                        | проверить `.env`, пароль `demo`, что `seed` завершился                                                                                      |
| `catalog` exits с `ModuleNotFoundError: service_client` | в `services/catalog/pyproject.toml` не объявлена зависимость `sputnik-service-client` (BUILD-1); добавить, `uv lock`, пересобрать `catalog` |
| `Connection refused`                                    | `docker compose --profile base up -d`, проверить порт 8000                                                                                  |
| `catalog` не поднялся после эксперимента                | `docker compose start catalog`, `docker compose logs catalog`                                                                               |
| Порт занят                                              | освободить 8000–8006/8050 или остановить старый профиль                                                                                     |

## Сдача

- `seminar_01.py` с заполненными `TODO`.
- Вывод `run_checks()` без `FAIL`.
- Короткий вывод (3–5 предложений) в `ANSWERS`.

## Код

[`code/seminars/01_architecture`](https://github.com/yanchick/dde-course/tree/main/code/seminars/01_architecture){ target="_blank" } — скрипт, README и план занятия.