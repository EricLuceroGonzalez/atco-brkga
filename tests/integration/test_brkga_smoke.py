"""Smoke test del motor BRKGA con instancia real y pocas generaciones."""

from __future__ import annotations

from atco.algorithms.brkga import BRKGAConfig, BRKGAEngine, StoppingCriteria
from atco.algorithms.brkga.decoders import PermutationDecoder
from atco.fitness import FitnessConfig
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


def test_brkga_converge_o_al_menos_no_empeora(
    entrada_mad_n_m1: Entrada, parametros: Parametros
) -> None:
    """Tras N generaciones, el mejor fitness no debe ser peor que la semilla."""
    n = len(entrada_mad_n_m1.get_controladores())
    decoder = PermutationDecoder(n_controladores=n)
    config = BRKGAConfig(
        population_size=20,
        elite_fraction=0.20,
        mutant_fraction=0.20,
        rho_elite=0.70,
        seed=42,
        stopping=StoppingCriteria(
            max_generations=10,
            max_evaluations=None,
            max_seconds=60.0,
            stagnation_generations=None,
        ),
    )
    engine = BRKGAEngine(
        config=config,
        fitness_config=FitnessConfig(),
        decoder=decoder,
    )
    result = engine.run(entrada_mad_n_m1, parametros)

    assert result.best_individual.fitness <= result.seed_fitness, (
        f"Mejor ({result.best_individual.fitness:.4f}) peor que la semilla "
        f"({result.seed_fitness:.4f}) — el motor no mejora ni mantiene."
    )
    assert result.generations >= 1
    assert len(result.history) >= 1
    assert result.history[0].generation == 0


def test_brkga_record_de_convergencia_es_coherente(
    entrada_mad_n_m1: Entrada, parametros: Parametros
) -> None:
    """Cada record tiene best ≤ avg ≤ worst y métricas no negativas."""
    n = len(entrada_mad_n_m1.get_controladores())
    decoder = PermutationDecoder(n_controladores=n)
    config = BRKGAConfig(
        population_size=12,
        seed=0,
        stopping=StoppingCriteria(
            max_generations=5,
            max_seconds=60.0,
            max_evaluations=None,
            stagnation_generations=None,
        ),
    )
    engine = BRKGAEngine(config, FitnessConfig(), decoder)
    result = engine.run(entrada_mad_n_m1, parametros)

    for rec in result.history:
        assert rec.best_fitness <= rec.avg_fitness <= rec.worst_fitness
        assert rec.diversity >= 0.0
        assert rec.elapsed_seconds >= 0.0
        assert rec.evaluations > 0
