# Makefile for running Amazon review scraper


.PHONY: help install install-pip test dev up down clean lint format type-check build logs

# Default target
help:
	@echo "Available targets:"
	@echo "  install     - Install dependencies with Poetry (if available) or pip"
	@echo "  install-pip - Install dependencies with pip"
	@echo "  test        - Run tests with coverage"
	@echo "  dev         - Run development server locally"
	@echo "  up          - Start services with docker-compose"
	@echo "  down        - Stop docker-compose services"
	@echo "  clean       - Clean up generated files and caches"
	@echo "  lint        - Run linting checks"
	@echo "  format      - Format code with black"
	@echo "  type-check  - Run type checking with mypy"
	@echo "  build       - Build Docker images"
	@echo "  logs        - Show docker-compose logs"

# Install dependencies
install:
	@if command -v poetry >/dev/null 2>&1; then \
		echo "Installing with Poetry..."; \
		poetry install --with dev; \
	else \
		echo "Poetry not found, installing with pip..."; \
		pip install -r requirements.txt; \
		pip install pytest pytest-asyncio pytest-cov vcrpy faker factory-boy black ruff mypy types-redis; \
	fi
	@echo "✅ Dependencies installed"

# Install with pip explicitly
install-pip:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov vcrpy faker factory-boy black ruff mypy types-redis
	@echo "✅ Dependencies installed with pip"

# Run tests
test:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html; \
	else \
		pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html; \
	fi

# Run development server
dev:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run uvicorn amazon_review_scraper.api:app --reload --host 0.0.0.0 --port 8080; \
	else \
		uvicorn amazon_review_scraper.api:app --reload --host 0.0.0.0 --port 8080; \
	fi

# Start Docker services
up:
	docker-compose up -d
	@echo "✅ Services started"
	@echo "API: http://localhost:8080"
	@echo "API Docs: http://localhost:8080/docs"
	@echo "Flower (if enabled): http://localhost:5555"

# Stop Docker services
down:
	docker-compose down
	@echo "✅ Services stopped"

# Build Docker images
build:
	docker-compose build
	@echo "✅ Docker images built"

# Show logs
logs:
	docker-compose logs -f

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	@echo "✅ Cleaned up"

# Linting
lint:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run ruff check src/; \
		poetry run flake8 src/; \
	else \
		ruff check src/; \
		flake8 src/; \
	fi

# Format code
format:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run black src/; \
		poetry run isort src/; \
	else \
		black src/; \
		isort src/; \
	fi

# Type checking
type-check:
	@if command -v poetry >/dev/null 2>&1; then \
		poetry run mypy src/; \
	else \
		mypy src/; \
	fi

# Run all checks
check: lint type-check test
	@echo "✅ All checks passed"

# Initialize project (first time setup)
init: install
	cp .env.example .env
	mkdir -p data logs
	@echo "✅ Project initialized"
	@echo "Please edit .env file with your configuration"

# Development with all services
dev-full:
	docker-compose --profile dev up

# Production deployment
deploy:
	docker-compose up -d --build
	@echo "✅ Deployed to production"
