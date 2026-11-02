# %% [markdown]
# # Семинар 6 — Системы разметки и аннотации
#
# **Версия студента.** Профиль `adv`, репозиторий
# [Sputnik-Mart](https://github.com/yanchick/Sputnik-Mart).
#
# Данные размечены — но кем и насколько хорошо? Семинар про то, как устроен
# цикл аннотации и как проверить его качество:
# 1. Собираем корпус из 100 отзывов и проект разметки в формате Label Studio —
#    задание 6.1.
# 2. Выбираем 15 задач активным обучением вместо всех 100 — задание 6.2.
# 3. Считаем согласие двух аннотаторов через Cohen's kappa — задание 6.3.
# 4. Экспортируем аннотации в JSON Label Studio и кладём в озеро — задание 6.4.
# 5. Учим лексикон на разметке и меряем, что она дала модели — задание 6.5.
# 6. Эксперимент: что делать, если аннотаторы расходятся на 40%.
#
# Задания отмечены `# TASK` и `TODO`: заполните тела функций, `MANUAL_SEED`
# и `ANSWERS`. Демо-ячейки, оракул и проверки менять не нужно.
#
# > [!important] Label Studio в стенде нет
# > В `docker-compose.yml` репозитория Label Studio **не описан**: это
# > backlog-задачи SRV-15 (поднять LS в профиле `adv/demo`) и SRV-16
# > (толкать задачи в LS через `/api/projects`). Поэтому семинар не
# > поднимает Docker и не изображает живой LS API: мы строим
# > **LS-совместимые** project/tasks/export JSON локально. Такой же payload
# > позже отправляется в реальный LS как есть.
#
# Запуск (Docker не нужен):
# ```bash
# export SPUTNIK_REPO=~/Sputnik-Mart
# uv run --project "$SPUTNIK_REPO" python seminar_06.py
# ```

# %%
from __future__ import annotations

import json
import os
import random
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from transform.gold_sentiment import NEGATIVE_WORDS, POSITIVE_WORDS, score_text

SEED = int(os.getenv("SEED", "42"))
N_REVIEWS = int(os.getenv("N_REVIEWS", "100"))
ACTIVE_BUDGET = int(os.getenv("ACTIVE_BUDGET", "15"))
N_TRAIN = int(os.getenv("N_TRAIN", "60"))
N_TEST = int(os.getenv("N_TEST", "40"))
KAPPA_N = int(os.getenv("KAPPA_N", "40"))
KAPPA_FLIPS_A = int(os.getenv("KAPPA_FLIPS_A", "6"))
KAPPA_FLIPS_B = int(os.getenv("KAPPA_FLIPS_B", "7"))
CONFLICT_N = int(os.getenv("CONFLICT_N", "40"))
CONFLICT_FLIPS = int(os.getenv("CONFLICT_FLIPS", "16"))

EXPORT_DT = os.getenv("EXPORT_DT", "2026-10-01")
LABELS_OUT = Path(os.getenv("LABELS_OUT", "./_out/labels"))
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "sputnik")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "sputnik123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lake")

CLASSES: tuple[str, ...] = ("positive", "negative", "neutral")
DATASETS: tuple[str, ...] = (
    "ds_weather-stations",
    "ds_air-quality",
    "ds_energy-consumption",
    "ds_traffic-flow",
    "ds_retail-sales",
)
START_DAY = date(2026, 9, 1)
SENTIMENT_THRESHOLD = 0.1
LEXICON_THRESHOLD = 0.15
STOPWORDS: frozenset[str] = frozenset(
    {"и", "в", "на", "с", "за", "по", "но", "что", "это", "как", "для", "от", "до", "из", "у", "же", "ли"}
)
TOKEN_RE = re.compile(r"[а-яёa-z]+")


# %% [markdown]
# ## 1. Корпус отзывов
#
# 100 различных русских отзывов: 30 положительных, 30 отрицательных,
# 30 нейтральных и 10 намеренно трудных — они стоят в конце (индексы 90–99),
# поэтому всегда попадают в тестовую часть. Базовые 85 отзывов (30/30/25)
# перемешиваются детерминированно (`random.Random(SEED)`), пять нейтральных
# из стартовой очереди ставятся в начало.
#
# Первые пять отзывов — нейтральные без единого попадания в лексикон
# («Скачал, посмотрю позже.»). Это стартовая очередь активного обучения:
# модель по ним ничего не знает, значит спрашивать надо именно их.
#
# Трюки размечены так, как решил бы человек, а не лексикон:
# - «Не понравилось…», «Не рекомендую…» — negative: лексикон видит основы
#   «нрав»/«рекоменд» и ставит positive;
# - «Данные хорошие, но половина пропусков» — negative: пропуски блокируют
#   работу, похвала их не компенсирует;
# - «Данные точные, но половина полей пустая» — negative;
# - сарказм «Отличная работа, снова всё сломалось» — negative;
# - «Ошибок нет, всё отлично» — positive, но это ловушка для рассказа:
#   основа «ошибк» не входит в «ошибок», поэтому лексикон видит только
#   «отличн» и угадывает ответ, а не понимает его.
#
# В элементах корпуса **нет поля `label`**: корпус — это вход для разметки.
# Истинные метки лежат отдельно в `SIM_LABELS` — это **оракул симуляции**,
# а не разметка людей. Он нужен проверкам и роли «второго аннотатора»;
# в реальном проекте метки приходят от людей через Label Studio.

# %%
QUEUE_TEXTS: list[str] = [
    "Скачал, посмотрю позже.",
    "Информация за сентябрь, три файла.",
    "Датасет весит два гигабайта.",
    "Описание полей на русском языке.",
    "Выгрузка в CSV и Parquet.",
]

POSITIVE_TEXTS: list[str] = [
    "Отлично, набор данных работает.",
    "Очень полезно, рекомендую.",
    "Данные точные и качественные.",
    "Удобно, быстро разобрался.",
    "Отлично, всё понравилось.",
    "Хорошо, качественные данные.",
    "Быстро, данные актуальные.",
    "Полезно, рекомендую коллегам.",
    "Отлично, ошибок не нашёл.",
    "Спасибо, очень удобно.",
    "Доволен, всё быстро.",
    "Понятная документация, хорошие примеры.",
    "Качественные данные, рекомендую.",
    "Удобно, есть готовые примеры.",
    "Отлично, понятная структура.",
    "Полезно, буду брать ещё.",
    "Спасибо, всё понравилось.",
    "Отлично, хорошие примеры.",
    "Быстро, всё работает.",
    "Актуальные данные, удобно.",
    "Отлично, всё понятно.",
    "Качественные данные, спасибо.",
    "Данные хорошие, ошибок не нашёл.",
    "Удобно, всё работает.",
    "Полезно, спасибо.",
    "Отлично, подходит для демо.",
    "Хорошо, что есть описание.",
    "Всё работает, я доволен.",
    "Быстро скачал, данные точные.",
    "Рекомендую, отлично.",
]

NEGATIVE_TEXTS: list[str] = [
    "Ужасно, ошибки в данных.",
    "Данные грязные, постоянно врут.",
    "Медленно, выгрузка занимает часы.",
    "Плохо, ничего не понятно.",
    "Дорого, качество плохо.",
    "Сложно разобраться, всё запутано.",
    "Половина полей пустая.",
    "Не советую, много пропусков.",
    "Не понравилось, данные грязные.",
    "Половина строк пустая, сложно работать.",
    "Баги, поддержка не отвечает.",
    "Дорого, а качество плохо.",
    "Медленно, загрузка занимает часы.",
    "Ошибки в данных, всё перепроверяю.",
    "Неудобно, сложно.",
    "Плохо, не буду пользоваться.",
    "Половина данных пустая.",
    "Много пропусков, грязные данные.",
    "Ужасно, медленно и дорого.",
    "Много пропусков, плохо.",
    "Ошибки, сломалось после обновления.",
    "Сложно, ничего не понятно.",
    "Дорого, не буду пользоваться.",
    "Ошибки, грязные данные.",
    "Медленно, поддержка молчит.",
    "Плохо, не советую.",
    "Сломалось после обновления, врут.",
    "Данные грязные, много пропусков.",
    "Ужасно, ждал часы.",
    "Сломалось, не буду пользоваться.",
]

NEUTRAL_TEXTS: list[str] = [
    "Удобно, но дорого.",
    "Полезно, но медленно.",
    "Быстро, но ошибки.",
    "Хорошо, но сложно.",
    "Отлично, но дорого.",
    "Плохо, но быстро.",
    "Медленно, но качественные данные.",
    "Дорого, но работает.",
    "Сложно, но полезно.",
    "Грязные данные, но удобно.",
    "Ошибки, но рекомендую.",
    "Пропусков немного, но рекомендую.",
    "Неудобно, но актуальные данные.",
    "Сломалось, но работает.",
    "Датасет как датасет, рядовой.",
    "Цена средняя, набор обычный.",
    "Есть описание полей.",
    "Три файла, два справочника.",
    "Обновление раз в сутки.",
    "Формат CSV и Parquet.",
    "Вес архива два гигабайта.",
    "Выгрузка за сентябрь, три файла.",
    "Описание полей на русском.",
    "Справочник полей и два файла.",
    "Датасет обновляется по средам.",
]

TRICKS: list[tuple[str, str]] = [
    ("Не понравилось: данные грязные.", "negative"),
    ("Не рекомендую, много пропусков.", "negative"),
    ("Ошибок нет, всё отлично.", "positive"),
    ("Данные хорошие, но половина пропусков.", "negative"),
    ("Отличная работа, снова всё сломалось.", "negative"),
    ("Полезный набор, но выгрузка занимает часы.", "negative"),
    ("Данные точные, но половина полей пустая.", "negative"),
    ("Качество среднее, набор рядовой.", "neutral"),
    ("Не плохо, но и не хорошо.", "neutral"),
    ("Спасибо, но больше не буду пользоваться.", "negative"),
]


def lexicon_hits(text: str) -> int:
    """Сколько основ лексикона встретилось в тексте (каждая — один раз)."""
    low = text.lower()
    return sum(1 for stem in (POSITIVE_WORDS | NEGATIVE_WORDS) if stem in low)


def _validate_text_bank() -> None:
    """Проверить размеры и уникальность банка текстов."""
    counts = {
        "positive": len(POSITIVE_TEXTS),
        "negative": len(NEGATIVE_TEXTS),
        "neutral": len(NEUTRAL_TEXTS) + len(QUEUE_TEXTS),
        "tricks": len(TRICKS),
    }
    expected = {"positive": 30, "negative": 30, "neutral": 30, "tricks": 10}
    if counts != expected:
        raise ValueError(f"банк текстов неполный: {counts}, ожидалось {expected}")
    overlapping = set(QUEUE_TEXTS) & set(NEUTRAL_TEXTS)
    if overlapping:
        raise ValueError(f"очередь пересекается с нейтральными: {sorted(overlapping)[:2]}")
    texts = [*POSITIVE_TEXTS, *NEGATIVE_TEXTS, *QUEUE_TEXTS, *NEUTRAL_TEXTS, *(text for text, _ in TRICKS)]
    if len(set(texts)) != len(texts):
        raise ValueError("в банке есть повторяющиеся тексты")
    if any(lexicon_hits(text) for text in QUEUE_TEXTS):
        raise ValueError("стартовая очередь должна быть без попаданий лексикона")


def _ordered_pairs(seed: int = SEED) -> list[tuple[str, str]]:
    """Детерминированный порядок (текст, метка оракула): очередь, микс, трюки."""
    _validate_text_bank()
    base = [(text, "positive") for text in POSITIVE_TEXTS]
    base += [(text, "negative") for text in NEGATIVE_TEXTS]
    base += [(text, "neutral") for text in NEUTRAL_TEXTS]
    random.Random(seed).shuffle(base)
    queue = [(text, "neutral") for text in QUEUE_TEXTS]
    return [*queue, *base, *TRICKS]


def build_corpus(n: int = N_REVIEWS, seed: int = SEED) -> list[dict[str, Any]]:
    """Собрать корпус из `n` отзывов без меток (метки — в SIM_LABELS)."""
    pairs = _ordered_pairs(seed)
    if n <= 0 or n > len(pairs):
        raise ValueError(f"n={n} вне диапазона 1..{len(pairs)}")
    items: list[dict[str, Any]] = []
    for index, (text, label) in enumerate(pairs[:n]):
        day = START_DAY + timedelta(days=index % 30)
        moment = datetime(day.year, day.month, day.day, 9 + index % 9, (index * 7) % 60, tzinfo=UTC)
        if label == "positive":
            rating = 4 + index % 2
        elif label == "negative":
            rating = 1 + index % 2
        else:
            rating = 3
        items.append(
            {
                "reviewId": f"rv_{index + 1:04d}",
                "datasetId": DATASETS[index % len(DATASETS)],
                "text": text,
                "rating": rating,
                "createdAt": moment.isoformat(),
            }
        )
    return items


# Оракул симуляции: истинные метки для seed=42, n=100.
# В реальном проекте этих меток не существует — их дают аннотаторы.
SIM_LABELS: dict[str, str] = {
    f"rv_{index + 1:04d}": label for index, (_, label) in enumerate(_ordered_pairs(SEED))
}

# %%
print(
    f"банк текстов: positive={len(POSITIVE_TEXTS)}, negative={len(NEGATIVE_TEXTS)}, "
    f"neutral={len(QUEUE_TEXTS) + len(NEUTRAL_TEXTS)}, tricks={len(TRICKS)}"
)
print(f"стартовая очередь без попаданий лексикона: {all(lexicon_hits(text) == 0 for text in QUEUE_TEXTS)}")
print("первые три отзыва:", json.dumps(build_corpus()[:3], ensure_ascii=False))


# %% [markdown]
# ## 2. Задание 6.1 — проект разметки в формате Label Studio
#
# Label Studio описывает интерфейс разметки XML-конфигом: `<Text>` показывает
# поле задачи, `<Choices>` даёт кнопки классов, `toName` связывает выбор с
# текстом, `choice="single"` запрещает несколько меток.
#
# Соберите `build_labeling_project`: словарь с `title`, `label_config` и
# `tasks`. В каждой задаче — `id` (1..100), `data.text`, `data.review_id`,
# `data.dataset_id`. Формат совпадает с телом `POST /api/projects` в
# настоящем Label Studio: backlog SRV-15 поднимает сам LS, SRV-16 добавляет
# отправку. Сейчас мы проверяем payload локально.

# %%
LABEL_CONFIG = """<View>
  <Text name="text" value="$text"/>
  <Choices name="sentiment" toName="text" choice="single">
    <Choice value="positive"/>
    <Choice value="negative"/>
    <Choice value="neutral"/>
  </Choices>
</View>"""


# %%
# TASK 6.1 — проект разметки
def build_labeling_project(corpus: list[dict[str, Any]]) -> dict[str, Any]:
    """LS-совместимый проект: title, label_config и tasks без меток."""
    # TODO (6.1): соберите LS-совместимый проект разметки.
    # Подсказки:
    # - title — любая осмысленная строка, label_config — LABEL_CONFIG;
    # - tasks: id = индекс + 1, в data положите text/review_id/dataset_id;
    # - меток в задачах быть не должно: их ставит аннотатор.
    raise NotImplementedError("Задание 6.1: реализуйте build_labeling_project")


# %% [markdown]
# ## 3. Задание 6.2 — активное обучение
#
# Размечать 100 отзывов дорого. `preannotate` прогоняет лексикон репозитория
# и для каждого отзыва сохраняет `score`, число попаданий `hits` и
# предсказание по порогам `±0.1`.
#
# Соберите `select_for_labeling`: неуверенность
# `uncertainty = 1 − min(1, |score|)`, плюс `1.0`, если `hits == 0`
# (модель не знает ни одного слова). Сортировка — по
# `(−uncertainty, review_id)`, вернуть ровно `budget` идентификаторов.
# Ровно поэтому в очередь попадают пять стартовых нейтральных отзывов:
# у них `score=0` и `hits=0`.
#
# `MANUAL_SEED` — то, что «человек» уже разметил руками. В полном решении значения
# заполнены; в студенческой версии — пустые строки.

# %%
def preannotate(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Предразметка лексиконом: score, hits и класс по порогам ±0.1."""
    rows: list[dict[str, Any]] = []
    for item in corpus:
        score = float(score_text(item["text"]))
        hits = lexicon_hits(item["text"])
        if score > SENTIMENT_THRESHOLD:
            predicted = "positive"
        elif score < -SENTIMENT_THRESHOLD:
            predicted = "negative"
        else:
            predicted = "neutral"
        rows.append(
            {
                "review_id": item["reviewId"],
                "score": round(score, 6),
                "hits": hits,
                "predicted": predicted,
            }
        )
    return rows


# TODO (6.2): впишите метки, которые «человек» поставил первым пяти отзывам.
# Допустимые значения: positive, negative, neutral.
MANUAL_SEED: dict[str, str] = {
    "rv_0001": "",
    "rv_0002": "",
    "rv_0003": "",
    "rv_0004": "",
    "rv_0005": "",
}


# %%
# TASK 6.2 — очередь активного обучения
def select_for_labeling(
    preannotations: list[dict[str, Any]], budget: int = ACTIVE_BUDGET
) -> list[str]:
    """Выбрать `budget` самых неуверенных отзывов (нулевые hits — первыми)."""
    # TODO (6.2): выберите budget самых неуверенных отзывов.
    # Подсказки:
    # - uncertainty = 1 - min(1, abs(score)), плюс 1.0, если hits == 0;
    # - сортировка по (-uncertainty, review_id) — детерминированная;
    # - верните ровно budget идентификаторов, без дублей.
    raise NotImplementedError("Задание 6.2: реализуйте select_for_labeling")


# %% [markdown]
# ## 4. Задание 6.3 — согласие аннотаторов: Cohen's kappa
#
# Доля совпадений врёт: если 90% корпуса — `neutral`, два аннотатора получат
# высокий процент, ничего не понимая. Cohen's kappa вычитает случайное
# согласие:
#
# `κ = (p_o − p_e) / (1 − p_e)`, где `p_o` — доля совпадений, а
# `p_e = Σ p_a(c)·p_b(c)` — вероятность совпасть случайно при данных
# распределениях меток.
#
# Шкала Landis & Koch: ≥0.8 «почти полное», 0.6–0.8 «существенное»,
# 0.4–0.6 «умеренное», 0.2–0.4 «слабое», <0.2 «ничтожное».
#
# `build_kappa_fixture` делает двух «аннотаторов» из оракула: A — истина с
# 6 детерминированными флипами, B — A ещё с 7 флипами (в следующую метку
# цикла). Индексы флипов не пересекаются, поэтому согласие ровно 33/40.
# Соберите `agreement_report`.

# %%
def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa по матрице ошибок (без sklearn)."""
    if len(a) != len(b):
        raise ValueError(f"длины не совпадают: {len(a)} и {len(b)}")
    n = len(a)
    if n == 0:
        raise ValueError("пустые списки меток")

    labels = sorted(set(a) | set(b))
    matrix: dict[str, dict[str, int]] = {
        left: dict.fromkeys(labels, 0) for left in labels
    }
    for left, right in zip(a, b, strict=True):
        matrix[left][right] += 1

    observed = sum(matrix[label][label] for label in labels) / n
    row = {label: sum(matrix[label].values()) / n for label in labels}
    column = {label: sum(matrix[other][label] for other in labels) / n for label in labels}
    expected = sum(row[label] * column[label] for label in labels)
    if 1.0 - expected < 1e-12:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def interpret_kappa(kappa: float) -> str:
    """Словесная интерпретация kappa по Landis & Koch."""
    if kappa >= 0.8:
        return "почти полное"
    if kappa >= 0.6:
        return "существенное"
    if kappa >= 0.4:
        return "умеренное"
    if kappa >= 0.2:
        return "слабое"
    return "ничтожное"


def _next_label(label: str) -> str:
    """Следующая метка в фиксированном цикле positive → negative → neutral."""
    cycle = {name: CLASSES[(index + 1) % len(CLASSES)] for index, name in enumerate(CLASSES)}
    if label not in cycle:
        raise ValueError(f"неизвестная метка {label!r}")
    return cycle[label]


def _flip_indices(n: int, count: int, forbidden: set[int], salt: int) -> list[int]:
    """Детерминированно выбрать `count` индексов, не заходя в `forbidden`."""
    if count < 0:
        raise ValueError(f"count должен быть >= 0, получено {count}")
    if count > n - len(forbidden):
        raise ValueError(f"нельзя флипнуть {count} из {n} при {len(forbidden)} занятых")
    candidates = [index for index in range(n) if index not in forbidden]
    random.Random(SEED + salt).shuffle(candidates)
    return sorted(candidates[:count])


def build_kappa_fixture(
    corpus: list[dict[str, Any]],
    n: int = KAPPA_N,
    flips_a: int = KAPPA_FLIPS_A,
    flips_b: int = KAPPA_FLIPS_B,
) -> tuple[list[str], list[str]]:
    """Два «аннотатора»: истина с 6 флипами и она же ещё с 7 другими."""
    if n <= 0 or n > len(corpus):
        raise ValueError(f"n={n} вне диапазона 1..{len(corpus)}")
    truth: list[str] = []
    for item in corpus[:n]:
        label = SIM_LABELS.get(item["reviewId"])
        if label is None:
            raise ValueError(f"нет метки оракула для {item['reviewId']}")
        truth.append(label)

    indices_a = _flip_indices(n, flips_a, set(), salt=1)
    first = list(truth)
    for index in indices_a:
        first[index] = _next_label(truth[index])

    indices_b = _flip_indices(n, flips_b, set(indices_a), salt=2)
    second = list(first)
    for index in indices_b:
        second[index] = _next_label(first[index])
    return first, second


# %%
# TASK 6.3 — отчёт о согласии
def agreement_report(a: list[str], b: list[str]) -> dict[str, Any]:
    """Согласие, kappa, интерпретация и список расхождений."""
    # TODO (6.3): соберите отчёт о согласии аннотаторов.
    # Подсказки:
    # - disagreements — список {index, a, b} только там, где метки разные;
    # - agreement = 1 - len(disagreements) / n;
    # - kappa считайте через cohen_kappa, слова — через interpret_kappa.
    raise NotImplementedError("Задание 6.3: реализуйте agreement_report")


# %% [markdown]
# ## 5. Задание 6.4 — экспорт аннотаций в озеро
#
# Разметка должна уехать туда, откуда её прочитает пайплайн. `build_export`
# собирает JSON в формате экспорта Label Studio: на каждый отзыв — `id`,
# `annotations[].completed_by`, `result[]` с
# `from_name="sentiment"`, `to_name="text"`, `type="choices"` и
# `value.choices=[label]`. Именно этот формат ждут `label-studio-converter`
# и downstream-скрипты; свой самодельный JSON пришлось бы переучивать.
#
# Соберите `export_annotations`: проверьте каждую метку (только три класса),
# соберите payload и положите его в MinIO по ключу
# `lake/labels/reviews/{dt}/annotations.json` (boto3, endpoint
# `localhost:9000`, ключи из env, `connect_timeout=2`, одна повторная
# попытка). Если MinIO недоступен — локальный fallback в `LABELS_OUT`
# (по умолчанию `./_out/labels/{dt}/annotations.json`) и
# `stored: "local"`. Верните `{count, schema_ok, stored, key}`.
#
# > MinIO может быть не поднят — это штатная ситуация, fallback не ошибка.
# > Настоящая отправка в LS (а не только JSON-файл) — backlog SRV-16.

# %%
def build_export(corpus: list[dict[str, Any]], labels: dict[str, str]) -> list[dict[str, Any]]:
    """Собрать экспорт LS: по одному объекту на отзыв, ровно один result."""
    missing = [item["reviewId"] for item in corpus if item["reviewId"] not in labels]
    if missing:
        raise ValueError(f"нет меток для {len(missing)} отзывов, например {missing[:3]}")
    payload: list[dict[str, Any]] = []
    for index, item in enumerate(corpus):
        payload.append(
            {
                "id": index + 1,
                "annotations": [
                    {
                        "completed_by": 1,
                        "result": [
                            {
                                "from_name": "sentiment",
                                "to_name": "text",
                                "type": "choices",
                                "value": {"choices": [labels[item["reviewId"]]]},
                            }
                        ],
                    }
                ],
            }
        )
    return payload


def _schema_ok(payload: list[dict[str, Any]]) -> bool:
    """Проверить, что каждая аннотация — ровно один допустимый выбор."""
    for item in payload:
        annotations = item.get("annotations") or []
        if len(annotations) != 1:
            return False
        results = annotations[0].get("result") or []
        if len(results) != 1:
            return False
        result = results[0]
        if result.get("from_name") != "sentiment" or result.get("to_name") != "text":
            return False
        if result.get("type") != "choices":
            return False
        choices = (result.get("value") or {}).get("choices") or []
        if len(choices) != 1 or choices[0] not in CLASSES:
            return False
    return True


def _upload_to_minio(object_key: str, body: bytes) -> bool:
    """Положить объект в MinIO; False, если сервис/пакет недоступен."""
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError
    except ModuleNotFoundError:
        return False

    try:
        client = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            region_name="us-east-1",
            config=Config(
                connect_timeout=2,
                read_timeout=2,
                retries={"max_attempts": 2},
            ),
        )
        client.put_object(
            Bucket=MINIO_BUCKET,
            Key=object_key,
            Body=body,
            ContentType="application/json",
        )
    except (BotoCoreError, ClientError, OSError):
        return False
    return True


# %%
# TASK 6.4 — экспорт аннотаций
def export_annotations(
    corpus: list[dict[str, Any]], labels: dict[str, str], dt: str
) -> dict[str, Any]:
    """Проверить метки и сохранить LS-экспорт в MinIO или локально."""
    # TODO (6.4): проверьте метки и сохраните LS-экспорт.
    # Подсказки:
    # - допустимые метки — CLASSES, метка нужна для каждого reviewId;
    # - payload собирает build_export, схему проверяет _schema_ok;
    # - сначала попробуйте MinIO (_upload_to_minio), при неудаче пишите в
    #   LABELS_OUT / dt / "annotations.json" и верните stored="local";
    # - верните {count, schema_ok, stored, key}.
    raise NotImplementedError("Задание 6.4: реализуйте export_annotations")


# %% [markdown]
# ## 6. Задание 6.5 — как разметка превращается в признаки
#
# Это мини-цикл «разметка → признаки», а не продакшен-модель. На первых
# 60 отзывах (train) учим лексикон: для каждого токена считаем, сколько раз
# он встретился в positive и negative, вес `(pos − neg) / (pos + neg)`,
# оставляем токены с `total ≥ 2` и `|weight| ≥ 0.5`. Нейтральные отзывы в
# счёт не идут: у них нет полюса.
#
# Специально **не выбрасываем «не»**: отрицание — сигнал. Стоп-лист
# крошечный (предлоги/союзы), иначе можно выкинуть как раз «не».
# `score_with_lexicon` — среднее весов известных токенов, порог `±0.15`.
#
# Соберите `evaluate_labeling_impact`: baseline — фиксированный `score_text`,
# learned — лексикон, обученный на train. Тест — последние 40 отзывов,
# трюки (индексы 90–99) гарантированно в тесте. Метрика честная: тестовые
# метки не участвуют в обучении.
#
# > Утечка была бы, если бы мы учили лексикон на всех 100 отзывах и потом
# > мерили на тех же 100. Здесь train/test фиксированы по порядку корпуса.
# >
# > Метрика не различает «понял» и «повезло»: на «Ошибок нет, всё отлично»
# > оба лексикона правы, но по разным причинам. Поэтому в дебрифинге важно
# > смотреть не только на accuracy, но и на errors_after.

# %%
def tokenize(text: str) -> list[str]:
    """Токены текста: строчная кириллица/латиница, без пунктуации."""
    return TOKEN_RE.findall(text.lower())


def learn_lexicon(
    corpus: list[dict[str, Any]], labels: dict[str, str], min_count: int = 2
) -> dict[str, float]:
    """Выучить веса токенов по меткам positive/negative."""
    if min_count <= 0:
        raise ValueError(f"min_count должен быть > 0, получено {min_count}")
    counts: dict[str, list[int]] = {}
    for item in corpus:
        label = labels.get(item["reviewId"])
        if label is None:
            raise ValueError(f"нет метки для {item['reviewId']}")
        if label not in ("positive", "negative"):
            continue
        for token in tokenize(item["text"]):
            if token in STOPWORDS:
                continue
            bucket = counts.setdefault(token, [0, 0])
            bucket[0 if label == "positive" else 1] += 1

    lexicon: dict[str, float] = {}
    for token, (positive, negative) in counts.items():
        total = positive + negative
        if total < min_count:
            continue
        weight = (positive - negative) / total
        if abs(weight) >= 0.5:
            lexicon[token] = weight
    return lexicon


def score_with_lexicon(text: str, lexicon: dict[str, float]) -> float:
    """Средний вес известных токенов; 0, если известных нет."""
    weights = [lexicon[token] for token in tokenize(text) if token in lexicon]
    if not weights:
        return 0.0
    return sum(weights) / len(weights)


def _predict(score: float, threshold: float) -> str:
    """Класс по симметричному порогу."""
    if score > threshold:
        return "positive"
    if score < -threshold:
        return "negative"
    return "neutral"


# %%
# TASK 6.5 — влияние разметки на качество
def evaluate_labeling_impact(
    corpus: list[dict[str, Any]], labels: dict[str, str]
) -> dict[str, Any]:
    """Сравнить фиксированный лексикон и лексикон, обученный на разметке."""
    # TODO (6.5): сравните фиксированный и обученный лексикон.
    # Подсказки:
    # - train = corpus[:N_TRAIN], test = corpus[N_TRAIN:N_TRAIN + N_TEST];
    # - baseline — _predict(score_text(text), SENTIMENT_THRESHOLD);
    # - learned — learn_lexicon(train, labels) и score_with_lexicon;
    # - верните accuracy, delta, learned_words и errors_after.
    raise NotImplementedError("Задание 6.5: реализуйте evaluate_labeling_impact")


# %% [markdown]
# ## 7. Эксперимент — разногласие 40%
#
# Вторая пара аннотаторов: A — истина, B — та же истина с 16 флипами
# (каждый второй индекс). Согласие 24/40 = 0.6, disagreement 0.4.
# Соберите `analyze_conflicts`: disagreement, kappa, разбивка по классам
# (`a`, `b`, `disagreements`) и три примера спора.
#
# В `per_class` одно расхождение учитывается у обоих классов: если A сказал
# positive, а B — negative, оно попадёт и в positive, и в negative. Так видно,
# какой класс «перетягивает» спор.
#
# 40% — это не «плохие аннотаторы», а сигнал: инструкция неоднозначна или
# классы пересекаются. Дальше — арбитраж, уточнение инструкции, переобучение
# аннотаторов и, возможно, отдельный класс «неуверен».

# %%
def build_conflict_fixture(
    corpus: list[dict[str, Any]], n: int = CONFLICT_N, flips: int = CONFLICT_FLIPS
) -> tuple[list[str], list[str]]:
    """A — истина, B — она же с `flips` флипами по чётным индексам."""
    if n <= 0 or n > len(corpus):
        raise ValueError(f"n={n} вне диапазона 1..{len(corpus)}")
    truth: list[str] = []
    for item in corpus[:n]:
        label = SIM_LABELS.get(item["reviewId"])
        if label is None:
            raise ValueError(f"нет метки оракула для {item['reviewId']}")
        truth.append(label)

    targets = [index for index in range(n) if index % 2 == 0][:flips]
    if len(targets) < flips:
        raise ValueError(f"не хватает чётных индексов: нужно {flips}, есть {len(targets)}")
    second = list(truth)
    for index in targets:
        second[index] = _next_label(truth[index])
    return truth, second


# %%
# TASK — эксперимент с конфликтами
def analyze_conflicts(
    a: list[str], b: list[str], corpus: list[dict[str, Any]]
) -> dict[str, Any]:
    """Доля разногласий, kappa, разбивка по классам и три примера."""
    # TODO (эксперимент): посчитайте конфликты аннотаторов.
    # Подсказки:
    # - disagreement — доля индексов, где a[i] != b[i];
    # - kappa — cohen_kappa(a, b);
    # - per_class: для каждого класса a, b и число disagreements;
    # - examples — первые три расхождения с review_id, text, a, b.
    raise NotImplementedError("Эксперимент: реализуйте analyze_conflicts")


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
CORPUS: list[dict[str, Any]] = []
PROJECT: dict[str, Any] | None = None
PREANNOTATIONS: list[dict[str, Any]] = []
QUEUE: list[str] = []
KAPPA_A: list[str] = []
KAPPA_B: list[str] = []
KAPPA_REPORT: dict[str, Any] | None = None
EXPORT_PAYLOAD: list[dict[str, Any]] = []
EXPORT_RESULT: dict[str, Any] | None = None
IMPACT: dict[str, Any] | None = None
CONFLICT_A: list[str] = []
CONFLICT_B: list[str] = []
CONFLICT_REPORT: dict[str, Any] | None = None

# %%
try:
    CORPUS = build_corpus()
    print(f"корпус: {len(CORPUS)} отзывов, датасетов: {len({item['datasetId'] for item in CORPUS})}")
    print(
        "оракул (симуляция): "
        + ", ".join(f"{label}={sum(1 for value in SIM_LABELS.values() if value == label)}" for label in CLASSES)
    )
    print(f"очередь-затравка без попаданий лексикона: "
          f"{sum(1 for item in CORPUS[:5] if lexicon_hits(item['text']) == 0)}/5")
except Exception as error:
    print(f"Не удалось собрать корпус: {error}")

# %%
try:
    PROJECT = build_labeling_project(CORPUS)
    print(f"проект: {PROJECT['title']}, задач: {len(PROJECT['tasks'])}")
    print("первая задача:", json.dumps(PROJECT["tasks"][0], ensure_ascii=False))
except NotImplementedError as error:
    print(f"Задание 6.1 не выполнено: {error}")
except Exception as error:
    print(f"Задание 6.1 не удалось: {error}")

# %%
try:
    PREANNOTATIONS = preannotate(CORPUS)
    QUEUE = select_for_labeling(PREANNOTATIONS)
    selected = set(QUEUE)
    zero_hit = sum(1 for row in PREANNOTATIONS if row["review_id"] in selected and row["hits"] == 0)
    filled = sum(1 for value in MANUAL_SEED.values() if value in CLASSES)
    print(
        f"очередь: {len(QUEUE)} из {len(PREANNOTATIONS)} "
        f"({len(QUEUE) / max(1, len(PREANNOTATIONS)):.0%}), без попаданий лексикона: {zero_hit}"
    )
    print(f"  первые 5: {', '.join(QUEUE[:5])}")
    print(f"  ручная разметка: {filled}/{len(MANUAL_SEED)}")
except NotImplementedError as error:
    print(f"Задание 6.2 не выполнено: {error}")
except Exception as error:
    print(f"Задание 6.2 не удалось: {error}")

# %%
try:
    KAPPA_A, KAPPA_B = build_kappa_fixture(CORPUS)
    KAPPA_REPORT = agreement_report(KAPPA_A, KAPPA_B)
    print(
        f"kappa: agreement={KAPPA_REPORT['agreement']:.4f}, "
        f"kappa={KAPPA_REPORT['kappa']:.4f} ({KAPPA_REPORT['interpretation']}), "
        f"расхождений={len(KAPPA_REPORT['disagreements'])}"
    )
except NotImplementedError as error:
    print(f"Задание 6.3 не выполнено: {error}")
except Exception as error:
    print(f"Задание 6.3 не удалось: {error}")

# %%
try:
    EXPORT_PAYLOAD = build_export(CORPUS, SIM_LABELS)
    EXPORT_RESULT = export_annotations(CORPUS, SIM_LABELS, EXPORT_DT)
    print(
        f"экспорт: count={EXPORT_RESULT['count']}, schema_ok={EXPORT_RESULT['schema_ok']}, "
        f"stored={EXPORT_RESULT['stored']}"
    )
    print(f"  key={EXPORT_RESULT['key']}")
    if EXPORT_RESULT["stored"] == "local":
        print(f"  файл: {LABELS_OUT / EXPORT_DT / 'annotations.json'}")
except NotImplementedError as error:
    print(f"Задание 6.4 не выполнено: {error}")
except Exception as error:
    print(f"Задание 6.4 не удалось: {error}")

# %%
try:
    IMPACT = evaluate_labeling_impact(CORPUS, SIM_LABELS)
    print(
        f"влияние разметки: baseline={IMPACT['baseline_accuracy']:.4f}, "
        f"learned={IMPACT['learned_accuracy']:.4f}, delta={IMPACT['delta']:+.4f}"
    )
    print(
        f"  train={IMPACT['n_train']}, test={IMPACT['n_test']}, "
        f"слов в лексиконе={IMPACT['learned_words']}, ошибок после={len(IMPACT['errors_after'])}"
    )
    for item in IMPACT["errors_after"][:3]:
        print(f"  {item['review_id']}: {item['expected']} → {item['predicted']} | {item['text']}")
except NotImplementedError as error:
    print(f"Задание 6.5 не выполнено: {error}")
except Exception as error:
    print(f"Задание 6.5 не удалось: {error}")

# %%
try:
    CONFLICT_A, CONFLICT_B = build_conflict_fixture(CORPUS)
    CONFLICT_REPORT = analyze_conflicts(CONFLICT_A, CONFLICT_B, CORPUS)
    print(
        f"конфликты: disagreement={CONFLICT_REPORT['disagreement']:.4f}, "
        f"kappa={CONFLICT_REPORT['kappa']:.4f}"
    )
    print("  по классам:", json.dumps(CONFLICT_REPORT["per_class"], ensure_ascii=False))
    for item in CONFLICT_REPORT["examples"]:
        print(f"  {item['review_id']}: A={item['a']}, B={item['b']} | {item['text']}")
except NotImplementedError as error:
    print(f"Эксперимент не выполнен: {error}")
except Exception as error:
    print(f"Эксперимент не удался: {error}")


# %% [markdown]
# ## 10. Проверки

# %%
def check_project(project: dict[str, Any]) -> None:
    """6.1: 100 задач, уникальные id, непустые тексты, 3 выбора в конфиге."""
    tasks = project["tasks"]
    assert len(tasks) == 100, f"задач {len(tasks)}, ожидалось 100"
    ids = [task["id"] for task in tasks]
    assert len(set(ids)) == 100, "id задач не уникальны"
    assert sorted(ids) == list(range(1, 101)), "id должны быть 1..100"
    for task in tasks:
        data = task["data"]
        assert str(data.get("text", "")).strip(), f"пустой текст в задаче {task['id']}"
        assert data.get("review_id") and data.get("dataset_id"), f"нет data.* в задаче {task['id']}"

    config = project["label_config"]
    assert 'name="sentiment"' in config, "в конфиге нет Choices name=sentiment"
    assert 'toName="text"' in config, "Choices не привязан к text"
    assert config.count("<Choice ") == 3, f"выборов {config.count('<Choice ')}, ожидалось 3"
    assert "$text" in config, "Text не читает $text"


def check_active(queue: list[str], preannotations: list[dict[str, Any]]) -> None:
    """6.2: 5 ручных меток, 15 уникальных задач, 15%, >=5 без попаданий."""
    assert len(MANUAL_SEED) == 5, f"в MANUAL_SEED {len(MANUAL_SEED)} ключей, ожидалось 5"
    assert all(value in CLASSES for value in MANUAL_SEED.values()), "заполните MANUAL_SEED тремя классами"
    assert len(queue) == ACTIVE_BUDGET, f"в очереди {len(queue)}, ожидалось {ACTIVE_BUDGET}"
    assert len(set(queue)) == len(queue), "в очереди есть дубли"
    known = {row["review_id"] for row in preannotations}
    assert set(queue) <= known, "в очереди есть id вне предразметки"
    assert len(queue) / N_REVIEWS < 0.2, f"бюджет {len(queue)} / {N_REVIEWS} >= 20%"
    selected = set(queue)
    zero_hit = sum(1 for row in preannotations if row["review_id"] in selected and row["hits"] == 0)
    assert zero_hit >= 5, f"в очереди только {zero_hit} отзывов без попаданий, нужно >= 5"


def check_kappa(report: dict[str, Any]) -> None:
    """6.3: n=40, kappa >= 0.6, kappa < agreement, сходятся расхождения."""
    assert report["n"] == KAPPA_N, f"n={report['n']}, ожидалось {KAPPA_N}"
    assert report["kappa"] >= 0.6, f"kappa={report['kappa']:.4f} < 0.6"
    assert report["interpretation"] in {"существенное", "почти полное"}, (
        f"интерпретация {report['interpretation']!r}"
    )
    assert report["kappa"] < report["agreement"], "kappa должна быть меньше agreement"
    expected = KAPPA_N - round(report["agreement"] * KAPPA_N)
    assert len(report["disagreements"]) == expected, (
        f"расхождений {len(report['disagreements'])}, ожидалось {expected}"
    )
    for item in report["disagreements"]:
        assert item["a"] != item["b"], f"расхождение {item['index']} без разницы меток"


def check_export(result: dict[str, Any], payload: list[dict[str, Any]]) -> None:
    """6.4: 100 записей, схема LS, одно допустимое значение на result."""
    assert result["count"] == 100, f"count={result['count']}, ожидалось 100"
    assert result["schema_ok"] is True, "schema_ok=False"
    assert result["stored"] in {"minio", "local"}, f"stored={result['stored']!r}"
    assert result["key"].endswith(f"labels/reviews/{EXPORT_DT}/annotations.json"), "неверный key"
    assert len(payload) == 100, f"в payload {len(payload)} записей"
    for item in payload:
        annotations = item["annotations"]
        assert len(annotations) == 1, f"у задачи {item['id']} не одна аннотация"
        results = annotations[0]["result"]
        assert len(results) == 1, f"у задачи {item['id']} не один result"
        result_item = results[0]
        assert result_item["from_name"] == "sentiment", "from_name не sentiment"
        assert result_item["to_name"] == "text", "to_name не text"
        assert result_item["type"] == "choices", "type не choices"
        choices = result_item["value"]["choices"]
        assert len(choices) == 1 and choices[0] in CLASSES, f"неверный выбор {choices}"


def check_impact(result: dict[str, Any]) -> None:
    """6.5: 60/40, learned не хуже baseline, прирост >= 0.05."""
    assert result["n_train"] == N_TRAIN, f"n_train={result['n_train']}"
    assert result["n_test"] == N_TEST, f"n_test={result['n_test']}"
    assert result["learned_accuracy"] >= result["baseline_accuracy"], (
        f"learned={result['learned_accuracy']:.4f} < baseline={result['baseline_accuracy']:.4f}"
    )
    assert result["delta"] >= 0.05, f"delta={result['delta']:.4f} < 0.05"
    expected_errors = N_TEST - round(result["learned_accuracy"] * N_TEST)
    assert len(result["errors_after"]) == expected_errors, (
        f"ошибок {len(result['errors_after'])}, ожидалось {expected_errors}"
    )


def check_conflicts(report: dict[str, Any], a: list[str], b: list[str]) -> None:
    """Эксперимент: disagreement 0.4, kappa < 0.6, 3 примера с разницей."""
    assert abs(report["disagreement"] - 0.4) < 1e-9, f"disagreement={report['disagreement']}"
    assert report["kappa"] < 0.6, f"kappa={report['kappa']:.4f} >= 0.6"
    present = set(a) | set(b)
    assert present <= set(report["per_class"]), "per_class не покрывает все классы"
    assert len(report["examples"]) == 3, f"примеров {len(report['examples'])}, ожидалось 3"
    for item in report["examples"]:
        assert item["a"] != item["b"], f"пример {item['review_id']} без разногласия"
        assert item["text"].strip(), "пустой текст в примере"


def run_checks() -> None:
    """Прогнать все проверки и напечатать отчёт."""
    checks: list[tuple[str, Any]] = []

    if PROJECT is not None:
        checks.append(("6.1 проект", lambda: check_project(PROJECT)))
    else:
        checks.append(("6.1 проект", lambda: (_ for _ in ()).throw(AssertionError("не выполнен"))))

    if QUEUE:
        checks.append(("6.2 активное обучение", lambda: check_active(QUEUE, PREANNOTATIONS)))
    else:
        checks.append(("6.2 активное обучение", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))

    if KAPPA_REPORT is not None:
        checks.append(("6.3 kappa", lambda: check_kappa(KAPPA_REPORT)))
    else:
        checks.append(("6.3 kappa", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))

    if EXPORT_RESULT is not None and EXPORT_PAYLOAD:
        checks.append(("6.4 экспорт", lambda: check_export(EXPORT_RESULT, EXPORT_PAYLOAD)))
    else:
        checks.append(("6.4 экспорт", lambda: (_ for _ in ()).throw(AssertionError("не выполнен"))))

    if IMPACT is not None:
        checks.append(("6.5 влияние", lambda: check_impact(IMPACT)))
    else:
        checks.append(("6.5 влияние", lambda: (_ for _ in ()).throw(AssertionError("не выполнено"))))

    if CONFLICT_REPORT is not None:
        checks.append(("эксперимент", lambda: check_conflicts(CONFLICT_REPORT, CONFLICT_A, CONFLICT_B)))
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
