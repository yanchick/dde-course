# Семинар 2 — запуск и сдача

## Что внутри

| Файл            | Кому          | Что                                      |
| --------------- | ------------- | ---------------------------------------- |
| `seminar_02.py` | студенту      | задания с `# TASK` и `TODO`              |
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

Семинар работает только с профилем `adv`: нужны `sensor-gateway` (приём
чтений на 8006), `ingestion` (дедуп → bronze) и MinIO (озеро, 9000). Дождитесь,
пока `api-gateway`, `catalog`, `sensor-gateway`, `ingestion` будут `running`,
а `migrate`/`seed` — `exited (0)`.

> В актуальной ветке `master` (коммит `5972c86` и новее) BUILD-1 исправлен:
> `services/catalog` объявляет workspace-зависимость `sputnik-service-client`.
> Для старых коммитов (например, `6906cf5`) профиль `base` может падать на
> `catalog` с `ModuleNotFoundError: service_client`; патч `BUILD-1.patch` лежит
> в `code/seminars/01_architecture/`. Для семинара 2 он не нужен.

## Запуск

### Вариант 1 — из терминала

```bash
export SPUTNIK_REPO=~/Sputnik-Mart
cd "code/seminars/02_data_collection"

# студенческая версия (ожидаемо часть проверок FAIL до выполнения заданий)
uv run --project "$SPUTNIK_REPO" \
  --with httpx --with pandas --with boto3 --with scrapy \
  python seminar_02.py

```

`--with httpx --with pandas` обязательны, `--with boto3` нужен для чтения
bronze, `--with scrapy` — для паука (задание 2.2). Без boto3/scrapy скрипт не
падает, но соответствующие задания помечаются как невыполненные.

### Вариант 2 — JupyterLab

```bash
cd ~/Sputnik-Mart
uv run jupyter lab
```

Откройте `seminar_02.py` как notebook (JupyterLab понимает percent-format) или
скопируйте файл в `notebooks/` репозитория. Выполняйте ячейки сверху вниз.

!!! warning "Про Scrapy в Jupyter"
    `CrawlerProcess` запускает Twisted-реактор и в ядре Jupyter может
    конфликтовать с уже запущенным реактором. Задание 2.2 надёжнее гонять
    терминальным запуском (`Вариант 1`). Если ячейка паука висит — перезапустите
    ядро и выполните только её.


## Переменные окружения

| Переменная           | По умолчанию            | Зачем                        |
| -------------------- | ----------------------- | ---------------------------- |
| `SPUTNIK_REPO`       | —                       | путь к Sputnik-Mart для `uv` |
| `GATEWAY_URL`        | `http://localhost:8000` | gateway (каталог)            |
| `SENSOR_GATEWAY_URL` | `http://localhost:8006` | приём чтений                 |
| `MINIO_ENDPOINT`     | `http://localhost:9000` | озеро (bronze)               |
| `MINIO_ACCESS_KEY`   | `sputnik`               | S3-ключ MinIO                |
| `MINIO_SECRET_KEY`   | `sputnik123`            | S3-секрет MinIO              |
| `MINIO_BUCKET`       | `lake`                  | бакет озера                  |
| `DEMO_EMAIL`         | `buyer@sputnik.demo`    | демо-покупатель              |
| `DEMO_PASSWORD`      | `demo`                  | пароль                       |
| `SEED`               | `42`                    | детерминизм                  |
| `N_CSV_ROWS`         | `200000`                | строк партнёрского CSV       |
| `MEMORY_LIMIT_MB`    | `50`                    | порог пика памяти (2.3)      |

## Ожидаемый результат

1. Стенд-чек: `gateway` и `sensor_gateway` — `true`.
2. Каталог: собрано 5 датасетов, `total=5`, без повторов `datasetId`.
3. Паук: 24 карточки, у каждой есть название и цена-число > 0.
4. Чанки: `rows=200000`, пик памяти заметно ниже `MEMORY_LIMIT_MB`.
5. Публикация: `{"accepted": 10, "dead": 1}`; в bronze — 10 чтений с
   `receivedAt >= measuredAt`.
6. Дедуп: `before == after` (`total` и `distinct` не изменились).
7. Эксперимент: `{"accepted": 0, "dead": 2}`, классификация
   `"abc"→SCHEMA_MISMATCH`, `999→OUT_OF_RANGE`.
8. `Итог: 7/7 проверок пройдено`.

!!! note "Про «битую запись» в батче 2.4"
    В батче намеренно лежит запись без `stationId`. Шлюз отбраковывает её на
    приёме и возвращает `dead=1` — она **не** попадает в bronze. Остальные 10
    чтений проходят шлюз, `ingestion` пишет их в bronze, а `receivedAt` проставляет
    только шлюз, поэтому `receivedAt ≥ measuredAt` выполняется всегда.


## Диагностика

| Симптом                                             | Что делать                                                                                          |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `gateway`/`sensor_gateway` = `false`                | `docker compose --profile adv up -d`, проверить порты 8000 и 8006                                   |
| `401` при логине                                    | проверить `.env`, пароль `demo`, что `seed` завершился                                              |
| `Connection refused` на 8006                        | `sensor-gateway` есть только в профиле `adv`, не `base`                                             |
| Задание 2.2 не выполнено: Scrapy не установлен       | добавить `--with scrapy` в команду запуска                                                          |
| Проверка receivedAt/дедупа не удалась               | boto3 не установлен (`--with boto3`); либо `ingestion` не поднят — `docker compose ps`             |
| `dead` больше ожидаемого                             | батч уже отправлялся, но это норма: шлюз не дедуплицирует, дедуп — на стороне `ingestion`          |
| В bronze 0 чтений после публикации                  | `ingestion` не запущен или Redpanda недоступна — `docker compose logs ingestion`                   |
| Scrapy-паук висит в Jupyter                          | перезапустить ядро, запускать паука терминалом (см. предупреждение выше)                           |
| Порт 9000/9001 занят                                 | освободить или использовать compose-override (см. ТЗ §3.3)                                         |

## Сдача

- Заполненные `TODO` в `seminar_02.py`.
- `run_checks()` без `FAIL`.
- `ANSWERS` заполнены.
- Преподаватель задаёт 2–3 вопроса: почему чанки не всегда быстрее, что
  происходит с дублями, где должна стоять проверка валидности.