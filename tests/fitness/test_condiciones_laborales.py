"""Tests de tiempo_optimo_posicion (vn_1), tiempo_optimo_trabajo (vn_2)
y porcentaje_ejecutivo (vn_3).
pipenv run pytest tests/fitness/test_condiciones_laborales.py -v
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from atco.fitness.components import (
    porcentaje_ejecutivo,
    tiempo_optimo_posicion,
    tiempo_optimo_trabajo,
)


@dataclass
class _SolucionMock:
    turnos: list[str]


@dataclass
class _ParametrosMock:
    tamano_slots: int = 5


# ============================================================================
# vn_1: tiempo_optimo_posicion
# ============================================================================


class TestTiempoOptimoPosicion:
    def test_solucion_vacia(self) -> None:
        sol = _SolucionMock(turnos=[])
        par = _ParametrosMock()
        assert tiempo_optimo_posicion(sol, par) == (0.0, 0.0)

    def test_intervalo_exacto_al_optimo_no_penaliza(self) -> None:
        # 9 slots × 5 min = 45 min, igual al pos_opt -> desviación 0
        cadena = "aab" * 9 + "111"  # 10 slots
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _cota = tiempo_optimo_posicion(sol, par)
        assert crudo == pytest.approx(0.0)

    def test_intervalo_mas_corto_que_optimo(self) -> None:
        # 5 slots × 5 min = 25 min -> desviación |45 - 25| = 20 min
        cadena = "aab" * 5 + "111" * 5
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_posicion(sol, par)
        assert crudo == pytest.approx(20.0)  # 20 / 1 controlador

    def test_intervalo_mas_largo_que_optimo(self) -> None:
        # 15 slots × 5 min = 75 min -> desviación |45 - 75| = 30 min
        cadena = "aab" * 15 + "111" * 3
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_posicion(sol, par)
        assert crudo == pytest.approx(30.0)

    def test_cambio_de_token_corta_intervalo(self) -> None:
        # aab (5 slots = 25 min) + aac (5 slots = 25 min)
        # Dos intervalos de 25 min cada uno -> 2 × |45 - 25| = 40 min
        cadena = "aab" * 5 + "aac" * 5
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_posicion(sol, par)
        assert crudo == pytest.approx(40.0)

    def test_division_por_n_atcos(self) -> None:
        # Dos controladores con el mismo patrón -> mismo crudo (no se duplica)
        cadena = "aab" * 5 + "111" * 5
        sol = _SolucionMock(turnos=[cadena, cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_posicion(sol, par)
        # 20 (cada uno) × 2 controladores / 2 atcos = 20
        assert crudo == pytest.approx(20.0)

    def test_solo_descanso_no_penaliza(self) -> None:
        cadena = "111" * 10
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_posicion(sol, par)
        assert crudo == pytest.approx(0.0)

    def test_cota_segun_formula_tello(self) -> None:
        # |45 - 15| × 8 × (T / 30). Con T=30, cota = 240.
        cadena = "aab" * 30
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        _, cota = tiempo_optimo_posicion(sol, par)
        assert cota == pytest.approx(30 * 8 * (30 / 30))


# ============================================================================
# vn_2: tiempo_optimo_trabajo
# ============================================================================


class TestTiempoOptimoTrabajo:
    def test_solucion_vacia(self) -> None:
        sol = _SolucionMock(turnos=[])
        par = _ParametrosMock()
        assert tiempo_optimo_trabajo(sol, par) == (0.0, 0.0)

    def test_intervalo_exacto_al_optimo(self) -> None:
        # 18 slots × 5 min = 90 min, igual al trab_opt -> desviación 0
        cadena = "aab" * 18 + "111" * 2
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_trabajo(sol, par)
        assert crudo == pytest.approx(0.0)

    def test_cambios_de_sector_no_cortan_intervalo(self) -> None:
        # aab × 9 + aac × 9 = 18 slots de trabajo continuo = 90 min -> 0
        cadena = "aab" * 9 + "aac" * 9 + "111" * 2
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_trabajo(sol, par)
        assert crudo == pytest.approx(0.0)

    def test_descanso_corta_intervalo(self) -> None:
        # 9 slots trabajo + 1 descanso + 9 slots trabajo = 2 intervalos de 45 min
        # |90 - 45| × 2 = 90 min de desviación total
        cadena = "aab" * 9 + "111" + "aab" * 9 + "111"
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        crudo, _ = tiempo_optimo_trabajo(sol, par)
        assert crudo == pytest.approx(90.0)

    def test_cota_segun_formula_tello(self) -> None:
        # |90 - 15| × (T / 6). Con T=60, cota = 75 × 10 = 750.
        cadena = "aab" * 60
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        _, cota = tiempo_optimo_trabajo(sol, par)
        assert cota == pytest.approx(75 * (60 / 6))


# ============================================================================
# vn_3: porcentaje_ejecutivo
# ============================================================================


class TestPorcentajeEjecutivo:
    def test_solucion_vacia(self) -> None:
        sol = _SolucionMock(turnos=[])
        assert porcentaje_ejecutivo(sol) == (0.0, 0.0)

    def test_pct_exactamente_50_no_penaliza(self) -> None:
        # 5 slots EJ + 5 slots PL -> pEje = 0.5 ∈ [0.4, 0.6]
        cadena = "AAB" * 5 + "aab" * 5
        sol = _SolucionMock(turnos=[cadena])
        crudo, cota = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.0)
        assert cota == pytest.approx(0.4)  # 1 controlador activo × 0.4

    def test_pct_dentro_del_rango_no_penaliza(self) -> None:
        # 4 EJ + 6 PL -> pEje = 0.4 (borde inferior, no penaliza)
        cadena = "AAB" * 4 + "aab" * 6
        sol = _SolucionMock(turnos=[cadena])
        crudo, _ = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.0)

    def test_todo_ejecutivo_penalizacion_maxima(self) -> None:
        # 10 EJ + 0 PL -> pEje = 1.0 -> δ = 1.0 - 0.6 = 0.4
        cadena = "AAB" * 10
        sol = _SolucionMock(turnos=[cadena])
        crudo, cota = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.4)
        assert cota == pytest.approx(0.4)
        assert crudo == cota  # ratio = 1, peor caso

    def test_todo_planificador_penalizacion_maxima(self) -> None:
        # 0 EJ + 10 PL -> pEje = 0.0 -> δ = 0.4 - 0.0 = 0.4
        cadena = "aab" * 10
        sol = _SolucionMock(turnos=[cadena])
        crudo, _ = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.4)

    def test_pct_30_penaliza_diferencia_a_borde(self) -> None:
        # 3 EJ + 7 PL -> pEje = 0.3 -> δ = 0.4 - 0.3 = 0.1
        cadena = "AAB" * 3 + "aab" * 7
        sol = _SolucionMock(turnos=[cadena])
        crudo, _ = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.1)

    def test_pct_70_penaliza_diferencia_a_borde(self) -> None:
        # 7 EJ + 3 PL -> pEje = 0.7 -> δ = 0.7 - 0.6 = 0.1
        cadena = "AAB" * 7 + "aab" * 3
        sol = _SolucionMock(turnos=[cadena])
        crudo, _ = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.1)

    def test_controlador_sin_trabajo_excluido(self) -> None:
        # ctrl0 trabaja perfecto (0.5), ctrl1 todo descanso -> excluido
        cadena_buena = "AAB" * 5 + "aab" * 5
        cadena_descanso = "111" * 10
        sol = _SolucionMock(turnos=[cadena_buena, cadena_descanso])
        crudo, cota = porcentaje_ejecutivo(sol)
        # Sólo 1 controlador activo: cota = 0.4 × 1 = 0.4 (no 0.8)
        assert crudo == pytest.approx(0.0)
        assert cota == pytest.approx(0.4)

    def test_dos_controladores_uno_perfecto_uno_malo(self) -> None:
        # ctrl0 = 0.5 (perfecto), ctrl1 = 1.0 (max penalty 0.4)
        cadena_perfecto = "AAB" * 5 + "aab" * 5
        cadena_malo = "AAB" * 10
        sol = _SolucionMock(turnos=[cadena_perfecto, cadena_malo])
        crudo, cota = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.4)
        assert cota == pytest.approx(0.8)  # 2 activos × 0.4

    def test_descansos_no_cuentan_en_el_porcentaje(self) -> None:
        # 5 EJ + 5 descansos + 5 PL -> slots_trabajo = 10, pEje = 0.5 -> 0
        cadena = "AAB" * 5 + "111" * 5 + "aab" * 5
        sol = _SolucionMock(turnos=[cadena])
        crudo, _ = porcentaje_ejecutivo(sol)
        assert crudo == pytest.approx(0.0)


# ============================================================================
# Propiedades invariantes cruzadas
# ============================================================================


class TestPropiedadesInvariantes:
    @pytest.mark.parametrize(
        "cadena",
        [
            "aab" * 10,
            "AAB" * 5 + "aab" * 5,
            "aab" * 3 + "111" * 4 + "AAC" * 3,
            "111" * 10,
            "AAB" * 9 + "aac" * 9,
        ],
    )
    def test_crudo_y_cota_no_negativos(self, cadena: str) -> None:
        sol = _SolucionMock(turnos=[cadena])
        par = _ParametrosMock(tamano_slots=5)
        c1, ct1 = tiempo_optimo_posicion(sol, par)
        c2, ct2 = tiempo_optimo_trabajo(sol, par)
        c3, ct3 = porcentaje_ejecutivo(sol)
        assert c1 >= 0 and ct1 >= 0
        assert c2 >= 0 and ct2 >= 0
        assert c3 >= 0 and ct3 >= 0

    @pytest.mark.parametrize(
        "cadena",
        [
            "aab" * 18,
            "AAB" * 5 + "aab" * 5,
            "aab" * 6 + "111" * 3 + "aac" * 6,
        ],
    )
    def test_porcentaje_ejecutivo_crudo_no_supera_cota(self, cadena: str) -> None:
        sol = _SolucionMock(turnos=[cadena])
        crudo, cota = porcentaje_ejecutivo(sol)
        assert crudo <= cota + 1e-9
