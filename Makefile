# Atalhos de desenvolvimento. Requer Python 3.11+ e Node 22+.
.PHONY: install data dev build check lint test

install:
	python3 -m venv .venv && .venv/bin/pip install -e "pipelines[dev]"
	cd web && npm install

data:
	.venv/bin/python -m dataan run

dev:
	cd web && npm run dev

build:
	cd web && npm run build

check: lint
	cd web && npm run check

lint:
	.venv/bin/ruff check pipelines
	.venv/bin/ruff format --check pipelines

test:
	cd pipelines && ../.venv/bin/python -m pytest -q
