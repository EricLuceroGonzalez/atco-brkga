"""Tests del componente `balance_carga` (desviación estándar de cargas)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from atco.fitness.components import balance_carga


@dataclass
class _ControladorMock:
    slots_trabajados: int


@dataclass
class _SolucionMock:
    controladores: list[_ControladorMock] = field(default_factory=list)
    turnos: list[str] = field(default_factory=list)  # no se consulta aquí


def _sol(cargas: list[int]) -> _SolucionMock:
    """Factory: crea una Solucion con n controladores cuyos slots_trabajados son `cargas`."""
    return _SolucionMock(controladores=[_ControladorMock(s) for s in cargas])


# ============================================================================
# Casos base
# ============================================================================


class TestBalanceCargaBase:
    def test_sin_controladores(self) -> None:
        sol = _SolucionMock()
        assert balance_carga(sol) == (0.0, 0.0)

    def test_un_unico_controlador(self) -> None:
        # n=1: media=carga, varianza=0, σ=0
        sol = _sol([50])
        sigma, sigma_max = balance_carga(sol)
        assert sigma == 0.0
        assert sigma_max == 50.0

    def test_todos_con_carga_cero(self) -> None:
        # Nadie trabajó -> caso degenerado, devuelve (0, 0)
        sol = _sol([0, 0, 0])
        assert balance_carga(sol) == (0.0, 0.0)


# ============================================================================
# Balance perfecto y desbalance máximo
# ============================================================================


class TestExtremos:
    def test_balance_perfecto_dos_controladores(self) -> None:
        sol = _sol([40, 40])
        sigma, sigma_max = balance_carga(sol)
        assert sigma == 0.0
        assert sigma_max == 40.0

    def test_balance_perfecto_cuatro_controladores(self) -> None:
        sol = _sol([30, 30, 30, 30])
        sigma, sigma_max = balance_carga(sol)
        assert sigma == 0.0
        assert sigma_max == 30.0

    def test_desbalance_maximo_dos_controladores(self) -> None:
        # Uno trabaja 80, el otro 0 -> media=40, var=40², σ=40 (= σ_max)
        sol = _sol([80, 0])
        sigma, sigma_max = balance_carga(sol)
        assert sigma == pytest.approx(40.0)
        assert sigma_max == pytest.approx(40.0)
        assert sigma == pytest.approx(sigma_max)  # peor caso

    def test_desbalance_maximo_cuatro_controladores(self) -> None:
        # Mitad trabajando 100, mitad 0 -> media=50, var=50², σ=50
        sol = _sol([100, 100, 0, 0])
        sigma, sigma_max = balance_carga(sol)
        assert sigma == pytest.approx(50.0)
        assert sigma_max == pytest.approx(50.0)


# ============================================================================
# Casos intermedios + comparación con el rango
# ============================================================================


class TestSensibilidad:
    def test_outlier_unico_apenas_mueve_sigma(self) -> None:
        """Un único atípico (vs el rango): σ se mueve poco, max-min se dispara."""
        cargas_homogeneas = [40] * 9 + [80]  # 9 normales, 1 atípico
        sol = _sol(cargas_homogeneas)
        sigma, sigma_max = balance_carga(sol)

        # rango = 80 - 40 = 40 (la mitad de la media)
        # σ = sqrt((9·(40-44)² + 1·(80-44)²) / 10) = sqrt((144 + 1296)/10) = sqrt(144) = 12
        assert sigma == pytest.approx(12.0)
        assert sigma_max == pytest.approx(44.0)
        # 12 / 44 ≈ 0.27, vs el rango que daría 40/80 = 0.5 -> σ es menos sensible

    def test_desbalance_sistematico_mueve_sigma(self) -> None:
        """Cuando la mitad trabaja más, σ sí refleja la dispersión."""
        sol = _sol([60, 60, 60, 60, 20, 20, 20, 20])
        sigma, sigma_max = balance_carga(sol)
        # media = 40, varianza = ((4·400) + (4·400))/8 = 400, σ = 20
        assert sigma == pytest.approx(20.0)
        assert sigma_max == pytest.approx(40.0)


# ============================================================================
# Casos con controladores inactivos
# ============================================================================


class TestInactivos:
    def test_un_controlador_inactivo_baja_la_media(self) -> None:
        sol = _sol([60, 60, 0])
        sigma, sigma_max = balance_carga(sol)
        # media = 40
        # varianza = ((60-40)² · 2 + (0-40)²) / 3 = (800 + 1600)/3 = 800
        # σ ≈ 28.28
        assert sigma_max == pytest.approx(40.0)
        assert sigma == pytest.approx(800**0.5)


# ============================================================================
# Propiedades invariantes
# ============================================================================


class TestPropiedadesInvariantes:
    @pytest.mark.parametrize(
        "cargas",
        [
            [10],
            [10, 10, 10],
            [80, 60, 40, 20],
            [0, 50, 50],
            [55, 45, 50, 50, 50],
        ],
    )
    def test_sigma_no_supera_sigma_max(self, cargas: list[int]) -> None:
        sol = _sol(cargas)
        sigma, sigma_max = balance_carga(sol)
        assert sigma >= 0.0
        assert sigma_max >= 0.0
        assert sigma <= sigma_max + 1e-9

    @pytest.mark.parametrize(
        "cargas",
        [
            [10, 10, 10, 10],
            [25, 25, 25, 25, 25],
            [42, 42],
        ],
    )
    def test_cargas_iguales_dan_sigma_cero(self, cargas: list[int]) -> None:
        sol = _sol(cargas)
        sigma, sigma_max = balance_carga(sol)
        assert sigma == pytest.approx(0.0)
        # sigma_max > 0 si hay trabajo
        assert sigma_max == pytest.approx(cargas[0])
