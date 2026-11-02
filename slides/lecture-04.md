---
marp: true
theme: default
size: 16:9
paginate: true
math: katex
title: "Лекция 4: Сложная предобработка и трансформация данных"
author: "Инжиниринг данных (продвинутый уровень)"
footer: "Сложная предобработка и трансформация данных — Лекция 4"
---

<!--
ОБЩИЕ ЗАМЕТКИ К ПРЕЗЕНТАЦИИ
- Хронометраж: ~90 минут. Блок 1 — 30 мин, Блок 2 — 20 мин, Блок 3 — 20 мин, Блок 4 — 15 мин + вступление и итоги
- Баланс: теория ↔ код. Слайды с кодом помечены «→ семинар», полные листинги разбираются на семинаре
- TikZ-блоки — самодостаточные standalone-документы; рендер отдаётся Kroki (endpoint /tikz/{png|svg}, см. https://kroki.io)
- Математика рендерится KaTeX (math: katex)
- Блоки `> Ключевое:` — главные выводы, которые нужно проговаривать
-->

<!-- _class: lead -->

# Сложная предобработка и трансформация данных

**Лекция 4**

Инжиниринг данных (продвинутый уровень)

---

## План лекции

| Блок | Тема | Время |
|:-----|:-----|:------|
| 1 | Feature Engineering для ML | ~30 мин |
| 2 | Работа с временными рядами | ~20 мин |
| 3 | Обработка текстовых данных (NLP) | ~20 мин |
| 4 | Изображения и мультимедиа | ~15 мин |

**Формат:** теория + код → детальный разбор кода на семинаре

**Сквозная идея:** любой источник данных (числа, время, текст, медиа) сводится к **матрице признаков** $X \in \mathbb{R}^{n \times d}$, которую понимает модель.

---

## Карта лекции

```tikz
\documentclass[tikz]{standalone}
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian]{babel}
\begin{document}
\begin{tikzpicture}[font=\small,
    box/.style={rectangle, rounded corners, draw, minimum height=1.1cm, minimum width=2.7cm, align=center},
    num/.style={rectangle, rounded corners, draw, minimum height=1.1cm, minimum width=3.2cm, align=center, fill=orange!25},
    arr/.style={->, thick}]
    \node[box, fill=blue!10] (raw) at (0,0) {Сырые данные:\\файлы, БД, API};
    \node[num] (fe) at (4.6,0) {Блок 1:\\Feature Engineering};
    \node[num, fill=green!20] (ts) at (4.6,-2.3) {Блок 2:\\Временные ряды};
    \node[num, fill=cyan!20] (nlp) at (4.6,-4.6) {Блок 3:\\Обработка текста};
    \node[num, fill=violet!20] (cv) at (4.6,-6.9) {Блок 4:\\Мультимедиа};
    \node[box, fill=green!15] (mat) at (9.8,-2.3) {Матрица признаков\\$X$ ($n$ объектов, $d$ признаков)};
    \node[box, fill=green!15] (model) at (14.0,-2.3) {Модель ML};
    \draw[arr] (raw) -- (fe);
    \draw[arr] (raw) to[out=-90, in=180] (ts);
    \draw[arr] (raw) to[out=-90, in=180] (nlp);
    \draw[arr] (raw) to[out=-90, in=180] (cv);
    \draw[arr] (fe) -- (mat);
    \draw[arr] (ts) -- (mat);
    \draw[arr] (nlp) -- (mat);
    \draw[arr] (cv) -- (mat);
    \draw[arr] (mat) -- (model);
\end{tikzpicture}
\end{document}
```

> Ключевое: предобработка — **мост** между «сырым» источником данных и моделью. Качество этого моста определяет потолок качества модели.

---

## Цели лекции

После лекции вы сможете:

- **Обосновать**, почему качество признаков важнее выбора конкретного алгоритма
- **Выбирать** метод масштабирования, кодирования и импутации под тип данных и алгоритм
- **Строить** признаки для временных рядов без утечки данных
- **Превращать** текст в числовые векторы — от TF-IDF до BERT
- **Проектировать** пайплайн подготовки изображений, аудио и мультимодальных данных

---

## Почему признаки важнее модели

<!-- 5 мин — мотивация -->

- По опросам практиков, **60–80% времени** data-специалиста уходит на подготовку данных, а не на модели
- Модель не может «вытащить» информацию, которой нет в признаках
- Один и тот же алгоритм (например, градиентный бустинг) на хороших признаках часто обгоняет «продвинутую» модель на сырых данных

$$ \text{Качество} \approx \underbrace{\text{данные и признаки}}_{\text{потолок}} \;+\; \text{алгоритм} $$

> Ключевое: **garbage in — garbage out**. Сначала признаки, потом тюнинг модели.

---

<!-- _class: lead -->

# Раздел 1
## Feature Engineering для ML

<!-- ~30 мин -->

---

## Что такое Feature Engineering

**Определение:** превращение сырых данных в признаки, которые максимизируют предсказательную силу модели.

Пять составляющих:

- **Трансформация** — масштабирование, логарифм, биннинг
- **Кодирование** — категории → числа, векторы, эмбеддинги
- **Генерация** — комбинации, агрегаты, предметные признаки
- **Импутация** — заполнение пропусков
- **Отбор** — отсечение шума и избыточности

---

## Типы признаков

| Тип | Примеры | Типичная обработка |
|-----|---------|--------------------|
| Числовые | возраст, цена, метрики | масштабирование, биннинг, $\log$ |
| Категориальные | город, категория товара | One-Hot, Target Encoding |
| Бинарные | флаг подписки | уже $0/1$; индикаторы пропусков |
| Временные | дата, timestamp | лаги, цикличность, сезонность |
| Текстовые | отзывы, описания | TF-IDF, эмбеддинги |
| Производные | площадь, BMI, CTR | создаются вручную |

> Ключевое: тип признака диктует **набор применимых методов** — сначала классифицируйте данные, потом выбирайте инструменты.

---

## Зачем масштабировать числовые признаки

<!-- 4 мин -->

Чувствительны к масштабу: линейная/логистическая регрессия, SVM, kNN, кластеризация, нейросети (градиентный спуск).

```tikz
\documentclass[tikz]{standalone}
\begin{document}
\begin{tikzpicture}[scale=0.62]
    % До масштабирования
    \draw[->] (0,0) -- (8,0) node[right] {$x_1$};
    \draw[->] (0,0) -- (0,8) node[above] {$x_2$};
    \foreach \k in {0.7,1.3,2.0,2.8,3.7,4.7,5.8,7.0} {
        \draw[blue!60, thick] (0,0) ellipse ({0.18*\k} and {\k});
    }
    \draw[red!80!40!black, very thick, ->] (1.2,1.2) -- (0.5,2.8) -- (0.9,3.6) -- (0.45,5.2);
    \node[align=center] at (4,-1.5) {До: овалы вытянуты,\\градиент «петляет»};
    % После масштабирования
    \begin{scope}[xshift=11cm]
        \draw[->] (0,0) -- (8,0) node[right] {$x_1'$};
        \draw[->] (0,0) -- (0,8) node[above] {$x_2'$};
        \foreach \k in {0.7,1.3,2.0,2.8,3.7,4.7,5.8,7.0} {
            \draw[blue!60, thick] (0,0) circle ({\k*0.55});
        }
        \draw[red!80!40!black, very thick, ->] (0,0) -- (3.8,3.8);
        \node[align=center] at (4,-1.5) {После: круги,\\градиент идёт напрямую};
    \end{scope}
\end{tikzpicture}
\end{document}
```

- Древесные модели (Random Forest, XGBoost) **не требуют** масштабирования — их сплиты инвариантны к монотонным преобразованиям

---

## Методы масштабирования

| Метод | Формула | Выход | Устойчивость к выбросам |
|-------|---------|-------|--------------------------|
| Min-Max | $\dfrac{x - x_{\min}}{x_{\max} - x_{\min}}$ | $[0,1]$ | ✗ |
| Z-score | $\dfrac{x - \mu}{\sigma}$ | $\mu=0,\ \sigma=1$ | средняя |
| Robust | $\dfrac{x - \text{медиана}}{IQR}$ | центрирован | ✓ |
| Max-Abs | $\dfrac{x}{\max |x|}$ | $[-1,1]$ | ✗ |

> Ключевое: **fit только на train**, transform — и на train, и на test. Параметры, оценённые на всей выборке, — классическая утечка данных.

---

## Сравнение трансформаций

```tikz
\documentclass[tikz]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\begin{document}
\begin{tikzpicture}
\begin{axis}[
    width=12cm, height=6.5cm,
    xlabel={Исходное значение $x$},
    ylabel={Трансформированное значение},
    legend pos=north west, grid=major,
    domain=0:100, samples=200,
    ymin=-2.6, ymax=2.6
]
\addplot[blue, thick] {x/100};
\addlegendentry{Min-Max: $[0,1]$}
\addplot[red, thick] {(x-50)/28.87};
\addlegendentry{Z-score: $\mu=50$, $\sigma\approx28.9$}
\addplot[green!55!black, thick] {(x-50)/40};
\addlegendentry{Robust: медиана 50, IQR 40}
\end{axis}
\end{tikzpicture}
\end{document}
```

- Min-Max сохраняет форму распределения, но «сжимает» всё в $[0,1]$
- Z-score не ограничивает диапазон — выбросы остаются заметными
- Robust ориентируется на квартили — оптимален при «грязных» данных

---

## Биннинг (дискретизация)

**Мотивация:** подавить шум, уменьшить влияние выбросов, добавить нелинейности в линейные модели, упростить интерпретацию.

```tikz
\documentclass[tikz]{standalone}
\begin{document}
\begin{tikzpicture}[font=\small]
    \node[anchor=east, align=right] at (-0.3,1.5) {Equal-width:\\равная ширина};
    \foreach \x/\l in {0/{[0,25)}, 3/{[25,50)}, 6/{[50,75)}, 9/{[75,100]}} {
        \draw[blue!70!black, very thick] (\x,0.9) rectangle (\x+3,1.8);
        \node[white, font=\scriptsize] at (\x+1.5,1.35) {\l};
    }
    \node[anchor=east, align=right] at (-0.3,-1.2) {Equal-frequency:\\равное число\\наблюдений};
    \draw[green!50!black, very thick] (0,-2.4) rectangle (4.5,-1.5);
    \draw[green!50!40!black, very thick] (4.5,-2.4) rectangle (5.7,-1.5);
    \draw[green!50!black, very thick] (5.7,-2.4) rectangle (8.4,-1.5);
    \draw[green!50!40!black, very thick] (8.4,-2.4) rectangle (12,-1.5);
    \foreach \p in {1,2,3,4} {\fill (0.9*\p,-1.95) circle (1.7pt);}
    \foreach \p in {4.65,4.95,5.25,5.55} {\fill (\p,-1.95) circle (1.7pt);}
    \foreach \p in {6.3,7.0,7.7,8.1} {\fill (\p,-1.95) circle (1.7pt);}
    \foreach \p in {9.0,9.9,10.8,11.4} {\fill (\p,-1.95) circle (1.7pt);}
\end{tikzpicture}
\end{document}
```

- **Equal-width** (`pd.cut`, `bins=5`) — чувствителен к выбросам
- **Equal-frequency** (`pd.qcut`, `q=5`) — чаще лучший выбор
- **Custom bins** — содержательные границы: $[0,18), [18,35), [35,60), [60,100]$

---

## Логарифмическая и степенная трансформация

<!-- 5 мин -->

Применяются к **скошенным** распределениям: доходы, цены, размеры аудиторий.

- Сжимают правый хвост → приближают распределение к нормальному
- Стабилизируют дисперсию (гомоскедастичность для линейных моделей)

$$ X_{\log} = \log(X + 1), \qquad \text{Box–Cox: } y^{(\lambda)} = \frac{y^\lambda - 1}{\lambda} $$

```tikz
\documentclass[tikz]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\begin{document}
\begin{tikzpicture}
    \begin{axis}[
        name=before, width=6.8cm, height=5cm,
        title={До: скошенное}, xlabel={Значение}, ylabel={Частота},
        ymin=0, domain=0:10, samples=80
    ]
    \addplot[blue!70!black, fill=blue!25, thick] {2.8*exp(-x/2)};
    \end{axis}
    \begin{axis}[
        at={(before.east)}, anchor=west, xshift=1.1cm,
        width=6.8cm, height=5cm,
        title={После: ближе к нормальному}, xlabel={Значение}, ylabel={Частота},
        ymin=0, domain=-3:3, samples=80
    ]
    \addplot[red!70!40!black, fill=red!25, thick] {exp(-x^2/2)/sqrt(2*pi)};
    \end{axis}
\end{tikzpicture}
\end{document}
```

> Ключевое: $\log(X+1)$ — для данных с нулями; Box–Cox — для строго положительных; Yeo–Johnson работает и с отрицательными.

---

## Категориальные признаки: One-Hot Encoding

<!-- 6 мин -->

Принцип: каждая категория → отдельный бинарный столбец.

```tikz
\documentclass[tikz]{standalone}
\begin{document}
\begin{tikzpicture}[font=\small,
    cell/.style={draw, minimum width=1.6cm, minimum height=0.8cm, align=center},
    one/.style={draw, minimum width=1.6cm, minimum height=0.8cm, align=center, fill=green!25},
    zero/.style={draw, minimum width=1.6cm, minimum height=0.8cm, align=center, fill=white}]
    \node[cell, fill=gray!20] at (0,1.1) {Цвет};
    \node[cell, fill=gray!20] at (1.8,1.1) {is\_red};
    \node[cell, fill=gray!20] at (3.6,1.1) {is\_blue};
    \node[cell, fill=gray!20] at (5.4,1.1) {is\_green};
    \node[cell] at (0,0) {red};
    \node[one] at (1.8,0) {1};
    \node[zero] at (3.6,0) {0};
    \node[zero] at (5.4,0) {0};
    \node[cell] at (0,-1.1) {blue};
    \node[zero] at (1.8,-1.1) {0};
    \node[one] at (3.6,-1.1) {1};
    \node[zero] at (5.4,-1.1) {0};
    \node[cell] at (0,-2.2) {green};
    \node[zero] at (1.8,-2.2) {0};
    \node[zero] at (3.6,-2.2) {0};
    \node[one] at (5.4,-2.2) {1};
\end{tikzpicture}
\end{document}
```

```python
pd.get_dummies(df['color'])          # → семинар
pd.get_dummies(df, drop_first=True)  # убираем избыточный столбец
```

---

## Проблемы One-Hot и альтернативы

Проблемы при **высокой кардинальности** (город, IP, ID товара):

- Взрыв размерности: 100 тыс. категорий → 100 тыс. столбцов
- Разреженная матрица: почти одни нули
- Мультиколлинеарность: сумма dummy-столбцов равна константе

Решения:

- **Label Encoding** — порядковый номер (опасен: модель увидит ложный порядок)
- **Binary Encoding** — номер категории в двоичном виде, $\lceil\log_2 K\rceil$ столбцов
- **Frequency Encoding** — частота категории в выборке
- **Hashing Encoding** — хэш в фиксированное число столбцов

---

## Target Encoding

<!-- 5 мин -->

Идея: заменить категорию средним значением целевой переменной по ней.

$$ TE(c) = \frac{n_c \cdot \bar{y}_c + m \cdot \bar{y}_{global}}{n_c + m} $$

- $n_c$ — число наблюдений категории, $\bar{y}_c$ — её средний таргет
- $m$ — параметр сглаживания: при малых $n_c$ тянем к глобальному среднему
- Один столбец на категорию → нет взрыва размерности

> Ключевое: без сглаживания редкие категории переобучаются. Среднее таргета нужно считать **внутри кросс-валидации**, иначе — утечка.

---

## Сравнение методов кодирования

| Метод | Столбцов | Учитывает связь с таргетом | Риск переобучения | Подходит для |
|-------|----------|---------------------------|-------------------|--------------|
| One-Hot | $K$ | нет | низкий | линейные модели |
| Label | $1$ | нет | средний | деревья (осторожно) |
| Binary | $\lceil\log_2 K\rceil$ | нет | низкий | высокая кардинальность |
| Frequency | $1$ | косвенно | низкий | деревья |
| Target | $1$ | да | **высокий** | бустинги с CV |
| Embedding | $d \ll K$ | обучается | средний | нейросети |

> Практика: для линейных моделей — One-Hot; для бустинга — target/catboost-кодирование с валидацией.

---

## Embeddings для категорий

- Категория → плотный вектор размерности $d$ (обычно $d = 10\ldots100$)
- Веса эмбеддинга **обучаются вместе с моделью**
- Близкие категории (например, похожие города) получают близкие векторы

```python
# → семинар: keras / torch
embedding = nn.Embedding(num_categories, dim=16)
```

- Альтернатива «с нуля»: предобученные на графе/тексте векторы (geonames, wikidata)

---

## Пропуски: три механизма

<!-- 5 мин -->

```tikz
\documentclass[tikz]{standalone}
\usetikzlibrary{arrows.meta}
\begin{document}
\begin{tikzpicture}[
    box/.style={rectangle, rounded corners, draw, align=center, font=\small,
        minimum height=1.1cm, minimum width=4.0cm},
    arr/.style={-{Stealth[length=2.5mm]}, thick}]
    \node[box, fill=blue!10] (q) at (0,0) {Почему значение\\пропущено?};
    \node[box, fill=green!15] (mcar) at (-6,-2.8) {MCAR\\\scriptsize пропуск случаен:\\\scriptsize сбой датчика};
    \node[box, fill=yellow!20] (mar) at (0,-2.8) {MAR\\\scriptsize зависит от других\\\scriptsize наблюдаемых признаков};
    \node[box, fill=red!15] (mnar) at (6.5,-2.8) {MNAR\\\scriptsize зависит от самого\\\scriptsize пропущенного значения};
    \draw[arr] (q) -- (mcar);
    \draw[arr] (q) -- (mar);
    \draw[arr] (q) -- (mnar);
\end{tikzpicture}
\end{document}
```

Примеры:

- **MCAR** — сбой системы сбора данных (пропуски неинформативны)
- **MAR** — женщины реже указывают возраст: пропуск объясним признаком «пол»
- **MNAR** — люди с высоким доходом не отвечают про доход: пропуск информативен сам по себе

> Ключевое: механизм пропусков определяет **допустимые методы импутации** и то, можно ли просто удалить строки.

---

## Простые методы импутации

| Метод | Плюсы | Минусы |
|-------|-------|--------|
| Удаление строк | просто | теряем данные; при MNAR — смещение |
| Константа ($0$, "Unknown") | быстро, честно | модель может «не понять» |
| Среднее/медиана | просто | занижает дисперсию, портит корреляции |
| Мода | для категорий | игнорирует связи |
| Forward/Backward fill | для временных рядов | искажает сезонность при больших дырах |

**Трюк:** добавьте бинарный признак-индикатор `is_missing` — часто пропуск сам по себе информативен.

---

## KNN Imputation

- Для объекта с пропуском ищем $k$ ближайших соседей по **полным** признакам
- Пропущенное значение = среднее (или мода) значений соседей
- Учитывает похожесть объектов, но чувствителен к масштабу признаков и дорог вычислительно

```python
from sklearn.impute import KNNImputer
imputer = KNNImputer(n_neighbors=5)
X_filled = imputer.fit_transform(X)   # → семинар
```

---

## MICE (Multiple Imputation by Chained Equations)

```tikz
\documentclass[tikz]{standalone}
\usetikzlibrary{arrows.meta}
\begin{document}
\begin{tikzpicture}[
    box/.style={rectangle, rounded corners, draw, align=center, font=\small,
        minimum height=1.1cm, minimum width=3.0cm},
    arr/.style={-{Stealth[length=2.5mm]}, thick}]
    \node[box, fill=blue!12] (init) at (0,0) {Начальная\\импутация};
    \node[box, fill=orange!20] (it) at (5,0) {Итерации: для каждого\\признака с пропусками\\обучаем модель};
    \node[box, fill=green!20] (fin) at (11,0) {Сходимость и\\пул результатов};
    \draw[arr] (init) -- (it);
    \draw[arr] (it) -- (fin);
    \draw[arr] (it.north) .. controls (5,1.7) and (0,1.7) .. (init.north)
        node[midway, above, font=\scriptsize] {пока значения не стабилизируются};
\end{tikzpicture}
\end{document}
```

- Каждый признак с пропусками предсказывается моделью по остальным признакам
- Многократные запуски → честная оценка **неопределённости** импутации
- Дорого на больших данных; альтернатива — `sklearn` `IterativeImputer`
---

## Генерация признаков: полиномиальные

$$ [x_1, x_2] \;\rightarrow\; [1,\ x_1,\ x_2,\ x_1^2,\ x_1x_2,\ x_2^2] $$

- Позволяют линейной модели захватывать нелинейные зависимости (граница решения — кривая)
- Размерность растёт как $C_{d+r}^{r}$ — проклятие размерности при больших $d$ и $r$

```python
from sklearn.preprocessing import PolynomialFeatures
poly = PolynomialFeatures(degree=2, include_bias=False)  # → семинар
```

> Практика: degree 2–3 достаточно; дальше — переобучение. Комбинируйте с Lasso-регуляризацией.

---

## Интерактивные и предметные признаки

Примеры «ручных» комбинаций:

- Площадь = длина × ширина
- BMI = вес / рост²
- Цена за единицу = цена / количество
- Доля отказов = число отказов / число операций

Предметные знания (domain knowledge):

- для кредитного скоринга: отношение долга к доходу (DTI)
- для e-commerce: средний чек клиента за 30 дней
- для IoT: скорость = разность показаний / интервал

> Ключевое: лучшие признаки часто рождаются из **понимания предметной области**, а не из библиотек.

---

## Математические трансформации

| Семейство | Примеры | Когда помогает |
|-----------|---------|----------------|
| Степенные | $x^2,\ x^3,\ \sqrt{x}$ | нелинейности, сжатие хвостов |
| Логарифмические | $\log(x+1)$ | скошенные распределения |
| Экспоненциальные | $e^x$ | «перевёрнутая» скошенность |
| Обратные | $1/x,\ 1/(x+1)$ | асимптотические зависимости |
| Тригонометрические | $\sin,\ \cos$ | циклы (время суток, сезон) |
| Кусочные | $\max(0, x-\tau)$ | пороговые эффекты |

---

## Feature Selection: зачем

- **Переобучение** — лишние признаки дают модели возможность «запомнить» шум
- **Скорость** — обучение и инференс пропорциональны числу признаков
- **Интерпретируемость** — модель с 10 признаками объяснима, с 10 000 — нет

Три семейства методов:

```tikz
\documentclass[tikz]{standalone}
\usetikzlibrary{arrows.meta}
\begin{document}
\begin{tikzpicture}[
    box/.style={rectangle, rounded corners, draw, align=center, font=\small,
        minimum height=1.0cm, minimum width=3.4cm},
    arr/.style={-{Stealth[length=2.5mm]}, thick}]
    \node[box, fill=blue!12] (f) at (0,0) {Filter\\статистика признака};
    \node[box, fill=orange!18] (w) at (5,0) {Wrapper\\качество модели};
    \node[box, fill=green!18] (e) at (10,0) {Embedded\\отбор внутри обучения};
    \draw[arr, dashed] (f) -- (w) node[midway, above, font=\scriptsize] {дороже};
    \draw[arr, dashed] (w) -- (e) node[midway, above, font=\scriptsize] {дешевле};
\end{tikzpicture}
\end{document}
```

---

## Filter методы

Признак оценивается **без модели**: быстро, но не учитывает взаимодействия.

- **Корреляция** с таргетом (Pearson/Spearman)
- **Chi-square** — категориальный признак × категориальный таргет
- **ANOVA F** — числовой признак × категориальный таргет
- **Mutual Information** — ловит нелинейные зависимости

```python
from sklearn.feature_selection import mutual_info_classif
scores = mutual_info_classif(X, y)   # → семинар
```

> Осторожно: корреляция ловит **линейные** связи; MI чувствителен к шумной оценке плотности при малых выборках.

---

## Wrapper методы

Пробуем подмножества признаков и смотрим на качество модели.

- **RFE** (Recursive Feature Elimination): обучаем модель → ранжируем по важности → удаляем слабейший → повторяем
- **Forward/Backward Selection** — жадное добавление/удаление
- **Exhaustive Search** — полный перебор (реально только до ~15–20 признаков)

```python
from sklearn.feature_selection import RFE
rfe = RFE(estimator=LogisticRegression(), n_features_to_select=10)  # → семинар
```

Плюсы: учитывают взаимодействия. Минусы: $O(\text{моделей} \times \text{итераций})$ — дорого.

---

## Embedded методы

Отбор «встроен» в обучение модели.

- **Lasso (L1)** — зануляет коэффициенты → признак исключён
- **Ridge (L2)** — лишь сжимает коэффициенты
- **Elastic Net** — комбинация L1 + L2
- **Tree-based importance** — impurity/Gain (LightGBM, XGBoost)

$$ \text{Lasso: } \min_w \|y - Xw\|^2 + \lambda \|w\|_1 $$

> Практика: быстрый скрининг — MI/корреляция; финальный отбор — Lasso или важность бустинга; качество всегда проверяется на валидации.

---

## Сравнение методов отбора

```tikz
\documentclass[tikz]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\begin{document}
\begin{tikzpicture}
    \begin{axis}[
        width=12cm, height=7cm,
        xlabel={Вычислительная стоимость},
        ylabel={Качество отбора},
        xmin=0, xmax=10, ymin=0, ymax=10, grid=major
    ]
    \addplot[only marks, mark=*, blue, mark size=4pt] coordinates {(2,4)};
    \node[blue!80!black] at (axis cs:2,3.1) {Filter};
    \addplot[only marks, mark=*, red, mark size=4pt] coordinates {(8,8)};
    \node[red!80!black] at (axis cs:8,7.1) {Wrapper};
    \addplot[only marks, mark=*, green!60!black, mark size=4pt] coordinates {(5,7)};
    \node[green!55!40!black] at (axis cs:5,6.1) {Embedded};
    \end{axis}
\end{tikzpicture}
\end{document}
```

Компромисс «цена/качество»: на практике чаще всего — **Embedded**.

---

## Автоматический Feature Engineering

<!-- 4 мин -->

- **FeatureTools** — Deep Feature Synthesis: рекурсивно комбинирует примитивы (transform + aggregation) поверх реляционной схемы

```python
import featuretools as ft
es = ft.EntitySet(id="shop")
es = es.add_dataframe(dataframe_name="tx", dataframe=df,
                      index="tx_id", time_index="ts")
features = ft.dfs(entityset=es, target_dataframe_name="tx", max_depth=2)  # → семинар
```

- **tsfresh** — 700+ признаков для временных рядов + отбор релевантных
- Оба инструмента дают **сотни кандидатов** — дальше обязательно feature selection

---

## Дисбаланс классов: в чём проблема

<!-- 5 мин -->

```tikz
\documentclass[tikz]{standalone}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\begin{document}
\begin{tikzpicture}
\begin{axis}[
    width=9cm, height=6cm,
    ybar, bar width=1.6cm,
    ylabel={Объектов},
    symbolic x coords={Класс 0, Класс 1}, xtick=data,
    ymin=0, nodes near coords,
    nodes near coords style={font=\small}
]
\addplot[fill=blue!40] coordinates {(Класс 0, 9500) (Класс 1, 500)};
\end{axis}
\end{tikzpicture}
\end{document}
```

- Модель, всегда предсказывающая класс 0, получит accuracy 95% — и не поймает ни одного случая класса 1
- Смотрите не на accuracy, а на **precision/recall/F1**, **PR-AUC** и confusion matrix
- Проблема — не только в классах, но и в **разной цене ошибок** (fraud, болезнь)

---

## Методы борьбы с дисбалансом

| Метод | Идея | Риск |
|-------|------|------|
| Undersampling | выкинуть часть мажоритарного класса | теряем данные |
| Oversampling | дублировать миноритарный | переобучение на дублях |
| SMOTE / ADASYN | синтетические примеры между соседями | шумовые связи |
| class\_weight / scale\_pos\_weight | штраф за ошибки минорного класса | настройка весов |
| Ансамбли (BalancedRandomForest) | балансировка внутри бутстрапа | — |
| Tomek links / ENN | чистка границ классов | сложно на больших данных |

> Ключевое: **никогда** не балансируйте тестовую выборку — распределение теста должно отражать реальность.

---

## SMOTE: синтетические примеры

$$ x_{new} = x_i + \lambda \cdot (x_{neighbor} - x_i), \quad \lambda \sim U[0,1] $$

```tikz
\documentclass[tikz]{standalone}
\begin{document}
\begin{tikzpicture}[scale=0.85]
    % Миноритарный класс
    \fill[red!80!black] (1,1) circle (3pt) node[left] {$x_i$};
    \fill[red!80!40!black] (2,3) circle (3pt) node[above] {$x_{n}$};
    \fill[red!80!40!black] (3,2) circle (3pt);
    % Синтетическая точка
    \fill[magenta] (1.5,2) circle (3pt) node[right] {$x_{new}$};
    \draw[dashed, red!70!black, thick] (1,1) -- (2,3);
    % Мажоритарный класс
    \fill[blue!60!black] (5,1) circle (2pt);
    \fill[blue!60!40!black] (6,2) circle (2pt);
    \fill[blue!60!black] (7,1.5) circle (2pt);
    \fill[blue!60!40!20] (5.5,3) circle (2pt);
    \fill[blue!60!black] (6.5,2.5) circle (2pt);
    \node[red!80!black] at (4.2,-0.7) {$\bullet$ миноритарный};
    \node[blue!60!black] at (4.2,-1.3) {$\bullet$ мажоритарный};
    \node[magenta] at (4.2,-1.9) {$\bullet$ синтетический};
\end{tikzpicture}
\end{document}
```

Шаги: взять объект миноритарного класса → найти $k$ ближайших соседей из него же → выбрать случайного соседа → создать точку на отрезке между ними.

---

## Вопросы для самопроверки (блок 1)

1. Когда выбрать стандартизацию, а когда — Robust-масштабирование?
2. В чём риск target encoding и как его контролировать?
3. Чем MICE лучше подстановки среднего?
4. Почему для оценки модели с импутацией нельзя просто удалить строки с пропусками в тесте?
5. Какие метрики использовать при сильном дисбалансе классов?

---

## Резюме блока 1

- Масштабирование ускоряет сходимость и влияет на линейные/метрические модели
- Кодирование категорий выбирается по кардинальности и алгоритму
- Импутация должна учитывать **механизм пропусков**
- Генерация признаков — сочетание техники и предметных знаний
- Отбор признаков — защита от переобучения и проклятия размерности
- Дисбаланс лечится на **тренировочной** части, метрики — под задачу
