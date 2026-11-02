# Семинар 3 — запуск и сдача

## Что внутри

| Файл            | Кому          | Что                                      |
| --------------- | ------------- | ---------------------------------------- |
| `seminar_03.py` | студенту      | задания с `# TASK` и `TODO`              |
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

Семинар работает только с профилем `adv`: нужны Redpanda (9092), `ingestion`
(консьюмер группы `ingestion-bronze`) и `sensor-gateway`. Дождитесь, пока
`redpanda` станет `healthy`, а `ingestion` — `running`.

## Запуск

### Вариант 1 — из терминала

```bash
export SPUTNIK_REPO=~/Sputnik-Mart
cd "code/seminars/03_event_systems"

# студенческая версия (ожидаемо часть проверок FAIL до выполнения заданий)
uv run --project "$SPUTNIK_REPO" --with aiokafka --with httpx --with pandas \
  python seminar_03.py

```

`aiokafka` уже в зависимостях `sputnik-db` (workspace), `--with aiokafka` —
страховка на случай запуска вне `--project`. `httpx` нужен для проверки
gateway, `pandas` — для таблиц.

### Вариант 2 — JupyterLab

```bash
cd ~/Sputnik-Mart
uv run jupyter lab
```

Откройте `seminar_03.py` как notebook (JupyterLab понимает percent-format).
Выполняйте ячейки сверху вниз.

!!! warning "Про `asyncio` в Jupyter"
    Скрипт вызывает `asyncio.run(...)` для каждой операции с Kafka. В ядре
    Jupyter это работает, если нет запущенного event-loop (иначе
    `RuntimeError: asyncio.run() cannot be called from a running event loop`).
    При проблеме перезапустите ядро и выполняйте только Kafka-ячейки подряд.


## Переменные окружения

| Переменная       | По умолчанию                        | Зачем                          |
| ---------------- | ----------------------------------- | ------------------------------ |
| `SPUTNIK_REPO`   | поиск вверх по дереву               | путь к Sputnik-Mart            |
| `GATEWAY_URL`    | `http://localhost:8000`             | проверка gateway               |
| `KAFKA_BOOTSTRAP`| `localhost:9092`                    | брокер Redpanda                |
| `PARTITIONS`     | `3`                                 | партиций учебного топика       |
| `SEED`           | `42`                                | детерминизм                    |
| `N_PERIODS`      | `30`                                | точек на станцию (3.1/3.4)     |
| `INTERVAL_SEC`   | `10`                                | шаг между чтениями, сек        |
| `WINDOW_SECONDS` | `60`                                | размер окна (3.4)              |
| `RUN_EXPERIMENT` | выключен                            | включает остановку `redpanda`  |

## Ожидаемый результат

1. Стенд-чек: `gateway` и `kafka` — `true`.
2. Сгенерировано 180 чтений, прочитано из учебного топика — 180.
3. Партиции: 6 станций → 3 партиции, каждая станция в одной партиции, offset
   внутри партиции идут подряд (`ordered: true`).
4. Лаг: `lag_before.total_lag > 0`, `lag_after.total_lag == 0`.
5. Дедуп: `kept` = 3 уникальных, `duplicates` = 3 повтора.
6. Окно: 30 окон, сумма `count` = 180, `min ≤ avg ≤ max`.
7. Эксперимент (с `RUN_EXPERIMENT=1`): `produce_while_down=false`,
   `kafka_recovered=true`, `produce_after_recovery=true`.
8. `Итог: 7/7 проверок пройдено`.

!!! note "Про партиции в Redpanda"
    Топик `sensors.seminar3.partitioned` создаёт сам скрипт с `PARTITIONS=3`
    партициями (в compose партиции не прописаны, а у автосоздаваемых топиков
    Redpanda по умолчанию 1 партиция). Поэтому задание 3.1 работает с учебным
    топиком, а не с `sensors.readings.v1`.


## Диагностика

| Симптом                                        | Что делать                                                                                          |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `kafka` = `false`                              | `docker compose --profile adv up -d`, проверить порт 9092, `docker compose ps`                     |
| `Не найден Sputnik-Mart`                       | `export SPUTNIK_REPO=/путь/к/Sputnik-Mart`                                                          |
| `NoBrokersAvailable` / таймаут при записи       | Redpanda ещё не `healthy` — подождать, `docker compose logs redpanda`                              |
| Задание 3.2: `docker compose` не найден         | установить Docker Compose v2                                                                        |
| Задание 3.2: лаг не растёт                      | `ingestion` не остановлен (проверить `docker compose ps ingestion`) или группа не `ingestion-bronze` |
| `asyncio.run() cannot be called...` (Jupyter)  | перезапустить ядро, выполнять Kafka-ячейки подряд                                                  |
| Эксперимент «завис»                             | `docker compose start redpanda`, дождаться `healthy`, повторить                                    |
| Порт 9092/8080 занят                            | освободить или использовать compose-override (см. ТЗ §3.3)                                         |

## Сдача

- Заполненные `TODO` в `seminar_03.py`.
- `run_checks()` без `FAIL`.
- `ANSWERS` и таблица `KAFKA_NATS` заполнены.
- Преподаватель задаёт 2–3 вопроса: offset vs acknowledgement, почему оплатам
  нельзя at-least-once, что гарантирует ключ партиции.