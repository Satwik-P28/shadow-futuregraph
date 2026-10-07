PY := .venv/bin/python
UV := uv

.PHONY: setup dev test benchmark-local build lint

setup:
	$(UV) venv --python 3.12 .venv
	$(UV) pip install -e ".[dev]" --python $(PY)
	cd frontend && npm install

dev:
	$(PY) -m uvicorn shadow.api.app:app --app-dir backend --reload --host 127.0.0.1 --port 8000

test:
	$(PY) -m ruff check backend
	$(PY) -m pytest
	$(PY) -m coverage run -m pytest -q
	$(PY) -m coverage report
	cd frontend && npm test && npm run typecheck

benchmark-local:
	$(PY) -m shadow.benchmark.run --seeds 1000:1030 --run-id local-gate

build:
	cd frontend && npm run build

lint:
	$(PY) -m ruff check backend
	cd frontend && npm run lint && npm run typecheck
