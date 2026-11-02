SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install slides serve build clean check

install:
	@if command -v uv >/dev/null 2>&1; then \
		uv venv --python 3.12 $(VENV) 2>/dev/null || uv venv $(VENV); \
		uv pip install --python $(PY) -r requirements.txt; \
	else \
		python3 -m venv $(VENV); \
		$(PIP) install -r requirements.txt; \
	fi
	npm install

slides:
	bash scripts/build_slides.sh

serve: slides
	NO_MKDOCS_2_WARNING=1 $(PY) -m mkdocs serve

build: slides
	NO_MKDOCS_2_WARNING=1 $(PY) -m mkdocs build --strict

check: slides
	NO_MKDOCS_2_WARNING=1 $(PY) -m mkdocs build --strict
	$(PY) scripts/check_links.py
	bash scripts/check_public.sh

clean:
	rm -rf site docs/slides .cache
