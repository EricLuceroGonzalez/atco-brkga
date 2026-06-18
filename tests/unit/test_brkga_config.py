"""Tests de configuración del BRKGA."""

from __future__ import annotations

import pytest

from atco.algorithms.brkga.config import BRKGAConfig, StoppingCriteria


class TestStoppingCriteria:
    def test_defaults_son_validos(self) -> None:
        sc = StoppingCriteria()
        assert sc.max_generations == 200
        assert sc.max_seconds == 300.0

    def test_todos_none_lanza_error(self) -> None:
        with pytest.raises(ValueError, match="al menos un criterio|todos los"):
            StoppingCriteria(
                max_generations=None,
                max_evaluations=None,
                max_seconds=None,
                stagnation_generations=None,
            )

    def test_valores_no_positivos_lanzan_error(self) -> None:
        with pytest.raises(ValueError, match="max_generations"):
            StoppingCriteria(max_generations=0)
        with pytest.raises(ValueError, match="max_seconds"):
            StoppingCriteria(max_seconds=-1.0)

    def test_should_stop_max_generations(self) -> None:
        from atco.algorithms.brkga.population import RunState

        sc = StoppingCriteria(
            max_generations=5,
            max_evaluations=None,
            max_seconds=None,
            stagnation_generations=None,
        )
        assert not sc.should_stop(
            RunState(generation=4, evaluations=0, gens_sin_mejora=0)
        )
        assert sc.should_stop(RunState(generation=5, evaluations=0, gens_sin_mejora=0))

    def test_should_stop_stagnation(self) -> None:
        from atco.algorithms.brkga.population import RunState

        sc = StoppingCriteria(
            max_generations=None,
            max_evaluations=None,
            max_seconds=None,
            stagnation_generations=10,
        )
        assert not sc.should_stop(
            RunState(generation=0, evaluations=0, gens_sin_mejora=9)
        )
        assert sc.should_stop(RunState(generation=0, evaluations=0, gens_sin_mejora=10))

    def test_should_stop_or_de_varios_criterios(self) -> None:
        """Cualquier criterio activo dispara la parada."""
        from atco.algorithms.brkga.population import RunState

        sc = StoppingCriteria(
            max_generations=100,
            max_evaluations=None,
            max_seconds=None,
            stagnation_generations=5,
        )
        # Sin alcanzar ningún tope, no para
        assert not sc.should_stop(
            RunState(generation=10, evaluations=0, gens_sin_mejora=4)
        )
        # Estancado dispara aunque queden generaciones
        assert sc.should_stop(RunState(generation=10, evaluations=0, gens_sin_mejora=5))


class TestBRKGAConfig:
    def test_defaults_son_validos(self) -> None:
        cfg = BRKGAConfig()
        assert cfg.population_size == 50
        assert cfg.n_elite == 10
        assert cfg.n_mutants == 10
        assert cfg.n_crossover == 30

    def test_population_size_minimo(self) -> None:
        with pytest.raises(ValueError, match="population_size"):
            BRKGAConfig(population_size=3)

    def test_elite_fraction_fuera_de_rango(self) -> None:
        with pytest.raises(ValueError, match="elite_fraction"):
            BRKGAConfig(elite_fraction=0.6)

    def test_mutant_fraction_fuera_de_rango(self) -> None:
        with pytest.raises(ValueError, match="mutant_fraction"):
            BRKGAConfig(elite_fraction=0.5, mutant_fraction=0.5)

    def test_rho_elite_fuera_de_rango(self) -> None:
        with pytest.raises(ValueError, match="rho_elite"):
            BRKGAConfig(rho_elite=0.4)

    def test_suma_de_clases_iguala_poblacion(self) -> None:
        cfg = BRKGAConfig(population_size=100)
        assert cfg.n_elite + cfg.n_mutants + cfg.n_crossover == cfg.population_size
