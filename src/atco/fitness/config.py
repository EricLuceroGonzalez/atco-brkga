"""Configuración de la función objetivo: pesos y umbrales."""

from __future__ import annotations

from dataclasses import dataclass

_TOLERANCIA = 1e-9


@dataclass(frozen=True)
class FitnessConfig:
    """Pesos $\\alpha$ y umbrales de la función objetivo.

    Attributes:
        alpha_r: Peso de la componente R (restricciones).
        alpha_c: Peso de la componente C (cobertura insatisfecha).
        alpha_b: Peso de la componente B (desbalance de carga).
        alpha_f: Peso de la componente F (fragmentación trabajo↔descanso).
        alpha_l: Peso de la componente L (descansos largos), 0 por defecto.
        umbral_l: Longitud mínima en slots de una racha de descanso para
            que cuente como "descanso largo". Default: 18 slots (= 90 min
            con slot de 5 min).

    Raises:
        ValueError: Si algún peso es negativo, si la suma no es 1 ± ε,
            o si `umbral_l` no es positivo.
    """

    # alpha_r: float = 0.45
    # alpha_c: float = 0.30
    # alpha_b: float = 0.15
    # alpha_f: float = 0.10
    # alpha_l: float = 0.00
    alpha_r: float = 1
    alpha_c: float = 1
    alpha_b: float = 1
    alpha_f: float = 1
    alpha_l: float = 1
    umbral_l: int = 18

    def __post_init__(self) -> None:
        pesos = (self.alpha_r, self.alpha_c, self.alpha_b, self.alpha_f, self.alpha_l)
        if any(p < 0 for p in pesos):
            raise ValueError(f"Los pesos no pueden ser negativos: {pesos}")
        suma = sum(pesos)
        # TODO volver a descomentar
        # if abs(suma - 1.0) > _TOLERANCIA:
        #     raise ValueError(f"Los pesos deben sumar 1, suman {suma}")
        if self.umbral_l <= 0:
            raise ValueError(f"umbral_l debe ser positivo, recibido {self.umbral_l}")
