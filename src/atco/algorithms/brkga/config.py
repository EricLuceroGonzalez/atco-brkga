"""Configuración del motor BRKGA y criterios de parada."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atco.algorithms.brkga.population import RunState


@dataclass(frozen=True)
class StoppingCriteria:
    """Política de parada del BRKGA: combinación OR de cuatro criterios.

    El motor termina cuando **cualquier** criterio activo se cumple.
    Pasar `None` desactiva ese criterio.

    Attributes:
        max_generations: Tope de generaciones. None = sin tope.
        max_evaluations: Tope de llamadas a `evaluar_fitness`. None = sin tope.
        max_seconds: Tope wall-clock en segundos. None = sin tope.
        stagnation_generations: Generaciones consecutivas sin mejorar el best
            antes de parar. None = sin tope.

    Raises:
        ValueError: Si todos los criterios son `None` (motor sin parada).
    """

    max_generations: int | None = 200
    max_evaluations: int | None = None
    max_seconds: float | None = 300.0
    stagnation_generations: int | None = 1000

    def __post_init__(self) -> None:
        if all(
            v is None
            for v in (
                self.max_generations,
                self.max_evaluations,
                self.max_seconds,
                self.stagnation_generations,
            )
        ):
            raise ValueError(
                "Al menos un criterio de parada debe estar activo "
                "(todos los argumentos son None)"
            )
        for nombre, valor in (
            ("max_generations", self.max_generations),
            ("max_evaluations", self.max_evaluations),
            ("stagnation_generations", self.stagnation_generations),
        ):
            if valor is not None and valor <= 0:
                raise ValueError(f"{nombre} debe ser positivo, recibido {valor}")
        if self.max_seconds is not None and self.max_seconds <= 0:
            raise ValueError(
                f"max_seconds debe ser positivo, recibido {self.max_seconds}"
            )

    def should_stop(self, estado: RunState) -> bool:
        """Devuelve True si algún criterio activo se cumple (OR).

        Args:
            estado: Estado actual de la corrida (generación, evaluaciones,
                tiempo transcurrido, generaciones sin mejora).

        Returns:
            True cuando cualquier criterio no-None llegue a su tope.
        """
        if (
            self.max_generations is not None
            and estado.generation >= self.max_generations
        ):
            return True
        if (
            self.max_evaluations is not None
            and estado.evaluations >= self.max_evaluations
        ):
            return True
        if (
            self.max_seconds is not None
            and estado.elapsed_seconds() >= self.max_seconds
        ):
            return True
        if (
            self.stagnation_generations is not None
            and estado.gens_sin_mejora >= self.stagnation_generations
        ):
            return True
        return False


@dataclass(frozen=True)
class BRKGAConfig:
    """Configuración del motor BRKGA.

    Sigue las convenciones de Resende & Gonçalves (2011): población dividida
    en élite, no-élite y mutantes; crossover sesgado controlado por `rho_elite`.

    Attributes:
        population_size: Tamaño total de la población.
        elite_fraction: Fracción élite, en (0, 0.5].
        mutant_fraction: Fracción de mutantes generados aleatoriamente cada
            generación, en (0, 1 - elite_fraction).
        rho_elite: Probabilidad de heredar un gen del padre élite en el
            crossover sesgado, en [0.5, 1].
        stopping: Criterios de parada.
        seed: Semilla para reproducibilidad. None = no determinista.

    Raises:
        ValueError: Si alguno de los rangos se viola.
    """

    population_size: int = 50
    elite_fraction: float = 0.20
    mutant_fraction: float = 0.20
    rho_elite: float = 0.70
    stopping: StoppingCriteria = StoppingCriteria()
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.population_size < 4:
            raise ValueError(
                f"population_size debe ser ≥ 4, recibido {self.population_size}"
            )
        if not (0.0 < self.elite_fraction <= 0.5):
            raise ValueError(
                f"elite_fraction debe estar en (0, 0.5], recibido {self.elite_fraction}"
            )
        if not (0.0 < self.mutant_fraction < 1.0 - self.elite_fraction):
            raise ValueError(
                f"mutant_fraction debe estar en (0, 1 - elite_fraction), "
                f"recibido {self.mutant_fraction} con elite_fraction={self.elite_fraction}"
            )
        if not (0.5 <= self.rho_elite <= 1.0):
            raise ValueError(
                f"rho_elite debe estar en [0.5, 1.0], recibido {self.rho_elite}"
            )

    @property
    def n_elite(self) -> int:
        """Número de individuos élite (redondeado a entero)."""
        return max(1, round(self.population_size * self.elite_fraction))

    @property
    def n_mutants(self) -> int:
        """Número de mutantes por generación."""
        return max(1, round(self.population_size * self.mutant_fraction))

    @property
    def n_crossover(self) -> int:
        """Número de hijos por crossover sesgado."""
        return self.population_size - self.n_elite - self.n_mutants
