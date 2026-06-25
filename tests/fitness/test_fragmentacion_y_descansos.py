"""Tests de `fragmentacion` (refactorizada a bloques) e `intervalos_descanso`.

pipenv run pytest tests/fitness/test_fragmentacion_y_descansos.py -v
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from atco.fitness.components import fragmentacion, intervalos_descanso


@dataclass
class _SolucionMock:
    turnos: list[str]


# ============================================================================
# fragmentacion (nueva versión por bloques)
# ============================================================================


class TestFragmentacion:
    def test_solucion_vacia(self) -> None:
        assert fragmentacion(_SolucionMock(turnos=[])) == (0, 0, 0)

    def test_fila_toda_fuera_de_turno_no_cuenta(self) -> None:
        # "000" llena la ventana -> ventana = (0, 0) -> fila se ignora
        sol = _SolucionMock(turnos=["000" * 5])
        assert fragmentacion(sol) == (0, 0, 0)

    def test_fila_completamente_trabajando_un_solo_bloque(self) -> None:
        # 5 slots de trabajo seguido -> 1 bloque
        sol = _SolucionMock(turnos=["aab" * 5])
        crudo, v_min, v_max = fragmentacion(sol)
        assert crudo == 1
        assert v_min == 1
        assert v_max == 5

    def test_fila_completamente_descansando_un_solo_bloque(self) -> None:
        # 5 slots de descanso en la ventana -> 1 bloque
        sol = _SolucionMock(turnos=["111" * 5])
        crudo, v_min, v_max = fragmentacion(sol)
        assert crudo == 1
        assert v_min == 1
        assert v_max == 5

    def test_dos_bloques_trabajo_descanso(self) -> None:
        # aab × 3 + 111 × 2 -> 2 bloques
        sol = _SolucionMock(turnos=["aab" * 3 + "111" * 2])
        crudo, _, _ = fragmentacion(sol)
        assert crudo == 2

    def test_alternancia_maxima(self) -> None:
        # aab, 111, aab, 111, aab -> 5 bloques (peor caso para ventana=5)
        cadena = "aab" + "111" + "aab" + "111" + "aab"
        sol = _SolucionMock(turnos=[cadena])
        crudo, v_min, v_max = fragmentacion(sol)
        assert crudo == 5
        assert crudo == v_max  # peor caso: bloques = longitud de ventana

    def test_cambios_de_sector_no_son_cambios_de_estado(self) -> None:
        # aab, aac, aab -> todos trabajo -> 1 solo bloque
        sol = _SolucionMock(turnos=["aab" + "aac" + "aab"])
        crudo, _, _ = fragmentacion(sol)
        assert crudo == 1

    def test_no_turno_inicio_y_fin_no_inflan_ventana(self) -> None:
        # 000, aab, aab, 111, 000 -> ventana = [1, 4), 2 bloques
        sol = _SolucionMock(turnos=["000" + "aab" + "aab" + "111" + "000"])
        crudo, v_min, v_max = fragmentacion(sol)
        assert crudo == 2
        assert v_min == 1
        assert v_max == 3  # tamaño de ventana

    def test_dos_filas_se_suman(self) -> None:
        """Suma sobre filas con la misma longitud T (invariante del dominio)."""
        sol = _SolucionMock(
            turnos=[
                "aab" * 3 + "111" * 2,  # T=5, 2 bloques (work, rest)
                "aab" + "111" + "aab" * 3,  # T=5, 3 bloques (work, rest, work)
            ]
        )
        crudo, v_min, v_max = fragmentacion(sol)
        assert crudo == 5  # 2 + 3
        assert v_min == 2  # ambas filas con ventana
        assert v_max == 5 + 5  # ambas tienen T=5 slots de ventana


# ============================================================================
# intervalos_descanso
# ============================================================================


class TestIntervalosDescanso:
    def test_solucion_vacia(self) -> None:
        assert intervalos_descanso(_SolucionMock(turnos=[])) == (0, 0, 0)

    def test_fila_fuera_de_turno_no_cuenta(self) -> None:
        sol = _SolucionMock(turnos=["000" * 5])
        assert intervalos_descanso(sol) == (0, 0, 0)

    def test_fila_sin_descansos(self) -> None:
        # 5 slots todo trabajo -> 0 bloques de descanso
        sol = _SolucionMock(turnos=["aab" * 5])
        crudo, v_min, v_max = intervalos_descanso(sol)
        assert crudo == 0
        assert v_min == 1
        assert v_max == 5 // 6  # T=5, n_activos=1 -> 0

    def test_fila_un_solo_descanso(self) -> None:
        sol = _SolucionMock(turnos=["aab" * 2 + "111" * 3 + "aab" * 1])
        crudo, _, _ = intervalos_descanso(sol)
        assert crudo == 1

    def test_fila_tres_descansos_separados(self) -> None:
        # 111, aab, 111, aab, 111 -> 3 bloques de descanso
        cadena = "111" + "aab" + "111" + "aab" + "111"
        sol = _SolucionMock(turnos=[cadena])
        crudo, _, _ = intervalos_descanso(sol)
        assert crudo == 3

    def test_fila_toda_descanso_un_bloque(self) -> None:
        sol = _SolucionMock(turnos=["111" * 5])
        crudo, _, _ = intervalos_descanso(sol)
        assert crudo == 1

    def test_no_turno_no_cuenta_como_descanso(self) -> None:
        # 000 al inicio queda fuera de ventana, no afecta al conteo
        sol = _SolucionMock(turnos=["000" + "aab" + "111" + "aab"])
        crudo, _, _ = intervalos_descanso(sol)
        assert crudo == 1  # solo el bloque central de "111"

    def test_dos_filas_se_suman(self) -> None:
        sol = _SolucionMock(
            turnos=[
                "aab" + "111" + "aab",  # 1 bloque
                "111" + "aab" + "111",  # 2 bloques
            ]
        )
        crudo, v_min, v_max = intervalos_descanso(sol)
        assert crudo == 3
        assert v_min == 2
        assert v_max == (3 * 2) // 6  # = 1 (T=3, n_activos=2)

    def test_v_max_segun_formula_tello(self) -> None:
        # T=12 slots, n_activos=3 -> v_max = 12*3//6 = 6
        sol = _SolucionMock(turnos=["aab" * 12, "aab" * 12, "aab" * 12])
        _, _, v_max = intervalos_descanso(sol)
        assert v_max == 6


# ============================================================================
# Propiedades cruzadas e invariantes
# ============================================================================


class TestPropiedadesInvariantes:
    @pytest.mark.parametrize(
        "cadena",
        [
            "aab" * 10,
            "111" * 10,
            "aab" * 3 + "111" * 4 + "aac" * 3,
            "000" + "aab" * 8 + "000",
            "aab" + "111" + "aab" + "111" + "aab",
        ],
    )
    def test_crudo_acotado_por_v_min_y_v_max(self, cadena: str) -> None:
        sol = _SolucionMock(turnos=[cadena])

        f_crudo, f_min, f_max = fragmentacion(sol)
        d_crudo, d_min, d_max = intervalos_descanso(sol)

        # Fragmentación: si hay ventana, hay al menos 1 bloque
        if f_min > 0:
            assert f_min <= f_crudo <= f_max
        else:
            assert f_crudo == 0
        # Descansos: 0 ≤ crudo ≤ T (no acotado por v_min hacia arriba estrictamente)
        assert d_crudo >= 0

    def test_bloques_descanso_no_supera_bloques_totales(self) -> None:
        # Los bloques de descanso son un SUBCONJUNTO de los bloques totales
        cadena = "aab" * 3 + "111" * 2 + "aab" + "111" * 4
        sol = _SolucionMock(turnos=[cadena])
        bloques_total, _, _ = fragmentacion(sol)
        bloques_descanso, _, _ = intervalos_descanso(sol)
        assert bloques_descanso <= bloques_total
