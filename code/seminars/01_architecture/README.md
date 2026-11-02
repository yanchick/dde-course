# Семинар 1 — запуск и сдача

## Что внутри

| Файл            | Кому          | Что                                      |
| --------------- | ------------- | ---------------------------------------- |
| `seminar_01.py` | студенту      | задания с `# TASK` и `TODO`              |
| `README.md`     | обоим         | запуск, ожидаемый результат, диагностика |

Оба файла — IPython-скрипты: ячейки разделены `# %%`, markdown-ячейки —
`# %% [markdown]`. Открываются в JupyterLab, VS Code, PyCharm и запускаются
как обычный Python-скрипт.

## Подготовка стенда

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

## Запуск

### Вариант 1 — из терминала

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

### Вариант 2 — JupyterLab

```bash
cd ~/Sputnik-Mart
uv run jupyter lab
```

Откройте `seminar_01.py` как notebook (JupyterLab понимает percent-format) или
скопируйте файл в `notebooks/` репозитория. Выполняйте ячейки сверху вниз.

## Переменные окружения

| Переменная       | По умолчанию            | Зачем                        |
| ---------------- | ----------------------- | ---------------------------- |
| `SPUTNIK_REPO`   | поиск вверх по дереву   | путь к Sputnik-Mart          |
| `GATEWAY_URL`    | `http://localhost:8000` | gateway                      |
| `CATALOG_URL`    | `http://localhost:8001` | прямой вызов catalog         |
| `DEMO_EMAIL`     | `buyer@sputnik.demo`    | демо-покупатель              |
| `DEMO_PASSWORD`  | `demo`                  | пароль                       |
| `PROFILE`        | `base`                  | профиль compose              |
| `RUN_EXPERIMENT` | выключен                | включает остановку `catalog` |

## Если `base` не поднимается (BUILD-1)

!!! note "BUILD-1 исправлен в коммите `5972c86` (2026-11-02)"
    В актуальной ветке `master` `services/catalog/pyproject.toml` уже объявляет
    workspace-зависимость `sputnik-service-client`, поэтому патч ниже нужен только
    для старых коммитов (например, `6906cf5`).


На коммите `6906cf5` профиль `base` падает на `catalog`:

```text
ModuleNotFoundError: No module named 'service_client'
```

Причина: `services/catalog/pyproject.toml` не объявляет `sputnik-service-client`.
Примените патч из этой папки:

```bash
cd ~/Sputnik-Mart
git apply /путь/к/dde-course/code/seminars/01_architecture/BUILD-1.patch
uv lock
docker compose --profile base build catalog
docker compose --profile base up -d
```

## Ожидаемый результат

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


## Диагностика

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

- Заполненные `TODO` в `seminar_01.py`.
- `run_checks()` без `FAIL`.
- `ANSWERS` заполнены.
- Преподаватель задаёт 2–3 вопроса по таблице и эксперименту.