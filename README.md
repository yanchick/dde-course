# ДДЕ · ИТМО — сайт курса «Инжиниринг данных»

Статический сайт курса: программа, десять лекционных колод, семинары, проект и опросник самопроверки. Собран на MkDocs Material, слайды — Marp.

- Сайт: <https://yanchick.github.io/dde-course/>
- Репозиторий: <https://github.com/yanchick/dde-course>

## Структура

```text
docs/                 страницы сайта (Markdown)
overrides/            шаблон главной и кастомная шапка/футер
slides/               исходники колод Marp и ассеты
code/seminars/        студенческие скрипты и README семинаров
materials/            локальный архив исходников (в git не входит)
instructor/solutions/ полные решения (в git не попадают)
scripts/              сборка слайдов и проверки
.github/workflows/    публикация на GitHub Pages
```

`materials/` — локальный архив курса: он остаётся на диске и не коммитится. В репозиторий и на сайт попадают только `docs/`, `slides/` и `code/` (плюс конфигурация и скрипты сборки).

## Локальный запуск

Нужны Python 3.12+, Node.js 20+ и npm.

```bash
make install     # .venv + Python-зависимости + npm install
make serve       # собрать слайды и поднять mkdocs serve
```

Откройте <http://127.0.0.1:8000/>.

Другие команды:

```bash
make slides   # только HTML/PDF слайдов в docs/slides/
make build    # слайды + mkdocs build --strict
make check    # слайды, strict-сборка, проверка ссылок и публичных файлов
make clean    # удалить site/, docs/slides/, .cache/
```

Если `uv` не установлен, `make install` откатится на `python3 -m venv`. Слайды собираются локальным `node_modules/.bin/marp`, иначе через `npx`.

## Как добавить лекцию

1. Положите колоду в `slides/lecture-XX.md` с frontmatter:

   ```yaml
   ---
   marp: true
   theme: default
   size: 16:9
   paginate: true
   math: katex
   ---
   ```

2. Добавьте страницу `docs/lectures/XX-topic.md` по образцу соседних: заголовок, «О чём лекция», таблица материалов, «Дальше».
3. Добавьте пункт в `nav` в `mkdocs.yml` и строку в `docs/lectures/index.md` (и, при желании, на главной).
4. Запустите `make build`.

Слайды и PDF собираются автоматически из `slides/lecture-*.md`; в git они не коммитятся.

## Семинары

Студенческие скрипты лежат в `code/seminars/<slug>/seminar_XX.py`, планы занятий — в `plan.md`, инструкции по запуску и сдаче — в `README.md`. Полные решения хранятся в `instructor/solutions/` и исключены через `.gitignore`.

## Публикация

Push в `main` запускает GitHub Actions: установка зависимостей, сборка слайдов, `mkdocs build --strict`, выкладка артефакта на GitHub Pages. Пошаговая инструкция — в [PUSH.md](PUSH.md).

## Семестр

Семестр указан в `mkdocs.yml`:

```yaml
extra:
  semester: "Осень 2025"
```

Он выводится в футере. При смене семестра обновите это значение и, при необходимости, подписи на главной.

## Лицензии

- Код — [MIT](LICENSE).
- Тексты, слайды и задания — [CC BY-NC-SA 4.0](LICENSE-CONTENT.md).

Материалы курса предоставляются для обучения; формулировки заданий и состав колод могут меняться.
