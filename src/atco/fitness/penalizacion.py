"""Conversión de violaciones de restricciones a penalización aditiva.

El módulo aísla la política de penalización del cálculo de los
componentes positivos del fitness. Los usuarios pueden:

  - Anular pesos por restricción individual sin tocar el orquestador.
  - Reportar el desglose por restricción al sistema de gráficos.
  - Sustituir el esquema lineal por uno no-lineal (exponencial,
    saturado, etc.) sin propagar el cambio fuera de este módulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from atco.problem.restrictions.checks import NOMBRES_RESTRICCIONES, N_RESTRICCIONES


def _pesos_uniformes() -> dict[str, float]:
    """Peso 1.0 para las 14 restricciones (alineado con Tello sec 6.3.3.1)."""
    return {nombre: 1.0 for nombre in NOMBRES_RESTRICCIONES}


@dataclass(frozen=True)
class PesosPenalizacion:
    """Configura cómo el conteo de violaciones se convierte en penalización.

    Attributes:
        coeficiente_global: Multiplicador aplicado a la suma ponderada
            de violaciones. Controla la "dureza" global de la penalización
            respecto al fitness positivo. Con componentes positivos en
            [0, 1] y un total ponderado típico de 1, un coeficiente de
            0.01 hace que 100 violaciones reduzcan el fitness en 1.0 (es
            decir, eliminen toda la calidad del horario).
        pesos_por_restriccion: Diccionario ``nombre_restriccion -> peso``.
            Permite priorizar la corrección de unas restricciones sobre
            otras. Por defecto todas pesan 1.0 (uniformemente).
    """

    coeficiente_global: float = 0.01
    pesos_por_restriccion: dict[str, float] = field(default_factory=_pesos_uniformes)

    def __post_init__(self) -> None:
        if self.coeficiente_global < 0:
            raise ValueError(
                f"coeficiente_global debe ser ≥ 0, recibido {self.coeficiente_global}"
            )
        faltantes = set(NOMBRES_RESTRICCIONES) - set(self.pesos_por_restriccion)
        if faltantes:
            raise ValueError(
                f"pesos_por_restriccion no cubre todas las restricciones. "
                f"Faltan: {sorted(faltantes)}"
            )
        if any(p < 0 for p in self.pesos_por_restriccion.values()):
            raise ValueError("Todos los pesos individuales deben ser ≥ 0")


def calcular_penalizacion(
    violaciones: dict[str, float],
    pesos: PesosPenalizacion,
) -> float:
    """Suma ponderada de violaciones, multiplicada por el coeficiente global.

    Args:
        violaciones: Conteo crudo por restricción (output de
            ``contar_violaciones``).
        pesos: Configuración de pesos.

    Returns:
        Escalar ≥ 0 a **restar** al fitness positivo. Vale 0 si la
        solución es factible.
    """
    suma = sum(
        violaciones[nombre] * pesos.pesos_por_restriccion[nombre]
        for nombre in NOMBRES_RESTRICCIONES
    )
    return pesos.coeficiente_global * suma


def desglose_penalizacion(
    violaciones: dict[str, float],
    pesos: PesosPenalizacion,
) -> dict[str, float]:
    """Contribución individual de cada restricción a la penalización total.

    Útil para gráficos tipo *stacked bar* que muestren qué restricciones
    son las que más están castigando el fitness en cada iteración.
    """
    return {
        nombre: pesos.coeficiente_global
        * violaciones[nombre]
        * pesos.pesos_por_restriccion[nombre]
        for nombre in NOMBRES_RESTRICCIONES
    }


def calcular_factibilidad_normalizada(
    violaciones: dict[str, float],
    pesos: PesosPenalizacion,
    n_controladores: int,
    es_turno_noche: bool,
) -> tuple[float, float, float]:
    """Convierte el conteo de violaciones en factibilidad ∈ [0, 1].

    Sigue el esquema de Tello sec 6.3.3 con cap operacional heurístico:

        r_max = κ · N,  κ = 20 si noche, 18 otherwise
        f_fact = max(0, (r_max - r) / r_max)

    Returns:
        ``(f_factibilidad, r, r_max)``. El primer valor es lo que entra al
        bloque A; los otros dos se conservan para tracking.
    """
    r = sum(
        violaciones[nombre] * pesos.pesos_por_restriccion[nombre]
        for nombre in NOMBRES_RESTRICCIONES
    )
    kappa = 20.0 if es_turno_noche else 18.0
    r_max = kappa * max(1, n_controladores)
    f_fact = max(0.0, (r_max - r) / r_max)
    return f_fact, r, r_max
