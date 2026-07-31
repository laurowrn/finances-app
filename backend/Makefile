.PHONY: setup seed run test lint format

setup:
	uv venv --python 3.12 .venv
	uv pip install -e . --group dev

seed:
	.venv/bin/python -m app.seed

run:
	.venv/bin/uvicorn app.main:app --reload --port 8000

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check app tests

format:
	.venv/bin/ruff format app tests
