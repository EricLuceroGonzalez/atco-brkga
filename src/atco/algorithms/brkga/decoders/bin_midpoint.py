"""Decoder bin-midpoint: traduce cada gen del cromosoma a un token de la matriz.

A diferencia del `PermutationDecoder` (constructivo), este decoder asigna
**un gen por celda** de la matriz N×T y traduce su valor directamente a un
token del alfabeto mediante el esquema bin-midpoint clásico:

    chromosome[c*T + t] ∈ [0, 1)
    token_idx = floor(chromosome[c*T + t] · |alfabeto|)
    token = alfabeto[token_idx]

El alfabeto contiene `STRING_NO_TURNO`, `STRING_DESCANSO` y los IDs de
todos los sectores en mayúsculas (EJ) y minúsculas (PL).

Ventajas:
    * Codificación inversa exacta: `decode(encode(sol)) == sol`.
    * Espacio de búsqueda completo: cualquier matriz N×T es alcanzable.

Desventajas:
    * El cromosoma no respeta restricciones del dominio (ventana de
      turno, licencias, cap, descanso). El BRKGA debe descubrirlas
      a través del fitness, lo que ralentiza la convergencia inicial.

Pensado como alternativa de comparación frente al `PermutationDecoder`.
"""

from __future__ import annotations

import numpy as np

from atco.algorithms.brkga.decoders.base import DecoderBase
from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


def construir_alfabeto(entrada: Entrada) -> list[str]:
    """Construye el alfabeto ordenado de tokens admitidos por el decoder.

    Orden determinista:
        0: STRING_NO_TURNO ("000")
        1: STRING_DESCANSO ("111")
        2k+2: sector_k.id.upper()   (EJ)
        2k+3: sector_k.id.lower()   (PL)
    Donde k itera sobre los sectores globales ordenados por `id`.

    Args:
        entrada: Instancia del problema.

    Returns:
        Lista de tokens de 3 caracteres en orden canónico.
    """
    alfabeto: list[str] = [STRING_NO_TURNO, STRING_DESCANSO]
    for sector in sorted(entrada.get_lista_sectores(), key=lambda s: s.id):
        alfabeto.append(sector.id.upper())
        alfabeto.append(sector.id.lower())
    return alfabeto


class BinMidpointDecoder(DecoderBase):
    """Decoder de codificación bin-midpoint con cromosoma de longitud N·T.

    Attributes:
        n_controladores: Número de filas (N) de la matriz de turnos.
        longitud_t: Número de slots (T) por fila.
        alfabeto: Lista determinista de tokens; ver `construir_alfabeto`.
    """

    def __init__(
        self,
        n_controladores: int,
        longitud_t: int,
        alfabeto: list[str],
    ) -> None:
        if n_controladores <= 0:
            raise ValueError(
                f"n_controladores debe ser positivo, recibido {n_controladores}"
            )
        if longitud_t <= 0:
            raise ValueError(f"longitud_t debe ser positivo, recibido {longitud_t}")
        if not alfabeto:
            raise ValueError("El alfabeto no puede estar vacío")
        self.n_controladores = n_controladores
        self.longitud_t = longitud_t
        self.alfabeto = tuple(alfabeto)

    @property
    def num_genes(self) -> int:
        return self.n_controladores * self.longitud_t

    def decode(
        self,
        chromosome: np.ndarray,
        entrada: Entrada,
        parametros: Parametros,  # noqa: ARG002
    ) -> Solucion:
        """Decodifica un cromosoma como matriz directa de tokens.

        Args:
            chromosome: Vector de shape `(N · T,)` con valores en [0, 1].
            entrada: Instancia del problema (se usa para clonar controladores).
            parametros: No se consulta. Aceptado por contrato.

        Returns:
            `Solucion` con `turnos` reconstruido, `controladores` con
            `slots_trabajados` derivado del conteo de celdas de trabajo,
            y `longdescansos=0`.

        Raises:
            ValueError: Si la entrada no encaja en dimensiones.
        """
        self.validate_chromosome(chromosome)

        n_real = len(entrada.get_controladores())
        if n_real != self.n_controladores:
            raise ValueError(
                f"Entrada tiene {n_real} controladores pero el decoder "
                f"espera {self.n_controladores}"
            )

        M = len(self.alfabeto)
        T = self.longitud_t
        controladores_clonados = [c.clone() for c in entrada.get_controladores()]
        cadenas: list[str] = []

        for c in range(self.n_controladores):
            tokens: list[str] = []
            trabajados = 0
            for t in range(T):
                gen = float(chromosome[c * T + t])
                # Clamp por si gen == 1.0 exacto (evita IndexError)
                token_idx = max(0, min(int(gen * M), M - 1))
                token = self.alfabeto[token_idx]
                tokens.append(token)
                if token not in (STRING_DESCANSO, STRING_NO_TURNO):
                    trabajados += 1
            cadenas.append("".join(tokens))
            controladores_clonados[c].slots_trabajados = trabajados
            controladores_clonados[c].turno_asignado = c

        return Solucion(
            turnos=cadenas,
            controladores=controladores_clonados,
            longdescansos=0,
        )


def encode_solucion(
    solucion: Solucion,
    longitud_t: int,
    alfabeto: list[str],
) -> np.ndarray:
    """Codifica una `Solucion` como cromosoma bin-midpoint.

    Para cada celda (c, t) de la matriz, el gen es el centro del bin del
    token presente:

        chromosome[c·T + t] = (alfabeto.index(token) + 0.5) / |alfabeto|

    Garantiza round-trip exacto: `BinMidpointDecoder.decode(encode(sol))`
    reconstruye la misma `Solucion` (mismos `turnos` y misma derivación
    de `slots_trabajados`).

    Args:
        solucion: Solución a codificar.
        longitud_t: T del turno (slots por fila).
        alfabeto: Mismo alfabeto que usará el decoder.

    Returns:
        Vector NumPy de shape `(N · T,)` con genes en (0, 1).

    Raises:
        ValueError: Si alguna celda contiene un token no presente en `alfabeto`.
    """
    indice = {tok: i for i, tok in enumerate(alfabeto)}
    M = len(alfabeto)
    N = len(solucion.turnos)
    chromosome = np.zeros(N * longitud_t, dtype=float)
    for c, cadena in enumerate(solucion.turnos):
        for t in range(longitud_t):
            tok = cadena[t * 3 : (t + 1) * 3]
            if tok not in indice:
                raise ValueError(
                    f"Token {tok!r} en (c={c}, t={t}) no está en el alfabeto"
                )
            chromosome[c * longitud_t + t] = (indice[tok] + 0.5) / M
    return chromosome
