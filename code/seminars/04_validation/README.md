# Семинар 4 — запуск и сдача

## Что внутри

| Файл            | Кому          | Что                                      |
| --------------- | ------------- | ---------------------------------------- |
| `seminar_04.py` | студенту      | задания с `# TASK` и `TODO`              |
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
docker compose --profile adv up -d
docker compose ps
```

Семинар работает с профилем `adv`: нужны `quality` (через gateway), MinIO
(для записи `report.json` в задании 4.5) и установленные зависимости
репозитория (`pandera`, `great_expectations`, `boto3`). Сам стенд не
обязательно должен быть в `running` для заданий 4.1–4.4 и эксперимента — они
чисто вычислительные; сверка 4.5 требует живого `quality` + MinIO.

## Запуск

### Вариант 1 — из терминала

```bash
export SPUTNIK_REPO=~/Sputnik-Mart
cd "code/seminars/04_validation"

# студенческая версия (ожидаемо часть проверок FAIL до выполнения заданий)
uv run --project "$SPUTNIK_REPO" --with httpx python seminar_04.py

```

`pandera`, `great_expectations` и `boto3` приходят из зависимостей репозитория
(`sputnik-validation`, `sputnik-db`), поэтому добавлять их не нужно. `--with httpx`
нужен для обращения к Quality API в задании 4.5.

!!! note "Скрипт импортирует код репозитория"
    В отличие от семинаров 1–3, этот скрипт импортирует `validation.validator`,
    `validation.quality_report` и `sim.*` напрямую. Без `--project "$SPUTNIK_REPO"`
    (или вне venv репозитория) эти импорты не разрешатся.


### Вариант 2 — JupyterLab

```bash
cd ~/Sputnik-Mart
uv run jupyter lab
```

Откройте `seminar_04.py` как notebook (JupyterLab понимает percent-format).
Выполняйте ячейки сверху вниз.

!!! warning "Great Expectations пишет прогресс в stderr"
    Ячейка с `run_ge_checks` выводит прогресс-бары GE («Calculating Metrics»).
    Это нормально; первый прогон GE может занять 10–30 секунд.


## Переменные окружения

| Переменная        | По умолчанию            | Зачем                          |
| ----------------- | ----------------------- | ------------------------------ |
| `SPUTNIK_REPO`    | поиск вверх по дереву   | путь к Sputnik-Mart            |
| `GATEWAY_URL`     | `http://localhost:8000` | Quality API (через gateway)    |
| `MINIO_ENDPOINT`  | `http://localhost:9000` | запись `report.json`           |
| `MINIO_ACCESS_KEY`| `sputnik`               | S3-ключ MinIO                  |
| `MINIO_SECRET_KEY`| `sputnik123`            | S3-секрет MinIO                |
| `MINIO_BUCKET`    | `lake`                  | бакет озера                    |
| `SEED`            | `42`                    | детерминизм                    |
| `PERIODS`         | `24`                    | точек на станцию               |
| `SPIKE_INDEX`     | `30`                    | индекс внедрённого выброса     |
| `SPIKE_FACTOR`    | `10.0`                  | множитель выброса              |
| `Z_THRESHOLD`     | `3.0`                   | порог z-score                  |

## Ожидаемый результат

1. Данные: 144 чистых и ~151 грязных чтений; примеры дефектов найдены.
2. `clean_readings`: clean — 144 строки, 0 карантин; dirty — 142 строки,
   25 в карантине; `weather_score` у dirty ниже, чем у clean (деградация).
3. Pandera: `clean=True`, `dirty=False`.
4. GE: `clean=True`, `dirty=False`.
5. DLQ: `{"NULL_VALUE": 18, "DUPLICATE": 4, "SCHEMA_MISMATCH": 3}` — 25 записей,
   3 причины.
6. PM2.5: выброс на индексе 30 найден, сезонный пик не помечен.
7. Сверка: `delta` близко к 0 (обычно 0.0).
8. Эксперимент: `clean_rows=144`, `renamed_rows=0`, причина `SCHEMA_MISMATCH`.
9. `Итог: 7/7 проверок пройдено`.

!!! note "Почему DLQ гарантированно 3 причины"
    `sim.dirty` с `broken=0.0` даёт пропуски и дубли, а три битые записи без
    `stationId` добавляются явно — иначе при некоторых seed `broken` не
    срабатывает и причина `SCHEMA_MISMATCH` может не появиться.


## Диагностика

| Симптом                                        | Что делать                                                                                          |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: validation.validator`    | запускать через `uv run --project "$SPUTNIK_REPO"`                                                  |
| `pandera`/`great_expectations` не импортируются| `uv sync --all-packages --dev` в репозитории                                                       |
| Задание 4.5: `Connection refused` на 8000      | поднять `docker compose --profile adv up -d`, проверить gateway                                     |
| Задание 4.5: `qualityScore` не совпал          | `docker compose ps quality`, `docker compose logs quality`; отчёт пишется в `reports/quality/{dt}/` |
| Задание 4.5: boto3 не установлен               | `--with boto3` (обычно уже есть через `sputnik-db`)                                                 |
| GE пишет прогресс/долго                        | это нормально; дождаться первого прогона                                                            |
| `clean_readings` вернул пустой silver          | проверьте формат записей: `stationId`/`value`/`measuredAt` обязательны                              |

## Сдача

- Заполненные `TODO` в `seminar_04.py`.
- `run_checks()` без `FAIL`.
- `ANSWERS` заполнены.
- Преподаватель задаёт 2–3 вопроса: DLQ vs починка, почему z-score врёт на
  сезонности, почему API и report.json обязаны совпадать.