"""Decoder de permutación implícita: random keys como prioridad por controlador."""

from __future__ import annotations

import random

import numpy as np

from atco.algorithms.brkga.decoders.base import DecoderBase
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds import construir_solucion_heuristica


class PermutationDecoder(DecoderBase):
    """Decoder de permutación implícita basado en prioridades por controlador y por sector.

    El cromosoma tiene `L = N + |S|` genes:
        - Los primeros `N` son prioridades por controlador (criterio primario
          en la fase 2 del greedy).
        - Los últimos `|S|` son prioridades por sector (orden de procesamiento
          en cada slot).

    Ambas dimensiones rompen simetrías del problema y dan al BRKGA leverage
    para distinguir soluciones permutadas.

    Attributes:
        n_controladores: Número de controladores que el decoder espera.
        n_sectores: Número de sectores globales.
    """

    _RNG_SEED_INTERNO: int = 0

    def __init__(self, n_controladores: int, n_sectores: int) -> None:
        if n_controladores <= 0:
            raise ValueError(
                f"n_controladores debe ser positivo, recibido {n_controladores}"
            )
        if n_sectores <= 0:
            raise ValueError(f"n_sectores debe ser positivo, recibido {n_sectores}")
        self.n_controladores = n_controladores
        self.n_sectores = n_sectores

    @property
    def num_genes(self) -> int:
        return self.n_controladores + self.n_sectores

    def decode(
        self,
        chromosome: np.ndarray,
        entrada: Entrada,
        parametros: Parametros,
    ) -> Solucion:
        """Decodifica un cromosoma a una `Solucion` factible.

        Args:
            chromosome: Vector de shape `(n_controladores + n_sectores,)`.
            entrada: Instancia del problema.
            parametros: Parámetros del dominio.

        Returns:
            `Solucion` resultante de aplicar el greedy con las dos
            dimensiones del cromosoma como guía.

        Raises:
            ValueError: Si la entrada no encaja con las dimensiones del
                decoder.
        """
        self.validate_chromosome(chromosome)

        n_real = len(entrada.get_controladores())
        if n_real != self.n_controladores:
            raise ValueError(
                f"Entrada tiene {n_real} controladores pero el decoder "
                f"espera {self.n_controladores}"
            )

        all_sectores = sorted(
            entrada.get_lista_sectores(),
            key=lambda s: s.id,
        )
        if len(all_sectores) != self.n_sectores:
            raise ValueError(
                f"Entrada tiene {len(all_sectores)} sectores pero el decoder "
                f"espera {self.n_sectores}"
            )

        priority_atcos = chromosome[: self.n_controladores].tolist()
        sector_genes = chromosome[self.n_controladores :]
        priority_sectores: dict[str, float] = {
            s.id: float(sector_genes[i]) for i, s in enumerate(all_sectores)
        }

        return construir_solucion_heuristica(
            entrada=entrada,
            parametros=parametros,
            rng=random.Random(self._RNG_SEED_INTERNO),
            prioridad=priority_atcos,
            prioridad_sectores=priority_sectores,
        )


def chromosome_from_solucion(
    solucion: Solucion,
    n_controladores: int,
    longitud_t: int,
    n_sectores: int,
) -> np.ndarray:
    """..."""
    if len(solucion.controladores) != n_controladores:
        raise ValueError(...)
    atco_part = np.array(
        [1.0 - (c.slots_trabajados / longitud_t) for c in solucion.controladores],
        dtype=float,
    )
    atco_part = np.clip(atco_part, 0.0, 1.0)
    # Sin información para derivar prioridad de sectores: aleatorio
    sector_part = np.random.default_rng(0).random(n_sectores)
    return np.concatenate([atco_part, sector_part])
