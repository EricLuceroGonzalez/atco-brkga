"""BRKGA con BinMidpointDecoder, sembrado con codificación inversa del greedy."""

from __future__ import annotations

import logging
import random
from pathlib import Path

import numpy as np

from atco.algorithms.brkga import BRKGAConfig, BRKGAEngine, StoppingCriteria
from atco.algorithms.brkga.decoders import (
    BinMidpointDecoder,
    construir_alfabeto,
    encode_solucion,
)
from atco.fitness import FitnessConfig
from atco.io.logging_setup import setup_logging
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds import construir_solucion_heuristica


def main() -> None:
    setup_logging(level="INFO")
    log = logging.getLogger("bin-midpoint")

    REPO_ROOT = Path(__file__).resolve().parent.parent
    p = Parametros.from_files(
        REPO_ROOT / "resources/problemParameters.properties",
        REPO_ROOT / "resources/options.properties",
    )
    e = Entrada.leer_entrada(REPO_ROOT, p, "madN_M1", "madN_M1-2019-02-12", "Madrid")

    n = len(e.get_controladores())
    sol_heuristica = construir_solucion_heuristica(e, p, rng=random.Random(42))
    T = len(sol_heuristica.turnos[0]) // 3
    alfabeto = construir_alfabeto(e)

    log.info("N=%d, T=%d, |alfabeto|=%d, L=N·T=%d", n, T, len(alfabeto), n * T)

    decoder = BinMidpointDecoder(n_controladores=n, longitud_t=T, alfabeto=alfabeto)

    # Warm-start con la semilla heurística codificada (round-trip exacto)
    seed_chromosome = encode_solucion(sol_heuristica, longitud_t=T, alfabeto=alfabeto)

    config = BRKGAConfig(
        population_size=100,
        elite_fraction=0.20,
        mutant_fraction=0.30,
        rho_elite=0.75,
        seed=42,
        stopping=StoppingCriteria(
            max_generations=50,
            max_seconds=300.0,
            stagnation_generations=25,
            max_evaluations=None,
        ),
    )
    engine = BRKGAEngine(config, FitnessConfig(), decoder)
    result = engine.run(e, p, seed_chromosomes=[seed_chromosome])

    log.info("=" * 60)
    log.info("Semilla heurística codificada : %.6f", result.seed_fitness)
    log.info("Mejor encontrado por BRKGA    : %.6f", result.best_individual.fitness)
    log.info("Mejora relativa               : %.2f%%", result.mejora_relativa * 100)


if __name__ == "__main__":
    main()
