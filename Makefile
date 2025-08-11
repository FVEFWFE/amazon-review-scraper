# Makefile for running Amazon review scraper


.PHONY: help install test dev up down clean lint format type-check build logs

# Default target
help:
	@echo "Available targets:"
	@echo "  install     - Install dependencies with Poetry"
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
	poetry install --with dev
	@echo "✅ Dependencies installed"

# Run tests
test:
	poetry run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

# Run development server
dev:
	poetry run uvicorn amazon_review_scraper.api:app --reload --host 0.0.0.0 --port 8080

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
	poetry run ruff check src/
	poetry run flake8 src/

# Format code
format:
	poetry run black src/
	poetry run isort src/

# Type checking
type-check:
	poetry run mypy src/

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
