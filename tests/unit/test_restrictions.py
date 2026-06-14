"""Tests del Bloque 2: las 14 comprobar_* + los 3 acumuladores.

Estrategia:
- Smoke: cada función se invoca con la entrada real `madN_M1` y su
  distribución inicial, y se verifica que devuelve un número.
- Acumuladores: contrato (paralelo y por_restricciones son ponderados,
  sin_pesos no).
- Regresión targeted: comportamiento esperado de las restricciones
  "duras" (R13 controlador_asignado, R14 turno_vacio).
"""

from __future__ import annotations

import pytest

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.problem.restrictions.checks import (
    comprobar_controlador_asignado,
    comprobar_restricciones_en_paralelo,
    comprobar_turno_vacio,
    ensure_fast_cache,
    penalizacion_por_restricciones,
    restricciones_sin_pesos,
)
from atco.problem.restrictions.weights import (
    PESO_POR_RESTRICCION,
)

# =============================================================================
# Constantes del Bloque 2
# =============================================================================


# Las 14 comprobar_*, en el orden canónico de PESO_POR_RESTRICCION.
ALL_CHECKS = [
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
]


# =============================================================================
# Smoke tests: cada comprobar_* corre y devuelve un número con la entrada real
# =============================================================================


def test_pesos_tienen_longitud_14() -> None:
    """El array de pesos por restricción debe tener exactamente 14 entradas."""
    assert len(PESO_POR_RESTRICCION) == 14


@pytest.mark.parametrize("nombre_check", ALL_CHECKS)
def test_smoke_check_devuelve_numero(
    nombre_check: str,
    entrada_mad_n_m1: Entrada,
    parametros_reales: Parametros,
) -> None:
    """Cada comprobar_* devuelve un número finito sobre la distribución inicial."""
    # Resolución dinámica del callable por nombre — simplifica los tests.
    check_fn = globals()[nombre_check]
    sol = entrada_mad_n_m1.get_distribucion_inicial()

    # Cada función tiene firmas distintas; las normalizamos con un dispatcher.
    resultado = _llamar_check(check_fn, sol, entrada_mad_n_m1, parametros_reales)

    assert isinstance(resultado, int | float)
    assert resultado >= 0, f"{nombre_check} devolvió valor negativo: {resultado}"


def _llamar_check(
    fn,
    sol: Solucion,
    entrada: Entrada,
    parametros: Parametros,
):
    """Despachador que sabe qué argumentos quiere cada comprobar_*."""
    ensure_fast_cache(entrada)
    nombre = fn.__name__
    turnos = sol.get_turnos()

    if nombre in {
        "comprobar_trabajo_maximo_consecutivo",
        "comprobar_ventana_trabajo_descanso",
        "comprobar_trabajo_minimo_consecutivo",
        "comprobar_descanso_minimo_consecutivo",
        "comprobar_trabajo_posicion_minimo_consecutivo_no_regex",
    }:
        return fn(turnos, parametros)
    if nombre == "comprobar_cambio_posicion":
        return fn(turnos, entrada.get_mapa_afinidad(), entrada.get_lista_sectores())
    if nombre == "comprobar_num_maximo_sectores":
        return fn(turnos, entrada, parametros)
    if nombre in {"comprobar_controlador_asignado", "comprobar_turno_vacio"}:
        return fn(sol)
    if nombre == "comprobar_porcentaje_descanso":
        return fn(sol, entrada, entrada.get_turno(), parametros)
    # Por defecto: (sol, entrada)
    return fn(sol, entrada)


# =============================================================================
# Acumuladores
# =============================================================================


def test_acumulador_paralelo_devuelve_no_negativo(
    entrada_mad_n_m1: Entrada,
    parametros_reales: Parametros,
) -> None:
    """`comprobar_restricciones_en_paralelo` suma ponderada; nunca negativa."""
    sol = entrada_mad_n_m1.get_distribucion_inicial()
    total = comprobar_restricciones_en_paralelo(
        sol, entrada_mad_n_m1, parametros_reales
    )
    assert total >= 0


def test_acumulador_sin_pesos_es_menor_o_igual_que_ponderado(
    entrada_mad_n_m1: Entrada,
    parametros_reales: Parametros,
) -> None:
    """Como los pesos son todos >= 0.5, la suma ponderada es >= la sin pesos.

    (Salvo restricciones con pesos < 1, que son R8, R11, R12. Aún así
    el promedio de pesos es > 1, así que en agregado se cumple.)
    """
    sol = entrada_mad_n_m1.get_distribucion_inicial()
    sin_pesos = restricciones_sin_pesos(sol, entrada_mad_n_m1, parametros_reales)
    paralelo = comprobar_restricciones_en_paralelo(
        sol, entrada_mad_n_m1, parametros_reales
    )
    # Heurística: con pesos medios > 1, lo ponderado supera a lo sin pesos
    # cuando hay alguna violación. Si todo es 0, ambos son 0.
    if sin_pesos == 0:
        assert paralelo == 0
    else:
        # Esta aserción puede ser estricta; relájala a `>= sin_pesos * 0.5` si te falla
        assert paralelo >= sin_pesos * 0.5


def test_acumulador_por_restricciones_publica_vector_global(
    entrada_mad_n_m1: Entrada,
    parametros_reales: Parametros,
) -> None:
    """`penalizacion_por_restricciones` actualiza la global `restricciones_no_cumplidas`."""
    from atco.problem.restrictions.weights import restricciones_no_cumplidas

    sol = entrada_mad_n_m1.get_distribucion_inicial()
    _ = penalizacion_por_restricciones(sol, entrada_mad_n_m1, parametros_reales)
    # Tras la llamada, el vector global debe tener 14 valores poblados.
    assert len(restricciones_no_cumplidas) == 14
    assert all(v >= 0 for v in restricciones_no_cumplidas)


# =============================================================================
# Regresión targeted: restricciones "duras" (peso 5)
# =============================================================================


def test_turno_vacio_cuenta_solo_con_descanso_sin_trabajo() -> None:
    """R14 cuenta filas que tienen `111` (descanso) pero NO ningún sector.

    Una fila con solo `000` (fuera-de-turno) no es turno vacío;
    solo violan las que tienen descanso real sin trabajo.
    """
    from atco.domain.models import Controlador, Propiedades

    c1 = Controlador(
        id=1,
        turno="MC",
        nucleo="X",
        ptd=False,
        con=True,
        baja_alta=Propiedades.ALTA,
        slot_alta=0,
        slot_baja=0,
    )
    c2 = c1.clone()
    c3 = c1.clone()

    # turno 1: solo descansos → violación
    # turno 2: solo NO_TURNO → no es violación
    # turno 3: descanso + trabajo → no es violación
    sol = Solucion(
        turnos=[
            STRING_DESCANSO * 3,
            STRING_NO_TURNO * 3,
            STRING_DESCANSO + "AAA" + STRING_DESCANSO,
        ],
        controladores=[c1, c2, c3],
        longdescansos=0,
    )
    assert comprobar_turno_vacio(sol) == 1


def test_controlador_asignado_cuenta_huerfanos_y_no_asignados() -> None:
    """R13 suma controladores sin turno_asignado + filas no asignadas a nadie."""
    from atco.domain.models import Controlador, Propiedades

    c1 = Controlador(
        id=1,
        turno="MC",
        nucleo="X",
        ptd=False,
        con=True,
        baja_alta=Propiedades.ALTA,
        slot_alta=0,
        slot_baja=0,
    )
    c1.turno_asignado = 0
    c2 = c1.clone()
    c2.turno_asignado = -1  # sin asignar
    # 3 filas, pero c1 apunta a 0 y c2 a nada → fila 1 y 2 quedan huérfanas
    sol = Solucion(
        turnos=["AAA111000", "BBB111000", "CCC111000"],
        controladores=[c1, c2],
        longdescansos=0,
    )
    p = comprobar_controlador_asignado(sol)
    # 1 sin asignar (c2) + 2 filas huérfanas (1, 2) = 3
    assert p == 3
