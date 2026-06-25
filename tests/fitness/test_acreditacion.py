"""Tests del componente de acreditación (sectores elementales cubiertos).
pipenv run pytest tests/unit/test_acreditacion.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from atco.fitness.components import acreditacion

# ============================================================================
# Mocks mínimos
# ============================================================================


@dataclass
class _SectorMock:
    id: str
    sectores_elementales: list[str] = field(default_factory=list)


@dataclass
class _SolucionMock:
    turnos: list[str]


@dataclass
class _EntradaMock:
    lista_sectores: list[_SectorMock] = field(default_factory=list)
    sectores_por_slot: dict[int, list[_SectorMock]] = field(default_factory=dict)

    def get_lista_sectores(self) -> list[_SectorMock]:
        return self.lista_sectores

    def get_sectores_abiertos_en(self, t: int) -> list[_SectorMock]:
        return self.sectores_por_slot.get(t, [])


# ============================================================================
# Casos básicos
# ============================================================================


class TestAcreditacionCasosBase:
    def test_sin_controladores_sin_sectores(self) -> None:
        sol = _SolucionMock(turnos=[])
        ent = _EntradaMock()
        assert acreditacion(sol, ent) == (0, 0, 0)

    def test_sin_elementales_definidos(self) -> None:
        # Sector existe, abre, pero no tiene elementales asociados
        s = _SectorMock("aab")
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s]})
        sol = _SolucionMock(turnos=["aab"])
        assert acreditacion(sol, ent) == (0, 1, 0)

    def test_un_controlador_un_sector_un_elemental(self) -> None:
        s = _SectorMock("aab", sectores_elementales=["ASL"])
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s]})
        sol = _SolucionMock(turnos=["aab"])
        # crudo=1 (controlador cubrió ASL), v_min=1, v_max=1*1=1
        assert acreditacion(sol, ent) == (1, 1, 1)

    def test_un_controlador_descansando_no_cubre_nada(self) -> None:
        s = _SectorMock("aab", sectores_elementales=["ASL", "ASU"])
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s]})
        sol = _SolucionMock(turnos=["111"])
        # crudo=0 (no trabajó), v_min=1, v_max=1*2=2
        assert acreditacion(sol, ent) == (0, 1, 2)


# ============================================================================
# Convención EJ/PL
# ============================================================================


class TestConvencionRol:
    def test_ej_y_pl_aportan_mismos_elementales(self) -> None:
        s = _SectorMock("aab", sectores_elementales=["ASL"])
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s], 1: [s]})

        sol_ej = _SolucionMock(turnos=["AAB" + "111"])  # 1 slot EJ + 1 descanso
        sol_pl = _SolucionMock(turnos=["aab" + "111"])  # 1 slot PL + 1 descanso

        assert acreditacion(sol_ej, ent) == acreditacion(sol_pl, ent)

    def test_alternar_ej_y_pl_no_duplica_elemental(self) -> None:
        # Trabajar AAB en t=0 y aab en t=1 cuenta como UN solo elemental cubierto
        s = _SectorMock("aab", sectores_elementales=["ASL"])
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s], 1: [s]})
        sol = _SolucionMock(turnos=["AAB" + "aab"])
        # Un controlador, ASL cubierto una vez (es un set)
        assert acreditacion(sol, ent) == (1, 1, 1)


# ============================================================================
# Acumulación a través de slots y filas
# ============================================================================


class TestAcumulacion:
    def test_trabajar_mismo_sector_repetido_cuenta_una_vez(self) -> None:
        # 5 slots seguidos en aab -> cubierto = {ASL}, crudo = 1
        s = _SectorMock("aab", sectores_elementales=["ASL"])
        ent = _EntradaMock(
            lista_sectores=[s], sectores_por_slot={i: [s] for i in range(5)}
        )
        sol = _SolucionMock(turnos=["aab" * 5])
        assert acreditacion(sol, ent) == (1, 1, 1)

    def test_sector_con_varios_elementales(self) -> None:
        # 1 controlador trabaja aab que contiene {ASL, ASU, ASN}
        s = _SectorMock("aab", sectores_elementales=["ASL", "ASU", "ASN"])
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s]})
        sol = _SolucionMock(turnos=["aab"])
        assert acreditacion(sol, ent) == (3, 1, 3)

    def test_dos_sectores_un_controlador_distintos_elementales(self) -> None:
        s_a = _SectorMock("aab", sectores_elementales=["ASL"])
        s_b = _SectorMock("aac", sectores_elementales=["ASM"])
        ent = _EntradaMock(
            lista_sectores=[s_a, s_b],
            sectores_por_slot={0: [s_a], 1: [s_b]},
        )
        sol = _SolucionMock(turnos=["aab" + "aac"])
        # Controlador cubre {ASL, ASM}, crudo=2, v_min=1, v_max=1*2=2
        assert acreditacion(sol, ent) == (2, 1, 2)

    def test_dos_sectores_con_elemental_compartido(self) -> None:
        # aab y aac comparten ASL
        s_a = _SectorMock("aab", sectores_elementales=["ASL", "ASU"])
        s_b = _SectorMock("aac", sectores_elementales=["ASL", "ASN"])
        ent = _EntradaMock(
            lista_sectores=[s_a, s_b],
            sectores_por_slot={0: [s_a], 1: [s_b]},
        )
        sol = _SolucionMock(turnos=["aab" + "aac"])
        # Controlador cubre {ASL, ASU, ASN}: 3 únicos. v_max = 1 * 3 = 3
        assert acreditacion(sol, ent) == (3, 1, 3)


# ============================================================================
# Múltiples controladores
# ============================================================================


class TestMultiplesControladores:
    def test_dos_controladores_cubriendo_lo_mismo(self) -> None:
        s = _SectorMock("aab", sectores_elementales=["ASL", "ASU"])
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s]})
        sol = _SolucionMock(turnos=["AAB", "aab"])
        # Ambos cubren {ASL, ASU}: crudo = 2 + 2 = 4, v_min=2, v_max=2*2=4
        assert acreditacion(sol, ent) == (4, 2, 4)

    def test_dos_controladores_cubriendo_sectores_distintos(self) -> None:
        s_a = _SectorMock("aab", sectores_elementales=["ASL"])
        s_b = _SectorMock("aac", sectores_elementales=["ASM"])
        ent = _EntradaMock(
            lista_sectores=[s_a, s_b],
            sectores_por_slot={0: [s_a, s_b]},
        )
        sol = _SolucionMock(turnos=["aab", "aac"])
        # ctrl0 cubre {ASL}, ctrl1 cubre {ASM}: crudo=2, v_min=2, v_max=2*2=4
        assert acreditacion(sol, ent) == (2, 2, 4)

    def test_uno_trabaja_otro_descansa(self) -> None:
        s = _SectorMock("aab", sectores_elementales=["ASL"])
        ent = _EntradaMock(lista_sectores=[s], sectores_por_slot={0: [s]})
        sol = _SolucionMock(turnos=["aab", "111"])
        # ctrl0 cubre {ASL}=1, ctrl1 cubre {}=0. crudo=1, v_min=2, v_max=2*1=2
        assert acreditacion(sol, ent) == (1, 2, 2)


# ============================================================================
# Filtrado por sectores abiertos
# ============================================================================


class TestSectoresCerrados:
    def test_sector_existente_pero_nunca_abre_no_cuenta(self) -> None:
        # Sector aac existe en lista_sectores pero no aparece en sectores_por_slot
        s_abierto = _SectorMock("aab", sectores_elementales=["ASL"])
        s_cerrado = _SectorMock("aac", sectores_elementales=["ASM"])  # nunca abre
        ent = _EntradaMock(
            lista_sectores=[s_abierto, s_cerrado],
            sectores_por_slot={0: [s_abierto], 1: [s_abierto]},
        )
        # Controlador "trabaja" aac (infactible operacionalmente):
        sol = _SolucionMock(turnos=["aac" + "aab"])
        # Sólo cuenta el trabajo en aab (sector abierto): {ASL}.
        # v_max = 1 ctrl × 1 elemental (ASL) = 1.
        crudo, v_min, v_max = acreditacion(sol, ent)
        assert crudo == 1
        assert v_min == 1
        assert v_max == 1


# ============================================================================
# Propiedades invariantes
# ============================================================================


class TestPropiedadesInvariantes:
    @pytest.mark.parametrize(
        "turnos",
        [
            ["aab"],
            ["AAB" * 3 + "111"],
            ["aab", "AAB", "111"],
            ["111" * 5],
        ],
    )
    def test_crudo_acotado_inferiormente_por_cero(self, turnos) -> None:
        s = _SectorMock("aab", sectores_elementales=["ASL", "ASU"])
        ent = _EntradaMock(
            lista_sectores=[s], sectores_por_slot={i: [s] for i in range(20)}
        )
        sol = _SolucionMock(turnos=turnos)
        crudo, _, _ = acreditacion(sol, ent)
        assert crudo >= 0

    def test_crudo_acotado_superiormente_por_v_max(self) -> None:
        # Configura un caso pequeño donde el controlador trabaja TODO
        s_a = _SectorMock("aab", sectores_elementales=["ASL", "ASU"])
        s_b = _SectorMock("aac", sectores_elementales=["ASN"])
        ent = _EntradaMock(
            lista_sectores=[s_a, s_b],
            sectores_por_slot={0: [s_a], 1: [s_b]},
        )
        # 2 controladores cubren ambos sectores
        sol = _SolucionMock(turnos=["aab" + "aac", "AAB" + "AAC"])
        crudo, v_min, v_max = acreditacion(sol, ent)
        assert crudo <= v_max
