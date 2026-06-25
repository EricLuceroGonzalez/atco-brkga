"""Configuración de la función objetivo: pesos ROC + umbrales + penalty."""

from __future__ import annotations

from dataclasses import dataclass, field

from atco.fitness.penalizacion import PesosPenalizacion

_TOL = 1e-6


def pesos_roc(n: int) -> list[float]:
    """Pesos del Rank-Order Centroid (ROC) para n criterios ordenados.

    Fórmula (Stillwell, Seaver & Edwards 1981):

        μ_i = (1/n) · Σ_{j=i}^{n} (1/j),   i = 1, 2, ..., n

    El criterio i=1 es el más importante; i=n el menos.

    Propiedades garantizadas:
      - sum(pesos_roc(n)) == 1.0 (± epsilon de punto flotante)
      - pesos_roc(n)[i] >= pesos_roc(n)[i+1]  (monotonía decreciente)
      - pesos_roc(1) == [1.0]

    Args:
        n: Número de criterios, ≥ 1.

    Returns:
        Lista de n pesos en orden decreciente de importancia.

    Raises:
        ValueError: si ``n < 1``.

    Ejemplos:
        >>> pesos_roc(5)
        [0.4566..., 0.2566..., 0.1566..., 0.09, 0.04]
        >>> pesos_roc(3)
        [0.6111..., 0.2777..., 0.1111...]
        >>> pesos_roc(1)
        [1.0]
    """
    if n < 1:
        raise ValueError(f"n debe ser ≥ 1, recibido {n}")
    return [sum(1.0 / j for j in range(i, n + 1)) / n for i in range(1, n + 1)]


def pesos_iguales(n: int) -> list[float]:
    """Pesos uniformes: ``[1/n] * n``. Útil para sub-grupos sin orden de prioridad.

    Args:
        n: Número de criterios, ≥ 1.

    Returns:
        Lista de n pesos, todos iguales a 1/n.
    """
    if n < 1:
        raise ValueError(f"n debe ser ≥ 1, recibido {n}")
    return [1.0 / n] * n


# Pesos por defecto computados al cargar el módulo (una sola vez).
_PESOS_GRUPOS_DEFAULT = pesos_roc(5)
_PESOS_LABORAL_DEFAULT = pesos_iguales(3)
_PESOS_ESTRUCTURA_DEFAULT = pesos_iguales(2)


@dataclass(frozen=True)
class PesosFitness:
    """Pesos de los 5 grupos + sub-pesos dentro de grupos.

    Defaults computados al cargar el módulo mediante
    :func:`pesos_roc` (grupos) y :func:`pesos_iguales` (sub-grupos).
    El usuario puede sobreescribir cualquier peso individual o construir
    una instancia con prioridades reordenadas usando
    :meth:`PesosFitness.con_orden`.
    """

    # Pesos de los 5 grupos (ROC, decrecientes en importancia)
    w_cobertura: float = _PESOS_GRUPOS_DEFAULT[0]
    w_laboral: float = _PESOS_GRUPOS_DEFAULT[1]
    w_estructura: float = _PESOS_GRUPOS_DEFAULT[2]
    w_acreditacion: float = _PESOS_GRUPOS_DEFAULT[3]
    w_balance: float = _PESOS_GRUPOS_DEFAULT[4]

    # Sub-pesos del grupo laboral (igualitarios por defecto)
    mu_pos: float = _PESOS_LABORAL_DEFAULT[0]
    mu_trab: float = _PESOS_LABORAL_DEFAULT[1]
    mu_eje: float = _PESOS_LABORAL_DEFAULT[2]

    # Sub-pesos del grupo estructura (igualitarios por defecto)
    mu_frag: float = _PESOS_ESTRUCTURA_DEFAULT[0]
    mu_desc: float = _PESOS_ESTRUCTURA_DEFAULT[1]

    def __post_init__(self) -> None:
        suma = (
            self.w_cobertura
            + self.w_laboral
            + self.w_estructura
            + self.w_acreditacion
            + self.w_balance
        )
        if abs(suma - 1.0) > _TOL:
            raise ValueError(f"Pesos de grupo deben sumar 1, suman {suma}")

        sub_lab = self.mu_pos + self.mu_trab + self.mu_eje
        if abs(sub_lab - 1.0) > _TOL:
            raise ValueError(f"Sub-pesos laboral deben sumar 1, suman {sub_lab}")

        sub_est = self.mu_frag + self.mu_desc
        if abs(sub_est - 1.0) > _TOL:
            raise ValueError(f"Sub-pesos estructura deben sumar 1, suman {sub_est}")

        if any(
            p < 0
            for p in (
                self.w_cobertura,
                self.w_laboral,
                self.w_estructura,
                self.w_acreditacion,
                self.w_balance,
                self.mu_pos,
                self.mu_trab,
                self.mu_eje,
                self.mu_frag,
                self.mu_desc,
            )
        ):
            raise ValueError("Todos los pesos deben ser no negativos")

    @classmethod
    def con_orden(cls, orden_grupos: list[str]) -> "PesosFitness":
        """Construye pesos ROC dados los grupos en orden de importancia decreciente.

        Los sub-pesos quedan con sus defaults igualitarios.

        Args:
            orden_grupos: Lista de exactamente 5 nombres válidos:
                ``"cobertura"``, ``"laboral"``, ``"estructura"``,
                ``"acreditacion"``, ``"balance"``. El primero es el más
                importante.

        Returns:
            Instancia con ``w_{nombre}`` = ROC_i según la posición en la lista.

        Raises:
            ValueError: si la lista no tiene 5 elementos o si contiene
                nombres no reconocidos.

        Ejemplo:
            >>> # Por defecto: cobertura > laboral > estructura > acreditacion > balance
            >>> PesosFitness.con_orden(
            ...     ["cobertura", "acreditacion", "laboral", "estructura", "balance"]
            ... )
            # → w_cobertura ≈ 0.457, w_acreditacion ≈ 0.257, ...
        """
        validos = {
            "cobertura",
            "laboral",
            "estructura",
            "acreditacion",
            "balance",
        }
        if len(orden_grupos) != 5:
            raise ValueError(f"Esperados 5 grupos, recibidos {len(orden_grupos)}")
        if set(orden_grupos) != validos:
            faltantes = validos - set(orden_grupos)
            extras = set(orden_grupos) - validos
            raise ValueError(
                f"orden_grupos inválido. Faltantes: {faltantes}. Extras: {extras}"
            )

        pesos = dict(zip(orden_grupos, pesos_roc(len(orden_grupos))))
        return cls(
            w_cobertura=pesos["cobertura"],
            w_laboral=pesos["laboral"],
            w_estructura=pesos["estructura"],
            w_acreditacion=pesos["acreditacion"],
            w_balance=pesos["balance"],
        )


@dataclass(frozen=True)
class UmbralesFitness:
    """Umbrales operativos en minutos para los componentes de condiciones laborales."""

    pos_opt_min: int = 45  # vn₁: óptimo en misma posición
    pos_min_min: int = 15  # vn₁: mínimo legal en posición
    trab_opt_min: int = 90  # vn₂: óptimo entre descansos
    trab_min_min: int = 15  # vn₂: mínimo trabajo sin violación
    pct_ejecutivo_min: float = 0.40  # vn₃: cota inferior banda EJ
    pct_ejecutivo_max: float = 0.60  # vn₃: cota superior banda EJ


@dataclass(frozen=True)
class FitnessConfig:
    """Configuración completa de la función objetivo.

    Componentes positivos (maximización, ∈ [0, 1]):
      - cobertura
      - laboral = (vn₁, vn₂, vn₃) ponderados
      - estructura = (frag, desc) ponderados
      - acreditacion
      - balance

    Penalty (a restar):
      - configurable por PesosPenalizacion (paso 3)
    """

    pesos: PesosFitness = field(default_factory=PesosFitness)
    umbrales: UmbralesFitness = field(default_factory=UmbralesFitness)
    pesos_penalizacion: PesosPenalizacion = field(default_factory=PesosPenalizacion)

    # tratamiento_infactible: Literal["rechazar", "penalizar"] = "rechazar"
    # peso_violaciones: float = 100.0  # sólo se usa si "penalizar"
    # Penalización por violaciones de restricciones
