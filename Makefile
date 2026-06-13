# Makefile — atajos del proyecto. Uso: make <objetivo>
.PHONY: help install lint format type test check all clean

help:
	@echo "Comandos disponibles:"
	@echo "  make install   Instalar dependencias (uv sync)"
	@echo "  make lint      Linter (ruff check)"
	@echo "  make format    Formatear código (ruff format)"
	@echo "  make type      Comprobar tipos (mypy)"
	@echo "  make test      Tests (pytest)"
	@echo "  make check     lint + type + test (pre-commit)"
	@echo "  make all       format + lint --fix + type + test"
	@echo "  make clean     Limpiar caches"

install:
	uv sync

LOG_DIR    := docs/logs
LINT_LOG   := $(LOG_DIR)/lint.log
FORMAT_LOG := $(LOG_DIR)/format.log
TYPE_LOG   := $(LOG_DIR)/type.log
TEST_LOG   := $(LOG_DIR)/test.log
STAMP      := $(shell date "+%Y-%m-%d %H:%M:%S")

$(LOG_DIR):
	@mkdir -p $(LOG_DIR)

lint: | $(LOG_DIR)
	@echo "" >> $(LINT_LOG)
	@echo "===== $(STAMP) — ruff check =====" >> $(LINT_LOG)
	@uv run ruff check src tests 2>&1 | tee -a $(LINT_LOG)

format: | $(LOG_DIR)
	@echo "" >> $(FORMAT_LOG)
	@echo "===== $(STAMP) — ruff format =====" >> $(FORMAT_LOG)
	@uv run ruff format src tests 2>&1 | tee -a $(FORMAT_LOG)

type: | $(LOG_DIR)
	@echo "" >> $(TYPE_LOG)
	@echo "===== $(STAMP) — mypy =====" >> $(TYPE_LOG)
	@uv run mypy src 2>&1 | tee -a $(TYPE_LOG)

test: | $(LOG_DIR)
	@echo "" >> $(TEST_LOG)
	@echo "===== $(STAMP) — pytest =====" >> $(TEST_LOG)
	@uv run pytest -v 2>&1 | tee -a $(TEST_LOG)

# Pipeline que se ejecuta antes de commit: lint + tipos + tests
check: lint type test

# Pipeline que se ejecuta al empezar: formatea, autocorrige, valida
all:
	uv run ruff format src tests >> docs/logs/ruff_format_errors.txt
	uv run ruff check src tests --fix >> docs/logs/ruff_lint_errors.txt
	uv run mypy src
	uv run pytest

clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +