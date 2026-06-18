"""Tests de los operadores genéticos."""

from __future__ import annotations

import numpy as np
import pytest

from atco.algorithms.brkga.operators import (
    biased_crossover,
    diversidad_poblacion,
    random_chromosome,
)


class TestRandomChromosome:
    def test_shape_correcta(self) -> None:
        rng = np.random.default_rng(42)
        c = random_chromosome(rng, num_genes=10)
        assert c.shape == (10,)

    def test_valores_en_rango_unitario(self) -> None:
        rng = np.random.default_rng(42)
        c = random_chromosome(rng, num_genes=100)
        assert (c >= 0.0).all() and (c <= 1.0).all()

    def test_reproducibilidad(self) -> None:
        c1 = random_chromosome(np.random.default_rng(7), 20)
        c2 = random_chromosome(np.random.default_rng(7), 20)
        assert np.allclose(c1, c2)


class TestBiasedCrossover:
    def test_shapes_distintos_lanzan_error(self) -> None:
        rng = np.random.default_rng(0)
        with pytest.raises(ValueError, match="shape"):
            biased_crossover(np.zeros(5), np.zeros(3), 0.7, rng)

    def test_rho_uno_hereda_todo_del_elite(self) -> None:
        rng = np.random.default_rng(0)
        elite = np.ones(10)
        non_elite = np.zeros(10)
        hijo = biased_crossover(elite, non_elite, rho_elite=1.0, rng=rng)
        assert np.allclose(hijo, elite)

    def test_rho_cero_hereda_todo_del_no_elite(self) -> None:
        rng = np.random.default_rng(0)
        elite = np.ones(10)
        non_elite = np.zeros(10)
        hijo = biased_crossover(elite, non_elite, rho_elite=0.0, rng=rng)
        assert np.allclose(hijo, non_elite)

    def test_rho_medio_mezcla_genes(self) -> None:
        rng = np.random.default_rng(42)
        elite = np.ones(1000)
        non_elite = np.zeros(1000)
        hijo = biased_crossover(elite, non_elite, rho_elite=0.7, rng=rng)
        proporcion_elite = float(hijo.sum() / len(hijo))
        # 0.7 ± 0.05 con 1000 genes es razonable
        assert 0.65 <= proporcion_elite <= 0.75


class TestDiversidad:
    def test_lista_vacia_o_corta_devuelve_cero(self) -> None:
        assert diversidad_poblacion([]) == 0.0
        assert diversidad_poblacion([0.5]) == 0.0

    def test_todos_iguales_devuelve_cero(self) -> None:
        assert diversidad_poblacion([0.3, 0.3, 0.3, 0.3]) == 0.0

    def test_diversidad_positiva_con_valores_distintos(self) -> None:
        assert diversidad_poblacion([0.0, 1.0, 0.5, 0.2]) > 0.0
