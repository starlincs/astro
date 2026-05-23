.PHONY: check lint format typecheck test fix cov-html

check: lint format typecheck test

lint:
	ruff check src tests

format:
	ruff format --check src tests

typecheck:
	ty check

test:
	pytest

fix:
	ruff check --fix src tests
	ruff format src tests

cov-html:
	pytest --cov=astro --cov-report=html
