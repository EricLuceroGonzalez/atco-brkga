"""Estructuras de datos del BRKGA: individuo, población y estado de corrida."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Individual:
    """Un individuo de la población BRKGA.

    Attributes:
        chromosome: Vector de random keys en [0, 1], shape `(num_genes,)`.
        fitness: Valor escalar a minimizar.
    """

    chromosome: np.ndarray
    fitness: float


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
