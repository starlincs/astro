.PHONY: check lint format typecheck test fix cov cov-html docs docs-serve build

check: lint format typecheck test

lint:
	ruff check src tests

format:
	ruff format --check src tests

typecheck:
	ty check

test:
	pytest

cov:
	pytest -m ""

fix:
	ruff check --fix src tests
	ruff format src tests

cov-html:
	pytest --cov=astro --cov-report=html

docs:
	sphinx-build -b html docs docs/_build/html

docs-serve:
	sphinx-autobuild docs docs/_build/html --open-browser

build:
	python -m build
	pip install --force-reinstall dist/*.whl
	python -c "import astro; print(astro.__version__)"
