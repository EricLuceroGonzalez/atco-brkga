"""Tests de `cobertura_insatisfecha` con foco en el bug histórico del PL doble.
ejecutar: pipenv run pytest tests/fitness/test_cobertura_insatisfecha.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from atco.fitness.components import cobertura_insatisfecha

# ============================================================================
# Mocks mínimos
# ============================================================================


@dataclass
class _SectorMock:
    id: str


@dataclass
class _SolucionMock:
    turnos: list[str]
    # cobertura_insatisfecha sólo usa .turnos, no necesitamos más


@dataclass
class _EntradaMock:
    """Mock de Entrada con sectorización por slot definida explícitamente."""

    sectores_por_slot: dict[int, list[_SectorMock]] = field(default_factory=dict)

    def get_sectores_abiertos_en(self, t: int) -> list[_SectorMock]:
        return self.sectores_por_slot.get(t, [])


_PAR = None  # `parametros` no se usa dentro de la función


# ============================================================================
# Casos básicos
# ============================================================================


class TestCoberturaCasosBase:
    def test_sin_sectores_ni_filas(self) -> None:
        sol = _SolucionMock(turnos=[])
        ent = _EntradaMock()
        assert cobertura_insatisfecha(sol, ent, _PAR) == (0, 0)

    def test_sin_sectores_abiertos_en_ningun_slot(self) -> None:
        # 2 controladores, 3 slots, nadie abre -> demanda 0, huecos 0
        sol = _SolucionMock(turnos=["111" * 3, "111" * 3])
        ent = _EntradaMock()
        assert cobertura_insatisfecha(sol, ent, _PAR) == (0, 0)

    def test_un_sector_cubierto_completo(self) -> None:
        # 1 sector "aab" abierto en t=0, cubierto por EJ (AAB) y PL (aab)
        ent = _EntradaMock({0: [_SectorMock("aab")]})
        sol = _SolucionMock(turnos=["AAB", "aab"])
        assert cobertura_insatisfecha(sol, ent, _PAR) == (0, 2)

    def test_un_sector_sin_ningun_ATCo(self) -> None:
        # Sector abierto, ambos ATCOs en descanso -> faltan EJ y PL
        ent = _EntradaMock({0: [_SectorMock("aab")]})
        sol = _SolucionMock(turnos=["111", "111"])
        assert cobertura_insatisfecha(sol, ent, _PAR) == (2, 2)


# ============================================================================
# Regresión: el bug del PL doble
# ============================================================================


class TestRegresionBugPlanificador:
    """Antes del fix, faltar PL incrementaba `crudo` en 2 (debía ser 1)."""

    def test_falta_solo_planificador(self) -> None:
        # EJ cubierto, PL ausente -> debería contar EXACTAMENTE 1 hueco
        ent = _EntradaMock({0: [_SectorMock("aab")]})
        sol = _SolucionMock(turnos=["AAB", "111"])
        huecos, demanda = cobertura_insatisfecha(sol, ent, _PAR)
        assert huecos == 1, (
            f"Antes del fix devolvía 2 por la línea duplicada `crudo += 1`. "
            f"Resultado obtenido: {huecos}."
        )
        assert demanda == 2

    def test_falta_solo_ejecutivo(self) -> None:
        # Simétrico al anterior: PL cubierto, EJ ausente -> 1 hueco
        ent = _EntradaMock({0: [_SectorMock("aab")]})
        sol = _SolucionMock(turnos=["111", "aab"])
        assert cobertura_insatisfecha(sol, ent, _PAR) == (1, 2)

    def test_simetria_ej_pl(self) -> None:
        """Faltar EJ y faltar PL deben producir el mismo coste (=1)."""
        ent = _EntradaMock({0: [_SectorMock("aab")]})
        sol_falta_ej = _SolucionMock(turnos=["111", "aab"])
        sol_falta_pl = _SolucionMock(turnos=["AAB", "111"])
        h_ej, _ = cobertura_insatisfecha(sol_falta_ej, ent, _PAR)
        h_pl, _ = cobertura_insatisfecha(sol_falta_pl, ent, _PAR)
        assert h_ej == h_pl == 1


# ============================================================================
# Casos compuestos
# ============================================================================


class TestCoberturaCasosCompuestos:
    def test_varios_sectores_un_slot(self) -> None:
        # t=0: aab, aac. EJ aab cubierto, PL aac cubierto. Faltan PL aab y EJ aac.
        ent = _EntradaMock({0: [_SectorMock("aab"), _SectorMock("aac")]})
        # ATCO0=AAB (EJ aab) | ATCO1=aac (PL aac)
        sol = _SolucionMock(turnos=["AAB", "aac"])
        huecos, demanda = cobertura_insatisfecha(sol, ent, _PAR)
        assert demanda == 4  # 2 sectores × 2 posiciones
        assert huecos == 2  # faltan PL_aab y EJ_aac

    def test_sector_repetido_en_varios_slots(self) -> None:
        # Mismo sector aab abierto en t=0, 1, 2.
        # t=0 cubierto. t=1 falta PL. t=2 todo desierto.
        ent = _EntradaMock({i: [_SectorMock("aab")] for i in range(3)})
        sol = _SolucionMock(
            turnos=[
                "AAB" "AAB" "111",  # ATCO0
                "aab" "111" "111",  # ATCO1
            ]
        )
        huecos, demanda = cobertura_insatisfecha(sol, ent, _PAR)
        assert demanda == 6  # 3 slots × 2 posiciones
        # t=0: 0 huecos | t=1: 1 hueco (PL) | t=2: 2 huecos (EJ y PL)
        assert huecos == 3

    def test_slots_sin_sectores_no_inflan_demanda(self) -> None:
        # Solo t=1 tiene sector abierto; t=0 y t=2 vacíos.
        ent = _EntradaMock({1: [_SectorMock("aab")]})
        sol = _SolucionMock(turnos=["111" * 3, "111" * 3])
        huecos, demanda = cobertura_insatisfecha(sol, ent, _PAR)
        assert demanda == 2
        assert huecos == 2


# ============================================================================
# Propiedades invariantes
# ============================================================================


class TestPropiedadesInvariantes:
    @pytest.mark.parametrize(
        "turnos,sectores_t0",
        [
            (["AAB", "aab"], ["aab"]),
            (["111", "111"], ["aab"]),
            (["AAB", "111"], ["aab", "aac"]),
            (["AAA", "aaa", "AAB", "aab"], ["aaa", "aab"]),
        ],
    )
    def test_huecos_no_supera_demanda(self, turnos, sectores_t0) -> None:
        ent = _EntradaMock({0: [_SectorMock(s) for s in sectores_t0]})
        sol = _SolucionMock(turnos=turnos)
        huecos, demanda = cobertura_insatisfecha(sol, ent, _PAR)
        assert 0 <= huecos <= demanda

    @pytest.mark.parametrize("n_filas", [1, 2, 5, 10])
    def test_todos_descansando_huecos_igual_demanda(self, n_filas) -> None:
        """Si todo el mundo descansa, cada posición está descubierta."""
        ent = _EntradaMock({0: [_SectorMock("aab"), _SectorMock("aac")]})
        sol = _SolucionMock(turnos=["111"] * n_filas)
        huecos, demanda = cobertura_insatisfecha(sol, ent, _PAR)
        assert huecos == demanda == 4
