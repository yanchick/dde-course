---
title: ETL/ELT пайплайны и оркестрация
description: Apache Airflow, надёжные пайплайны, мониторинг, обработка ошибок и восстановление после сбоев.
---

# ETL/ELT пайплайны и оркестрация

## О чём лекция

- Оркестрация и Apache Airflow: архитектура, компоненты, DAG, операторы, триггеры, cron, XCom и масштабирование.
- Надёжные пайплайны: идемпотентность, атомарность, инкрементальная обработка и чекпоинты.
- Мониторинг: ключевые метрики, Prometheus и Grafana, структурное логирование, алерты и дашборды.
- Обработка ошибок: типы ошибок, retry-стратегии, exponential backoff, graceful degradation, dead letter queue и автовосстановление.
- Практический кейс: архитектура, реализация DAG, тесты и мониторинг.

## Материалы

| Материал | Ссылка |
| --- | --- |
| Слайды | [HTML](../slides/lecture-06.html){ target="_blank" } · [PDF](../slides/lecture-06.pdf){ target="_blank" } |
| Исходник | [slides/lecture-06.md](https://github.com/yanchick/dde-course/blob/main/slides/lecture-06.md){ target="_blank" } |
| Семинар | [Семинар 7](../seminars/07-orchestration.md) |
| Код | [code/seminars/07_orchestration](https://github.com/yanchick/dde-course/tree/main/code/seminars/07_orchestration){ target="_blank" } |

## Дальше

Следующая лекция: [Современные хранилища данных](07-storage.md).
