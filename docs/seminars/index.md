---
title: Семинары
description: Десять практикумов продвинутого уровня на стенде Sputnik-Mart — от архитектуры сервисов до observability.
---

# Семинары

Практикумы продвинутого уровня. Студент поднимает стенд [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart) с профилем `base` или `adv` и работает в IPython-скриптах: ячейки разделены `# %%`, задания помечены `# TASK` и `TODO`, проверки собраны в `run_checks()`.

| № | Семинар | Тема | Лекция | Формат |
| --- | --- | --- | --- | --- |
| 01 | [Архитектура](01-architecture.md) | Сервисы, профили, `requestId` | [1](../lectures/01-architecture.md) | Docker, профиль `base` |
| 02 | [Сбор данных](02-data-collection.md) | REST, Scrapy, чанки, дедуп | [2](../lectures/02-data-collection.md) | Docker, профиль `adv` |
| 03 | [Event-системы](03-event-systems.md) | Kafka, партиции, лаг, окна | [2](../lectures/02-data-collection.md) | Docker, профиль `adv` |
| 04 | [Валидация](04-validation.md) | Pandera, Great Expectations, DLQ | [3](../lectures/03-cleaning-validation.md) | Без Docker |
| 05 | [Трансформация](05-transformation.md) | Признаки, временные ряды, прогноз | [4](../lectures/04-transformation.md) | Без Docker |
| 06 | [Разметка](06-labeling.md) | Label Studio JSON, kappa, экспорт | [5](../lectures/05-labeling.md) | Без Docker |
| 07 | [Оркестрация](07-orchestration.md) | DAG, идемпотентность, ETL/ELT | [6](../lectures/06-etl-orchestration.md) | Без Docker |
| 08 | [Хранилища](08-storage.md) | Слои озера, MergeTree, Mongo | [7](../lectures/07-storage.md) | Без Docker |
| 09 | [Observability](09-observability.md) | Лаг, мутационные тесты, 429, PII | [6](../lectures/06-etl-orchestration.md) | Без Docker |
| 10 | [Сквозной прогон](10-end-to-end.md) | Сборка всех шагов | — | Материалы готовятся |

## Как устроен семинар

- **90 минут** (семинар 3 — 90–120): вход и проверка стенда, разбор, демо, самостоятельная работа, дебрифинг и сдача.
- **Скрипт** — обычный `.py`, который открывается в JupyterLab, VS Code и PyCharm; запускается и из терминала.
- **Проверки** — `run_checks()` печатает таблицу PASS/FAIL. Задание считается выполненным, когда нет `FAIL`.
- **Сдача** — заполненные `TODO`, зелёный `run_checks()` и короткие ответы в `ANSWERS`; преподаватель задаёт 2–3 вопроса по работе.

## Что понадобится

- Python 3.11+ и [uv](https://docs.astral.sh/uv/).
- Docker Compose v2 — только для семинаров 1–3.
- Репозиторий `Sputnik-Mart`, клонированный рядом; путь передаётся через `SPUTNIK_REPO`.

```bash
git clone https://github.com/yanchick/Sputnik-Mart.git ~/Sputnik-Mart
cd ~/Sputnik-Mart
cp .env.example .env
uv sync --all-packages --dev
docker compose --profile base up -d   # или --profile adv
```

Код семинаров лежит в репозитории курса: [`code/seminars`](https://github.com/yanchick/dde-course/tree/main/code/seminars). Подробности запуска, переменные окружения и диагностика — на странице каждого семинара.
