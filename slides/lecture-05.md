---
marp: true
theme: default
size: 16:9
paginate: true
math: katex
title: "Лекция 5: Системы разметки и аннотации данных"
author: "Инжиниринг данных (продвинутый уровень)"
footer: "Системы разметки и аннотации данных — Лекция 5"
---

<!--
ОБЩИЕ ЗАМЕТКИ К ПРЕЗЕНТАЦИИ
- Хронометраж: ~95 минут. Введение — 10, Блок 1 (платформы) — 20, Блок 2 (активное обучение) — 20,
  Блок 3 (качество) — 20, Блок 4 (автоматизация) — 15, кейсы + итоги — 10
- Баланс: теория ↔ код. Полные листинги разбираются на семинаре, на слайдах — только суть API
- TikZ-блоки — самодостаточные standalone-документы (\documentclass[tikz]{standalone});
  рендер отдаётся Kroki (endpoint /tikz/{svg|png}, см. https://kroki.io) или локальным LaTeX
- Mermaid в этой колоде НЕ используется: он не рендерится в Marp. Все схемы переведены в TikZ
- Математика рендерится KaTeX (math: katex)
- Блоки `> Ключевое:` — главные выводы, которые нужно проговорить
- Слайды с пометкой «доп.» — материал сверх исходной колоды (расширение темы)
- Числа на иллюстративных графиках — синтетические, для демонстрации формы кривой, не результат эксперимента
-->

<!-- _class: lead -->

# Системы разметки и аннотации данных

**Лекция 5**

Инжиниринг данных (продвинутый уровень)

---

## План лекции

| Блок | Тема | Время |
|:-----|:-----|:------|
| 0 | Зачем нужна разметка и сколько она стоит | ~10 мин |
| 1 | Платформы для разметки | ~20 мин |
| 2 | Активное обучение и weak supervision | ~20 мин |
| 3 | Контроль качества и агрегация меток | ~20 мин |
| 4 | Автоматизация и HITL | ~15 мин |
| 5 | Кейсы, ML-пайплайн, этика | ~10 мин |

**Формат:** теория + код → детальный разбор кода на семинаре

**Сквозная идея:** разметка — это **производственный процесс**, у которого есть стоимость, пропускная способность, качество и версии. Модель — лишь один из его потребителей.

---

## Карта лекции

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, matrix, calc}
\begin{document}
\begin{tikzpicture}[font=\small,
    data/.style={rectangle, rounded corners, draw, minimum height=1.1cm, minimum width=2.5cm, align=center, fill=blue!10},
    block/.style={rectangle, rounded corners, draw, minimum height=1.1cm, minimum width=3.1cm, align=center},
    arr/.style={->, thick}]
    \node[data] (raw) at (0,0) {Сырые\\данные};
    \node[block, fill=orange!25] (p1) at (4.0,0) {Блок 1\\Платформы};
    \node[block, fill=green!20] (p2) at (8.0,0) {Блок 2\\Активное обучение};
    \node[block, fill=cyan!20] (p3) at (12.0,0) {Блок 3\\Контроль качества};
    \node[block, fill=violet!20] (p4) at (16.0,0) {Блок 4\\Автоматизация};

    \node[data, fill=green!15, minimum width=4.2cm] (ds) at (10,-3.2) {Версионируемый датасет\\+ метаданные + метрики качества};
    \node[data, fill=blue!15, minimum width=3.4cm] (ml) at (15.5,-3.2) {Модель ML};
    \node[data, fill=red!12, minimum width=3.4cm] (drift) at (15.5,-5.4) {Дрифт данных\\→ новые примеры};

    \draw[arr] (raw) -- (p1);
    \draw[arr] (p1) -- (p2);
    \draw[arr] (p2) -- (p3);
    \draw[arr] (p3) -- (p4);
    \draw[arr] (p4.south) -- ++(0,-0.7) -| (ds.east);
    \draw[arr] (ds) -- (ml);
    \draw[arr] (ml) -- (drift);
    \draw[arr, dashed] (drift.west) -| (9.2,-5.4) -- (9.2,-4.0) node[pos=0.5, left, align=right, font=\scriptsize] {доразметка\\\& переобучение};
\end{tikzpicture}
\end{document}
```

> Ключевое: разметка — не «одноразовая акция перед обучением», а **замкнутый контур**, который живёт столько же, сколько модель в продакшене.

---

## Цели лекции

После лекции вы сможете:

- **Оценить** стоимость и сроки проекта разметки до его старта
- **Выбрать** платформу и формат задачи под тип данных
- **Спроектировать** цикл активного обучения и посчитать экономию
- **Измерить** качество разметки — согласием, эталонами, моделями
- **Собрать** пайплайн «предразметка → проверка человеком → версия датасета»
- **Аргументировать** решения по этике и оплате труда разметчиков

---

<!-- _class: lead -->

# Блок 0
## Зачем нужна разметка

<!-- ~10 мин -->

---

## Три роли разметки

| Роль | Что даёт | Пример |
|:-----|:---------|:-------|
| **Обучение** | целевая переменная $y$ | классы, боксы, сущности |
| **Оценка** | ground truth для метрик | тест-сет 2–5 тыс. примеров |
| **Спецификация** | формализация требований | «что считается оскорблением» |

- Разметка — это **перевод человеческого суждения в данные**
- Значительная часть «требований» к ML-системе существует только в виде инструкции разметчику
- Датасет — такой же артефакт производства, как код: у него есть автор, версия и дефекты

---

## Типы задач разметки

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, matrix, calc}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    root/.style={rectangle, rounded corners, draw, thick, fill=gray!15, align=center, minimum height=0.9cm, minimum width=3.4cm},
    dom/.style={rectangle, rounded corners, draw, fill=blue!12, align=center, minimum height=0.8cm, minimum width=2.9cm},
    leaf/.style={rectangle, draw, fill=white, align=left, minimum height=0.62cm, text width=3.15cm},
    arr/.style={->, semithick}]
    \node[root] (r) at (7.2,0) {Тип носителя\\→ тип задачи};
    \node[dom] (t) at (1.9,-1.6) {Текст};
    \node[dom] (v) at (5.4,-1.6) {Изображение\\/видео};
    \node[dom] (a) at (8.9,-1.6) {Аудио};
    \node[dom] (s) at (12.4,-1.6) {Таблицы и\\временные ряды};

    \node[leaf] (t1) at (0.5,-3.0) {классификация документа};
    \node[leaf] (t2) at (0.5,-3.75) {NER (BIO-теги)};
    \node[leaf] (t3) at (0.5,-4.5) {отношения, coref};
    \node[leaf] (t4) at (0.5,-5.25) {перевод, QA, preference};

    \node[leaf] (v1) at (4.0,-3.0) {класс / multi-label};
    \node[leaf] (v2) at (4.0,-3.75) {bounding box};
    \node[leaf] (v3) at (4.0,-4.5) {полигоны, маски};
    \node[leaf] (v4) at (4.0,-5.25) {keypoints, треки};

    \node[leaf] (a1) at (7.5,-3.0) {транскрипт};
    \node[leaf] (a2) at (7.5,-3.75) {диаризация};
    \node[leaf] (a3) at (7.5,-4.5) {события и метки времени};
    \node[leaf] (a4) at (7.5,-5.25) {эмоция, качество};

    \node[leaf] (s1) at (11.0,-3.0) {метка на строку};
    \node[leaf] (s2) at (11.0,-3.75) {аномалии, change points};
    \node[leaf] (s3) at (11.0,-4.5) {прогноз на горизонте};
    \node[leaf] (s4) at (11.0,-5.25) {причинно-следственные связи};

    \draw[arr] (r) -- (t); \draw[arr] (r) -- (v); \draw[arr] (r) -- (a); \draw[arr] (r) -- (s);
    \foreach \d/\f in {t/t1,t/t2,t/t3,t/t4,v/v1,v/v2,v/v3,v/v4,a/a1,a/a2,a/a3,a/a4,s/s1,s/s2,s/s3,s/s4}
        \draw[arr, gray] (\d.south) -- (\f.north);
\end{tikzpicture}
\end{document}
```

> Ключевое: **дорогие** задачи — те, где один объект требует много решений (маски, треки, отношения). Дешёвые — одна метка на объект. Это определяет и бюджет, и стратегию.

---

## Анатомия одного объекта разметки

<!-- доп. -->

- **Единица разметки** (unit): документ, предложение, окно 10 с, кадр, пара «запрос-ответ»
- **Схема** (schema): набор допустимых меток + правила их применения
- **Контекст**: что разметчик видит рядом с объектом (история, метаданные, соседние кадры)
- **Неоднозначность**: что делать, если объект не подходит ни под одну метку

| Решение | Хорошо | Плохо |
|:--------|:-------|:------|
| Единица | короткая, самодостаточная | требует весь документ в голове |
| Схема | 5–15 взаимоисключающих меток | 60 меток «на всякий случай» |
| Неоднозначность | явная метка `unknown` + правило | «разметчик разберётся» |

---

## Сколько стоит разметка: модель затрат

<!-- доп. -->

$$
C_{\text{total}} = N \cdot \big(c_{\text{annot}} + k \cdot c_{\text{review}} + c_{\text{rework}}\big) + C_{\text{setup}} + C_{\text{infra}}
$$

- $N$ — число объектов, $k$ — кратность перекрёстной проверки
- $C_{\text{setup}}$ — инструкции, пилот, обучение команды: **обычно 15–30% бюджета**
- $c_{\text{rework}} = p_{\text{err}} \cdot c_{\text{annot}}$ — переделка после QA
- Скрытые статьи: онбординг, калибровка, споры, тулинг, простой

> Ключевое: в смете «на разметку» обычно забывают **QA и переделку**. Без них цифра занижается в 1,5–2 раза.

---

## Видимая и скрытая часть проекта

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, matrix, calc}
\begin{document}
\begin{tikzpicture}[font=\small]
    % вода
    \fill[blue!8] (-5.4,0) rectangle (8.6,3.4);
    \draw[blue!40, thick] (-5.4,0) -- (8.6,0);
    \node[blue!50!black, font=\scriptsize, anchor=west] at (-5.3,3.15) {ВИДНО ЗАКАЗЧИКУ};

    \node[rectangle, rounded corners, draw, thick, fill=orange!25, align=center, minimum width=4.6cm, minimum height=1.3cm]
        (ui) at (-1.4,1.6) {\textbf{Интерфейс и платформа}\\клик по метке};
    \node[font=\scriptsize, align=center, text width=3.2cm] at (4.6,1.6) {~};
    \fill[blue!8, opacity=0.0] (0,0) rectangle (0,0);

    \draw[blue!40, thick, dashed] (-5.4,0) -- (8.6,0);
    \node[blue!50!black, font=\scriptsize, anchor=west] at (-5.3,-0.35) {НЕ ВИДНО: 70–85\% усилий};

    \node[rectangle, rounded corners, draw, fill=blue!12, align=center, minimum width=2.9cm, minimum height=0.95cm] (g) at (-4.0,-3.2) {Инструкции\\и калибровка};
    \node[rectangle, rounded corners, draw, fill=blue!12, align=center, minimum width=2.9cm, minimum height=0.95cm] (h) at (-0.8,-3.2) {Найм, обучение,\\удержание};
    \node[rectangle, rounded corners, draw, fill=blue!12, align=center, minimum width=2.9cm, minimum height=0.95cm] (q) at (2.4,-3.2) {QA: эталоны,\\согласие, аудит};
    \node[rectangle, rounded corners, draw, fill=blue!12, align=center, minimum width=2.9cm, minimum height=0.95cm] (ag) at (5.6,-3.2) {Агрегация\\и версионирование};
    \node[rectangle, rounded corners, draw, fill=green!15, align=center, minimum width=2.9cm, minimum height=0.95cm] (d) at (0.8,-4.9) {Датасет, которому\\можно верить};

    \draw[->, thick] (ui) -- (g.north);
    \draw[->, thick] (ui) -- (h.north);
    \draw[->, thick] (ui) -- (q.north);
    \draw[->, thick] (ui) -- (ag.north);
    \draw[->, thick] (g) -- (d); \draw[->, thick] (h) -- (d);
    \draw[->, thick] (q) -- (d); \draw[->, thick] (ag) -- (d);
\end{tikzpicture}
\end{document}
```

> Ключевое: платформа — это **10% проблемы**. Остальное — процесс, люди и контроль качества.

---

## Вызовы, с которыми вы точно столкнётесь

- **Стоимость**: ручная работа масштабируется линейно, бюджет — нет
- **Субъективность**: нет «истины», есть распределение суждений
- **Согласованность**: два разметчика дают разные метки на одном объекте
- **Дрейф инструкций**: правила меняются, старые метки уже невалидны
- **Утечки**: разметчик видит тест-сет; одна и та же сущность в train и test
- **Хрупкость процесса**: ушёл ведущий разметчик — ушло знание

> Ключевое: почти все проблемы разметки — **не про инструмент, а про неопределённость задачи**. Побеждает тот, кто управляет неопределённостью, а не тот, кто купил платформу.

---

## Вопрос для обсуждения

**Какие проблемы возникают при разметке данных в ваших проектах?**

Что из этого — про инструмент, а что — про постановку задачи?

---

<!-- _class: lead -->

# Блок 1
## Платформы для разметки

<!-- ~20 мин -->

---

## Что должна уметь платформа

<!-- доп.: критерии выбора вместо простого списка -->

| Требование | Зачем | Проверка на пилоте |
|:-----------|:------|:-------------------|
| Формат задачи | NER ≠ боксы ≠ аудио | 5 минут реальной разметки |
| Управление проектом | очередь, назначения, роли | распределить 100 задач на 3 человека |
| QA встроенный | эталоны, доля проверок, согласие | включить 10% двойной разметки |
| API / SDK | автозагрузка и выгрузка | выгрузить в нужном формате за час |
| ML-бэкенд | предразметка, активное обучение | подклеить модель с порогом |
| Развёртывание | on-prem / облако / GDPR | развернуть там, где можно данные |

> Ключевое: критерий выбора — **не список фич, а время до первого валидного датасета** на вашей задаче.

---

## Label Studio

- Open-source (Apache 2.0), self-hosted, есть облачная версия
- Один конфиг-файл (XML-подобный `label_config`) описывает интерфейс
- Мультимодальность: текст, изображения, аудио, видео, HTML, PDF, временные ряды
- REST API + Python SDK; webhooks на события разметки
- ML-backend: предразметка, активное обучение, авто-приём предсказаний

```python
from label_studio_sdk import Client

ls = Client(url="http://localhost:8080", api_key="...")
project = ls.start_project(
    title="NER для новостей",
    label_config="""
    <View>
      <Text name="text" value="$text"/>
      <Labels name="label" toName="text">
        <Label value="PER" background="#e74c3c"/>
        <Label value="ORG" background="#3498db"/>
        <Label value="LOC" background="#2ecc71"/>
      </Labels>
    </View>
    """
)
```

> Практика: начинайте с `label_config` в git — интерфейс разметки тоже версионируется.

---

## Prodigy

- От создателей spaCy (Explosion), коммерческая лицензия (per-seat)
- Фокус — **NLP и потоковая разметка**: NER, классификация, spans, relations, coref
- Активное обучение и `ner.teach` / `textcat.teach` «из коробки»
- Конфигурация — Python-скриптами (`prodigy.json`, рецепты), а не XML
- Данные — JSONL, легко склеиваются с пайплайном spaCy

```bash
# потоковая разметка с активным обучением
prodigy ner.teach news_ner ./model ./data/news.jsonl \
        --label PER,ORG,LOC --unsegmented
```

> Ключевое: Prodigy продаёт не интерфейс, а **рецепт «модель в цикле»**. Если у вас NLP и Python-команда — это самый короткий путь.

---

## Labelbox

- Enterprise-платформа (SaaS, on-prem по запросу)
- Сильный блок **операционного управления**: команды, роли, ёмкость, SLA
- Встроенная аналитика: скорость, качество, стоимость по проектам и людям
- Model-assisted labeling, автоматизация QA (consensus, benchmark-наборы)
- Интеграции с CV-стеком: маски, полигоны, видео-трекинг, 3D-облака точек

| Плюс | Минус |
|:-----|:------|
| Готовый процесс на 50+ разметчиков | Цена и vendor lock-in |
| Аудит и отчётность для заказчика | Избыточно для пилота |

---

## Amazon SageMaker Ground Truth

- Управляемый сервис AWS: инфраструктура, воркфлоу, аудит — на стороне провайдера
- Три источника труда: **private workforce**, **vendor workforce**, **Mechanical Turk**
- Automatic data labeling: предразметка моделью + порог уверенности → человеку только спорное
- Pay-per-use: платите за размеченный объект, а не за место
- Ground Truth Plus — полностью управляемая команда разметки

> Ключевое: покупая Ground Truth, вы покупаете **не софт, а операционный процесс**. Это правильный выбор, когда команды разметки нет и не планируется.

---

## Сравнение платформ

| | Label Studio | Prodigy | Labelbox | Ground Truth |
|:--|:--|:--|:--|:--|
| Лицензия | OSS / Cloud | Commercial | Enterprise SaaS | AWS, pay-per-use |
| Развёртывание | self-host | локально | облако | облако AWS |
| Сильные данные | мультимодальные | текст | CV, видео | любые, «под ключ» |
| Активное обучение | через ML-backend | встроено | есть | встроено |
| Операционный QA | базовый | минимальный | сильный | сильный |
| Барьер входа | низкий | средний (Python) | высокий (деньги) | средний (AWS) |
| Кому | пилот, research | NLP-команда | enterprise CV | нет своей команды |

---

## Дерево выбора платформы

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, matrix, calc}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    q/.style={diamond, draw, aspect=2.2, fill=yellow!20, align=center, inner sep=1pt},
    a/.style={rectangle, rounded corners, draw, align=center, minimum height=0.85cm, minimum width=2.7cm},
    arr/.style={->, semithick}]
    \node[q] (q1) at (0,0) {Данные можно\\выносить в облако?};
    \node[q] (q2) at (-3.6,-1.9) {Есть команда\\и Python-стек?};
    \node[q] (q3) at (3.6,-1.9) {Нужен процесс\\«под ключ»?};

    \node[a, fill=green!15] (ls) at (-6.2,-3.7) {Label Studio\\self-hosted};
    \node[a, fill=orange!20] (pr) at (-2.0,-3.7) {Prodigy\\(NLP)};
    \node[a, fill=cyan!20] (lb) at (2.0,-3.7) {Labelbox\\CV / enterprise};
    \node[a, fill=violet!20] (gt) at (6.2,-3.7) {SageMaker\\Ground Truth};

    \node[font=\scriptsize, fill=white, inner sep=1pt] at (-1.9,-0.85) {нет};
    \node[font=\scriptsize, fill=white, inner sep=1pt] at (1.9,-0.85) {да};
    \node[font=\scriptsize, fill=white, inner sep=1pt] at (-4.9,-2.75) {да};
    \node[font=\scriptsize, fill=white, inner sep=1pt] at (2.3,-2.75) {да};
    \node[font=\scriptsize, fill=white, inner sep=1pt] at (4.9,-2.75) {нет};

    \draw[arr] (q1) -- (q2);
    \draw[arr] (q1) -- (q3);
    \draw[arr] (q2) -- (ls);
    \draw[arr] (q2) -- (pr);
    \draw[arr] (q3) -- (lb);
    \draw[arr] (q3) -- (gt);
\end{tikzpicture}
\end{document}
```

- Бюджет ограничен → OSS (Label Studio, CVAT, Doccano) + свои руки
- Много CV и большая команда → Labelbox / Supervisely / CVAT
- Нет команды разметки вообще → managed-сервис

---

## Интерфейсы для текста

| Задача | Что видит разметчик | Формат метки |
|:-------|:--------------------|:-------------|
| Классификация | документ + кнопки классов | `label` |
| Multi-label | документ + чекбоксы | набор меток |
| NER | текст + подсветка span | `(start, end, type)` |
| Relations | две сущности + стрелка | `(head, tail, rel)` |
| Coreference | цепочки упоминаний | кластеры |
| QA | вопрос + контекст + ответ | `(start, end)` |
| Preference | два ответа модели | `A / B / tie` |

- BIO-схема: `B-PER`, `I-PER`, `O` — стандарт де-факто для последовательностей
- Span-разметка устойчивее к переносу строк, token-level — к токенизатору

---

## Интерфейсы для изображений и видео

| Задача | Инструмент | Стоимость объекта |
|:-------|:-----------|:------------------|
| Классификация | кнопки классов | низкая |
| Детекция | bounding box | средняя |
| Instance segmentation | полигон / маска | высокая |
| Semantic segmentation | маска по пикселям | очень высокая |
| Keypoints | точки + скелет | средняя |
| Tracking | бокс + ID между кадрами | очень высокая |

- Полигон из 40 точек стоит в 5–10 раз дороже бокса — выбирайте минимально достаточный формат
- Для видео размечают **каждый $k$-й кадр**, промежуточные — интерполяцией (и это надо валидировать)
- Инструменты: CVAT, Labelme, Supervisely, Roboflow

> Ключевое: формат разметки должен совпадать с **форматом выхода модели**. Лишняя точность масок не улучшит детектор боксов.

---

## Интерфейсы для аудио и временных рядов

- **Транскрипция**: сегменты + текст; диаризация — «кто говорит»
- **События**: интервалы с метками (кашель, музыка, речь)
- **Качество**: MOS-оценки, наличие шума, клиппинг
- **Временные ряды**: аномалии, change points, режимы работы оборудования
- Ключевая сложность — **границы**: где кончается событие, решается субъективно

```
# формат аннотации аудио (упрощённо)
{"file": "call_0412.wav", "start": 12.4, "end": 15.9,
 "speaker": "SPK_2", "text": "перезагрузите роутер", "event": null}
```

> Ключевое: договоритесь о **допуске на границу** (например, ±100 мс) и запишите его в инструкцию — иначе согласие никогда не сойдётся.

---

## Пайплайн разметки в общем виде

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, matrix, calc}
\begin{document}
\begin{tikzpicture}[font=\small,
    b/.style={rectangle, rounded corners, draw, align=center, minimum height=1.0cm, minimum width=2.5cm},
    arr/.style={->, thick}]
    \node[b, fill=blue!10] (raw) at (0,0) {Сырые\\данные};
    \node[b, fill=gray!12] (pre) at (3.4,0) {Предобработка\\и дедупликация};
    \node[b, fill=orange!20] (pl) at (6.9,0) {Предразметка\\моделью};
    \node[b, fill=yellow!25] (h) at (10.4,0) {Ручная\\разметка};
    \node[b, fill=cyan!20] (qa) at (13.9,0) {QA:\\эталоны, согласие};
    \node[b, fill=green!18] (ds) at (17.4,0) {Датасет\\+ метаданные};

    \node[b, fill=red!10, minimum width=3.0cm] (rej) at (13.9,-2.6) {Возврат на\\переразметку};
    \node[b, fill=violet!15, minimum width=3.0cm] (ml) at (17.4,-2.6) {Обучение\\модели};

    \draw[arr] (raw) -- (pre);
    \draw[arr] (pre) -- (pl);
    \draw[arr] (pl) -- (h);
    \draw[arr] (h) -- (qa);
    \draw[arr] (qa) -- node[above, font=\scriptsize] {pass} (ds);
    \draw[arr] (qa) -- node[right, font=\scriptsize] {fail} (rej);
    \draw[arr] (rej) -- (h);
    \draw[arr] (ds) -- (ml);
    \draw[arr, dashed] (ml.west) -| (6.9,-3.9) -- (pl.south);
    \node[font=\scriptsize, align=center] at (10.4,-3.55) {следующая итерация: предразметка лучше};
\end{tikzpicture}
\end{document}
```

> Ключевое: на второй итерации меняется только одно звено — **качество предразметки**. Остальной процесс должен быть неизменным, иначе вы не измерите улучшение.

---

## Управление проектом разметки

**До старта**

- Цели и метрики: какое качество модели считается достаточным?
- Инструкция (guidelines) с примерами **и антипримерами**
- Пилот на 100–300 объектах: замер времени, согласия, неоднозначностей
- Смета: часы × ставка + QA + переделка

**В процессе**

- Онбординг: тестовое задание + разбор ошибок
- Распределение: стратификация по сложности, не «всё подряд»
- Мониторинг: скорость, согласие, доля `unknown`
- Еженедельная калибровка: разбор спорных случаев → правка инструкции

> Ключевое: инструкция — **живой документ**. Если за месяц она не изменилась, вы либо не смотрите на ошибки, либо задача тривиальна.

---

## Инструкция разметчика: что в ней должно быть

<!-- доп. -->

1. **Определение метки** через критерий, а не через пример («содержит прямую просьбу о действии»)
2. **Границы**: что входит в объект, что нет (включая границы span/бокса)
3. **Приоритет меток** при конфликте: какая побеждает
4. **Правило для неоднозначного**: `unknown`, `skip`, эскалация
5. **10–20 пограничных примеров** с объяснением решения
6. **Чего делать нельзя**: гуглить, додумывать, исправлять текст

| Антипаттерн | Почему плохо |
|:------------|:-------------|
| «Размечайте спам» | нет критерия → каждый понимает своё |
| 40 примеров без контрпримеров | разметчик не видит границу класса |
| Молчание про неоднозначность | скрытая метка «на усмотрение» |

---

## Пример: проект в Label Studio целиком

```python
import pandas as pd
from label_studio_sdk import Client

ls = Client(url="http://localhost:8080", api_key=API_KEY)
project = ls.start_project(title="Sentiment v1", label_config=open("config.xml").read())

# 1. загрузка задач пачками
tasks = [{"data": {"text": t, "meta": {"src": s}}} for t, s in df[["text", "src"]].values]
project.import_tasks(tasks)

# 2. предразметка из модели (predictions)
project.create_predictions([{
    "task": task_id,
    "result": [{"from_name": "label", "to_name": "text", "type": "choices",
                "value": {"choices": ["positive"]}}],
    "score": 0.93
}])

# 3. выгрузка готового
exported = project.export_tasks(export_type="JSON")
```

> Практика: храните `label_config.xml`, инструкцию и скрипт загрузки **в одном репозитории** с версией датасета.

---

## Вопрос для размышления

**Как выбрать платформу разметки для проекта с ограниченным бюджетом?**

Подсказка: считайте не стоимость лицензии, а стоимость часа работы разметчика, умноженную на часы до готового датасета.

---

## Резюме блока 1

- Платформа — это **ускоритель процесса**, а не замена процессу
- Выбор определяется типом данных, масштабом и наличием команды
- Ключевые критерии: формат задачи, API, встроенный QA, ML-бэкенд
- Open-source решения конкурентоспособны для пилотов и research
- Управление проектом (инструкции, пилот, калибровка) важнее выбора софта

---

<!-- _class: lead -->

# Блок 2

## Активное обучение и weak supervision

<!-- ~20 мин -->

---

## Постановка задачи активного обучения

- Пул $U$ без меток и небольшой размеченный $L$; оракул даёт метку за деньги и время
- Бюджет $B$ — максимум запросов к оракулу: не «сколько хотим», а «сколько можем»
- Нужно выбрать $S\subseteq U$, $|S|\le B$, при котором модель получится лучшей

$$
\min_{S\subseteq U,\ |S|\le B}\ \mathbb{E}\big[\mathcal{L}(f_{L\cup S})\big]
$$

- Задача **комбинаторная**: перебор $\binom{|U|}{B}$ невозможен → жадный выбор по скору
- AL — это **optimal experimental design**: ищем, какое измерение даст максимум информации
- Качество выбранных примеров важнее их количества

> Ключевое: AL меняет не модель, а **порядок**, в котором данные попадают в обучение.

---

## Цикл активного обучения

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    box/.style={rectangle, rounded corners, draw, align=center, minimum height=0.95cm, minimum width=2.7cm},
    arr/.style={->, semithick}]
    \node[box, fill=blue!10] (pool) at (0,2.8) {Начальный пул\\$L_0$, $U$};
    \node[box, fill=green!12] (train) at (4.0,2.8) {Обучение\\$f$ на $L$};
    \node[box, fill=green!12] (score) at (8.0,2.8) {Скоринг пула $U$\\$s(x)$};
    \node[box, fill=orange!20] (pick) at (8.0,0) {Выбор $k$\\примеров};
    \node[box, fill=orange!20] (label) at (4.0,0) {Разметка\\оракулом};
    \node[box, fill=blue!10] (add) at (0,0) {Пополнение\\$L \leftarrow L\cup S$};
    \node[box, draw=red!60, fill=red!8, minimum width=3.2cm] (stop) at (8.0,-2.4) {Стоп: бюджет /\\плато метрики};

    \draw[arr] (pool) -- (train);
    \draw[arr] (train) -- (score);
    \draw[arr] (score) -- (pick);
    \draw[arr] (pick) -- (label);
    \draw[arr] (label) -- (add);
    \draw[arr] (add) -- (pool);
    \draw[arr, dashed] (pick.south) -- (stop.north);
\end{tikzpicture}
\end{document}
```

- **Батч, а не по одному**: переобучение на каждый пример слишком дорого; $k$ = 32–256
- **Критерий остановки** задаётся заранее: бюджет, плато метрики, доля `unknown`
- **Холодный старт**: с нуля меток скор бессмыслен — нужен seed-набор 100–500 примеров

---

## Uncertainty sampling: три способа

<!-- доп. -->

| Стратегия | Формула | Идея |
|:----------|:--------|:-----|
| Least confidence | $1-\max_y p(y\mid x)$ | берём там, где модель не уверена |
| Margin | $p_1-p_2$ | минимальный отрыв двух лучших классов |
| Entropy | $-\sum_y p(y\mid x)\log p(y\mid x)$ | максимум неопределённости |

- $\hat{y}=\arg\max_y p(y\mid x)$ — базовый предикт, всё остальное лишь надстройка над ним
- Margin устойчивее LC на многоклассовых задачах, entropy — самый «мягкий» скор
- Дёшево: одна модель, один проход по пулу, без эмбеддингов
- **Калибровка**: softmax завышает уверенность, и на «уверенных» ошибках AL выберет не то — проверяйте ECE и temperature scaling

---

## Diversity sampling

- Проблема: uncertainty тянет **одно и то же** — 200 почти одинаковых пограничных примеров
- **Кластеризация**: разбить $U$ на кластеры и брать по одному представителю из каждого
- **Core-set (k-center)**: выбрать $S$, минимизирующее максимальное расстояние от $U$ до $S$
- **BADGE**: эмбеддинги × уверенность, затем k-means++ по ним
- При малом $L$ **покрытие пространства** важнее локальной неопределённости

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize]
    % A. uncertainty
    \draw[gray!60] (0,0) rectangle (4.6,4.0);
    \draw[dashed, thick, gray] (0.4,3.8) -- (4.2,0.2);
    \foreach \p in {(0.7,3.3),(1.0,3.5),(0.8,2.5),(1.4,3.1),(0.5,1.9),(1.2,1.8),(0.9,1.2)}
        \fill[blue!70] \p circle (2.2pt);
    \foreach \p in {(3.4,1.0),(3.9,1.6),(3.0,0.6),(3.5,2.2),(4.1,0.7),(2.7,1.2),(3.2,1.8),(3.7,2.8)}
        \fill[red!75] \p circle (2.2pt);
    \foreach \p in {(1.2,3.0),(2.1,2.1),(3.0,1.2)}{
        \draw[thick, orange!90!black] \p circle (5pt);
        \fill[orange!90!black] \p circle (2.2pt);
    }
    \node[align=center] at (2.3,4.38) {A. Uncertainty: у границы};

    % B. diversity / core-set
    \draw[gray!60] (6.0,0) rectangle (10.6,4.0);
    \foreach \c/\rx/\ry in {(7.0,3.2)/0.62/0.42,(9.7,3.2)/0.58/0.45,(7.2,0.9)/0.55/0.38,(9.8,1.0)/0.60/0.40}
        \draw[dashed, gray] \c ellipse [x radius=\rx, y radius=\ry];
    \foreach \c in {(7.0,3.2),(9.7,3.2),(7.2,0.9),(9.8,1.0)}{
        \draw[thick, orange!90!black] \c circle (5pt);
        \fill[green!55!black] \c circle (2.2pt);
    }
    \foreach \p in {(6.6,3.5),(7.4,2.9),(9.4,3.5),(10.0,3.0),(6.8,0.6),(7.6,1.2),(10.2,0.7),(9.4,1.2),(8.3,2.0),(8.5,1.0),(8.6,3.0)}
        \fill[blue!60] \p circle (1.8pt);
    \node[align=center] at (8.3,4.38) {B. Diversity / core-set};
\end{tikzpicture}
\end{document}
```

> Ключевое: uncertainty и diversity — не альтернативы, а **два слагаемых** одного скора: неопределённость × новизна.

---

## Query-by-Committee и BALD

<!-- доп. -->

- **Комитет** — $k$ моделей: бэггинг, разные сиды, разные архитектуры
- **Vote entropy**: $-\sum_c \frac{V_c}{k}\log\frac{V_c}{k}$ — насколько комитет не согласен
- **BALD** отбирает примеры с максимумом *эпистемической* неопределённости

$$
\mathbb{I}[y;\theta\mid x]=H[y\mid x]-\mathbb{E}_{p(\theta\mid D)}\,H[y\mid x,\theta]
$$

- Первое слагаемое — вся неопределённость, второе — «неустранимый шум»; разность снимается меткой
- На практике: MC-dropout или ансамбль из 5–10 моделей

> Ключевое: BALD не любит шумные объекты — он ищет **незнание модели**, а не сложность примера.

---

## Сравнение стратегий

| Стратегия | Сильная сторона | Слабая | Когда брать |
|:----------|:----------------|:-------|:------------|
| Uncertainty | дёшево, одна модель | дубликаты, зависит от калибровки | старт, много классов |
| Margin | устойчивее LC | нужны вероятности классов | 3–20 классов |
| Entropy | гладкий скор | тянет шумные примеры | анализ, baseline |
| Core-set / BADGE | покрытие пространства | дороже, нужны эмбеддинги | мало меток, CV |
| QBC / BALD | явно измеряет незнание | $k$ моделей, дорого | есть бюджет на ансамбль |
| Random | честный baseline | не использует модель | всегда как контроль |

- Гибрид «uncertainty × diversity» обычно лучше любой чистой стратегии
- Сравнивать только на **одинаковом бюджете** и с одинаковым seed-набором

---

## Сколько меток экономит AL

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usepackage{pgfplots}
\pgfplotsset{compat=1.15}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}
\begin{axis}[
    width=11.4cm, height=6.2cm,
    xlabel={число размеченных примеров},
    ylabel={F1},
    xmin=0, xmax=100, ymin=0.60, ymax=0.93,
    grid=both, grid style={gray!25},
    legend pos=south east, legend style={font=\scriptsize},
    tick label style={font=\scriptsize}, label style={font=\scriptsize}]
    \addplot[blue, thick, domain=0:100, samples=120] {0.62+0.28*(1-exp(-x/22))};
    \addlegendentry{случайная выборка}
    \addplot[red, thick, domain=0:100, samples=120] {0.62+0.28*(1-exp(-x/7))};
    \addlegendentry{активное обучение}
    \addplot[only marks, mark=*, blue, mark size=2.2pt] coordinates {(42.8,0.86)};
    \addplot[only marks, mark=*, red, mark size=2.2pt] coordinates {(13.6,0.86)};
    \draw[<->, thick] (axis cs:13.6,0.86) -- (axis cs:42.8,0.86)
        node[midway, above, fill=white, inner sep=1pt, font=\scriptsize] {$\approx$3,1$\times$ меньше меток};
\end{axis}
\end{tikzpicture}
\end{document}
```

$$
N_{\text{saved}}=N_{\text{rand}}-N_{\text{AL}}
$$

- На графике: до одного и того же F1 нужно ≈3× меньше меток
- Экономия растёт с числом классов и падает с шумом оракула
- **Числа синтетические** — показана форма кривой, а не результат эксперимента

> Ключевое: AL экономит **метки**, но не обязательно **время** — добавляются обучение, скоринг и оркестрация.

---

## Практика: батчи, холодный старт, дисбаланс

<!-- доп. -->

- Батч 32–256: меньше — дороже по переобучению, больше — теряется адаптивность
- Seed-набор 100–500 примеров, стратифицированный по классам
- Скор пересчитывать после батча, а не после каждого отдельного примера
- Дисбаланс: uncertainty «съест» редкий класс → квота на класс внутри батча
- Логировать всё: какой пример, какой скор, кто и когда разметил

| Когда AL не работает | Почему |
|:---------------------|:-------|
| Шумный оракул | метка хуже сигнала, который она приносит |
| Слабая модель | скор не отражает полезность примера |
| Дубликаты | батч из 100 копий одного объекта |
| Дрейф данных | скор устаревает быстрее, чем приходит метка |

---

## Semi-supervised learning

- **Self-training**: модель размечает уверенные примеры и добавляет их в обучение
- **Co-training**: два независимых «взгляда» на данные учат друг друга
- **Graph-based**: метки распространяются по графу сходства
- **Generative / consistency**: SSL-регуляризация, аугментации, pseudo-label + EMA
- Общее: используем **структуру** неразмеченных данных, а не мнение оракула

| Подход | Когда работает |
|:-------|:---------------|
| Self-training | много неразмеченных, калиброванная модель, мало классов |
| Co-training | есть два действительно независимых представления |
| Graph-based | данные образуют плотные кластеры сходства |
| Generative / consistency | есть сильные аугментации или предобучение |

---

## Self-training: псевдо-разметка

```python
from sklearn.semi_supervised import SelfTrainingClassifier
from sklearn.linear_model import LogisticRegression

base = LogisticRegression(max_iter=1000)
model = SelfTrainingClassifier(
    base,
    threshold=0.95,        # порог уверенности для псевдо-метки
    criterion="threshold",
    k_best=50,             # сколько добавлять за итерацию
    max_iter=10,
    verbose=True,
)
model.fit(X, y)            # y: -1 = объект без метки
pseudo = model.transduction_   # итоговые метки
```

- **Confirmation bias**: модель закрепляет свои ошибки — порог и `k_best` обязательны
- Псевдо-метки не равны настоящим: меньший вес, валидация только на ручной разметке
- Следите за балансом классов в псевдо-наборе, иначе редкий класс исчезнет

---

## Weak supervision: labeling functions

- **LF** — функция, которая по объекту выдаёт метку или `ABSTAIN`
- Типы: keyword, regex/pattern, внешняя база знаний, предобученная модель, эвристика
- **Точность vs покрытие**: узкая LF точна, широкая — покрывает, но шумит

```python
from snorkel.labeling import labeling_function, PandasLFApplier

@labeling_function()
def lf_refund(x):
    return REFUND if "верните деньги" in x.text.lower() else ABSTAIN
```

- Одна LF — слабая; вместе они покрывают больше, а конфликты разрешает label model

> Ключевое: LF пишут **быстро и грязно** — их шум исправляет label model, а не ручная отладка каждой функции.

---

## Snorkel: пайплайн

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    box/.style={rectangle, rounded corners, draw, align=center, minimum height=1.0cm, minimum width=2.2cm},
    src/.style={rectangle, draw, dashed, align=center, fill=gray!8, minimum height=0.6cm, minimum width=1.7cm},
    arr/.style={->, semithick}]
    \node[box, fill=blue!10] (raw) at (0,0) {Неразмеченные\\данные};
    \node[box, fill=orange!18] (lf) at (3.4,0) {Набор LF\\матрица $L$};
    \node[box, fill=green!15] (lm) at (6.8,0) {Label\\model};
    \node[box, fill=green!15] (pr) at (10.0,0) {Вероятностные\\метки $\hat{y}$};
    \node[box, fill=violet!15] (em) at (13.2,0) {End\\model};

    \node[src] (s1) at (1.3,2.0) {правила};
    \node[src] (s2) at (3.4,2.0) {внешние БД};
    \node[src] (s3) at (5.5,2.0) {предобученные\\модели};

    \draw[arr] (raw) -- (lf);
    \draw[arr] (lf) -- (lm);
    \draw[arr] (lm) -- (pr);
    \draw[arr] (pr) -- (em);
    \draw[arr, dashed] (s1) -- (lf.north west);
    \draw[arr, dashed] (s2) -- (lf.north);
    \draw[arr, dashed] (s3) -- (lf.north east);
\end{tikzpicture}
\end{document}
```

- LF применяются к каждому объекту → матрица $L$ размера $n\times m$
- Label model оценивает точность LF **без разметки** и выдаёт вероятности классов
- End model учится на вероятностных метках или прямо на матрице $L$

---

## Label model: как из шумных меток получить вероятность

<!-- доп. -->

- **Генеративная модель**: у каждой LF есть скрытая точность $\alpha_j$ и склонность к классу
- Обучение — по **согласию** между LF: кто часто спорит с большинством, тот шумный
- Ключевое допущение: при известном истинном $y$ метки LF условно независимы

$$
\hat{y}_i=\arg\max_y\ P_\theta\big(y\mid L_i\big)
$$

```python
from snorkel.labeling.model import LabelModel

label_model = LabelModel(cardinality=2, verbose=True)
label_model.fit(L_train, n_epochs=500, log_freq=100)
probs = label_model.predict_proba(L)     # (n, 2)
weak  = label_model.predict(L, tie_break_policy="abstain")
```

- Аккуратно с коррелированными LF: две копии одного правила ломают оценку

---

## Чек-лист внедрения AL

1. Есть ли поток неразмеченных данных, который **дешевле** случайной выборки?
2. Задан ли seed-набор и стратификация по классам?
3. Выбран ли скор под задачу: uncertainty, diversity или гибрид?
4. Зафиксированы ли размер батча и критерий остановки **до** старта?
5. Есть ли baseline «случайная выборка» на том же бюджете?
6. Логируются ли запросы, скоры и версия модели на каждой итерации?

> Ключевое: без baseline на том же бюджете вы не знаете, сэкономил ли AL хоть одну метку.

---

## Вопрос для обсуждения

**В каких случаях активное обучение может быть неэффективным?**

Подсказка: подумайте про шумного оракула, стоимость переобучения на каждой итерации, дубликаты в пуле и про то, что AL оптимизирует уверенность модели, а не вашу бизнес-метрику.

---

## Резюме блока 2

- AL выбирает, **что** размечать; weak supervision — **чем** заменить разметку
- Uncertainty дёшева, diversity надёжнее, BALD теоретически чище
- Экономия меток реальна, но её нужно мерить против random baseline
- Self-training и labeling functions снижают стоимость, но добавляют свои ошибки
- Внедрение начинается с логов и baseline, а не с выбора библиотеки

---

<!-- _class: lead -->

# Блок 3
## Контроль качества и агрегация меток

<!-- ~20 мин -->

---

## Цена шумных меток

<!-- доп. -->

- **Модель учит ошибки**: шум в обучающем наборе становится частью функции, а не «шумом, который сгладится»
- **Потолок качества**: даже идеальная модель не обгонит эталон, по которому её проверяют
- **Скрытые расходы**: переделка, повторная разметка, разбор спорных случаев, простой пайплайна
- **Потеря доверия**: после одного «странного» релиза команда перестаёт верить и метрикам, и датасету

$$
\hat p_{\text{err}} = \frac{n_{\text{err}}}{n_{\text{gold}}}
$$

- $n_{\text{err}}$ — расхождения с эталоном, $n_{\text{gold}}$ — размер эталонной подвыборки
- Оценка даёт **нижнюю границу** шума: часть ошибок не видит даже эталон
- Сравнивайте $\hat p_{\text{err}}$ между итерациями — важна динамика, а не абсолют

> Ключевое: шумные метки — это не «чуть хуже», а **жёсткий потолок** на качество всей системы.

---

## Источники ошибок

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    cause/.style={rectangle, rounded corners, draw, align=center, minimum height=0.9cm, minimum width=3.1cm, fill=orange!12},
    arr/.style={->, semithick, gray!60!black}]
    \useasboundingbox (-7.3,-3.95) rectangle (7.3,4.05);
    \node[circle, draw, thick, fill=red!12, align=center, minimum size=2.7cm, inner sep=1pt] (n) at (0,0) {\textbf{Шум}\\\textbf{в метках}};

    \node[cause] (c1) at (-5.2,2.5) {невнимательность};
    \node[cause] (c2) at (-5.2,0) {усталость и\\монотонность};
    \node[cause] (c3) at (-5.2,-2.5) {недостаточное\\обучение};

    \node[cause, fill=blue!12] (s1) at (5.2,2.5) {неоднозначные\\инструкции};
    \node[cause, fill=blue!12] (s2) at (5.2,0) {сложность\\задачи};
    \node[cause, fill=blue!12] (s3) at (5.2,-2.5) {плохой\\интерфейс};

    \draw[rounded corners, dashed, gray] (-6.9,3.75) rectangle (-3.5,-3.55);
    \draw[rounded corners, dashed, gray] (3.5,3.75) rectangle (6.9,-3.55);
    \node[font=\scriptsize\bfseries, gray!55!black] at (-5.2,3.35) {ЧЕЛОВЕК};
    \node[font=\scriptsize\bfseries, gray!55!black] at (5.2,3.35) {СИСТЕМА};

    \foreach \c in {c1,c2,c3,s1,s2,s3} \draw[arr] (\c) -- (n);
\end{tikzpicture}
\end{document}
```

- Ошибки **человека** лечатся обучением, калибровкой и ритмом работы
- Ошибки **системы** лечатся инструкцией, декомпозицией задачи и интерфейсом

> Ключевое: прежде чем наказывать разметчика, проверьте, не создали ли вы условия, в которых ошибиться — нормально.

---

## Систематические и случайные ошибки

| Тип | Как проявляется | Как обнаружить | Что делать |
|:----|:----------------|:---------------|:-----------|
| **Случайная** | метки «дрожат», согласие низкое, но без смещения | низкое $\kappa$ при высоком качестве каждого отдельного разметчика | больше примеров, чётче критерии, агрегация |
| **Систематическая** | все дружно смещены в один класс | высокое согласие **и** низкая точность на эталоне | правка инструкции, переобучение команды |
| **Коррелированная** | ошибка повторяется у группы (один шаблон, один наставник) | ошибки кластеризуются по людям и сменам | независимые проверки, ротация |
| **Дрейф правил** | старые метки не согласуются с новыми | расхождение версий датасета во времени | версионирование инструкции + переразметка |

- Согласие измеряет **случайную** компоненту, эталон — **систематическую**: нужны оба инструмента
- Высокое согласие при низкой точности — самый опасный случай: команда уверенно делает не то

> Ключевое: **согласие ≠ правильность**. Единственный способ поймать систематическую ошибку — эталон.

---

## Метрики согласия: что выбрать

| Метрика | Разметчиков | Шкала | Когда применять |
|:--------|:------------|:------|:----------------|
| **Cohen's $\kappa$** | ровно 2 | номинальная / порядковая | быстрая проверка пары, аудит |
| **Fleiss' $\kappa$** | 3 и больше | номинальная | много разметчиков, равное число меток на объект |
| **Krippendorff $\alpha$** | 2 и больше | любая | пропуски, разные шкалы, неравное число меток |
| **Weighted $\kappa$** | 2 | порядковая | ошибка «на класс мимо» мягче, чем «на два» |
| **ICC** | 2 и больше | интервальная | числовые оценки (1–5, MOS), не категории |

- Все метрики сравнивают наблюдаемое согласие с **ожидаемым случайно** — отсюда «поправка на угадывание»
- Номинальная шкала: порядок меток не важен (спам / не спам); порядковая: важен (плохо / нейтрально / хорошо)
- Для непрерывных оценок $\kappa$ неприменим — берите ICC или корреляцию

> Ключевое: метрику диктует **шкала и структура пропусков**, а не привычка команды.

---

## Cohen's $\kappa$

$$
\kappa=\frac{p_o-p_e}{1-p_e}
$$

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\small,
    cell/.style={draw, minimum width=1.45cm, minimum height=0.9cm, anchor=center},
    hdr/.style={draw=none, font=\bfseries\small, minimum width=1.45cm, minimum height=0.8cm},
    tot/.style={draw=none, fill=gray!12, minimum width=1.45cm, minimum height=0.9cm},
    diag/.style={cell, draw=green!45!black, fill=green!18},
    off/.style={cell, draw=red!55!black, fill=red!10}]
    \matrix (m) [matrix of nodes, nodes={cell}, column sep=2pt, row sep=2pt] {
        |[hdr]| & |[hdr]| \textbf{Спам} & |[hdr]| \textbf{Не спам} & |[hdr]| \textbf{$\Sigma$} \\
        |[hdr]| \textbf{Спам} & |[diag]| 42 & |[off]| 6 & |[tot]| 48 \\
        |[hdr]| \textbf{Не спам} & |[off]| 4 & |[diag]| 48 & |[tot]| 52 \\
        |[hdr]| \textbf{$\Sigma$} & |[tot]| 46 & |[tot]| 54 & |[tot]| 100 \\
    };
    \node[font=\scriptsize, gray!55!black, rotate=90] at (-3.55,0) {Разметчик A};
    \node[font=\scriptsize, gray!55!black] at (0,2.35) {Разметчик B};

    \node[anchor=west, align=left, font=\small] at ([xshift=7mm]m.east) {%
        $p_o=\frac{42+48}{100}=0.90$\\[5pt]
        $p_e=\frac{48\cdot 46+52\cdot 54}{100^2}=0.50$\\[5pt]
        $\kappa=\frac{0.90-0.50}{1-0.50}\approx 0.80$};
\end{tikzpicture}
\end{document}
```

- $p_o$ — доля совпадений по диагонали, $p_e$ — ожидаемое согласие при независимых метках
- $\kappa=1$ — полное согласие, $\kappa=0$ — ровно случайный уровень, $\kappa<0$ — хуже случайного

> Ключевое: $\kappa$ отвечает на вопрос «насколько мы согласованы **сверх случайного угадывания**», а не «какой процент совпал».

---

## Интерпретация $\kappa$

| $\kappa$ | Уровень (Landis & Koch) | Как читать |
|:---------|:------------------------|:-----------|
| $<0.00$ | Poor | хуже случайного — сломана инструкция или данные |
| $0.00$–$0.20$ | Slight | почти нет сигнала, разметка не годится |
| $0.21$–$0.40$ | Fair | есть сигнал, но шум слишком велик |
| $0.41$–$0.60$ | Moderate | рабочий минимум для черновых экспериментов |
| $0.61$–$0.80$ | Substantial | обычно достаточно для обучения |
| $0.81$–$1.00$ | Almost perfect | эталонный уровень, дальше расти некуда |

- **Base-rate paradox**: при редком классе (2%) точность 0.98 может дать $\kappa\approx0.2$ — метрика «наказывает» за дисбаланс
- $\kappa$ **не различает типы ошибок**: путаница «спам → не спам» и «не спам → спам» весит одинаково
- $\kappa$ **зависит от числа категорий**: больше классов — ниже $\kappa$ при той же доле совпадений

> Ключевое: порог «0.8» — не закон природы. Смотрите на $\kappa$ вместе с ценой ошибки и базовой частотой классов.

---

## Fleiss' $\kappa$ и Krippendorff $\alpha$

<!-- доп. -->

**Fleiss' $\kappa$ — много разметчиков, номинальная шкала**

$$
\bar P=\frac{1}{N}\sum_{i=1}^{N}\frac{1}{n(n-1)}\sum_{j=1}^{k} n_{ij}(n_{ij}-1),
\qquad
\kappa_F=\frac{\bar P-\bar P_e}{1-\bar P_e}
$$

**Krippendorff $\alpha$ — любая шкала, любые пропуски**

$$
\alpha=1-\frac{D_o}{D_e}
$$

- $n_{ij}$ — сколько разметчиков дали объекту $i$ метку $j$, $n$ — число разметчиков
- $D_o$ — наблюдаемое расхождение, $D_e$ — ожидаемое случайно; для номинальной шкалы $\alpha\approx\kappa_F$
- Fleiss требует **фиксированное** $n$ на объект; Krippendorff допускает **пропуски** и разное число меток
- Ориентиры Krippendorff: $\alpha\ge0.80$ — надёжно, $0.67$–$0.80$ — только для выводов, ниже — переделать

> Ключевое: если в данных есть пропуски или больше одной шкалы — **Krippendorff $\alpha$**, остальное потребует предварительной чистки.

---

## Согласие для сложных структур

<!-- доп. -->

- **Боксы**: согласие через IoU с порогом (0.5 / 0.75) и mAP-подобное сравнение — «совпало, если IoU выше порога»
- **Span'ы**: token-level F1 для пересечения + допуск на границу (например, ±2 токена или ±100 мс)
- **Порядок и ранжирование**: weighted $\kappa$ или коэффициент корреляции рангов, а не «точное совпадение»

| Структура | Метрика согласия | Параметр, который надо зафиксировать |
|:----------|:-----------------|:-------------------------------------|
| Боксы | IoU-матрица + порог | порог 0.5 или 0.75 |
| Маски | IoU / Dice по пикселям | минимальная площадь объекта |
| Span'ы | token-level F1 | допуск на границы |
| Ранжирование | weighted $\kappa$ / $\tau$ | веса соседних позиций |

> Ключевое: для структурных меток **порог совпадения — часть определения метрики**. Без него согласие не сравнимо между проектами.

---

## Расчёт метрик

```python
import numpy as np
from sklearn.metrics import cohen_kappa_score
from statsmodels.stats.inter_rater import fleiss_kappa
import krippendorff

a = np.array([1, 0, 1, 1, 0, 1, 0, 1])          # разметчик A
b = np.array([1, 0, 1, 0, 0, 1, 1, 1])          # разметчик B
print(cohen_kappa_score(a, b))                   # пара, номинальная

counts = np.array([[45, 5], [5, 45]])            # объекты x классы
print(fleiss_kappa(counts, method="fleiss"))     # несколько разметчиков

M = np.vstack([a, b]).astype(float)              # разметчики x объекты
print(krippendorff.alpha(M, level_of_measurement="nominal"))
```

- Для порядковых шкал: `cohen_kappa_score(a, b, weights="quadratic")`
- В `krippendorff` пропуски кодируются `np.nan` — не заменяйте их нулями или отдельным классом
- Считайте метрику **до** агрегации: после majority vote согласия уже нет, есть только решение

> Ключевое: метрика согласия — это диагностика процесса, а не финальный KPI датасета.

---

## Золотые стандарты и honeypots

- **Золотой стандарт** — подвыборка, размеченная экспертами и выверенная консенсусом
- **Honeypot** — объект с известным ответом, вброшенный в поток как обычная задача
- Эталон должен быть **недоступен** разметчикам: утечка превращает проверку в формальность
- Точность на эталоне считайте **регулярно**, а не один раз при приёмке
- Honeypots ловят невнимательность и «клик без чтения», но не систематическое непонимание задачи
- При изменении инструкции эталон **пересматривается** — иначе вы измеряете старые правила

| Этап | Доля проверок | Что проверяем |
|:-----|:--------------|:--------------|
| Пилот | 20–30% | понимание инструкции, спорные случаи, время на объект |
| Стабильный процесс | 5–10% | дрейф качества, усталость, новые типы объектов |
| Спорные / новые классы | до 100% | калибровка и сбор примеров для инструкции |

> Ключевое: эталон — это **инструмент измерения**, и он тоже требует валидации: плохой эталон тихо портит весь QA.

---

## Диагностика проблем

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    box/.style={rectangle, rounded corners, draw, align=center, minimum height=0.9cm, minimum width=3.0cm},
    act/.style={rectangle, rounded corners, draw, align=center, minimum height=0.8cm, minimum width=3.0cm, fill=green!12},
    arr/.style={->, semithick}]
    \useasboundingbox (-7.8,-6.9) rectangle (7.4,0.85);
    \node[box, fill=blue!12, minimum width=5.2cm] (mon) at (0,0) {Мониторинг метрик\\согласие · скорость · эталоны};
    \node[box, fill=orange!18] (b1) at (-5.2,-2.2) {Низкое согласие};
    \node[box, fill=orange!18] (b2) at (0,-2.2) {Низкая скорость};
    \node[box, fill=orange!18] (b3) at (5.2,-2.2) {Систематические\\ошибки};

    \node[act] (a1) at (-5.2,-3.9) {правка инструкций\\и примеров};
    \node[act] (a2) at (0,-3.9) {упрощение\\интерфейса};
    \node[act] (a3) at (5.2,-3.9) {дообучение\\и калибровка};

    \node[box, fill=red!10, minimum width=4.6cm] (re) at (0,-5.7) {Повторная разметка\\пилотного батча};

    \draw[arr] (mon) -- (b1); \draw[arr] (mon) -- (b2); \draw[arr] (mon) -- (b3);
    \draw[arr] (b1) -- (a1); \draw[arr] (b2) -- (a2); \draw[arr] (b3) -- (a3);
    \draw[arr] (a1.south) -- ++(0,-0.6) -| (re.west);
    \draw[arr] (a2) -- (re.north);
    \draw[arr] (a3.south) -- ++(0,-0.6) -| (re.east);
    \draw[arr, dashed] (re.south) -- ++(0,-0.5) -- ++(-7.35,0) |- (mon.west);
\end{tikzpicture}
\end{document}
```

- Каждая ветвь ведёт к **своему** действию: не лечите низкую скорость правкой инструкции
- После вмешательства обязателен **повторный замер** на том же батче — иначе неясно, помогло ли

> Ключевое: метрики нужны не для отчёта, а чтобы **выбрать одно из трёх действий** и проверить, что оно сработало.

---

## Агрегация: от многих меток к одной

```python
from collections import Counter
import numpy as np

def weighted_majority_vote(labels, weights):
    """labels: (объекты x разметчики), weights: компетентность."""
    out = []
    for row in labels:
        score = Counter()
        for lab, w in zip(row, weights):
            if lab is not None:              # пропуск не голосует
                score[lab] += w
        out.append(score.most_common(1)[0][0])
    return np.array(out)
```

- **Majority vote** — частный случай с равными весами: прост, устойчив, но игнорирует качество разметчиков
- При чётном числе голосов нужен **tie-break**: случайный выбор, эксперт или `unknown`
- Веса берите из эталона или из согласия с большинством, но **не** из самооценки разметчика

> Ключевое: агрегация — это модель доверия. Простое большинство предполагает, что все ошибаются одинаково, — обычно это неправда.

---

## Dawid–Skene: модель компетентности

<!-- доп. -->

- **Генеративная модель**: у каждого разметчика своя матрица ошибок, истинная метка скрыта

$$
\pi_{jk}^{(r)}=P\big(\text{разметчик } r \text{ даёт } k \;\big|\; \text{истина } j\big)
$$

- **E-шаг**: posterior истины по текущим матрицам ошибок

$$
q_{ij}\ \propto\ \prod_{r}\ \pi_{j,\,y_{ir}}^{(r)}
$$

- **M-шаг**: обновление матриц ошибок по posterior

$$
\pi_{jk}^{(r)}=\frac{\sum_i q_{ij}\,\mathbb{1}[y_{ir}=k]}{\sum_i q_{ij}}
$$

- EM сходится к локальному оптимуму: инициализация majority vote, несколько стартов
- **MACE** моделирует «спамящего» разметчика (почти постоянная метка), **GLAD** добавляет сложность объекта
- Требует достаточно объектов на класс; при малом $N$ оценка компетентности неустойчива

> Ключевое: Dawid–Skene отвечает на вопрос «кому верить», но сам нуждается в данных — на 50 объектах он бесполезен.

---

## Обучение и мотивация разметчиков

| Онбординг и калибровка | Мотивация и оплата |
|:-----------------------|:-------------------|
| Тестовое задание 20–30 объектов с разбором ошибок | Оплата за час, а не только за объект — иначе скорость важнее качества |
| Первая неделя: 100% проверка, затем выборочная | Прозрачные критерии премии: качество на эталоне, а не объём |
| Еженедельная калибровка: 30 минут на спорные случаи | Ротация однотипных задач — монотонность убивает внимание |
| Наставник на 5–8 новичков, эскалация сложного | Признание экспертизы: лучшие пишут примеры в инструкцию |
| Доступ к «золотым» примерам и разбору своих ошибок | Понятная карьерная ветка: разметчик → QA → владелец схемы |

- Плохая оплата привлекает случайных людей и ускоряет текучку — экономия на ставке возвращается переделкой
- Ошибки разметчика чаще следствие **процесса**, а не личных качеств: сначала проверьте инструкцию и интерфейс

> Ключевое: качество разметки — функция **условий труда**, а не только старательности конкретного человека.

---

## Итеративное улучшение: PDCA

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    lab/.style={align=center, text width=2.7cm, font=\scriptsize},
    arr/.style={->, thick}]
    \useasboundingbox (-4.7,-3.7) rectangle (4.7,3.35);
    \draw[arr, blue!70!black]    (168:2.0) arc[start angle=168, end angle=104, radius=2.0];
    \draw[arr, green!50!black]   ( 76:2.0) arc[start angle=76,  end angle=12,  radius=2.0];
    \draw[arr, orange!80!black]  (-14:2.0) arc[start angle=-14, end angle=-78, radius=2.0];
    \draw[arr, red!65!black]     (-104:2.0) arc[start angle=-104, end angle=-168, radius=2.0];

    \node[circle, draw, thick, fill=gray!10, align=center, minimum size=1.95cm, inner sep=1pt]
        at (0,0) {\textbf{Рост}\\\textbf{качества}};

    \node[lab] at (-3.1,2.45) {\textbf{Plan}\\инструкция и пилот};
    \node[lab] at ( 3.1,2.45) {\textbf{Do}\\разметка};
    \node[lab] at ( 3.1,-2.45) {\textbf{Check}\\согласие и эталоны};
    \node[lab] at (-3.1,-2.45) {\textbf{Act}\\правка правил};
\end{tikzpicture}
\end{document}
```

- **Plan**: гипотеза «где теряем качество» + правка инструкции + пилот на 100–300 объектах
- **Do**: разметка по новой версии правил, с логированием времени и спорных случаев
- **Check**: согласие, точность на эталоне, скорость — сравнение с предыдущей итерацией
- **Act**: закрепляем удачное в инструкцию и интерфейс, неудачное откатываем

> Ключевое: одна итерация PDCA — это **одно изменение за раз**, иначе вы не узнаете, что именно помогло.

---

## Вопрос для размышления

**Как балансировать скорость разметки и её качество?**

Подсказка: сравните стоимость часа разметчика со стоимостью переделки батча и ошибки модели в продакшене. Часто выгоднее платить за медленную и аккуратную разметку на пилоте и ускорять процесс за счёт интерфейса и предразметки, а не за счёт сокращения проверок.

---

## Резюме блока 3

- Шум в метках задаёт **потолок** качества модели и почти всегда скрыт в смете
- Согласие ловит случайные ошибки, эталоны — систематические: нужны оба инструмента
- Метрику выбирают по шкале и пропускам: Cohen, Fleiss, Krippendorff, weighted $\kappa$, ICC
- Агрегация — это модель доверия: majority vote, веса, Dawid–Skene
- Качество поддерживается процессом: honeypots, доли проверок, калибровка и цикл PDCA

---

<!-- _class: lead -->

# Блок 4

## Автоматизация разметки и HITL

<!-- ~15 мин -->

---

## Три уровня автоматизации

| Уровень | Что даёт | Риск | Когда |
|:--------|:---------|:-----|:------|
| Правила и эвристики | дёшево, мгновенно, объяснимо | низкое покрытие, хрупкость | есть устойчивые паттерны |
| Модель-предразметка | покрытие выше, учится на ваших метках | тиражирует свои ошибки | есть 1–2 тыс. размеченных объектов |
| LLM few-shot | старт без обучения, гибкие классы | дрейф, цена токенов, нестабильность | мало данных, сложный текст |

- Уровни **не взаимоисключающие**: правила закрывают очевидное, модель — остальное, LLM — холодный старт
- Автоматизация всегда возвращает **уверенность**, а решение «доверять или нет» принимает порог

> Ключевое: автоматизация не убирает человека, а **перераспределяет** его внимание на трудные случаи.

---

## Архитектура предразметки

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix, shapes.geometric}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    box/.style={rectangle, rounded corners, draw, align=center, minimum height=0.9cm, minimum width=2.3cm, fill=blue!8},
    qa/.style={box, fill=orange!12},
    model/.style={box, fill=green!10},
    arr/.style={-{Stealth}, thick}]
    \useasboundingbox (-8.6,-2.9) rectangle (10.9,4.1);

    \node[box] (data) at (-7.2,0) {Новые\\данные};
    \node[model] (model) at (-4.1,0) {Модель\\предразметки};
    \node[diamond, draw, aspect=1.7, align=center, inner sep=1pt, fill=yellow!15] (tau) at (-0.7,0) {$c>\tau$?};

    \node[box] (auto) at (3.1,1.5) {Авто-метка\\+ лог $c$};
    \node[qa] (qa) at (6.4,1.5) {Выборочный\\QA};
    \node[model] (ds) at (9.2,1.5) {Датасет\\v$k$};
    \node[model] (retrain) at (6.4,3.3) {Дообучение\\модели};
    \node[box] (manual) at (3.1,-1.7) {Очередь ручной\\разметки};

    \draw[arr] (data) -- (model);
    \draw[arr] (model) -- (tau);
    \draw[arr] (tau) -- node[above] {да} (auto);
    \draw[arr] (auto) -- (qa);
    \draw[arr] (qa) -- (ds);
    \draw[arr] (ds.north) |- (retrain.east);
    \draw[dashed, arr] (retrain.west) to[out=180,in=90] node[midway, above, align=center] {обновление} (model.north);
    \draw[arr] (tau) -- node[below] {нет} (manual);
    \draw[arr] (manual.east) -| (qa.south);
\end{tikzpicture}
\end{document}
```

- Порог $\tau$ калибруется на пилоте: 100–300 объектов с эталоном, максимизируем precision авто-меток при приемлемом покрытии
- Логируем $c$ для каждой авто-метки — по ним потом видно дрейф и зону, где модель ошибается
- Датасет версионируется: $v_k$ — это вход следующего цикла, а не «финальный файл»

---

## Правила и эвристики

```python
import re

class AnnotationRules:
    spam_words = ("viagra", "casino", "lottery")
    url_re = re.compile(r"https?://\S+")

    def predict(self, text: str) -> str | None:
        low = text.lower()
        if any(w in low for w in self.spam_words):
            return "spam"
        if len(self.url_re.findall(low)) >= 3:
            return "spam"
        if len(low) < 20:
            return "short"
        return None      # не правило — уходит человеку или модели
```

- Правила дают **мгновенную и объяснимую** метку; `None` — это осознанный отказ, а не ошибка
- Покрытие и точность считайте по каждому правилу отдельно, иначе широкое правило «съест» узкое

---

## Точность и покрытие правил

<!-- доп. -->

| Правило | Precision | Coverage | Комментарий |
|:--------|----------:|---------:|:------------|
| Словарь спама | 0.98 | 0.06 | почти не ошибается, мало ловит |
| 3+ ссылки в тексте | 0.92 | 0.11 | хороший сигнал для ботов |
| Длина > 500 и 1 ссылка | 0.71 | 0.40 | шумно, но покрывает много |

- Правило с precision 0.7 **полезно**, если его можно скомбинировать с другим: вместе они дают и точность, и покрытие
- Не автоматизируйте класс, где **ошибка дороже часа разметки**: цена ложной метки быстро перекрывает экономию

> Ключевое: правило оценивают парой **(precision, coverage)**, а не одной цифрой «точность».

---

## Confident Learning

- Идея: сравнить **уверенность модели** с данной меткой и найти объекты, где они расходятся
- Предсказание $\hat{y}=\arg\max_j p_j$; кандидат на ошибку, если $\hat y \ne y$ и $p_{\hat y} > t$
- Порог $t$ отсекает пограничные случаи: мы ищем не «трудные», а **уверенно переубеждённые** метки

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    cell/.style={minimum size=0.95cm, draw, align=center},
    diag/.style={cell, fill=green!25},
    off/.style={cell, fill=red!18}]
    \useasboundingbox (-1.9,-2.2) rectangle (3.9,2.5);

    \node at (0.95,2.15) {$\tilde y$ (дано)};
    \node[rotate=90] at (-1.15,0) {$y$ (модель)};

    \foreach \i/\x in {1/0, 2/0.95, 3/1.9} {
        \node[font=\scriptsize] at (\x,1.65) {\i};
        \node[font=\scriptsize] at (-0.72,{1.0-0.95*(\i-1)}) {\i};
    }

    \node[diag] at (0,1.0) {0.86};
    \node[off]  at (0.95,1.0) {0.03};
    \node[off]  at (1.9,1.0) {0.01};
    \node[off]  at (0,0.05) {0.04};
    \node[diag] at (0.95,0.05) {0.79};
    \node[off]  at (1.9,0.05) {0.02};
    \node[off]  at (0,-0.9) {0.01};
    \node[off]  at (0.95,-0.9) {0.03};
    \node[diag] at (1.9,-0.9) {0.91};

    \node[align=center] at (0.95,-1.75) {off-diagonal = оценка шума};
\end{tikzpicture}
\end{document}
```

> Ключевое: Confident Learning оценивает шум **без эталона**, но опирается на калибровку модели.

---

## cleanlab на практике

```python
from cleanlab.filter import find_label_issues

issues = find_label_issues(
    labels=y,
    pred_probs=model.predict_proba(X),
    return_indices_ranked_by="self_confidence",
    frac_noise=0.02,        # проверить 2% самых подозрительных
)
```

- Смотрите **топ-N** и переразмечайте вручную, а не удаляйте пачкой: часть «ошибок» — спорные случаи
- Не удаляйте всё, что нашлось: редкий класс часто выглядит как шум для модели
- Следите за дрейфом: доля найденных ошибок должна падать, иначе проблема в данных или в калибровке

---

## HITL: принцип распределения усилий

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize]
    \useasboundingbox (-1.1,-2.7) rectangle (10.9,2.4);

    \fill[red!55]    (0,0) rectangle (2,0.9);
    \fill[orange!55] (2,0) rectangle (5,0.9);
    \fill[green!55]  (5,0) rectangle (10,0.9);
    \draw[thick] (0,0) rectangle (10,0.9);

    \node[align=center, text width=1.8cm] at (1,0.45) {эксперт\\разбирает};
    \node[align=center, text width=2.7cm] at (3.5,0.45) {человек\\подтверждает};
    \node[align=center, text width=4.5cm] at (7.5,0.45) {авто,\\$c>0.95$};

    \node[align=center] at (1,-0.45) {$c<0.6$};
    \node[align=center] at (3.5,-0.45) {$0.6\le c\le0.95$};
    \node[align=center] at (7.5,-0.45) {$c>0.95$};

    \node at (1,-1.25) {5\%};
    \node at (3.5,-1.25) {25\%};
    \node at (7.5,-1.25) {70\%};
    \node[gray] at (5.5,-1.75) {доли — пример, не норматив};

    \draw[-{Stealth}, thick] (0.2,1.45) -- (9.8,1.45);
    \node[above] at (5,1.5) {рост уверенности модели};
\end{tikzpicture}
\end{document}
```

- Зоны задаются **порогами**, а не интуицией: их калибруют по цене ошибки и доле ручной работы
- Дешёвые ошибки можно отдавать автопилоту, дорогие — всегда человеку, даже при высокой $c$

> Ключевое: HITL — это не «человек на всякий случай», а **маршрутизация по уверенности**.

---

## HITL: где человек реально нужен

- **Низкая уверенность**: модель не различает классы — решает человек
- **Конфликт моделей**: предразметка и правило расходятся — нужен арбитр
- **Новый класс / дрейф**: данных ещё нет в обучении — эксперт задаёт эталон
- **Дорогая ошибка**: медицина, финансы, безопасность — проверка обязательна
- **Обучающий сигнал**: часть объектов идёт в эталон и в обучение модели

| Тип случая | Кто решает |
|:-----------|:-----------|
| Уверенная авто-метка | никто, только выборочный QA |
| Средняя уверенность | разметчик по инструкции |
| Спорная граница классов | эксперт / владелец схемы |
| Новый класс или дрейф | эксперт + обновление инструкции |

---

## Масштабирование: очередь задач

```python
from celery import Celery

app = Celery("labels", broker="redis://localhost:6379/0")

@app.task(bind=True, max_retries=3, rate_limit="50/s")
def annotate_batch(self, ids):
    texts = load_texts(ids)
    scores = model.predict_proba(texts)[:, 1]
    auto = scores >= 0.95
    store(ids[auto], scores[auto])
    queue_manual(ids[~auto])
    return {"auto": int(auto.sum()), "manual": int((~auto).sum())}
```

- **Очередь** отделяет приём данных от разметки: пики не роняют пайплайн
- **Воркеры** масштабируются горизонтально; модель грузится один раз на процесс
- **Backpressure**: ограничивайте длину очереди и размер батча, иначе ручная очередь растёт быстрее, чем её разбирают

---

## Синтетика и аугментация

<!-- доп. -->

```python
import albumentations as A
import nlpaug.augmenter.word as naw

image_aug = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(p=0.3),
    A.Rotate(limit=10, p=0.3),
])
text_aug = naw.SynonymAug(aug_src="wordnet", aug_p=0.1)

aug_image = image_aug(image=img)["image"]
aug_text = text_aug.augment(text)
```

- **Distribution shift**: аугментации меняют распределение — проверяйте на реальной валидации, а не на синтетике
- **Shortcut learning**: модель цепляется за артефакт аугментации, а не за класс
- **Дубликаты**: копии одного объекта в train и test завышают метрики — дедуплицируйте до сплита

---

## KPI автоматизации

| Метрика | Как считать | Целевой ориентир |
|:--------|:------------|:-----------------|
| Доля авто-меток | авто / все объекты | 50–80% на зрелом потоке |
| Precision авто | эталонная выборка из авто | ≥ 0.95 для дешёвых ошибок |
| Стоимость на объект | бюджет / принятые объекты | ниже ручной разметки в 2–5 раз |
| Throughput | объектов в час на воркер | стабилен при росте потока |
| Доля переделок | возвраты / авто-метки | < 5% и не растёт |

- Метрики считайте **на одном окне** и с одинаковым эталоном, иначе сравнение бессмысленно
- Рост доли авто при падении precision — это не успех, а отложенная переделка

---

## Дашборд

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize]
    \useasboundingbox (-3.2,-2.7) rectangle (13.6,3.2);

    % gauge
    \draw[line width=10pt, red!70, line cap=round]    (120:2.2) arc[start angle=120, end angle=180, radius=2.2];
    \draw[line width=10pt, orange!80, line cap=round] (60:2.2)  arc[start angle=60,  end angle=120, radius=2.2];
    \draw[line width=10pt, green!65!black, line cap=round] (0:2.2) arc[start angle=0, end angle=60, radius=2.2];

    \draw[-{Stealth}, very thick] (0,0) -- (45:1.75);
    \fill (0,0) circle (2pt);
    \node at (0,-0.85) {автоматизация 75\%};
    \node at (-2.55,-0.25) {0};
    \node at (2.55,-0.25) {100};
    \node at (0,2.45) {50};

    % mini chart
    \draw[-{Stealth}] (5,-1.4) -- (12.0,-1.4) node[right] {недели};
    \draw[-{Stealth}] (5,-1.4) -- (5,2.7) node[above] {точность};

    \node[anchor=east] at (4.95,-1.0) {0.80};
    \node[anchor=east] at (4.95,0.8)  {0.90};
    \node[anchor=east] at (4.95,2.6)  {1.00};

    \draw[blue!75!black, thick] (5.6,0.8) -- (6.4,0.98) -- (7.2,0.8) -- (8.0,1.16)
        -- (8.8,0.98) -- (9.6,-0.28) -- (10.4,0.44) -- (11.2,0.8);
    \foreach \p in {(5.6,0.8),(6.4,0.98),(7.2,0.8),(8.0,1.16),(8.8,0.98),(10.4,0.44),(11.2,0.8)}
        \fill[blue!75!black] \p circle (1.8pt);
    \fill[red] (9.6,-0.28) circle (3pt);
    \draw[-{Stealth}, red] (9.9,-0.95) -- (9.65,-0.42);
    \node[red, align=center] at (10.5,-1.0) {drift};

    \node at (5.6,-1.75) {1};
    \node at (11.2,-1.75) {8};
\end{tikzpicture}
\end{document}
```

- Слева — **сводка** «сколько автоматизировано», справа — **тренд** точности авто-меток
- Провал на графике важнее среднего: он показывает, где нужен пересмотр порога или дообучение

---

## Best practices

- Начинайте с **правил и baseline**, автоматизацию добавляйте только поверх измеренного процесса
- Калибруйте порог на пилоте и фиксируйте его в конфиге, а не в голове дежурного
- Логируйте уверенность, версию модели и версию правил для каждой метки
- Считайте **стоимость ошибки**, а не только долю автоматизации
- Пересматривайте пороги и KPI после каждого дрейфа и каждого обновления модели

> Ключевое: автоматизация — это **управляемый компромисс** между покрытием, точностью и ценой проверки.

---

## Вопрос для обсуждения

**Какой процент автоматизации разметки приемлем для вашей задачи?**

Подсказка: сравните стоимость одной ошибки авто-метки (переделка, инцидент, штраф) со стоимостью часа разметчика. Если ошибка дороже часа — поднимайте порог и долю ручной проверки; если дешевле — агрессивнее автоматизируйте и следите за precision на эталоне.

---

## Резюме блока 4

- Автоматизация идёт по уровням: правила → модель-предразметка → LLM few-shot
- Предразметка — это контур с порогом, QA и дообучением, а не одноразовый скрипт
- Confident Learning и cleanlab находят шум без эталона, но требуют калибровки
- HITL маршрутизирует объекты по уверенности и цене ошибки
- KPI автоматизации — доля авто, precision, стоимость, throughput и переделки

---

<!-- _class: lead -->

# Блок 5
## Кейсы, пайплайн и этика

<!-- ~10 мин -->

---

## Кейс 1: NER для новостей

| Параметр | Значение |
|:---------|:---------|
| Данные | 10 000 новостных статей (ru/en) |
| Схема | PER, ORG, LOC, MISC |
| Срок | 2 месяца |
| Бюджет | ≈300 ч разметки, 2 разметчика |
| Выход | модель + датасет + инструкция |

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    box/.style={rectangle, rounded corners, draw, align=center, minimum height=1.0cm, minimum width=3.0cm, text width=2.75cm},
    arr/.style={->, semithick}]
    \node[box, fill=blue!10]   (n1) at (0,1.6)    {10K статей\\входной пул};
    \node[box, fill=orange!15] (n2) at (3.6,1.6)  {Предразметка\\BERT-NER};
    \node[box, fill=orange!15] (n3) at (7.2,1.6)  {Фильтр по\\уверенности $c$};
    \node[box, fill=orange!15] (n4) at (10.8,1.6) {2K авто\\8K на проверку};
    \node[box, fill=violet!12] (n5) at (10.8,-1.1){Активное обучение\\3K приоритетных};
    \node[box, fill=green!14]  (n6) at (7.2,-1.1) {Финальная\\модель};
    \node[box, fill=green!14]  (n7) at (3.6,-1.1) {Предразметка\\остатка};
    \node[box, fill=green!14]  (n8) at (0,-1.1)   {Валидация\\на эталоне};

    \draw[arr] (n1) -- (n2);
    \draw[arr] (n2) -- (n3);
    \draw[arr] (n3) -- (n4);
    \draw[arr] (n4.south) -- (n5.north);
    \draw[arr] (n5) -- (n6);
    \draw[arr] (n6) -- (n7);
    \draw[arr] (n7) -- (n8);
\end{tikzpicture}
\end{document}
```

- Схема фиксируется до старта: MISC — самая шумная категория

---

## Кейс 1: арифметика

| Этап | Расчёт | Часы |
|:-----|:-------|-----:|
| Ручная разметка всего пула | 10 000 × 40 с | 111 |
| Приёмка 2K авто-меток | 2 000 × 5 с | ~3 |
| Ручная разметка ядра | 3 000 × 35 с | ~29 |
| QA и переделка (10%) | 0,1 × 32 ч | ~3 |
| **Итого гибрид** | | **~35** |

> Ключевое: экономия ~3× — из **объёма ручной работы**, а не из скорости. Числа — пример, не бенчмарк.

---

## Кейс 2: детекция объектов

50 000 изображений · 5 разметчиков · боксы, 12 классов

- **100 эталонных изображений** — приёмка и регрессии
- **10% двойной разметки** — расхождения в арбитраж
- **Автопроверка геометрии** — битые боксы, пересечение > 0,9
- **Недельная калибровка** — 20 спорных кейсов
- **Согласие κ > 0,8**; ниже — пересмотр класса

> Ключевое: в CV качество держится на **геометрии и согласии**, а не на числе кадров.

---

## Кейс 3: sentiment на краудсорсинге

100 000 отзывов · 3 класса · фиксированный бюджет

| Слой | Что делает |
|:-----|:-----------|
| Weak supervision | ключевые слова и смайлы, покрытие ~60% |
| Краудсорсинг | люди размечают спорное и непокрытое |
| Агрегация | Dawid–Skene: надёжность исполнителя |
| Контроль | honeypots и скрытые дубли |

$$
P(y \mid \ell_1..\ell_m) \;\propto\; \pi_y \prod_{j=1}^{m} P(\ell_j \mid y,\ \text{worker}_j)
$$

- Honeypot pass rate < 0,9 → переобучение или отстранение

---

## Жизненный цикл данных

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    st/.style={rectangle, rounded corners, draw, align=center, minimum height=0.9cm, minimum width=2.3cm, text width=2.05cm},
    arr/.style={->, semithick}]
    \node[st, fill=blue!10]   (collect) at (90:3.3)   {сбор};
    \node[st, fill=orange!15] (label)   at (30:3.3)   {разметка};
    \node[st, fill=orange!15] (valid)   at (-30:3.3)  {валидация};
    \node[st, fill=violet!12] (vers)    at (-90:3.3)  {версионирование};
    \node[st, fill=green!14]  (train)   at (-150:3.3) {обучение};
    \node[st, fill=green!14]  (mon)     at (150:3.3)  {мониторинг};

    \draw[arr] (collect) to[bend left=12] (label);
    \draw[arr] (label)   to[bend left=12] (valid);
    \draw[arr] (valid)   to[bend left=12] (vers);
    \draw[arr] (vers)    to[bend left=12] (train);
    \draw[arr] (train)   to[bend left=12] (mon);
    \draw[arr, red!70!black] (mon) to[bend left=12] (collect);
    \node[red!70!black, font=\scriptsize\bfseries] at (-2.9,4.15) {дрейф};
\end{tikzpicture}
\end{document}
```

- Каждый переход — **артефакт**: датасет, отчёт QA, версия модели; нет артефакта — нет перехода
- **Дрейф** не алертит, а замыкает цикл: данные возвращаются в сбор с новыми метками

---

## Версионирование датасетов

```bash
dvc init
dvc add data/raw/news.jsonl
dvc add data/labeled/v3
git add data/raw/news.jsonl.dvc data/labeled/v3.dvc .gitignore
git commit -m "data: labeled v3 (NER, 12k spans)"
dvc remote add -d storage s3://bucket/dvc
dvc push
git tag -a data-v3 -m "NER dataset v3"
git push --tags
```

- DVC держит в git **хэши и метаданные**, сами данные — в объектном хранилище
- Тег связывает код, датасет и модель: без этого эксперимент не воспроизводится через месяц

---

## Метаданные разметки

```json
{
  "dataset": "news_ner", "version": "3.1.0",
  "created": "2026-09-14", "instruction_sha": "9f2c1a",
  "schema": {"labels": ["PER", "ORG", "LOC", "MISC"]},
  "annotators": ["a01", "a07", "a12"], "n_items": 12480,
  "source": "news_2024_2026.jsonl", "n_spans": 31204,
  "agreement": {"kappa": 0.84, "double_labeled": 0.1},
  "gold": "gold_100.jsonl", "model": "bert-ner-ru-1.4",
  "license": "internal"
}
```

- **Схема и хэш инструкции** — по каким правилам размечали
- **Разметчики** — для аудита и переобучения людей
- **Происхождение и лицензия** — можно ли учить модель
- **Согласие и gold** — доверие к датасету, а не размер

---

## Мониторинг в продакшене

| Метрика | Сигнал | Действие |
|:--------|:-------|:---------|
| Доля HITL-обращений | ↑ на 20% за неделю | проверить порог и дрейф |
| Средняя уверенность | ↓ или горб у 0,5 | дообучение, ревизия |
| Распределение классов | новый класс > 1% | добавить класс |
| Доля переделок | > 5% | аудит инструкции |
| A/B на эталоне | падение precision | откат, разбор |

- Мониторить надо **вход и выход разметки**, а не только метрику модели на отложенной выборке

---

## Continuous annotation

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    st/.style={rectangle, rounded corners, draw, align=center, minimum height=0.9cm, minimum width=2.3cm, text width=2.05cm},
    arr/.style={->, semithick}]
    \node[st, fill=green!14]  (prod)    at (90:3.3)   {прод-модель};
    \node[st, fill=blue!10]   (log)     at (30:3.3)   {сбор\\предсказаний};
    \node[st, fill=orange!15] (filter)  at (-30:3.3)  {фильтр низкой уверенности};
    \node[st, fill=orange!15] (queue)   at (-90:3.3)  {очередь разметки};
    \node[st, fill=violet!12] (review)  at (-150:3.3) {валидация};
    \node[st, fill=green!14]  (train)   at (150:3.3)  {обучение};

    \draw[arr] (prod)   to[bend left=12] (log);
    \draw[arr] (log)    to[bend left=12] (filter);
    \draw[arr] (filter) to[bend left=12] (queue);
    \draw[arr] (queue)  to[bend left=12] (review);
    \draw[arr] (review) to[bend left=12] (train);
    \draw[arr] (train)  to[bend left=12] (prod);
\end{tikzpicture}
\end{document}
```

- Петля окупается только при **дешёвой разметке одного объекта** — иначе очередь не разбирается
- Порог фильтра пересматривается по precision на эталоне, а не «когда захотелось»

---

## Инструменты: open source и commercial

| Open source | Commercial |
|:-----------|:-----------|
| Label Studio — self-hosted, всё | Labelbox — операции, SLA |
| CVAT — видео, боксы | Scale AI — данные «под ключ» |
| Doccano — текст, NER | Supervisely — CV-платформа |
| Labelme — маски, полигоны | Ground Truth — процесс AWS |
| — | Google Vertex AI — managed |

- OSS — за **self-hosted и кастомные схемы**, commercial — за скорость запуска
- Считайте не лицензию, а **стоимость владения**

---

## Библиотеки

```python
from modAL.models import ActiveLearner
learner = ActiveLearner(estimator=clf, X_training=X0, y_training=y0)
idx, _ = learner.query(X_pool, n_instances=64)
learner.teach(X_pool[idx], y_new)
```

```python
from snorkel.labeling import PandasLFApplier
from snorkel.labeling.model import LabelModel
L_train = PandasLFApplier(lfs=lfs).apply(df_train)
probs = LabelModel(cardinality=2).fit(L_train).predict_proba(L_train)
```

```python
from cleanlab.classification import CleanLearning
cl = CleanLearning(clf=base_model)
issues = cl.find_label_issues(X=X, y=y)
cl.fit(X, y)
```

→ семинар: полные листинги и разбор API

---

## Этика: оплата и условия труда

| Оплата | Условия труда |
|:-------|:--------------|
| Ставка за час, не «за задачу» | Норма выработки — заранее |
| Бонус за качество, не за скорость | Перерывы, ротация задач |
| Переделки по вине инструкции — оплата | Апелляция решения QA |
| Имя в датасете — по желанию | Нагрузка: модерация |

- Дешёвая разметка оплачена **чужой усталостью** — видно по качеству через 2–3 недели

> Ключевое: этика — это **структура оплаты и KPI**, а не декларация.

---

## Bias в разметке

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\usetikzlibrary{arrows.meta, positioning, matrix}
\begin{document}
\begin{tikzpicture}[font=\scriptsize,
    box/.style={rectangle, rounded corners, draw, align=center, minimum height=0.95cm, minimum width=2.6cm, text width=2.3cm},
    arr/.style={->, semithick}]
    \node[box, fill=blue!10]   (instr) at (0,2.1)  {инструкции и схема};
    \node[box, fill=orange!15] (ann)   at (4.6,0)  {разметчики};
    \node[box, fill=green!14]  (model) at (0,-2.1) {модель};
    \node[box, fill=violet!12] (prod)  at (-4.6,0) {данные в\\продакшене};
    \node[circle, draw, thick, fill=red!10, align=center, minimum size=2.6cm, text width=2.2cm] (ctr) at (0,0) {ошибка\\возвращается\\как истина};

    \draw[arr] (instr) -- (ann);
    \draw[arr] (ann) -- (model);
    \draw[arr] (model) -- (prod);
    \draw[arr] (prod) -- (instr);
\end{tikzpicture}
\end{document}
```

- **Разнообразие команды**: разные диалекты, возраст, домен — иначе «норма» одна на всех
- **Слепая разметка**: разметчик не видит предсказание модели и метку коллеги
- **Аудит подгрупп**: метрики отдельно по полу, возрасту, языку, а не только средний F1
- **Ревизия схемы**: класс, который всегда размечают по-разному, — плохо определён

---

## Конфиденциальность

- **Анонимизация до разметки**: PII вырезается или заменяется плейсхолдерами на входе пайплайна
- **Минимальные права**: разметчик видит только свою порцию, экспорт — только у владельца
- **NDA и обучение**: подрядчики подписывают договор, а не «соглашаются галочкой»
- **Сроки хранения**: сырые данные и логи удаляются по политике, а не «когда-нибудь»
- **GDPR/152-ФЗ**: основание обработки, право на удаление, трансграничная передача — до старта

> Ключевое: разметка — это **обработка персональных данных** людьми вне вашего контура; проектируйте это как риск, а не как деталь.

---

## Будущее: foundation models

- Предразметка «из коробки»: zero/few-shot вместо своей модели
- Разметчик — **арбитр и редактор**, а не исполнитель
- Схемы проще: меньше классов, свободный текст на выходе
- Дистилляция большой модели в маленькую — часть пайплайна
- Экономика: платим за токены и проверку, не за часы

<!-- доп. -->
- **LLM-судья смещён**: длина, позиция, собственный стиль
- **Дорого на масштабе**: 100K объектов × токены дороже разметчика
- **Нет гарантий**: нет калибровки и воспроизводимости

> Ключевое: foundation-модели снижают **стоимость черновика**, но не отменяют эталон, QA и ответственность за метку.

---

## Декларативная разметка

```python
pipeline = AnnotationPipeline(
    source=JsonlSource("data/raw/*.jsonl"),
    prelabel=ModelPrelabel("bert-ner", version="1.4", threshold=0.9),
    route=RouteByConfidence(auto=0.95, human=0.6),
    review=SampleReview(rate=0.1, gold="gold_100.jsonl"),
    export=Export("datasets/ner/v4", format="spans"),
)
pipeline.run()
```

- Пайплайн лежит в git рядом с данными: шаг, порог и версия модели — **часть артефакта**, а не память дежурного
- Любое изменение процесса — diff в коде и новая версия датасета, а не «поправили на проде»

---

## Ключевые выводы

- Разметка — **производственный процесс**: стоимость, пропускная способность, качество, версии
- Дорогие задачи определяются числом решений на объект, а не типом данных
- Активное обучение и weak supervision экономят метки, но требуют baseline для доказательства
- Качество держится на эталоне, двойной разметке, согласии и живых инструкциях
- Автоматизация — управляемый компромисс: покрытие × точность × цена проверки

> Ключевое: побеждает не тот, кто купил платформу, а тот, кто **управляет неопределённостью** задачи и людьми.

---

## Домашнее задание

| Задание | Что сдать | Критерий |
|:--------|:----------|:---------|
| 1. Разметить 300 объектов по готовой схеме | экспорт JSON + скриншот статистики | согласие с эталоном ≥ 0,85 |
| 2. Прогнать AL на своём датасете | ноутбук + кривая quality vs budget | есть честный random baseline |
| 3. Смета проекта на 20K объектов | таблица «часы / деньги» | учтены QA и переделки |
| 4. Инструкция разметчика | 1 страница | есть спорные кейсы и допуски |

---

## Литература

1. Settles B. *Active Learning Literature Survey*. UW–Madison, 2012.
2. Ratner A. et al. *Snorkel: Rapid Training Data Creation*. VLDB, 2020.
3. Northcutt C. et al. *Confident Learning*. JAIR, 2021.
4. Monarch R. *Human-in-the-Loop Machine Learning*. Manning, 2021.
5. Sambasivan N. et al. *“Everyone wants to do the model work”*. CHI, 2021.
6. Label Studio Docs — labelstud.io/docs
7. Snorkel Tutorial — snorkel.ai/docs
8. cleanlab Docs — docs.cleanlab.ai

---

## Вопросы для обсуждения

- Где в вашем проекте **самое дорогое решение** на один объект — и можно ли его декомпозировать?
- Какой у вас эталон и кто имеет право его менять?
- Что произойдёт с пайплайном, если завтра дрейфанёт 20% входа?
- Как вы измеряете качество разметки, кроме «посмотрели глазами»?
- Кто отвечает за ошибку авто-метки, попавшую в продакшен?

**Контакты:** чат курса · семинар — разбор кода блоков 2–4

---

<!-- _class: lead -->

# Спасибо за внимание!

**Следующая лекция: ETL/ELT пайплайны и оркестрация**
