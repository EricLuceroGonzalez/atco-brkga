"""Tests de la lógica de penalización por violaciones.
pipenv run pytest tests/fitness/test_penalizacion.py -v"""

from __future__ import annotations

import pytest

from atco.fitness.penalizacion import (
    PesosPenalizacion,
    calcular_penalizacion,
    desglose_penalizacion,
)
from atco.problem.restrictions.checks import NOMBRES_RESTRICCIONES


def _violaciones_cero() -> dict[str, float]:
    return {n: 0.0 for n in NOMBRES_RESTRICCIONES}


def _violaciones_una(nombre: str, valor: float = 1.0) -> dict[str, float]:
    v = _violaciones_cero()
    v[nombre] = valor
    return v


# ============================================================================
# PesosPenalizacion: validación
# ============================================================================


class TestPesosValidacion:
    def test_default_es_uniforme(self) -> None:
        p = PesosPenalizacion()
        assert p.coeficiente_global == 0.01
        assert set(p.pesos_por_restriccion) == set(NOMBRES_RESTRICCIONES)
        assert all(v == 1.0 for v in p.pesos_por_restriccion.values())

    def test_coeficiente_negativo_falla(self) -> None:
        with pytest.raises(ValueError, match="coeficiente_global"):
            PesosPenalizacion(coeficiente_global=-0.1)

    def test_peso_individual_negativo_falla(self) -> None:
        pesos = {n: 1.0 for n in NOMBRES_RESTRICCIONES}
        pesos[NOMBRES_RESTRICCIONES[0]] = -0.5
        with pytest.raises(ValueError, match="≥ 0"):
            PesosPenalizacion(pesos_por_restriccion=pesos)

    def test_pesos_incompletos_falla(self) -> None:
        with pytest.raises(ValueError, match="Faltan"):
            PesosPenalizacion(pesos_por_restriccion={NOMBRES_RESTRICCIONES[0]: 1.0})


# ============================================================================
# calcular_penalizacion
# ============================================================================


class TestCalcularPenalizacion:
    def test_solucion_factible_penalty_cero(self) -> None:
        v = _violaciones_cero()
        assert calcular_penalizacion(v, PesosPenalizacion()) == 0.0

    def test_una_violacion_con_default(self) -> None:
        # coef_global=0.01, peso=1.0, valor=1.0 -> 0.01
        v = _violaciones_una(NOMBRES_RESTRICCIONES[0], 1.0)
        assert calcular_penalizacion(v, PesosPenalizacion()) == pytest.approx(0.01)

    def test_violaciones_fraccionales_se_propagan(self) -> None:
        # Algunas restricciones (R7, R8) acumulan micro-penalizaciones
        v = _violaciones_una(NOMBRES_RESTRICCIONES[0], 2.5)
        assert calcular_penalizacion(v, PesosPenalizacion()) == pytest.approx(0.025)

    def test_pesos_individuales_se_aplican(self) -> None:
        pesos_dict = {n: 1.0 for n in NOMBRES_RESTRICCIONES}
        pesos_dict[NOMBRES_RESTRICCIONES[0]] = 10.0  # esta pesa x10
        config = PesosPenalizacion(pesos_por_restriccion=pesos_dict)

        v = _violaciones_una(NOMBRES_RESTRICCIONES[0], 1.0)
        # 0.01 * 1.0 * 10.0 = 0.1
        assert calcular_penalizacion(v, config) == pytest.approx(0.1)

    def test_coeficiente_global_anulado_neutraliza_penalty(self) -> None:
        config = PesosPenalizacion(coeficiente_global=0.0)
        v = _violaciones_una(NOMBRES_RESTRICCIONES[0], 100.0)
        assert calcular_penalizacion(v, config) == 0.0

    def test_violaciones_multiples_suman_lineal(self) -> None:
        v = _violaciones_cero()
        v[NOMBRES_RESTRICCIONES[0]] = 3.0
        v[NOMBRES_RESTRICCIONES[1]] = 5.0
        # (3 + 5) * 1.0 * 0.01 = 0.08
        assert calcular_penalizacion(v, PesosPenalizacion()) == pytest.approx(0.08)


# ============================================================================
# desglose_penalizacion (para gráficos)
# ============================================================================


class TestDesglosePenalizacion:
    def test_solucion_factible_todo_ceros(self) -> None:
        v = _violaciones_cero()
        d = desglose_penalizacion(v, PesosPenalizacion())
        assert set(d) == set(NOMBRES_RESTRICCIONES)
        assert all(val == 0.0 for val in d.values())

    def test_suma_del_desglose_igual_penalty_total(self) -> None:
        v = _violaciones_cero()
        v[NOMBRES_RESTRICCIONES[0]] = 4.0
        v[NOMBRES_RESTRICCIONES[3]] = 7.5
        v[NOMBRES_RESTRICCIONES[9]] = 0.3

        config = PesosPenalizacion()
        d = desglose_penalizacion(v, config)
        total = calcular_penalizacion(v, config)
        assert sum(d.values()) == pytest.approx(total)

    def test_pesos_individuales_se_reflejan_en_desglose(self) -> None:
        pesos_dict = {n: 1.0 for n in NOMBRES_RESTRICCIONES}
        pesos_dict[NOMBRES_RESTRICCIONES[2]] = 5.0
        config = PesosPenalizacion(pesos_por_restriccion=pesos_dict)

        v = _violaciones_una(NOMBRES_RESTRICCIONES[2], 1.0)
        d = desglose_penalizacion(v, config)
        # 0.01 * 1.0 * 5.0 = 0.05
        assert d[NOMBRES_RESTRICCIONES[2]] == pytest.approx(0.05)
        # El resto en cero
        for nombre in NOMBRES_RESTRICCIONES:
            if nombre != NOMBRES_RESTRICCIONES[2]:
                assert d[nombre] == 0.0
