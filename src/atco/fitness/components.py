"""Componentes puras de la función objetivo: R, C, B, F, L.

Cada función recibe la solución (y la entrada/parámetros cuando aplica) y
devuelve valores **crudos**, sin normalizar. La normalización a [0, 1] y
la combinación ponderada las hace `objective.evaluar_fitness`.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

# from atco.problem.restrictions import checks as _checks
from atco.problem.restrictions.checks import _checks

NOMBRES_RESTRICCIONES: tuple[str, ...] = (
    "comprobar_nucleo_trabajo",
    "comprobar_tipo_sector",
    "comprobar_porcentaje_descanso",
    "comprobar_sectores_abiertos_noche",
    "comprobar_trabajo_maximo_consecutivo",
    "comprobar_controlador_turno_corto",
    "comprobar_ventana_trabajo_descanso",
    "comprobar_cambio_posicion",
    "comprobar_trabajo_minimo_consecutivo",
    "comprobar_descanso_minimo_consecutivo",
    "comprobar_trabajo_posicion_minimo_consecutivo_no_regex",
    "comprobar_num_maximo_sectores",
    "comprobar_controlador_asignado",
    "comprobar_turno_vacio",
)
N_RESTRICCIONES: int = len(NOMBRES_RESTRICCIONES)


def restricciones_violadas(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
) -> list[str]:
    """Devuelve los nombres de las comprobaciones con ≥1 violación.

    Delega en `_checks(...)` del módulo `restrictions.checks`, que ya
    sabe cómo invocar cada `comprobar_*` con sus argumentos específicos
    (incluido el `Turno` para R3 o el mapa de afinidad para R8).
    """
    violaciones = _checks(solucion, entrada, parametros)
    return [
        nombre
        for nombre, violacion in zip(NOMBRES_RESTRICCIONES, violaciones, strict=True)
        if violacion > 0
    ]


def desbalance_carga(solucion: Solucion) -> int:
    """Diferencia entre la carga máxima y mínima entre controladores.

    Args:
        solucion: Solución con `slots_trabajados` ya rellenado.

    Returns:
        `max(cargas) - min(cargas)`. Cero si todos trabajan lo mismo o si
        no hay controladores.
    """
    if not solucion.controladores:
        return 0
    cargas = [c.slots_trabajados for c in solucion.controladores]
    return max(cargas) - min(cargas)


def _longitud_t(solucion: Solucion) -> int:
    """Número de slots T deducido de la primera cadena.

    Cada slot ocupa 3 caracteres en la codificación (tokens como `"AAX"`,
    `"111"`, `"000"`).
    """
    if not solucion.turnos:
        return 0
    return len(solucion.turnos[0]) // 3


def _slot(cadena: str, t: int) -> str:
    """Token de 3 caracteres del slot `t` en la cadena."""
    return cadena[t * 3 : (t + 1) * 3]


def _es_trabajo(token: str) -> bool:
    """True si el token contiene un id de sector (no descanso ni fuera)."""
    return token not in (STRING_DESCANSO, STRING_NO_TURNO)


def _ventana_de_cadena(cadena: str, longitud_t: int) -> tuple[int, int]:
    """Devuelve `[a, b)`: primer slot in-ventana y siguiente al último.

    La "ventana" son los slots cuyo token no es `STRING_NO_TURNO`.
    Si la cadena está toda fuera de turno, devuelve `(0, 0)`.
    """
    a: int | None = None
    b = 0
    for t in range(longitud_t):
        if _slot(cadena, t) != STRING_NO_TURNO:
            if a is None:
                a = t
            b = t + 1
    return (0, 0) if a is None else (a, b)


def cobertura_insatisfecha(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,  # noqa: ARG001
) -> tuple[int, int]:
    """Cuenta posiciones (EJ o PL) sin cubrir respetando la sectorización por slot.

    Para cada slot `t`, la demanda de cobertura es:
    `2 · |sectores_abiertos_en(t)|` (un ejecutivo y un planificador por
    cada sector abierto en ese instante). El método
    `entrada.get_lista_sectores_abiertos(t)` proporciona la lista de
    sectores activos en el slot `t`, reflejando la **sectorización
    dinámica del espacio aéreo**: el número de sectores abiertos varía
    a lo largo del día según la configuración operativa.

    Returns:
        Tupla `(crudo, cota)`:
        - `crudo`: número total de posiciones (EJ o PL) sin cubrir.
        - `cota`: número total de posiciones a cubrir,
          `sum(2 · |abiertos(t)|) sobre t`.
    """
    cadenas = solucion.turnos
    n = len(cadenas)
    longitud = _longitud_t(solucion)

    cota = 0
    crudo = 0
    for t in range(longitud):
        abiertos_t = entrada.get_sectores_abiertos_en(t)
        cota += 2 * len(abiertos_t)
        if not abiertos_t:
            continue
        tokens_t = {
            _slot(cadenas[i], t) for i in range(n) if _es_trabajo(_slot(cadenas[i], t))
        }
        for sector in abiertos_t:
            if sector.id.upper() not in tokens_t:
                crudo += 1  # Falta ejecutivo
            if sector.id.lower() not in tokens_t:
                crudo += 1  # Falta planificador
                crudo += 1
    return crudo, cota


def fragmentacion(solucion: Solucion) -> tuple[int, int]:
    """Cuenta transiciones trabajo↔descanso dentro de cada ventana de turno.

    Returns:
        Tupla `(crudo, cota)`:
        - `crudo`: cambios de estado en celdas in-ventana consecutivas.
        - `cota`: número máximo posible de transiciones.
    """
    crudo = 0
    cota = 0
    longitud = _longitud_t(solucion)
    for cadena in solucion.turnos:
        a, b = _ventana_de_cadena(cadena, longitud)
        if b - a < 2:
            continue
        cota += b - a - 1
        for t in range(a, b - 1):
            if _es_trabajo(_slot(cadena, t)) != _es_trabajo(_slot(cadena, t + 1)):
                crudo += 1
    return crudo, cota


def descansos_largos(solucion: Solucion, umbral: int) -> int:
    """Cuenta rachas de descanso con longitud ≥ `umbral`.

    Args:
        solucion: Solución a evaluar.
        umbral: Longitud mínima en slots para "racha larga".

    Returns:
        Total de rachas largas sumando sobre todos los controladores.
    """
    total = 0
    longitud = _longitud_t(solucion)
    for cadena in solucion.turnos:
        racha = 0
        for t in range(longitud):
            token = _slot(cadena, t)
            if token == STRING_DESCANSO:
                racha += 1
            else:
                if racha >= umbral:
                    total += 1
                racha = 0
        if racha >= umbral:
            total += 1
    return total
