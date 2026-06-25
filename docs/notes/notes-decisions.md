# Decisiones

## Plan — Reescritura limpia del proyecto ABACO para tesis BRKGA

Tras la reunión con los directores de tesis, queda claro que el repositorio actual mezcla decisiones del estudiante anterior con cambios míos hechos sobre una base que no controlo del todo. La estrategia correcta es **partir de cero**, conservando solo las piezas verificadas y reutilizables, y construir desde ahí un proyecto académico mantenible durante los tres años de tesis. La metaheurística defendida será BRKGA; se elimina el SA y se reformulan la función objetivo y todo lo que dependía de ella.

**Lo que se conserva** (acordado contigo):
- `domain/models.py` -> clases `Solucion`, `Controlador`, `Sector`, `Nucleo`, `Turno`, `Propiedades`.
- `domain/constants.py` -> `STRING_DESCANSO`, `STRING_NO_TURNO`, `LONGITUD_CADENAS`.
- `problem/restrictions/` -> las 14 `comprobar_*` de `restrictions.py` (~900 líneas testeadas).
- `problem/instance.py` (ex-`entrada.py`) + `problem/parameters.py` + `problem/properties.py`.
- `io/` (ex-`tools/`): persistencia .pkl/.json/.xlsx.
- `resources/` y `entrada/` tal cual.
- `docs/` (los `.tex` que ya generamos).

**Lo que se reescribe desde cero**:
- Función objetivo / fitness (lo más importante para tu tesis).
- Motor BRKGA, decoders, codificación bin-midpoint.
- CLI.
- Capa de análisis / convergencia.
- Tests desde el primer día.

**Lo que se elimina**: SA (`simulated_annealing.py`, `move15.py`, `metaheuristic.py`, `initial_population.py`, `deterministic_random.py`), todo lo de `abaco_python/` previo, `fitness.py` actual, `codifi.py` actual.

**Gestor**: `uv` (resolutor rápido, formato estándar académico 2024+).

---

## Estructura nueva

```
atco/                                    # repo root (mismo nombre del repo)
├── pyproject.toml                       # uv-managed; configura ruff, mypy, pytest
├── uv.lock                              # lockfile (uv lo genera)
├── .python-version                      # uv lee la versión de Python desde aquí
├── README.md
├── .gitignore
│
├── src/
│   └── atco/                            # paquete principal (PEP 517 src-layout)
│       ├── __init__.py
│       │
│       ├── domain/                      # ★ CONSERVADO
│       │   ├── __init__.py
│       │   ├── models.py                # ← abaco_python/src_python/models.py
│       │   └── constants.py             # ← abaco_python/src_python/constants.py
│       │
│       ├── problem/                     # capa del problema (datos + reglas)
│       │   ├── __init__.py
│       │   ├── parameters.py            # ★ CONSERVADO (renombre)
│       │   ├── properties.py            # ★ CONSERVADO
│       │   ├── instance.py              # ★ ex-entrada.py (renombre + cleanup)
│       │   ├── encoding.py              # NUEVO: bin-midpoint encode/decode
│       │   └── restrictions/
│       │       ├── __init__.py
│       │       ├── checks.py            # ★ las 16 comprobar_* de restrictions.py
│       │       └── weights.py           # PESO_POR_RESTRICCION + acumuladores
│       │
│       ├── fitness/                     # ★ NUEVO — el corazón de tu tesis
│       │   ├── __init__.py
│       │   ├── objective.py             # tu nueva función multi-objetivo
│       │   ├── components.py            # cada Fi por separado
│       │   └── selector.py              # selector limpio (reemplazo de switch_fitness)
│       │
│       ├── algorithms/
│       │   ├── __init__.py
│       │   └── brkga/
│       │       ├── __init__.py
│       │       ├── engine.py            # BRKGA_Engine: initialize, evolve, run, dump
│       │       ├── config.py            # BRKGAConfig (dataclass + validación)
│       │       ├── population.py        # Population + ConvergenceRecord
│       │       ├── operators.py         # crossover sesgado, mutación, selección
│       │       └── decoders/
│       │           ├── __init__.py
│       │           ├── base.py          # DecoderBase ABC
│       │           ├── constructive.py
│       │           └── greedy.py
│       │
│       ├── io/                          # ★ CONSERVADO (de tools/)
│       │   ├── __init__.py
│       │   ├── solution.py              # write/load pkl, json
│       │   ├── excel.py                 # write_xlsx, gantt
│       │   └── logging_setup.py
│       │
│       ├── analysis/                    # post-procesado y plots
│       │   ├── __init__.py
│       │   ├── convergence.py           # load_convergence, plot_*
│       │   └── statistics.py            # tests estadísticos entre corridas
│       │
│       └── cli/
│           ├── __init__.py
│           ├── __main__.py              # entry point: python -m atco
│           └── run.py                   # argparse + dispatch
│
├── tests/
│   ├── conftest.py                      # fixtures: entrada de prueba, instancias mini
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_restrictions.py
│   │   ├── test_encoding.py
│   │   ├── test_fitness.py
│   │   └── test_brkga_operators.py
│   └── integration/
│       └── test_brkga_smoke.py          # corrida end-to-end con instancia mini
│
├── experiments/                         # scripts para campañas reproducibles
│   ├── README.md
│   └── 00_smoke.py
│
├── notebooks/                           # análisis exploratorio (Jupyter)
│   └── .gitkeep
│
├── resources/                           # ★ CONSERVADO tal cual
├── entrada/                             # ★ CONSERVADO tal cual
│
├── results/                             # outputs de corridas (en .gitignore)
│   └── .gitkeep
│
└── docs/                                # ★ CONSERVADO + memoria de tesis
    ├── thesis/                          # LaTeX de la memoria
    │   └── .gitkeep
    ├── diagrams.tex
    ├── pseudocodigos.tex
    ├── material_pedagogico.tex
    ├── decoders_detail.tex
    └── codificar_turnos.tex
```

---

## Principios de diseño aplicados

1. **src-layout (PEP 517)**: el paquete vive bajo `src/atco/`. Los tests se ejecutan contra la versión instalada, no contra el árbol de trabajo. Es el estándar académico actual y elimina la clase de bugs por imports relativos rotos.
2. **Separación de capas**: `domain` no importa nada del exterior; `problem` importa `domain`; `algorithms` importa `domain` y `problem`; `cli` orquesta. **Una capa solo importa hacia "abajo".**
3. **Sin God modules**: `restrictions.py` se parte en `checks.py` (lógica) + `weights.py` (pesos y acumuladores). Idem `fitness/` en `objective` + `components` + `selector`.
4. **Tests desde el día 1**: cada módulo conservado entra con un test mínimo. Cada módulo nuevo se escribe TDD.
5. **Configuración via pyproject.toml**: `ruff` (linter + formatter), `mypy` (tipos), `pytest`, `coverage` — todo en un solo archivo.
6. **Sin `__main__.py` en el paquete raíz**: el entry point oficial es `python -m atco` que dispara `atco/cli/__main__.py`.

---

## Comandos de setup (macOS terminal)

Asume que estás en `/Users/<tu-usuario>/` o donde tengas tus proyectos.

### 1. Crear el nuevo repo (al lado del viejo, no encima)

```bash
# Vete a donde quieres que viva el nuevo proyecto
cd ~/Documents/Academic     # ajusta a tu ruta

# Crea el directorio raíz nuevo
mkdir atco-brkga && cd atco-brkga

# Inicializa git
git init
git branch -m main
```

### 2. Instalar y configurar uv (una sola vez en la máquina)

```bash
# Instalar uv si no lo tienes (Homebrew)
brew install uv

# Verificar
uv --version
```

### 3. Arrancar el proyecto con uv

```bash
# Inicializa el proyecto (genera pyproject.toml mínimo + .python-version)
uv init --package --name atco --python 3.11

# Pin de versión Python
echo "3.11" > .python-version

# Dependencias core
uv add numpy pandas matplotlib openpyxl

# Dependencias de desarrollo
uv add --dev pytest pytest-cov ruff mypy ipykernel jupyterlab
```

### 4. Crear el árbol de carpetas y archivos vacíos

Un solo bloque, copiable de golpe en la terminal:

```bash
# === Estructura src/ ===
mkdir -p src/atco/{domain,problem/restrictions,fitness,algorithms/brkga/decoders,io,analysis,cli}

# __init__.py en cada paquete
touch src/atco/__init__.py
touch src/atco/domain/__init__.py
touch src/atco/problem/__init__.py
touch src/atco/problem/restrictions/__init__.py
touch src/atco/fitness/__init__.py
touch src/atco/algorithms/__init__.py
touch src/atco/algorithms/brkga/__init__.py
touch src/atco/algorithms/brkga/decoders/__init__.py
touch src/atco/io/__init__.py
touch src/atco/analysis/__init__.py
touch src/atco/cli/__init__.py

# Archivos del dominio (conservados)
touch src/atco/domain/models.py
touch src/atco/domain/constants.py

# Archivos del problema
touch src/atco/problem/parameters.py
touch src/atco/problem/properties.py
touch src/atco/problem/instance.py
touch src/atco/problem/encoding.py
touch src/atco/problem/restrictions/checks.py
touch src/atco/problem/restrictions/weights.py

# Archivos de fitness (NUEVOS)
touch src/atco/fitness/objective.py
touch src/atco/fitness/components.py
touch src/atco/fitness/selector.py

# Motor BRKGA
touch src/atco/algorithms/brkga/engine.py
touch src/atco/algorithms/brkga/config.py
touch src/atco/algorithms/brkga/population.py
touch src/atco/algorithms/brkga/operators.py
touch src/atco/algorithms/brkga/decoders/base.py
touch src/atco/algorithms/brkga/decoders/constructive.py
touch src/atco/algorithms/brkga/decoders/greedy.py

# I/O y análisis
touch src/atco/io/solution.py
touch src/atco/io/excel.py
touch src/atco/io/logging_setup.py
touch src/atco/analysis/convergence.py
touch src/atco/analysis/statistics.py

# CLI
touch src/atco/cli/__main__.py
touch src/atco/cli/run.py

# === Tests ===
mkdir -p tests/{unit,integration}
touch tests/__init__.py tests/conftest.py
touch tests/unit/__init__.py
touch tests/unit/test_models.py
touch tests/unit/test_restrictions.py
touch tests/unit/test_encoding.py
touch tests/unit/test_fitness.py
touch tests/unit/test_brkga_operators.py
touch tests/integration/__init__.py
touch tests/integration/test_brkga_smoke.py

# === Experiments + Notebooks + Results ===
mkdir -p experiments notebooks results
touch experiments/README.md
touch experiments/00_smoke.py
touch notebooks/.gitkeep
touch results/.gitkeep

# === Docs ===
mkdir -p docs/thesis
touch docs/thesis/.gitkeep
```

### 5. Trasplantar los archivos conservados desde el repo antiguo

Sustituye `OLD` por la ruta de tu repo antiguo (por ejemplo `~/Documents/Academic/atco`):

```bash
OLD=~/Documents/Academic/atco          # ajusta a tu ruta
NEW=$(pwd)                             # ya estás en atco-brkga/

# Dominio (verbatim)
cp "$OLD/abaco_python/src_python/models.py"      "$NEW/src/atco/domain/models.py"
cp "$OLD/abaco_python/src_python/constants.py"   "$NEW/src/atco/domain/constants.py"

# Problema
cp "$OLD/abaco_python/src_python/parameters.py"  "$NEW/src/atco/problem/parameters.py"
cp "$OLD/abaco_python/src_python/properties.py"  "$NEW/src/atco/problem/properties.py"
cp "$OLD/abaco_python/src_python/entrada.py"     "$NEW/src/atco/problem/instance.py"
cp "$OLD/abaco_python/src_python/restrictions.py" "$NEW/src/atco/problem/restrictions/checks.py"

# I/O (de tools/)
cp "$OLD/abaco_python/src_python/tools/solution_pickle.py" "$NEW/src/atco/io/solution.py"
cp "$OLD/abaco_python/src_python/tools/write_xlsx.py"      "$NEW/src/atco/io/excel.py"
cp "$OLD/abaco_python/src_python/tools/mainLogger.py"      "$NEW/src/atco/io/logging_setup.py"

# Recursos e instancias (tal cual)
cp -R "$OLD/resources" "$NEW/resources"
cp -R "$OLD/entrada"   "$NEW/entrada"

# Docs (los .tex que ya tenías)
cp "$OLD/docs/diagrams.tex"            "$NEW/docs/diagrams.tex"
cp "$OLD/docs/pseudocodigos.tex"       "$NEW/docs/pseudocodigos.tex"
cp "$OLD/docs/material_pedagogico.tex" "$NEW/docs/material_pedagogico.tex"
cp "$OLD/docs/decoders_detail.tex"     "$NEW/docs/decoders_detail.tex"
cp "$OLD/docs/codificar_turnos.tex"    "$NEW/docs/codificar_turnos.tex"
```

Después tendrás que **ajustar los imports** en los archivos trasplantados (eran `from .models import ...`; ahora son `from atco.domain.models import ...`). Un `sed` cubre la mayoría:

```bash
# Ajustar imports relativos del repo viejo a la nueva estructura
cd src/atco
# constants.py / models.py: nada que cambiar (no importaban nada local)
# instance.py (ex-entrada.py)
sed -i '' 's|from .models import|from atco.domain.models import|g' problem/instance.py
sed -i '' 's|from .constants import|from atco.domain.constants import|g' problem/instance.py
# restrictions/checks.py
sed -i '' 's|from .constants import|from atco.domain.constants import|g' problem/restrictions/checks.py
# Repite el patrón para parameters.py, properties.py, io/solution.py, io/excel.py
```

(Después conviene revisar uno por uno; `sed` cubre el 90 %.)

### 6. Configuración inicial de `pyproject.toml`

Edita `pyproject.toml` (el que `uv init` te dejó) y añade las secciones para ruff, mypy, pytest:

```toml
[project]
name = "atco"
version = "0.1.0"
description = "BRKGA-based optimizer for air traffic controller shift schedules"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
    "pandas>=2.0",
    "matplotlib>=3.8",
    "openpyxl>=3.1",
]

[project.scripts]
atco = "atco.cli.run:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/atco"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RET"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src/atco"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

### 7. `.gitignore` mínimo

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
*.egg-info/

# uv
.uv/

# IDE
.vscode/
.idea/
.DS_Store

# Logs y outputs
*.log
results/*
!results/.gitkeep

# Notebooks
.ipynb_checkpoints/

# LaTeX outputs
*.aux
*.log
*.out
*.pdf
!docs/**/*.pdf
EOF
```

### 8. Comprobación de que todo arranca

```bash
# Sync dependencias
uv sync

# Smoke test del import
uv run python -c "import atco; print('atco package OK')"

# Lanzar pytest (vacío por ahora, debe pasar)
uv run pytest

# Lint check
uv run ruff check src tests

# Type check
uv run mypy src
```

---

## Roadmap de implementación (orden recomendado para no abrumarte)

Cada bloque es una sesión de trabajo razonable (~2-4 h). No saltes pasos; cada uno deja los tests verdes antes de avanzar.

### Bloque 1 · Base estable (sesión 1)
1. Setup del entorno (todo lo de arriba).
2. Trasplante de los archivos conservados con sus imports arreglados.
3. Tests mínimos de `domain/models.py`: instanciar `Solucion`, clonar, verificar.
4. Test mínimo de `problem/instance.py`: leer `madN_M1` y comprobar que se cargan ≥ 1 controlador.

### Bloque 2 · Restricciones puras (sesión 2)
1. Migrar `problem/restrictions/checks.py` con los imports arreglados.
2. Crear `problem/restrictions/weights.py` con `PESO_POR_RESTRICCION` y los tres acumuladores (`paralelo`, `ponderada_clasica`, `sin_pesos`).
3. Tests parametrizados de las 14 `comprobar_*`: cada una con un caso pasante y uno fallante.

### Bloque 3 · Nueva función objetivo (sesión 3-4) — lo importante para la tesis
1. Diseñar el contrato en `fitness/components.py`: cada Fi como función pura `Solucion -> float`.
2. `fitness/objective.py`: composición ponderada con los pesos como parámetros explícitos (no globales).
3. `fitness/selector.py`: dispatcher por nombre, configurable desde `.properties`.
4. Tests con vectores de referencia: para `madN_M1` debes obtener X tras N iteraciones.

### Bloque 4 · Codificación BRKGA (sesión 5)
1. `problem/encoding.py`: bin-midpoint `Solucion ↔ list[float]` con tests de round-trip exacto.
2. Integración con `fitness/`: codifica, decodifica, evalúa fitness, comprueba consistencia.

### Bloque 5 · Motor BRKGA (sesión 6-7)
1. `algorithms/brkga/config.py`: dataclass con validación.
2. `algorithms/brkga/population.py`: `Population` y `ConvergenceRecord`.
3. `algorithms/brkga/operators.py`: crossover sesgado, generador aleatorio.
4. `algorithms/brkga/engine.py`: `BRKGA_Engine.run()` con criterios de parada.
5. Test integración: lanzar BRKGA durante 10 generaciones en una mini-instancia.

### Bloque 6 · Decoders (sesión 8)
1. `decoders/base.py`: `DecoderBase` ABC.
2. `decoders/constructive.py`: tu Algoritmo 1 (continuidad + fatiga + licencias) limpio.
3. `decoders/greedy.py`: baseline para comparar.
4. Tests que verifican que cada decoder respeta su contrato.

### Bloque 7 · CLI + análisis (sesión 9)
1. `cli/run.py`: argparse con subcomandos `run`, `analyze`.
2. `analysis/convergence.py`: load JSON, plot.
3. End-to-end: `uv run atco run --case madN_M1 ...` produce JSON y PNG.

### Bloque 8 · Documentación y experimentos (continuo)
1. Mover los `.tex` existentes a `docs/`.
2. Empezar `docs/thesis/` con los capítulos.
3. Scripts en `experiments/` para corridas reproducibles que vayan a la tesis.

---

## Funciones / utilidades del repo viejo a reutilizar

| Origen actual | Destino nuevo | Notas |
|---|---|---|
| `models.py:Propiedades,Controlador,Sector,Nucleo,Turno,Solucion` | `src/atco/domain/models.py` | Verbatim |
| `constants.py:*` | `src/atco/domain/constants.py` | Verbatim |
| `restrictions.py:comprobar_*` (las 14) | `src/atco/problem/restrictions/checks.py` | Verbatim + arreglar imports |
| `restrictions.py:PESO_POR_RESTRICCION` y acumuladores | `src/atco/problem/restrictions/weights.py` | Separar de checks |
| `restrictions.py:_slots, _ensure_fast_cache, _checks` | `src/atco/problem/restrictions/_helpers.py` (privado) | Ocultar como API interna |
| `entrada.py:Entrada,leer_entrada,…` | `src/atco/problem/instance.py` | Renombre + cleanup |
| `parameters.py:*` | `src/atco/problem/parameters.py` | Verbatim |
| `properties.py:load_properties` | `src/atco/problem/properties.py` | Verbatim |
| `tools/solution_pickle.py` | `src/atco/io/solution.py` | Verbatim |
| `tools/write_xlsx.py` | `src/atco/io/excel.py` | Verbatim |
| `tools/mainLogger.py` | `src/atco/io/logging_setup.py` | Verbatim |

---

## Lo que se reescribe completamente desde cero

1. **`src/atco/fitness/*`** — tu nueva métrica multi-objetivo. Esta es la pieza académica clave: el contrato es `Solucion -> float`, los pesos vienen de fuera, y cada componente Fi es testeable y trazable. **No portes nada del `fitness.py` viejo; cualquier cosa que necesites la reconstruyes con conocimiento causal.**
2. **`src/atco/algorithms/brkga/*`** — motor limpio, sin `populations: list[Population]` ni multi-pop heredado. Una sola población, una sola decisión de tamaño, semillas via `seed_chromosomes` opcional.
3. **`src/atco/problem/encoding.py`** — bin-midpoint con doctests del round-trip.
4. **`src/atco/cli/*`** — argparse con subcomandos `run` y `analyze`; entry point oficial `python -m atco` y script `atco` instalado vía `pyproject.toml`.
5. **`src/atco/analysis/*`** — convergencia, stats, comparativas. Vista mínima de inicio: `plot_convergence(json)` -> PNG.

---

## Verificación end-to-end

### Tras el bloque 1 (base estable)
```bash
uv run pytest tests/unit/test_models.py
uv run python -c "from atco.problem.instance import Entrada; print('import OK')"
```

### Tras el bloque 2 (restricciones)
```bash
uv run pytest tests/unit/test_restrictions.py -v
# Debes ver las 14 funciones con al menos un test verde cada una.
```

### Tras el bloque 3-4 (fitness + encoding)
```bash
uv run pytest tests/unit/test_fitness.py tests/unit/test_encoding.py -v
```

### Tras el bloque 5-6 (BRKGA + decoders)
```bash
uv run pytest tests/integration/test_brkga_smoke.py
# El test lanza una corrida real de 10 generaciones sobre madN_M1.
```

### Smoke test end-to-end (tras bloque 7)
```bash
uv run atco run --case madN_M1 --decoder constructive \
                --pop-size 30 --max-seconds 30 --max-iterations 20
# Debe crear: results/<timestamp>/convergence.json + best.pkl + best.xlsx
uv run atco analyze --convergence results/<timestamp>/convergence.json \
                    --out results/<timestamp>/curva.png
```

### Linter y tipos verdes
```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

---

## Fuera de alcance (no ahora)

- Empaquetado para PyPI (no se publica la tesis como paquete).
- CI/CD con GitHub Actions (añadir en el siguiente curso si te interesa).
- BRKGA multi-población o intercambio de élites (queda como extensión posible).
- Conexión con un dashboard interactivo (Streamlit / Plotly Dash) — útil después.
- Comparación con SA (eliminado por tu decisión).

---

## Reglas de oro para los próximos meses

1. **Un commit, una idea.** Mensajes en imperativo: "add ...", "fix ...", "refactor ...". Si un commit toca tres cosas, te van a doler los reviews del director.
2. **Tests antes de pasar al siguiente bloque.** Si dejas un bloque sin tests, dentro de tres meses no recordarás qué hacía.
3. **Pesos del fitness configurables desde `.properties`.** No los hardcodees nunca. Tu director va a pedir variaciones.
4. **Tu tesis no es el código.** El código es soporte. Que tu git log sea legible para ti dentro de un año, no para impresionar a nadie.
5. **Documenta decisiones**, no implementaciones. Si descartas un enfoque, escribe en `docs/thesis/notes-design.md` por qué.