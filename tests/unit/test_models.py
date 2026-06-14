"""Tests quirúrgicos para src/atco/domain/models.py.

Cubre lo justo para garantizar que las clases trasplantadas funcionan
tras la migración: enums cargan, constructores aceptan los args
documentados, clone() es deep copy, identidad de Sector por id.
"""

from __future__ import annotations

import pytest

from atco.domain.models import (
    Controlador,
    Nucleo,
    Propiedades,
    Sector,
    Solucion,
    Turno,
)
from atco.problem.parameters import Parametros

# =============================================================================
#  Propiedades
# =============================================================================


def test_propiedades_tiene_tres_valores() -> None:
    assert {p.value for p in Propiedades} == {"ALTA", "BAJA", "ALTABAJA"}


# =============================================================================
#  Controlador
# =============================================================================


def test_controlador_constructor_minimo(controlador_basico: Controlador) -> None:
    assert controlador_basico.id == 1
    assert controlador_basico.turno == "MC"
    assert controlador_basico.con is True
    assert controlador_basico.turno_asignado == -1  # default
    assert controlador_basico.turno_noche == 0  # default


def test_controlador_clone_es_independiente(controlador_basico: Controlador) -> None:
    clon = controlador_basico.clone()
    clon.set_turno_asignado(42)
    clon.set_nucleo("Otro Núcleo")
    # El clon cambió, pero el original NO debe haberse tocado.
    assert controlador_basico.get_turno_asignado() == -1
    assert controlador_basico.get_nucleo() == "Madrid Ruta 1"


def test_controlador_getters_setters_round_trip(
    controlador_basico: Controlador,
) -> None:
    controlador_basico.set_slot_alta(99)
    assert controlador_basico.get_slot_alta() == 99
    assert not hasattr(controlador_basico, "imaginario")


def test_controlador_slots_trabajados_default_cero() -> None:
    """`slots_trabajados` arranca a 0 hasta que un decoder lo actualice."""
    c = Controlador(
        id=1,
        turno="MC",
        nucleo="Madrid Ruta 1",
        ptd=False,
        con=True,
        baja_alta=Propiedades.ALTA,
        slot_alta=0,
        slot_baja=0,
    )
    assert c.slots_trabajados == 0


def test_controlador_slots_trabajados_se_clona() -> None:
    """`slots_trabajados` se preserva en clone() como cualquier otro campo."""
    c = Controlador(
        id=1,
        turno="MC",
        nucleo="Madrid Ruta 1",
        ptd=False,
        con=True,
        baja_alta=Propiedades.ALTA,
        slot_alta=0,
        slot_baja=0,
    )
    c.slots_trabajados = 42
    clon = c.clone()
    assert clon.slots_trabajados == 42
    # Mutar el original no afecta al clon.
    c.slots_trabajados = 7
    assert clon.slots_trabajados == 42


# =============================================================================
#  Sector
# =============================================================================


def test_sector_constructor() -> None:
    s = Sector(
        nombre="LECMR1I",
        id="lecmr1i",
        pdt=False,
        ruta=True,
        noche=0,
        sectores_elementales=["ASL", "BLL"],
    )
    assert s.is_ruta() is True
    assert s.get_sectores_elementales() == ["ASL", "BLL"]


def test_sector_igualdad_y_hash_por_id() -> None:
    # Dos Sector con mismo id deben ser == y compartir hash, aunque su
    # nombre o flags difieran. Crítico para set[Sector] en sectorización.
    a = Sector(
        nombre="A", id="x", pdt=False, ruta=True, noche=0, sectores_elementales=[]
    )
    b = Sector(
        nombre="B", id="x", pdt=True, ruta=False, noche=1, sectores_elementales=["foo"]
    )
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


# =============================================================================
#  Nucleo
# =============================================================================


def test_nucleo_constructor_sectores_default_vacio() -> None:
    n = Nucleo(nombre="Madrid Ruta 1", id="MR1")
    assert n.get_sectores() == []


# =============================================================================
#  Turno
# =============================================================================


@pytest.mark.parametrize(
    ("inicio_tl", "fin_tl", "inicio_tc", "fin_tc", "esperado"),
    [
        # Madrid turno mañana: TL 10:30→18:30 (8h) y TC 12:30→18:30 (6h)
        # Con slot_size=5 min → [tl_inicio=0, tl_fin=96, tc_inicio=24, tc_fin=96]
        ("10:30", "18:30", "12:30", "18:30", [0, 96, 24, 96]),
    ],
)
def test_turno_turnos_slots(
    inicio_tl: str,
    fin_tl: str,
    inicio_tc: str,
    fin_tc: str,
    esperado: list[int],
    fake_parametros: Parametros,
) -> None:
    resultado = Turno.turnos_slots(
        inicio_tl, fin_tl, inicio_tc, fin_tc, fake_parametros
    )
    assert resultado == esperado


# =============================================================================
#  Solucion
# =============================================================================


def test_solucion_constructor(solucion_basica: Solucion) -> None:
    assert solucion_basica.get_turnos() == ["AAA111AAB"]
    assert len(solucion_basica.get_controladores()) == 1
    assert solucion_basica.get_long_descansos() == 0


def test_solucion_clone_es_deep_en_controladores(solucion_basica: Solucion) -> None:
    clon = solucion_basica.clone()
    # Mutar el controlador del clon NO debe tocar al original.
    clon.get_controladores()[0].set_turno_asignado(7)
    assert solucion_basica.get_controladores()[0].get_turno_asignado() == -1


def test_solucion_shallow_clone_comparte_controladores(
    solucion_basica: Solucion,
) -> None:
    clon = solucion_basica.shallow_clone()
    # shallowClone NO clona los controladores; los comparte por referencia.
    # Esto es semántica explícita del método.
    assert clon.get_controladores() is solucion_basica.get_controladores()
