# Log docs

|Herramienta| Función | Idea|
|:---:|:---|:---|
|ruff| Estilo + bugs obvios + formato | Discusiones de "espacios o tabs", olvidos de import, nombres inconsistentes|
|mypy| Tipos (estáticos) | Pasar un `str` donde esperabas un `int` y descubrirlo en producción|
|pytest| Tests automáticos | Romper algo que funcionaba sin enterarte|
|`Makefile`| Serie de reglas que son ejecutadas en terminal. Tipo `.zshrc` |  Se definen en el archivo según lo que se quiera hacer |

## Flujo de trabajo

Antes de commit o terminar una sesión es saludable ejectuar los commandos:

```bash
    # 1. Formatear (te aplica el estilo automáticamente)
    uv run ruff format src tests

    # 2. Lint (te avisa de los problemas)
    uv run ruff check src tests --fix
    uv run ruff check src tests         # los que --fix no pudo

    # 3. Tipos (te avisa de inconsistencias)
    uv run mypy src

    # 4. Tests (te avisa de regresiones)
    uv run pytest
```

## Refactor

1. Truco para cambiar camelCase con RegEx: ([a-z])([A-Z]) -> $1_\l$2

## ruff

Es un _linter_ + _formateador_ escrito en Rust. Súper rápido (analiza miles de líneas en milisegundos). Hace dos cosas:

1. Linter (`ruff check`): lee código sin ejecutarlo y te avisa cuando hay:
   - Imports no usados (F401).
   - Variables asignadas y nunca leídas (F841).
   - Líneas demasiado largas (E501).
   - Imports desordenados (I001).
   - Nombres que no siguen PEP8 (N802, N803, N806).
   - Posibles bugs: bucles for X in [] triviales, mutable defaults, etc. (B007, B008).
2. Formateador (`ruff format`): reordena espacios, comillas, longitud de líneas, etc., para que tu código quede uniforme. Sustituye a black (es compatible con su estilo).

Lanza errores que se pueden encontrar [aquí](https://docs.astral.sh/ruff/rules/).

### Comandos ruff

```bash
    # 1. Detectar errores (no modifica nada)
    uv run ruff check <carpetas>  

    # 2. Auto-arreglar lo que sea seguro (imports, comillas, etc.)
    uv run ruff check  <carpetas> --fix

    # 3. Formatear el código a estilo uniforme
    uv run ruff format  <carpetas>

    # 4. Solo verificar formato sin tocar nada (útil en CI)
    uv run ruff format --check  <carpetas>
```

## mypy

Un _type checker_ estático. Lee código (sin ejecutarlo) y verifica que los tipos que son coherentes entre llamada y retorno. Por ejemplo: 

```python
    def calcula_fitness(sol: Solucion) -> float:
        return sol.getTurnos()      # ← devuelve list[str], no float!
```

### Comandos  mypy

```bash
    # Verificar tipos en todo el paquete
    uv run mypy src

    # Solo un archivo concreto (más rápido al iterar)
    uv run mypy src/atco/fitness/objective.py

    # Con explicación completa (útil cuando dudas)
    uv run mypy src --show-error-codes --pretty
```

## pytest

Un _framework_ para escribir y ejecutar tests automáticos del código. Un test es una función que:

   1. Prepara un estado conocido.
   2. Ejecuta la pieza que quieres comprobar.
   3. Afirma (`assert`) que el resultado es el esperado.
   4. Si la afirmación falla, `pytest` lo reporta. Si pasa, sigue adelante silenciosamente.

### Comandos para probar

```bash
# Uno concreto al iterar
uv run pytest tests/unit/test_models.py::test_controlador_clone_es_independiente -v

# Con cobertura para ver qué porcentaje cubrimos del dominio
uv run pytest --cov=src/atco/domain --cov-report=term-missing
```

### Otros comandos:

```bash
    # El target por defecto (tests/)
    make testf

    # Un archivo concreto
    make testf TARGET=tests/integration/test_instance.py

    # Un test concreto de un archivo
    make testf TARGET=tests/unit/test_models.py::test_controlador_clone_es_independiente

    # Una carpeta
    make testf TARGET=tests/unit

    # Por palabra clave (encuentra todos los tests cuyo nombre contenga "clone")
    make testk K=clone

    # Stop al primer fallo, traceback corto
    make testx TARGET=tests/integration

    # Combinación: K + stop al primero
    make testx K=clone

    # O los atajos:
    make t-models       # solo unit tests del modelo
    make t-instance     # solo integration test de Entrada
    make t-unit         # toda la carpeta unit/
    make t-int          # toda la carpeta integration/
```

### Posible mejora: usar timestampo en el nombre

```bash
    STAMP_DAY := $(shell date "+%Y-%m-%d")
    TEST_LOG  := $(LOG_DIR)/test-$(STAMP_DAY).log
```

### Ejemplo mínimo en `tests/unit/test_models.py`:

```python
    from atco.domain.models import Solucion

    def test_solucion_clone_preserves_turnos():
        sol = Solucion(turnos=["AAA111", "BBB000"], controladores=[], longdescansos=0)
        clone = sol.clone()
        assert clone.getTurnos() == sol.getTurnos()
        assert clone is not sol      # debe ser una copia, no la misma referencia
```

### Comandos pytest

```bash
    # Correr todos los tests
    uv run pytest

    # Más verboso (ver nombres de cada test)
    uv run pytest -v

    # Solo los tests de un archivo
    uv run pytest tests/unit/test_fitness.py

    # Solo un test concreto
    uv run pytest tests/unit/test_fitness.py::test_f1_sin_violaciones

    # Detenerse al primer fallo (útil al iterar)
    uv run pytest -x

    # Coverage: qué porcentaje del código está cubierto
    uv run pytest --cov=src/atco --cov-report=term-missing
```