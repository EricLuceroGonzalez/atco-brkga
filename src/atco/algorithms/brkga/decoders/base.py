"""Contrato común a todos los decoders del BRKGA."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


class DecoderBase(ABC):
    """Contrato de un decoder BRKGA.

    Un decoder transforma un cromosoma de valores aleatorios en [0, 1] en
    una `Solucion` concreta del problema. Es la **única** pieza específica
    del dominio dentro del BRKGA: el motor (engine, operators, population)
    es genérico y se reutiliza para cualquier problema.

    Subclases deben implementar:
        - `num_genes`: la longitud `L` del cromosoma que esperan.
        - `decode`: la función `[0, 1]^L -> Solucion`.
    """

    @property
    @abstractmethod
    def num_genes(self) -> int:
        """Longitud `L` del cromosoma que el decoder espera recibir."""

    @abstractmethod
    def decode(
        self,
        chromosome: np.ndarray,
        entrada: Entrada,
        parametros: Parametros,
    ) -> Solucion:
        """Decodifica un cromosoma en una solución factible (o casi).

        Args:
            chromosome: Vector de valores en [0, 1], de shape `(num_genes,)`.
            entrada: Instancia del problema.
            parametros: Parámetros del dominio.

        Returns:
            Una `Solucion` lista para ser evaluada por el fitness.

        Raises:
            ValueError: Si `chromosome` no tiene la longitud esperada
                o contiene valores fuera de [0, 1].
        """

    def validate_chromosome(self, chromosome: np.ndarray) -> None:
        """Verifica que el cromosoma cumple el contrato (longitud y rango).

        Pensada para llamarla al inicio de `decode` en subclases concretas.

        Raises:
            ValueError: Si la longitud es errónea o algún valor está fuera
                de [0, 1].
        """
        if chromosome.shape != (self.num_genes,):
            raise ValueError(
                f"Cromosoma debe tener shape ({self.num_genes},), "
                f"recibido {chromosome.shape}"
            )
        if not ((chromosome >= 0.0).all() and (chromosome < 1.0).all()):
            raise ValueError("Cromosoma contiene valores fuera de [0, 1)")

    def validate_controllers(self, entrada: Entrada, instance_atcos):
        n_real = len(entrada.get_controladores())
        if n_real != instance_atcos:
            raise ValueError(
                f"Entrada tiene {n_real} controladores pero el decoder "
                f"espera {instance_atcos}"
            )

    def validate_sectores(self, entrada: Entrada, instance_sectors):
        all_sectores = sorted(
            entrada.get_lista_sectores(),
            key=lambda s: s.id,
        )
        if len(all_sectores) != instance_sectors:
            raise ValueError(
                f"Entrada tiene {len(all_sectores)} sectores pero el decoder "
                f"espera {instance_sectors}"
            )
        return all_sectores
