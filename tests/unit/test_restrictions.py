"""Tests del Bloque 2: las 14 comprobar_* + los 3 acumuladores.

Estrategia:
- Smoke: cada función se invoca con la entrada real y se verifica
  que devuelve un número.
- Acumuladores: contrato (paralelo y por_restricciones son ponderados,
  sin_pesos no).
- Regresión targeted: comportamiento esperado de R13 y R14 (peso 5).
"""

from __future__ import annotations

import pytest

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.problem.restrictions import checks as _checks_mod
from atco.problem.restrictions.checks import (
    comprobar_restricciones_en_paralelo,
    ensure_fast_cache,
    penalizacion_por_restricciones,
    restricciones_sin_pesos,
)
from atco.problem.restrictions.weights import PESO_POR_RESTRICCION

# Lista canónica de las 14 comprobar_*, en orden de PESO_POR_RESTRICCION.
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
# Smoke tests
# =============================================================================


def test_pesos_tienen_longitud_14() -> None:
    assert len(PESO_POR_RESTRICCION) == 14


@pytest.mark.parametrize("nombre_check", ALL_CHECKS)
def test_smoke_check_devuelve_numero(
    nombre_check: str,
    entrada_mad_n_m1: Entrada,
    parametros: Parametros,
) -> None:
    """Cada comprobar_* devuelve un número finito sobre la distribución inicial."""
    check_fn = getattr(_checks_mod, nombre_check)
    sol = entrada_mad_n_m1.get_distribucion_inicial()
    resultado = _llamar_check(check_fn, sol, entrada_mad_n_m1, parametros)
    assert isinstance(resultado, int | float)
    assert resultado >= 0, f"{nombre_check} devolvió valor negativo: {resultado}"


def _llamar_check(fn, sol, entrada, parametros):
    """Despachador con preload del cache rápido."""
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
    return fn(sol, entrada)


# =============================================================================
# Acumuladores
# =============================================================================


def test_acumulador_paralelo_devuelve_no_negativo(
    entrada_mad_n_m1: Entrada,
    parametros: Parametros,
) -> None:
    sol = entrada_mad_n_m1.get_distribucion_inicial()
    total = comprobar_restricciones_en_paralelo(sol, entrada_mad_n_m1, parametros)
    assert total >= 0


def test_acumulador_sin_pesos_invariantes(
    entrada_mad_n_m1: Entrada,
    parametros: Parametros,
) -> None:
    sol = entrada_mad_n_m1.get_distribucion_inicial()
    sin_pesos = restricciones_sin_pesos(sol, entrada_mad_n_m1, parametros)
    paralelo = comprobar_restricciones_en_paralelo(sol, entrada_mad_n_m1, parametros)
    assert sin_pesos >= 0
    assert paralelo >= 0
    if sin_pesos > 0:
        assert paralelo > 0


def test_acumulador_por_restricciones_publica_vector_global(
    entrada_mad_n_m1: Entrada,
    parametros: Parametros,
) -> None:
    from atco.problem.restrictions.weights import restricciones_no_cumplidas

    sol = entrada_mad_n_m1.get_distribucion_inicial()
    _ = penalizacion_por_restricciones(sol, entrada_mad_n_m1, parametros)
    assert len(restricciones_no_cumplidas) == 14
    assert all(v >= 0 for v in restricciones_no_cumplidas)


# =============================================================================
# Regresión targeted: restricciones duras (peso 5)
# =============================================================================


def test_turno_vacio_cuenta_solo_con_descanso_sin_trabajo() -> None:
    from atco.domain.models import Controlador

    c1 = Controlador(
        id=1,
        turno="MC",
        nucleo="X",
        ptd=False,
        con=True,
        baja_alta=False,
        slot_alta=0,
        slot_baja=0,
    )
    c2 = c1.clone()
    c3 = c1.clone()
    sol = Solucion(
        turnos=[
            STRING_DESCANSO * 3,
            STRING_NO_TURNO * 3,
            STRING_DESCANSO + "AAA" + STRING_DESCANSO,
        ],
        controladores=[c1, c2, c3],
        longdescansos=0,
    )
    assert _checks_mod.comprobar_turno_vacio(sol) == 1


def test_controlador_asignado_cuenta_huerfanos_y_no_asignados() -> None:
    from atco.domain.models import Controlador

    c1 = Controlador(
        id=1,
        turno="MC",
        nucleo="X",
        ptd=False,
        con=True,
        baja_alta=False,
        slot_alta=0,
        slot_baja=0,
    )
    c1.turno_asignado = 0
    c2 = c1.clone()
    c2.turno_asignado = -1
    sol = Solucion(
        turnos=["AAA111000", "BBB111000", "CCC111000"],
        controladores=[c1, c2],
        longdescansos=0,
    )
    assert _checks_mod.comprobar_controlador_asignado(sol) == 3
