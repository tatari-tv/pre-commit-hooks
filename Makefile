.DEFAULT_GOAL := dev

.PHONY: all
all: dev unit-test type-check lint

# dev targets
.PHONY: dev
dev:
	uv sync


# Testing related targets
.PHONY: unit-test
unit-test: dev
	uv run pytest tests/python

.PHONY: type-check
type-check: dev
	uv run mypy

.PHONY: lint
lint: dev
	uv run pre-commit run --all-files


# Clean
.PHONY: clean
clean:
	rm -rf build/ dist/ .venv/ .mypy_cache/ .pytest_cache/
	rm -rf *.egg-info
	rm -rf .coverage
	find . -name '__pycache__' -delete
	find . -name '*.pyc' -delete
