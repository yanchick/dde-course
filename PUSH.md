# Публикация на GitHub Pages

Репозиторий уже создан локально, коммит сделан, remote `origin` добавлен. Осталось создать пустой публичный репозиторий на GitHub и отправить ветку `main`.

## 1. Создать репозиторий

Вариант через веб-интерфейс:

1. Откройте <https://github.com/new>.
2. Имя: `dde-course`.
3. Владелец: `yanchick`.
4. Видимость: **Public**.
5. Не добавляйте README, `.gitignore` и лицензию — они уже есть в локальном репозитории.

Вариант через GitHub CLI:

```bash
gh repo create yanchick/dde-course --public --source=. --remote=origin --push
```

`--push` сразу отправит `main`; если хотите сначала проверить настройки — уберите его и выполните шаг 2 вручную.

## 2. Отправить ветку

```bash
cd /home/yan/workspace/dde-course
git push -u origin main
```

Если remote ещё не добавлен:

```bash
git remote add origin https://github.com/yanchick/dde-course.git
git push -u origin main
```

## 3. Включить GitHub Pages

1. Откройте репозиторий → **Settings** → **Pages**.
2. В блоке **Build and deployment** выберите **Source: GitHub Actions**.
3. Дождитесь завершения workflow **Deploy course site** на вкладке **Actions**.
4. Сайт будет доступен по адресу <https://yanchick.github.io/dde-course/>.

Workflow `.github/workflows/pages.yml` запускается на каждый push в `main` и вручную через **Run workflow**. Он собирает слайды, сайт и выкладывает каталог `site`.

## 4. Проверка

```bash
gh run list --workflow=pages.yml
gh run watch
```

Если сборка упала на шаге `mkdocs build --strict`, проверьте ссылки и frontmatter: strict-режим превращает предупреждения в ошибки. Локально то же самое проверяет `make build`.

## Если репозиторий уже существует

```bash
git -C /home/yan/workspace/dde-course remote -v
git -C /home/yan/workspace/dde-course remote set-url origin https://github.com/yanchick/dde-course.git
```

Не используйте `git push --force`: история должна оставаться линейной.
