"""Motor BRKGA: bucle de evolución generación a generación."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from atco.algorithms.brkga.config import BRKGAConfig
from atco.algorithms.brkga.decoders.base import DecoderBase
from atco.algorithms.brkga.operators import (
    biased_crossover,
    diversidad_poblacion,
    random_chromosome,
)
from atco.algorithms.brkga.population import (
    ConvergenceRecord,
    Individual,
    Population,
    RunState,
)
from atco.domain.models import Solucion
from atco.fitness import FitnessConfig, FitnessResult, evaluar_fitness
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    """Resultado final de una corrida del BRKGA.

    Attributes:
        best_individual: Mejor individuo encontrado.
        best_solution: Solución decodificada del mejor cromosoma.
        best_fitness_result: Desglose del fitness del mejor (R, C, B, F, L).
        history: Lista de `ConvergenceRecord` por generación.
        seed_fitness: Fitness del mejor de la población inicial (semilla).
        elapsed_seconds: Tiempo total wall-clock.
        generations: Número total de generaciones ejecutadas.
        evaluations: Número total de evaluaciones de fitness.
    """

    best_individual: Individual
    best_solution: Solucion
    best_fitness_result: FitnessResult
    history: list[ConvergenceRecord]
    seed_fitness: float
    elapsed_seconds: float
    generations: int
    evaluations: int

    @property
    def mejora_relativa(self) -> float:
        """Mejora relativa del mejor frente a la semilla inicial."""
        if self.seed_fitness == 0:
            return 0.0
        return (self.seed_fitness - self.best_individual.fitness) / self.seed_fitness


class BRKGAEngine:
    """Motor genérico del BRKGA.

    No conoce el dominio: confía en el `decoder` para producir soluciones
    y en `evaluar_fitness` con `fitness_config` para evaluarlas.
    """

    def __init__(
        self,
        config: BRKGAConfig,
        fitness_config: FitnessConfig,
        decoder: DecoderBase,
    ) -> None:
        self.config = config
        self.fitness_config = fitness_config
        self.decoder = decoder

    def run(
        self,
        entrada: Entrada,
        parametros: Parametros,
        seed_chromosomes: list[np.ndarray] | None = None,
    ) -> RunResult:
        """Ejecuta el BRKGA hasta que se cumpla algún criterio de parada.

        Returns:
            `RunResult` con el mejor individuo, su solución decodificada,
            el desglose de fitness y el historial de convergencia.
        """
        rng = np.random.default_rng(self.config.seed)
        n_genes = self.decoder.num_genes
        start_time = time.monotonic()

        population = self._initial_population(
            rng, n_genes, entrada, parametros, seed_chromosomes
        )
        log.debug("Pop = %s", population)
        log.debug("Pop length = %s", len(population.individuals))
        evaluations = len(population.individuals)
        best = population.best
        seed_fitness = best.fitness
        gens_sin_mejora = 0
        history: list[ConvergenceRecord] = []
        generation = 0

        log.info(
            "✅ BRKGA arranca | pop=%d élite=%d mutantes=%d cross=%d rho_e=%.2f | "
            "seed_fitness=%.4f",
            self.config.population_size,
            self.config.n_elite,
            self.config.n_mutants,
            self.config.n_crossover,
            self.config.rho_elite,
            seed_fitness,
        )

        while True:
            state = RunState(
                generation=generation,
                evaluations=evaluations,
                gens_sin_mejora=gens_sin_mejora,
                _start_time=start_time,
            )
            history.append(self._record(generation, population, state))

            if self.config.stopping.should_stop(state):
                break

            population = self._next_generation(
                population, rng, n_genes, entrada, parametros
            )
            evaluations += self.config.n_mutants + self.config.n_crossover

            new_best = population.best
            if new_best.fitness < best.fitness - 1e-9:
                log.info(
                    "Gen %d | mejora: %.4f → %.4f (Δ=%.4f)",
                    generation + 1,
                    best.fitness,
                    new_best.fitness,
                    best.fitness - new_best.fitness,
                )
                best = new_best
                gens_sin_mejora = 0
            else:
                gens_sin_mejora += 1

            generation += 1

        elapsed = time.monotonic() - start_time
        best_solution = self.decoder.decode(best.chromosome, entrada, parametros)
        best_fitness_result = evaluar_fitness(
            best_solution, entrada, parametros, self.fitness_config
        )

        log.info(
            "BRKGA terminó | gens=%d evals=%d best=%.4f mejora=%.2f%% tiempo=%.1fs",
            generation,
            evaluations,
            best.fitness,
            (
                ((seed_fitness - best.fitness) / seed_fitness * 100)
                if seed_fitness
                else 0.0
            ),
            elapsed,
        )

        return RunResult(
            best_individual=best,
            best_solution=best_solution,
            best_fitness_result=best_fitness_result,
            history=history,
            seed_fitness=seed_fitness,
            elapsed_seconds=elapsed,
            generations=generation,
            evaluations=evaluations,
        )

    def _initial_population(
        self,
        rng: np.random.Generator,
        n_genes: int,
        entrada: Entrada,
        parametros: Parametros,
        seed_chromosomes: list[np.ndarray] | None,
    ) -> Population:
        individuals: list[Individual] = []
        seed_chromosomes = seed_chromosomes or []
        for chromosome in seed_chromosomes:
            if chromosome.shape != (n_genes,):
                raise ValueError(
                    f"seed_chromosome con shape {chromosome.shape} "
                    f"(esperado ({n_genes},))"
                )
            individuals.append(self._evaluate(chromosome, entrada, parametros))
        n_restantes = self.config.population_size - len(individuals)
        if n_restantes < 0:
            raise ValueError(
                f"Demasiados seed_chromosomes ({len(seed_chromosomes)}) "
                f"para population_size={self.config.population_size}"
            )
        for _ in range(n_restantes):
            individuals.append(
                self._evaluate(random_chromosome(rng, n_genes), entrada, parametros)
            )
        valores = sorted([ind.fitness for ind in individuals])
        log.info(
            "Pop inicial | N=%d | best=%.4f avg=%.4f worst=%.4f | distintos=%d",
            len(individuals),
            min(valores),
            sum(valores) / len(valores),
            max(valores),
            len(set(round(v, 6) for v in valores)),
        )
        return Population(individuals=individuals)

    def _next_generation(
        self,
        population: Population,
        rng: np.random.Generator,
        n_genes: int,
        entrada: Entrada,
        parametros: Parametros,
    ) -> Population:
        ordered = population.sorted_by_fitness()
        elite = ordered[: self.config.n_elite]
        non_elite = ordered[self.config.n_elite :]

        next_individuals: list[Individual] = list(elite)

        # Mutantes
        for _ in range(self.config.n_mutants):
            chromosome = random_chromosome(rng, n_genes)
            next_individuals.append(self._evaluate(chromosome, entrada, parametros))

        # Hijos por crossover sesgado
        for _ in range(self.config.n_crossover):
            parent_elite = elite[rng.integers(len(elite))].chromosome
            parent_non_elite = non_elite[rng.integers(len(non_elite))].chromosome
            child = biased_crossover(
                parent_elite, parent_non_elite, self.config.rho_elite, rng
            )
            next_individuals.append(self._evaluate(child, entrada, parametros))
        valores = sorted([ind.fitness for ind in next_individuals])
        log.info(
            "Pop nueva  | best=%.4f avg=%.4f worst=%.4f | distintos=%d",
            min(valores),
            sum(valores) / len(valores),
            max(valores),
            len(set(round(v, 6) for v in valores)),
        )
        return Population(individuals=next_individuals)

    def _evaluate(
        self,
        chromosome: np.ndarray,
        entrada: Entrada,
        parametros: Parametros,
    ) -> Individual:
        solucion = self.decoder.decode(chromosome, entrada, parametros)
        result = evaluar_fitness(solucion, entrada, parametros, self.fitness_config)
        return Individual(
            chromosome=chromosome,
            fitness=result.valor,
            fitness_result=result,
        )

    def _record(
        self,
        generation: int,
        population: Population,
        state: RunState,
    ) -> ConvergenceRecord:
        vals = population.fitness_values
        best_ind = min(population.individuals, key=lambda i: i.fitness)
        components = None
        violadas = None
        if best_ind.fitness_result is not None:
            components = dict(best_ind.fitness_result.componentes)
            violadas = list(best_ind.fitness_result.restricciones_violadas)
        return ConvergenceRecord(
            generation=generation,
            best_fitness=min(vals),
            avg_fitness=sum(vals) / len(vals),
            worst_fitness=max(vals),
            diversity=diversidad_poblacion(vals),
            elapsed_seconds=state.elapsed_seconds(),
            evaluations=state.evaluations,
            best_components=components,
            best_restricciones_violadas=violadas,
        )
