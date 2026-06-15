"""Función objetivo escalar: compone las componentes y aplica pesos."""

from __future__ import annotations

from dataclasses import dataclass

from atco.domain.models import Solucion
from atco.fitness.components import (
    N_RESTRICCIONES,
    cobertura_insatisfecha,
    desbalance_carga,
    descansos_largos,
    fragmentacion,
    restricciones_violadas,
)
from atco.fitness.config import FitnessConfig
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


@dataclass(frozen=True)
class FitnessResult:
    """Desglose del fitness con escalar y componentes individuales.

    Attributes:
        valor: Escalar a minimizar, suma ponderada de las componentes
            normalizadas.
        componentes: Diccionario con las cinco componentes normalizadas
            a [0, 1]. Claves: "R", "C", "B", "F", "L".
        crudos: Mismas claves, con los valores antes de normalizar.
        restricciones_violadas: Nombres de las `comprobar_*` violadas.
    """

    valor: float
    componentes: dict[str, float]
    crudos: dict[str, float]
    restricciones_violadas: list[str]

    def __float__(self) -> float:
        return self.valor


def evaluar_fitness(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
    config: FitnessConfig,
) -> FitnessResult:
    """Evalúa el fitness de una solución como escalar a minimizar.

    Compone R (restricciones), C (cobertura insatisfecha), B (desbalance),
    F (fragmentación) y L (descansos largos), normaliza cada una a [0, 1]
    y las combina con los pesos `α` de `config`.

    Args:
        solucion: Solución a evaluar.
        entrada: Instancia del problema.
        parametros: Parámetros del problema.
        config: Pesos y umbrales de la función objetivo.

    Returns:
        `FitnessResult` con el escalar y el desglose por componente.
    """
    n_controladores = max(1, len(solucion.controladores))

    violadas = restricciones_violadas(solucion, entrada, parametros)
    r_crudo = len(violadas)
    r_norm = r_crudo / max(1, N_RESTRICCIONES)

    c_crudo, c_cota = cobertura_insatisfecha(solucion, entrada, parametros)
    c_norm = c_crudo / max(1, c_cota)

    b_crudo = desbalance_carga(solucion)
    longitud_t = len(solucion.turnos[0]) // 3 if solucion.turnos else 0
    b_norm = b_crudo / max(1, longitud_t)

    f_crudo, f_cota = fragmentacion(solucion)
    f_norm = f_crudo / max(1, f_cota)

    l_crudo = descansos_largos(solucion, config.umbral_l)
    l_norm = l_crudo / n_controladores

    valor = (
        config.alpha_r * r_norm
        + config.alpha_c * c_norm
        + config.alpha_b * b_norm
        + config.alpha_f * f_norm
        + config.alpha_l * l_norm
    )

    return FitnessResult(
        valor=valor,
        componentes={"R": r_norm, "C": c_norm, "B": b_norm, "F": f_norm, "L": l_norm},
        crudos={
            "R": float(r_crudo),
            "C": float(c_crudo),
            "B": float(b_crudo),
            "F": float(f_crudo),
            "L": float(l_crudo),
        },
        restricciones_violadas=violadas,
    )
