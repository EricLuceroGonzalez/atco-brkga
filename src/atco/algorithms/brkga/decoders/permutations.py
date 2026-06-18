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
    """Decoder de permutación implícita basado en prioridades por controlador.

    El cromosoma tiene `N` genes, uno por controlador. El valor
    `chromosome[i] ∈ [0, 1]` es la prioridad global del controlador `i`
    para la fase 2 (fresh-pick) del greedy. Se aplica como tiebreaker
    tras ordenar por `slots_trabajados`: mayor `chromosome[i]` gana el
    empate.

    El decoder es determinista dado un cromosoma: para el mismo
    cromosoma y la misma entrada, produce la misma solución. La
    aleatoriedad del shuffle de sectores se fija con un `rng` interno
    de semilla constante.

    Attributes:
        n_controladores: Número de controladores que el decoder espera
            (igual al número de genes del cromosoma).
    """

    _RNG_SEED_INTERNO: int = 0

    def __init__(self, n_controladores: int) -> None:
        if n_controladores <= 0:
            raise ValueError(
                f"n_controladores debe ser positivo, recibido {n_controladores}"
            )
        self.n_controladores = n_controladores

    @property
    def num_genes(self) -> int:
        return self.n_controladores

    def decode(
        self,
        chromosome: np.ndarray,
        entrada: Entrada,
        parametros: Parametros,
    ) -> Solucion:
        """Decodifica un cromosoma a una `Solucion` factible.

        Args:
            chromosome: Vector de prioridades, shape (`n_controladores`,).
            entrada: Instancia del problema.
            parametros: Parámetros del dominio.

        Returns:
            `Solucion` resultante de aplicar el greedy con `chromosome`
            como tiebreaker en la fase 2.

        Raises:
            ValueError: Si el cromosoma no cumple el contrato (shape o
                rango), o si el número de controladores de la entrada
                no coincide con `n_controladores`.
        """
        self.validate_chromosome(chromosome)
        n_real = len(entrada.get_controladores())
        if n_real != self.n_controladores:
            raise ValueError(
                f"Entrada tiene {n_real} controladores pero el decoder "
                f"espera {self.n_controladores}"
            )
        return construir_solucion_heuristica(
            entrada=entrada,
            parametros=parametros,
            rng=random.Random(self._RNG_SEED_INTERNO),
            prioridad=chromosome.tolist(),
        )
