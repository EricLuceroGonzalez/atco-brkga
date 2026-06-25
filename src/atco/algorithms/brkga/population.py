"""Estructuras de datos del BRKGA: individuo, población y estado de corrida."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from atco.fitness import FitnessResult


@dataclass
class Individual:
    """Un individuo de la población BRKGA.

    Attributes:
        chromosome: Vector de random keys en [0, 1], shape `(num_genes,)`.
        fitness: Valor escalar a minimizar.
    """

    chromosome: np.ndarray
    fitness: float
    fitness_result: FitnessResult | None = None


@dataclass
class Population:
    """Población de individuos, sin orden garantizado."""

    individuals: list[Individual]

    def sorted_by_fitness(self) -> list[Individual]:
        """Devuelve la población ordenada por fitness ascendente (mejor primero)."""
        return sorted(self.individuals, key=lambda ind: ind.fitness)

    @property
    def best(self) -> Individual:
        return min(self.individuals, key=lambda ind: ind.fitness)

    @property
    def fitness_values(self) -> list[float]:
        return [ind.fitness for ind in self.individuals]


@dataclass
class RunState:
    """Estado de la corrida BRKGA, consumido por `StoppingCriteria.should_stop`."""

    generation: int
    evaluations: int
    gens_sin_mejora: int
    _start_time: float = field(default_factory=time.monotonic)

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time


@dataclass(frozen=True)
class ConvergenceRecord:
    """Snapshot de una generación para análisis posterior."""

    generation: int
    best_fitness: float
    avg_fitness: float
    worst_fitness: float
    diversity: float
    elapsed_seconds: float
    evaluations: int
    best_components: dict[str, float] | None = None
    best_restricciones_violadas: list[str] | None = None
    best_objetivos: dict[str, float] | None = None
    best_violaciones: dict[str, float] | None = None
    best_r: float | None = None
    best_f_factibilidad: float | None = None
    best_f_rendimiento: float | None = None


def record_from_best(
    best: Individual,
    population: Population,
    state: RunState,
    diversity: float,
) -> ConvergenceRecord:
    """Construye un `ConvergenceRecord` poblando todos los campos opcionales
    desde `best.fitness_result` si está disponible.

    Centraliza el desempaquetado para que el engine no tenga que conocer
    la estructura interna de `FitnessResult`.
    """
    fits = population.fitness_values
    fr = best.fitness_result

    return ConvergenceRecord(
        generation=state.generation,
        best_fitness=best.fitness,
        avg_fitness=float(sum(fits) / len(fits)) if fits else float("nan"),
        worst_fitness=max(fits) if fits else float("nan"),
        diversity=diversity,
        elapsed_seconds=state.elapsed_seconds(),
        evaluations=state.evaluations,
        best_components=dict(fr.componentes) if fr else None,
        best_restricciones_violadas=list(fr.restricciones_violadas) if fr else None,
        best_objetivos=dict(getattr(fr, "objetivos", {})) if fr else None,
        best_violaciones=dict(getattr(fr, "violaciones", {})) if fr else None,
        best_r=getattr(fr, "r_actual", None) if fr else None,
        best_f_factibilidad=getattr(fr, "f_factibilidad", None) if fr else None,
        best_f_rendimiento=getattr(fr, "f_rendimiento", None) if fr else None,
    )
