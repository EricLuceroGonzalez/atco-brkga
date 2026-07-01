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
# Pesos por defecto computados con la fórmula ROC.
_PESOS_OBJ_DEFAULT = pesos_roc(4)  # [25/48, 13/48, 7/48, 3/48]
_SUB_OBJ1_DEFAULT = pesos_iguales(3)  # [1/3, 1/3, 1/3]
_SUB_OBJ3_DEFAULT = pesos_iguales(2)  # [1/2, 1/2]


@dataclass(frozen=True)
class PesosFitness:
    """Pesos de los 4 objetivos de Tello cap. 6.3.3 + sub-objetivos.

    Estructura:
        Obj 1 (condiciones laborales): vn_1, vn_2, vn_3 con sub-pesos iguales
        Obj 2 (compactación):          fragmentación
        Obj 3 (descansos + acred.):    f₃.₁, f₃.₂ con sub-pesos iguales
        Obj 4 (balance):               std_dev de carga

    Defaults computados al cargar el módulo mediante `pesos_roc(4)` y
    `pesos_iguales(n)`. El usuario puede sobreescribir individualmente o
    reordenar prioridades con :meth:`PesosFitness.con_orden`.
    """

    # 4 objetivos (ROC, decrecientes en importancia)
    w_obj1: float = _PESOS_OBJ_DEFAULT[0]
    w_obj2: float = _PESOS_OBJ_DEFAULT[1]
    w_obj3: float = _PESOS_OBJ_DEFAULT[2]
    w_obj4: float = _PESOS_OBJ_DEFAULT[3]

    # Sub-pesos Obj 1 (condiciones deseables: vn_1, vn_2, vn_3)
    mu_1_1: float = _SUB_OBJ1_DEFAULT[0]  # tiempo óptimo en posición
    mu_1_2: float = _SUB_OBJ1_DEFAULT[1]  # tiempo óptimo entre descansos
    mu_1_3: float = _SUB_OBJ1_DEFAULT[2]  # porcentaje ejecutivo

    # Sub-pesos Obj 3 (descansos + acreditación)
    mu_3_1: float = _SUB_OBJ3_DEFAULT[0]  # minimizar intervalos descanso
    mu_3_2: float = _SUB_OBJ3_DEFAULT[1]  # maximizar acreditación

    def __post_init__(self) -> None:
        suma = self.w_obj1 + self.w_obj2 + self.w_obj3 + self.w_obj4
        if abs(suma - 1.0) > _TOL:
            raise ValueError(f"Pesos w_obj* deben sumar 1, suman {suma}")

        sub1 = self.mu_1_1 + self.mu_1_2 + self.mu_1_3
        if abs(sub1 - 1.0) > _TOL:
            raise ValueError(f"Sub-pesos Obj 1 deben sumar 1, suman {sub1}")

        sub3 = self.mu_3_1 + self.mu_3_2
        if abs(sub3 - 1.0) > _TOL:
            raise ValueError(f"Sub-pesos Obj 3 deben sumar 1, suman {sub3}")

        if any(
            p < 0
            for p in (
                self.w_obj1,
                self.w_obj2,
                self.w_obj3,
                self.w_obj4,
                self.mu_1_1,
                self.mu_1_2,
                self.mu_1_3,
                self.mu_3_1,
                self.mu_3_2,
            )
        ):
            raise ValueError("Todos los pesos deben ser no negativos")

    @classmethod
    def con_orden(cls, orden_objetivos: list[str]) -> "PesosFitness":
        """Construye pesos ROC dada una lista de 4 objetivos en orden de prioridad.

        Args:
            orden_objetivos: Permutación de
                ``["obj1", "obj2", "obj3", "obj4"]`` en orden decreciente
                de importancia.

        Returns:
            ``PesosFitness`` con los pesos asignados según ese orden.
            Los sub-pesos quedan con los defaults igualitarios.
        """
        validos = {"obj1", "obj2", "obj3", "obj4"}
        if len(orden_objetivos) != 4:
            raise ValueError(f"Esperados 4 objetivos, recibidos {len(orden_objetivos)}")
        if set(orden_objetivos) != validos:
            raise ValueError(
                f"orden_objetivos inválido. Esperados: {validos}, "
                f"recibidos: {set(orden_objetivos)}"
            )

        pesos = dict(zip(orden_objetivos, pesos_roc(4)))
        return cls(
            w_obj1=pesos["obj1"],
            w_obj2=pesos["obj2"],
            w_obj3=pesos["obj3"],
            w_obj4=pesos["obj4"],
        )


@dataclass(frozen=True)
class UmbralesFitness:
    """Umbrales operativos en minutos para los componentes de condiciones laborales."""

    pos_opt_min: int = 45  # vn_1: óptimo en misma posición
    pos_min_min: int = 15  # vn_1: mínimo legal en posición
    trab_opt_min: int = 90  # vn_2: óptimo entre descansos
    trab_min_min: int = 15  # vn_2: mínimo trabajo sin violación
    pct_ejecutivo_min: float = 0.40  # vn_3: cota inferior banda EJ
    pct_ejecutivo_max: float = 0.60  # vn_3: cota superior banda EJ


@dataclass(frozen=True)
class PesosBloques:
    """Pesos del meta-balance entre factibilidad y rendimiento.

    Tu tribunal exige peso_factibilidad = 0.7, peso_rendimiento = 0.3 para
    forzar al solver a priorizar soluciones factibles. La suma debe ser 1.
    """

    peso_factibilidad: float = 0.7
    peso_rendimiento: float = 0.3

    def __post_init__(self) -> None:
        suma = self.peso_factibilidad + self.peso_rendimiento
        if abs(suma - 1.0) > _TOL:
            raise ValueError(f"Pesos de bloque deben sumar 1, suman {suma}")
        if self.peso_factibilidad < 0 or self.peso_rendimiento < 0:
            raise ValueError("Pesos no pueden ser negativos")


@dataclass(frozen=True)
class FitnessConfig:
    """Configuración completa de la función objetivo.

    Componentes positivos (maximización, in [0, 1]):
      - cobertura
      - laboral = (vn_1, vn_2, vn_3) ponderados
      - estructura = (frag, desc) ponderados
      - acreditacion
      - balance
    Estructura:
      - ``pesos``: pesos ROC de los 4 objetivos de Tello sec 6.3.3 (Bloque B).
      - ``pesos_bloques``: meta-balance alpha/(1-alpha) entre factibilidad y
        rendimiento (defecto 0.7 / 0.3).
      - ``umbrales``: minutos óptimos / mínimos para vn_1, vn_2, vn_3.
      - ``pesos_penalizacion``: pesos por restricción + coeficiente
        global usados por ``calcular_factibilidad_normalizada``.
    """

    pesos: PesosFitness = field(default_factory=PesosFitness)
    umbrales: UmbralesFitness = field(default_factory=UmbralesFitness)
    pesos_bloques: PesosBloques = field(default_factory=PesosBloques)
    pesos_penalizacion: PesosPenalizacion = field(default_factory=PesosPenalizacion)

    # tratamiento_infactible: Literal["rechazar", "penalizar"] = "rechazar"
    # peso_violaciones: float = 100.0  # sólo se usa si "penalizar"
    # Penalización por violaciones de restricciones
