# Makefile — atajos del proyecto. Uso: make <objetivo>
.PHONY: help install lint format type test check all clean

bootstrap:
	@uv sync
	@$(MAKE) doctor

reset:
	rm -rf .venv uv.lock
	@uv sync
	@$(MAKE) doctor

doctor:
	@echo "→ Comprobando entorno..."
	@grep -q "^package = false" pyproject.toml && echo "⚠️  ATENCIÓN: package = false sigue ahí" || echo "✓ package config correcta"
	@uv pip list | grep -q "^atco" && echo "✓ atco instalado en el venv" || echo "✗ atco NO instalado — revisa pyproject.toml"
	@uv run python -c "import atco; print('✓ import atco funciona:', atco.__file__)" 2>/dev/null || echo "✗ import atco falla"

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
	@echo "Tests:"
	@echo "  make test                  Toda la batería"
	@echo "  make testf TARGET=<path>   Tests de un archivo/carpeta/test concreto"
	@echo "  make testk K=<patrón>      Tests cuyo nombre case con el patrón"
	@echo "  make testx TARGET=<path>   Stop al primer fallo (modo debug)"
	@echo "  make tlf                   Solo los tests que fallaron la última vez"
	@echo "  make t-cov TARGET=<path>   Tests con reporte de cobertura"
	@echo "  Atajos:"
	@echo "    make t-models            tests/unit/test_models.py"
	@echo "    make t-instance          tests/integration/test_instance.py"
	@echo "    make t-unit              toda la carpeta unit/"
	@echo "    make t-int               toda la carpeta integration/"

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

test_instance: | $(LOG_DIR)
	@echo "" >> $(TEST_LOG)
	@echo "===== $(STAMP) — pytest =====" >> $(TEST_LOG)
	@uv run pytest -v 2>&1 | tee -a $(TEST_LOG)
# 	@uv run pytest tests/integration/test_instance.py


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

# ----- Tests selectivos con logging ----------------------------------------

# Variable que el usuario puede sobreescribir
TARGET ?= tests

# Test en un path concreto (archivo, carpeta o test específico)
.PHONY: testf
testf: | $(LOG_DIR)
	@echo "" >> $(TEST_LOG)
	@echo "===== $(STAMP) — pytest $(TARGET) =====" >> $(TEST_LOG)
	@set -o pipefail; uv run pytest -v $(TARGET) 2>&1 | tee -a $(TEST_LOG)

# Test filtrado por palabra clave (pytest -k)
.PHONY: testk
testk: | $(LOG_DIR)
	@if [ -z "$(K)" ]; then \
		echo "Uso: make testk K=patron"; exit 1; \
	fi
	@echo "" >> $(TEST_LOG)
	@echo "===== $(STAMP) — pytest -k '$(K)' =====" >> $(TEST_LOG)
	@set -o pipefail; uv run pytest -v -k "$(K)" 2>&1 | tee -a $(TEST_LOG)

# Test detenerse al primer fallo
.PHONY: testx
testx: | $(LOG_DIR)
	@echo "" >> $(TEST_LOG)
	@echo "===== $(STAMP) — pytest -x $(TARGET) =====" >> $(TEST_LOG)
	@set -o pipefail; uv run pytest -x --tb=short -v $(TARGET) 2>&1 | tee -a $(TEST_LOG)	

# ----- Atajos para tests frecuentes ----------------------------------------

.PHONY: t-models t-instance t-restrictions t-unit t-int

t-models:
	@$(MAKE) testf TARGET=tests/unit/test_models.py

t-instance:
	@$(MAKE) testf TARGET=tests/integration/test_instance.py

t-restrictions:
	@$(MAKE) testf TARGET=tests/unit/test_restrictions.py

t-unit:
	@$(MAKE) testf TARGET=tests/unit

t-int:
	@$(MAKE) testf TARGET=tests/integration	