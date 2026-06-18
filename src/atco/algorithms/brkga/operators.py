"""Operadores genéticos del BRKGA: aleatorio inicial, crossover sesgado."""

from __future__ import annotations

import numpy as np


def random_chromosome(rng: np.random.Generator, num_genes: int) -> np.ndarray:
    """Genera un cromosoma aleatorio con valores en [0, 1].

    Args:
        rng: Generador NumPy.
        num_genes: Longitud `L` del cromosoma.

    Returns:
        Vector NumPy de shape `(num_genes,)` con valores en [0, 1].
    """
    return rng.random(num_genes)


def biased_crossover(
    parent_elite: np.ndarray,
    parent_non_elite: np.ndarray,
    rho_elite: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Crossover sesgado de Resende & Gonçalves (2011).

    Para cada gen, el hijo hereda del padre élite con probabilidad
    `rho_elite`; en caso contrario del padre no-élite.

    Args:
        parent_elite: Cromosoma del padre élite.
        parent_non_elite: Cromosoma del padre no-élite.
        rho_elite: Probabilidad de heredar del élite, en [0.5, 1].
        rng: Generador NumPy.

    Returns:
        Cromosoma hijo del mismo shape que los padres.

    Raises:
        ValueError: Si los padres tienen shapes distintos.
    """
    if parent_elite.shape != parent_non_elite.shape:
        raise ValueError(
            f"Padres con shape distinto: élite {parent_elite.shape}, "
            f"no-élite {parent_non_elite.shape}"
        )
    mask = rng.random(parent_elite.shape[0]) < rho_elite
    return np.where(mask, parent_elite, parent_non_elite)


def diversidad_poblacion(fitness_values: list[float]) -> float:
    """Métrica simple de diversidad: desviación estándar del fitness.

    Args:
        fitness_values: Lista de fitness de toda la población.

    Returns:
        Desviación estándar muestral. Cero si todos son iguales o si la
        lista tiene menos de dos elementos.
    """
    if len(fitness_values) < 2:
        return 0.0
    return float(np.std(fitness_values, ddof=1))
