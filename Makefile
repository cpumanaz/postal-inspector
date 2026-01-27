# =============================================================================
# Postal Inspector - Makefile
# =============================================================================
# AI-powered email security scanner
# Run 'make' or 'make help' for available targets
# =============================================================================

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------
SHELL := /bin/bash
.DEFAULT_GOAL := help

# Project settings
PROJECT_NAME := postal-inspector
PYTHON_VERSION := 3.12

# Docker settings
COMPOSE := docker compose
DOCKER_BUILDKIT ?= 1

# Paths
SRC_DIR := src
TEST_DIR := tests
COVERAGE_DIR := htmlcov

# UV settings
UV := uv
UV_RUN := $(UV) run

# Marker files for idempotency
VENV_MARKER := .venv/.installed
DEV_MARKER := .venv/.dev-installed

# -----------------------------------------------------------------------------
# Phony targets
# -----------------------------------------------------------------------------
.PHONY: help
.PHONY: install dev sync
.PHONY: test test-cov lint lint-fix format format-check type-check check
.PHONY: clean clean-all clean-docker
.PHONY: build build-no-cache up down logs restart status
.PHONY: logs-imap logs-processor logs-briefing logs-antivirus
.PHONY: shell-imap shell-processor shell-briefing
.PHONY: fetch-now test-briefing
.PHONY: briefing health

# =============================================================================
# Help
# =============================================================================

help:
	@echo ""
	@echo "Postal Inspector - AI-Powered Email Security Scanner"
	@echo "====================================================="
	@echo ""
	@echo "Installation:"
	@echo "  make install         Install production dependencies"
	@echo "  make dev             Install dev dependencies (lint, test, etc.)"
	@echo "  make sync            Force re-sync all dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test            Run tests"
	@echo "  make test-cov        Run tests with coverage report"
	@echo "  make lint            Run ruff linter (check only)"
	@echo "  make lint-fix        Run ruff linter with auto-fix"
	@echo "  make format          Format code with ruff"
	@echo "  make format-check    Check formatting without changes"
	@echo "  make type-check      Run mypy type checker"
	@echo "  make check           Run all quality checks (lint, type-check, test)"
	@echo "  make clean           Remove build artifacts and caches"
	@echo ""
	@echo "Docker:"
	@echo "  make build           Build all Docker images"
	@echo "  make build-no-cache  Build images without cache"
	@echo "  make up              Start all services (detached)"
	@echo "  make down            Stop all services"
	@echo "  make restart         Restart all services"
	@echo "  make status          Show service status"
	@echo "  make logs            Follow all service logs"
	@echo ""
	@echo "Docker Logs (individual):"
	@echo "  make logs-imap       Follow IMAP server logs"
	@echo "  make logs-processor  Follow mail processor logs"
	@echo "  make logs-briefing   Follow daily briefing logs"
	@echo "  make logs-antivirus  Follow antivirus logs"
	@echo ""
	@echo "Docker Shells:"
	@echo "  make shell-imap      Shell into IMAP container"
	@echo "  make shell-processor Shell into mail processor container"
	@echo "  make shell-briefing  Shell into briefing container"
	@echo ""
	@echo "Operations:"
	@echo "  make briefing        Generate daily briefing now"
	@echo "  make health          Check service health"
	@echo "  make fetch-now       Trigger immediate mail fetch (in container)"
	@echo "  make test-briefing   Test briefing generation (in container)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Remove Python build artifacts"
	@echo "  make clean-docker    Remove Docker images and volumes"
	@echo "  make clean-all       Remove all artifacts (Python + Docker)"
	@echo ""

# =============================================================================
# Installation
# =============================================================================

# Production install - installs only runtime dependencies
install: $(VENV_MARKER)

$(VENV_MARKER): pyproject.toml uv.lock
	@echo "Installing production dependencies..."
	$(UV) sync --no-dev
	@mkdir -p .venv
	@touch $(VENV_MARKER)
	@rm -f $(DEV_MARKER)

# Development install - includes dev dependencies (test, lint, type-check)
dev: $(DEV_MARKER)

$(DEV_MARKER): pyproject.toml uv.lock
	@echo "Installing development dependencies..."
	$(UV) sync --all-groups
	@mkdir -p .venv
	@touch $(DEV_MARKER)
	@rm -f $(VENV_MARKER)

# Force re-sync (useful when lock file changes or for troubleshooting)
sync:
	@echo "Force syncing all dependencies..."
	$(UV) sync --all-groups
	@mkdir -p .venv
	@touch $(DEV_MARKER)
	@rm -f $(VENV_MARKER)

# =============================================================================
# Development - Testing
# =============================================================================

test: dev
	$(UV_RUN) pytest $(TEST_DIR)/ -v

test-cov: dev
	$(UV_RUN) pytest $(TEST_DIR)/ --cov=postal_inspector --cov-report=term-missing --cov-report=html:$(COVERAGE_DIR)
	@echo "Coverage report generated in $(COVERAGE_DIR)/index.html"

# =============================================================================
# Development - Code Quality
# =============================================================================

# Lint check only (does not modify files)
lint: dev
	$(UV_RUN) ruff check $(SRC_DIR)/ $(TEST_DIR)/

# Lint with auto-fix
lint-fix: dev
	$(UV_RUN) ruff check --fix $(SRC_DIR)/ $(TEST_DIR)/

# Format code
format: dev
	$(UV_RUN) ruff format $(SRC_DIR)/ $(TEST_DIR)/

# Check formatting without modifying (useful for CI)
format-check: dev
	$(UV_RUN) ruff format --check $(SRC_DIR)/ $(TEST_DIR)/

# Type checking
type-check: dev
	$(UV_RUN) mypy $(SRC_DIR)/

# Run all quality checks
check: lint format-check type-check test
	@echo ""
	@echo "All checks passed!"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "Cleaning Python build artifacts..."
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf .coverage
	rm -rf $(COVERAGE_DIR)
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	rm -rf $(SRC_DIR)/*.egg-info
	rm -f $(VENV_MARKER) $(DEV_MARKER)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete."

clean-docker:
	@echo "Cleaning Docker artifacts..."
	$(COMPOSE) down --rmi local --volumes --remove-orphans 2>/dev/null || true
	@echo "Docker clean complete."

clean-all: clean clean-docker
	@echo "Full cleanup complete."

# =============================================================================
# Docker - Build
# =============================================================================

build:
	@echo "Building Docker images..."
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(COMPOSE) build

build-no-cache:
	@echo "Building Docker images (no cache)..."
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(COMPOSE) build --no-cache

# =============================================================================
# Docker - Services
# =============================================================================

up:
	@echo "Starting services..."
	$(COMPOSE) up -d
	@echo ""
	@echo "Services started. Run 'make logs' to follow logs or 'make status' to check status."

down:
	@echo "Stopping services..."
	$(COMPOSE) down

restart:
	@echo "Restarting services..."
	$(COMPOSE) restart

status:
	$(COMPOSE) ps

# =============================================================================
# Docker - Logs
# =============================================================================

logs:
	$(COMPOSE) logs -f

logs-imap:
	$(COMPOSE) logs -f imap

logs-processor:
	$(COMPOSE) logs -f mail-processor

logs-briefing:
	$(COMPOSE) logs -f daily-briefing

logs-antivirus:
	$(COMPOSE) logs -f antivirus

# =============================================================================
# Docker - Shells
# =============================================================================

shell-imap:
	$(COMPOSE) exec imap /bin/sh

shell-processor:
	$(COMPOSE) exec mail-processor /bin/bash

shell-briefing:
	$(COMPOSE) exec daily-briefing /bin/bash

# =============================================================================
# Docker - Operations
# =============================================================================

fetch-now:
	@echo "Triggering immediate mail fetch..."
	$(COMPOSE) exec mail-processor postal-inspector scanner --once

test-briefing:
	@echo "Testing briefing generation..."
	$(COMPOSE) exec daily-briefing postal-inspector briefing --now

# =============================================================================
# Operations (Local)
# =============================================================================

briefing: dev
	$(UV_RUN) postal-inspector briefing --now

health: dev
	$(UV_RUN) postal-inspector health
