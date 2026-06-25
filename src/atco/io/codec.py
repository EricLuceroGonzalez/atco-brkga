"""Codificador / decodificador de soluciones para BRKGA.

Esquema bin-midpoint con round-trip exacto:

    1. Se recolectan todos los tokens distintos de 3 caracteres presentes
       en los turnos de una `Solucion` (incluyendo "111" y "000"
       obligatoriamente) y se ordenan en un vocabulario V.
    2. Sea M = |V|. Cada token v con índice i en V se codifica como la
       clave aleatoria k = (i + 0.5) / M (el centro de su bin).
    3. El decoder hace la operación inversa: dada k, el índice del token
       es floor(k · M), que vuelve a i por construcción.

Esto garantiza ``decodificar(codificar(S)) == S`` sin depender del
fitness ni del estado del decoder BRKGA.

API:
  Núcleo (no depende de Entrada):
    - codificar(solucion, vocabulario=None) -> (cromosoma, vocabulario)
    - decodificar(cromosoma, vocabulario, plantilla) -> Solucion

  Wrappers retrocompatibles (atajos sobre entrada.getDistribucionInicial()):
    - codificar_distribucion_inicial(entrada) -> (cromosoma, vocabulario)
    - decodificar_a_solucion(cromosoma, entrada, vocabulario) -> Solucion

  Helpers de bajo nivel y sembrado:
    - codificar_turnos(turnos, vocabulario, N, T) -> cromosoma
    - construir_semillas_iniciales(entrada, soluciones_extra=None)
        -> (cromosomas, vocabulario)
"""

from __future__ import annotations

from typing import Any

from atco.domain.constants import LONGITUD_CADENAS, STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Solucion

# =============================================================================
# Vocabulario
# =============================================================================


def _construir_vocabulario(turnos: list[str]) -> list[str]:
    """Construye el vocabulario ordenado de tokens distintos de la matriz.

    Garantiza que ``STRING_NO_TURNO`` y ``STRING_DESCANSO`` siempre
    aparecen primero (en ese orden), seguidos del resto ordenado
    alfabéticamente para que sea determinista entre ejecuciones.
    """
    fijos = [STRING_NO_TURNO, STRING_DESCANSO]
    vistos: set[str] = set(fijos)
    extras: set[str] = set()
    for turno in turnos:
        for i in range(0, len(turno), LONGITUD_CADENAS):
            tok = turno[i : i + LONGITUD_CADENAS]
            if tok not in vistos:
                extras.add(tok)
                vistos.add(tok)
    return fijos + sorted(extras)


# =============================================================================
# Núcleo (no depende de Entrada)
# =============================================================================


def codificar(
    solucion: Solucion,
    vocabulario: list[str] | None = None,
) -> tuple[list[float], list[str]]:
    """Codifica cualquier `Solucion` en un cromosoma BRKGA.

    Función núcleo de codificación: no depende de `Entrada`, sólo
    necesita la `Solucion` que se quiera persistir como cromosoma.

    Args:
        solucion: La `Solucion` a codificar (cualquiera, no
            necesariamente la distribución inicial).
        vocabulario: Si se proporciona, se usa para mapear tokens a
            índices (útil para compartir un V unificado entre varias
            soluciones). Si es None, se construye uno nuevo a partir
            de los tokens de ``solucion.getTurnos()``.

    Returns:
        ``(cromosoma, vocabulario)``: cromosoma de longitud N·T (con N
        filas y T slots tomados de ``solucion``) y el vocabulario usado.
    """
    turnos: list[str] = solucion.get_turnos()
    if not turnos:
        return [], vocabulario or _construir_vocabulario([])

    if vocabulario is None:
        vocabulario = _construir_vocabulario(turnos)

    N = len(turnos)
    long_max = max(len(t) for t in turnos)
    T = long_max // LONGITUD_CADENAS
    return codificar_turnos(turnos, vocabulario, N, T), vocabulario


def decodificar(
    cromosoma: list[float],
    vocabulario: list[str],
    plantilla: Solucion,
) -> Solucion:
    """Decodifica un cromosoma en una `Solucion` usando una plantilla de forma.

    Función núcleo de decodificación: no depende de `Entrada`. La
    ``plantilla`` aporta:

      - la forma (N, T) que define cuántos genes consume el cromosoma,
      - los controladores a clonar (para preservar identidades),
      - el valor de ``longdescansos`` que se copia en la solución
        resultante.

    Args:
        cromosoma: Lista de floats en [0, 1) de longitud N·T.
        vocabulario: Vocabulario usado en la codificación.
        plantilla: `Solucion` de referencia que aporta forma y
            controladores.

    Returns:
        Una nueva `Solucion` reconstruida. Si ``cromosoma`` y
        ``vocabulario`` provienen de ``codificar(plantilla)``, el
        resultado es idéntico a ``plantilla`` (round-trip exacto).

    Raises:
        ValueError: si el vocabulario está vacío o el tamaño del
            cromosoma no encaja con la forma de la plantilla.
    """
    turnos_base = plantilla.get_turnos()
    ctrls_base = plantilla.get_controladores()

    if not turnos_base or not cromosoma:
        return Solucion(
            turnos=[],
            controladores=[c.clone() for c in ctrls_base],
            longdescansos=plantilla.get_long_descansos(),
        )

    M = len(vocabulario)
    if M == 0:
        raise ValueError("El vocabulario está vacío; no se puede decodificar.")

    N = len(turnos_base)
    long_max = max(len(t) for t in turnos_base)
    T = long_max // LONGITUD_CADENAS

    if len(cromosoma) != N * T:
        raise ValueError(
            f"Tamaño de cromosoma incompatible: esperado {N * T} "
            f"({N} filas × {T} slots), recibido {len(cromosoma)}."
        )

    turnos_reconstruidos: list[str] = []
    for c in range(N):
        partes: list[str] = []
        for t in range(T):
            gene = cromosoma[c * T + t]
            # Clamp defensivo para evitar IndexError con genes en [0, 1].
            i = max(0, min(int(gene * M), M - 1))
            partes.append(vocabulario[i])
        turnos_reconstruidos.append("".join(partes))

    ctrls = [c.clone() for c in ctrls_base]
    return Solucion(
        turnos=turnos_reconstruidos,
        controladores=ctrls,
        longdescansos=plantilla.get_long_descansos(),
    )


# =============================================================================
# Wrappers retrocompatibles (Entrada-based)
# =============================================================================


def codificar_distribucion_inicial(
    entrada: Any,
) -> tuple[list[float], list[str]]:
    """Atajo: codifica ``entrada.getDistribucionInicial()``.

    Equivale a ``codificar(entrada.getDistribucionInicial())``.
    """
    return codificar(entrada.get_distribucion_inicial())


def decodificar_a_solucion(
    cromosoma: list[float],
    entrada: Any,
    vocabulario: list[str],
) -> Solucion:
    """Atajo: decodifica usando ``entrada.getDistribucionInicial()`` como plantilla.

    Equivale a
    ``decodificar(cromosoma, vocabulario, entrada.getDistribucionInicial())``.
    """
    return decodificar(cromosoma, vocabulario, entrada.get_distribucion_inicial())


# =============================================================================
# Helpers de bajo nivel y sembrado
# =============================================================================


def codificar_turnos(
    turnos: list[str],
    vocabulario: list[str],
    N: int,
    T: int,
) -> list[float]:
    """Codifica una matriz de turnos arbitraria contra un vocabulario dado.

    A diferencia de :func:`codificar`, esta función no construye su
    propio vocabulario: requiere uno externo, típicamente el
    vocabulario *unificado* calculado sobre la unión de todos los
    horarios a sembrar, para que cromosomas de distintos individuos
    sean decodificables con el mismo V.

    Args:
        turnos: Matriz de strings (un string por fila).
        vocabulario: Lista ordenada de tokens (incluyendo "000" y "111").
        N: Número de filas objetivo (se rellena/trunca a esta longitud).
        T: Número de slots objetivo por fila (se rellena/trunca con "000").

    Returns:
        Cromosoma de longitud N·T con claves en (0, 1) en el centro de
        cada bin.

    Raises:
        ValueError: si algún token de ``turnos`` no está en
            ``vocabulario``.
    """
    indice_de = {tok: i for i, tok in enumerate(vocabulario)}
    M = len(vocabulario)

    cromosoma: list[float] = []
    for c in range(N):
        if c < len(turnos):
            turno = turnos[c]
        else:
            # Fila extra que no existía en `turnos` → toda fuera de turno.
            turno = STRING_NO_TURNO * T
        # Normalizar/truncar a T slots con padding NO_TURNO.
        slots_actuales = len(turno) // LONGITUD_CADENAS
        if slots_actuales < T:
            turno = turno + STRING_NO_TURNO * (T - slots_actuales)
        for t in range(T):
            tok = turno[t * LONGITUD_CADENAS : (t + 1) * LONGITUD_CADENAS]
            if tok not in indice_de:
                raise ValueError(
                    f"Token {tok!r} no está en el vocabulario "
                    f"(fila={c}, slot={t}). Reconstruye el vocabulario "
                    f"incluyendo todos los horarios a sembrar."
                )
            i = indice_de[tok]
            # Punto medio del bin: garantiza round-trip exacto.
            cromosoma.append((i + 0.5) / M)
    return cromosoma


def construir_semillas_iniciales(
    entrada: Any,
    soluciones_extra: list[Solucion] | None = None,
) -> tuple[list[list[float]], list[str]]:
    """Construye los cromosomas-semilla para inicializar el BRKGA.

    Calcula un vocabulario unificado a partir de la unión de
    ``entrada.getDistribucionInicial()`` y ``soluciones_extra``, y
    codifica cada horario contra ese vocabulario. Todos los cromosomas
    tienen la misma forma ``(N, T)``, tomada de la distribución
    inicial.

    Args:
        entrada: Objeto `Entrada` del problema.
        soluciones_extra: Lista opcional de `Solucion` adicionales a
            sembrar (p. ej. un individuo de alto fitness encontrado a
            mano u obtenido de una corrida previa). Si es None, sólo
            se siembra el horario base.

    Returns:
        ``(cromosomas, vocabulario)``:
          - ``cromosomas[0]`` codifica la distribución inicial; los
            siguientes, las ``soluciones_extra`` en el orden dado.
          - ``vocabulario`` debe pasarse a :func:`decodificar` o a
            :func:`codificar_turnos` para garantizar consistencia.
    """
    distribucion = entrada.get_distribucion_inicial()
    todas: list[Solucion] = [distribucion]
    if soluciones_extra:
        todas.extend(soluciones_extra)

    # Vocabulario unificado (unión de tokens de todos los horarios).
    union_turnos: list[str] = []
    for sol in todas:
        union_turnos.extend(sol.get_turnos())
    vocabulario = _construir_vocabulario(union_turnos)

    # Forma objetivo: N filas × T slots de la distribución inicial.
    base_turnos = distribucion.get_turnos()
    N = len(base_turnos)
    T = (max(len(t) for t in base_turnos) // LONGITUD_CADENAS) if base_turnos else 0

    cromosomas = [
        codificar_turnos(sol.get_turnos(), vocabulario, N, T) for sol in todas
    ]
    return cromosomas, vocabulario
