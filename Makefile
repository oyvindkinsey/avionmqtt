.PHONY: help install install-dev format lint test test-cov clean

help:
	@echo "Available commands:"
	@echo "  make install        - Install package"
	@echo "  make install-dev    - Install package with dev dependencies"
	@echo "  make format         - Format code with black and isort"
	@echo "  make lint           - Run linters (flake8, mypy)"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage report"
	@echo "  make test-fast      - Run tests without slow tests"
	@echo "  make clean          - Clean build artifacts"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

format:
	black src tests
	isort src tests

lint:
	flake8 src tests
	mypy src

test:
	pytest

test-cov:
	pytest --cov=avionmqtt --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/index.html"

test-fast:
	pytest -m "not slow"

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
