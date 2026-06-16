"""Tests unitarios de la función objetivo."""

from __future__ import annotations

import random

import pytest

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Solucion
from atco.fitness import FitnessConfig, FitnessResult, evaluar_fitness
from atco.fitness.components import (
    descansos_largos,
    desbalance_carga,
    fragmentacion,
)
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds import construir_solucion_heuristica

# ---------------------------------------------------------------------------
# FitnessConfig — validación
# ---------------------------------------------------------------------------


class TestFitnessConfig:
    def test_defaults_son_validos(self) -> None:
        cfg = FitnessConfig()
        suma = cfg.alpha_r + cfg.alpha_c + cfg.alpha_b + cfg.alpha_f + cfg.alpha_l
        assert abs(suma - 1.0) < 1e-9

    def test_pesos_que_no_suman_uno_lanzan_error(self) -> None:
        with pytest.raises(ValueError, match="suman"):
            FitnessConfig(
                alpha_r=0.5, alpha_c=0.5, alpha_b=0.5, alpha_f=0.0, alpha_l=0.0
            )

    def test_pesos_negativos_lanzan_error(self) -> None:
        with pytest.raises(ValueError, match="negativos"):
            FitnessConfig(
                alpha_r=-0.1, alpha_c=0.55, alpha_b=0.15, alpha_f=0.10, alpha_l=0.30
            )

    def test_umbral_l_no_positivo_lanza_error(self) -> None:
        with pytest.raises(ValueError, match="umbral_l"):
            FitnessConfig(umbral_l=0)


# ---------------------------------------------------------------------------
# Componentes en aislamiento (sin fixtures de instancia real)
# ---------------------------------------------------------------------------


class TestDescansosLargos:
    def test_sin_rachas_largas_devuelve_cero(self) -> None:
        cadena = STRING_DESCANSO * 5 + "AAX" * 5 + STRING_DESCANSO * 5
        sol = Solucion(turnos=[cadena], controladores=[], cadenas=[])
        assert descansos_largos(sol, umbral=18) == 0

    def test_una_racha_justo_en_umbral_cuenta_una(self) -> None:
        u = 18
        cadena = STRING_DESCANSO * u + "AAX" * 5
        sol = Solucion(turnos=[cadena], controladores=[], cadenas=[])
        assert descansos_largos(sol, umbral=u) == 1

    def test_dos_rachas_largas_misma_fila(self) -> None:
        u = 5
        cadena = STRING_DESCANSO * u + "AAX" * 2 + STRING_DESCANSO * u
        sol = Solucion(turnos=[cadena], controladores=[], cadenas=[])
        assert descansos_largos(sol, umbral=u) == 2

    def test_celdas_fuera_de_turno_no_cuentan_como_descanso(self) -> None:
        cadena = STRING_NO_TURNO * 20 + "AAX"
        sol = Solucion(turnos=[cadena], controladores=[], cadenas=[])
        assert descansos_largos(sol, umbral=5) == 0


class TestFragmentacion:
    def test_fila_homogenea_de_trabajo_da_cero(self) -> None:
        cadena = "AAX" * 10
        sol = Solucion(turnos=[cadena], controladores=[], cadenas=[])
        crudo, cota = fragmentacion(sol)
        assert crudo == 0
        assert cota == 9

    def test_alternancia_total_da_transiciones_maximas(self) -> None:
        cadena = "AAX" + STRING_DESCANSO + "AAX" + STRING_DESCANSO
        sol = Solucion(turnos=[cadena], controladores=[], cadenas=[])
        crudo, cota = fragmentacion(sol)
        assert crudo == 3
        assert cota == 3

    def test_celdas_fuera_de_turno_no_se_cuentan(self) -> None:
        cadena = STRING_NO_TURNO * 2 + "AAX" * 2 + STRING_NO_TURNO
        sol = Solucion(turnos=[cadena], controladores=[], cadenas=[])
        crudo, cota = fragmentacion(sol)
        assert crudo == 0
        assert cota == 1


# ---------------------------------------------------------------------------
# Función objetivo composición (smoke + invariantes)
# ---------------------------------------------------------------------------


class TestEvaluarFitness:
    def test_fitness_result_es_float_castable(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        sol = construir_solucion_heuristica(
            entrada_mad_n_m1, parametros, random.Random(42)
        )
        result = evaluar_fitness(sol, entrada_mad_n_m1, parametros, FitnessConfig())
        assert isinstance(result, FitnessResult)
        assert float(result) == result.valor

    def test_componentes_tiene_las_cinco_claves(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        sol = construir_solucion_heuristica(
            entrada_mad_n_m1, parametros, random.Random(42)
        )
        result = evaluar_fitness(sol, entrada_mad_n_m1, parametros, FitnessConfig())
        assert set(result.componentes) == {"R", "C", "B", "F", "L"}
        assert set(result.crudos) == {"R", "C", "B", "F", "L"}

    def test_componentes_estan_en_rango_unitario(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        sol = construir_solucion_heuristica(
            entrada_mad_n_m1, parametros, random.Random(42)
        )
        result = evaluar_fitness(sol, entrada_mad_n_m1, parametros, FitnessConfig())
        for nombre, valor in result.componentes.items():
            assert 0.0 <= valor <= 1.0 + 1e-9, f"{nombre} fuera de rango: {valor}"

    def test_alpha_l_cero_anula_componente_l_en_valor(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        sol = construir_solucion_heuristica(
            entrada_mad_n_m1, parametros, random.Random(42)
        )
        cfg = FitnessConfig()  # alpha_l = 0
        result = evaluar_fitness(sol, entrada_mad_n_m1, parametros, cfg)
        valor_sin_l = (
            cfg.alpha_r * result.componentes["R"]
            + cfg.alpha_c * result.componentes["C"]
            + cfg.alpha_b * result.componentes["B"]
            + cfg.alpha_f * result.componentes["F"]
        )
        assert abs(result.valor - valor_sin_l) < 1e-9

    def test_reproducibilidad_con_misma_semilla(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        sol_a = construir_solucion_heuristica(
            entrada_mad_n_m1, parametros, random.Random(7)
        )
        sol_b = construir_solucion_heuristica(
            entrada_mad_n_m1, parametros, random.Random(7)
        )
        cfg = FitnessConfig()
        assert (
            evaluar_fitness(sol_a, entrada_mad_n_m1, parametros, cfg).valor
            == evaluar_fitness(sol_b, entrada_mad_n_m1, parametros, cfg).valor
        )


def test_cobertura_cota_es_doble_del_total_de_sectores_por_slot(
    entrada_mad_n_m1: Entrada, parametros: Parametros
) -> None:
    """La cota normalizadora cuenta EJ + PL por (sector, slot)."""
    from atco.fitness.components import cobertura_insatisfecha

    sol = construir_solucion_heuristica(entrada_mad_n_m1, parametros, random.Random(42))
    _, cota = cobertura_insatisfecha(sol, entrada_mad_n_m1, parametros)

    T = len(sol.turnos[0]) // 3
    n_sectores = len(entrada_mad_n_m1.get_sectores_abiertos_todo_el_dia())
    assert cota == 2 * T * n_sectores


def test_cobertura_cota_respeta_sectorizacion_dinamica(
    entrada_mad_n_m1: Entrada, parametros: Parametros
) -> None:
    """La cota es la suma de 2·|abiertos(t)| sobre los T slots."""
    from atco.fitness.components import cobertura_insatisfecha

    sol = construir_solucion_heuristica(entrada_mad_n_m1, parametros, random.Random(42))
    _, cota = cobertura_insatisfecha(sol, entrada_mad_n_m1, parametros)

    T = len(sol.turnos[0]) // 3
    esperada = sum(
        2 * len(entrada_mad_n_m1.get_sectores_abiertos_en(t)) for t in range(T)
    )
    assert cota == esperada
