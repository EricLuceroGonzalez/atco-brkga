"""Función objetivo escalar: compone las componentes y aplica pesos."""

from __future__ import annotations

from dataclasses import dataclass

from atco.domain.models import Solucion
from atco.fitness.components import (
    acreditacion,
    balance_carga,
    cobertura_insatisfecha,
    fragmentacion,
    intervalos_descanso,
    porcentaje_ejecutivo,
    tiempo_optimo_posicion,
    tiempo_optimo_trabajo,
)
from atco.fitness.config import FitnessConfig
from atco.fitness.penalizacion import (
    calcular_penalizacion,
    desglose_penalizacion,
)
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.problem.restrictions.checks import contar_violaciones

# ============================================================================
# Normalizadores privados — todos a [0, 1] con MAXIMIZACIÓN
# ============================================================================


def _norm_cobertura(huecos: int, demanda: int) -> float:
    if demanda == 0:
        return 1.0
    return (demanda - huecos) / demanda


def _norm_desviacion_tipo_tello(crudo: float, cota: float) -> float:
    """Para vn₁, vn₂, vn₃ y balance: ``(cota - crudo) / cota`` con clamp."""
    if cota == 0:
        return 1.0
    f = (cota - crudo) / cota
    return max(0.0, min(1.0, f))


def _norm_fragmentacion(crudo: int, v_min: int, v_max: int) -> float:
    if v_max <= v_min:
        return 1.0
    crudo_efectivo = max(crudo, v_min)
    return (v_max - crudo_efectivo) / (v_max - v_min)


def _norm_intervalos_descanso(crudo: int, v_min: int, v_max: int) -> float:
    if v_max <= v_min:
        return 1.0
    crudo_efectivo = max(crudo, v_min)
    return (v_max - crudo_efectivo) / (v_max - v_min)


def _norm_acreditacion(crudo: int, v_min: int, v_max: int) -> float:
    if v_max <= v_min:
        return 1.0
    crudo_efectivo = max(crudo, v_min)
    return (crudo_efectivo - v_min) / (v_max - v_min)


# ============================================================================
# Resultado
# ============================================================================


@dataclass(frozen=True)
class FitnessResult:
    """Desglose del fitness con escalar y los componentes individuales.

    Convenciones:
      - ``valor`` es el escalar a MAXIMIZAR. Igual a
        ``valor_componentes - penalty``.
      - Todos los componentes en ``componentes`` están normalizados a
        [0, 1], higher-is-better.
      - ``crudos`` expone los valores antes de normalizar para análisis
        cuantitativo (gráficos, regresiones, comparativas Tello).

    Attributes:
        valor: Escalar final a maximizar.
        valor_componentes: Componentes positivos ponderados (sin penalty).
        penalty: Penalización aplicada por restricciones violadas. ≥ 0.
        factible: True ⇔ ``n_violaciones_total == 0``.
        grupos: 5 grupos del esquema ROC, todos ∈ [0, 1].
        componentes: 8 componentes individuales, todos ∈ [0, 1].
        crudos: Valores crudos (pre-normalización) de cada componente.
        violaciones: ``{nombre_restriccion: nº violaciones}``, 14 claves.
        n_violaciones_total: Suma sobre las 14 restricciones.
        penalty_por_restriccion: Contribución individual al ``penalty``.
    """

    valor: float
    valor_componentes: float
    penalty: float
    factible: bool
    grupos: dict[str, float]
    componentes: dict[str, float]
    crudos: dict[str, float]
    violaciones: dict[str, float]
    n_violaciones_total: float
    penalty_por_restriccion: dict[str, float]

    def __float__(self) -> float:
        return self.valor


# ============================================================================
# Orquestador
# ============================================================================


def evaluar_fitness(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
    config: FitnessConfig | None = None,
) -> FitnessResult:
    """Evalúa el fitness de una solución como escalar a maximizar.

    Estructura:
        valor = (grupos ponderados) − penalty

        grupos = w_cob·f_cob + w_lab·(f_pos·μ + f_trab·μ + f_eje·μ)
               + w_est·(f_frag·μ + f_desc·μ) + w_acr·f_acred + w_bal·f_bal

    Las restricciones NO entran como componente positiva: se cuentan
    aparte (tracking) y se convierten en ``penalty`` aditivo configurable
    en ``config.pesos_penalizacion``. Una solución infactible recibe un
    penalty proporcional al número de violaciones, sin ser rechazada.
    """
    if config is None:
        config = FitnessConfig()

    p = config.pesos
    u = config.umbrales

    # ─── Cobertura ─────────────────────────────────────────────────────
    cob_huecos, cob_demanda = cobertura_insatisfecha(solucion, entrada, parametros)
    f_cob = _norm_cobertura(cob_huecos, cob_demanda)

    # ─── Condiciones laborales ─────────────────────────────────────────
    pos_crudo, pos_cota = tiempo_optimo_posicion(
        solucion,
        parametros,
        pos_opt_min=u.pos_opt_min,
        pos_min_min=u.pos_min_min,
    )
    f_pos = _norm_desviacion_tipo_tello(pos_crudo, pos_cota)

    trab_crudo, trab_cota = tiempo_optimo_trabajo(
        solucion,
        parametros,
        trab_opt_min=u.trab_opt_min,
        trab_min_min=u.trab_min_min,
    )
    f_trab = _norm_desviacion_tipo_tello(trab_crudo, trab_cota)

    eje_crudo, eje_cota = porcentaje_ejecutivo(
        solucion,
        pct_min=u.pct_ejecutivo_min,
        pct_max=u.pct_ejecutivo_max,
    )
    f_eje = _norm_desviacion_tipo_tello(eje_crudo, eje_cota)

    g_laboral = f_pos * p.mu_pos + f_trab * p.mu_trab + f_eje * p.mu_eje

    # ─── Estructura ────────────────────────────────────────────────────
    frag_crudo, frag_vmin, frag_vmax = fragmentacion(solucion)
    f_frag = _norm_fragmentacion(frag_crudo, frag_vmin, frag_vmax)

    desc_crudo, desc_vmin, desc_vmax = intervalos_descanso(solucion)
    f_desc = _norm_intervalos_descanso(desc_crudo, desc_vmin, desc_vmax)

    g_estructura = f_frag * p.mu_frag + f_desc * p.mu_desc

    # ─── Acreditación ──────────────────────────────────────────────────
    acred_crudo, acred_vmin, acred_vmax = acreditacion(solucion, entrada)
    f_acred = _norm_acreditacion(acred_crudo, acred_vmin, acred_vmax)

    # ─── Balance de carga ──────────────────────────────────────────────
    bal_sigma, bal_sigma_max = balance_carga(solucion)
    f_bal = _norm_desviacion_tipo_tello(bal_sigma, bal_sigma_max)

    # ─── Combinación ponderada de grupos ───────────────────────────────
    valor_componentes = (
        f_cob * p.w_cobertura
        + g_laboral * p.w_laboral
        + g_estructura * p.w_estructura
        + f_acred * p.w_acreditacion
        + f_bal * p.w_balance
    )

    # ─── Restricciones (tracking + penalty) ────────────────────────────
    violaciones = contar_violaciones(solucion, entrada, parametros)
    penalty = calcular_penalizacion(violaciones, config.pesos_penalizacion)
    penalty_detalle = desglose_penalizacion(violaciones, config.pesos_penalizacion)
    n_violaciones = sum(violaciones.values())

    valor = valor_componentes - penalty

    return FitnessResult(
        valor=valor,
        valor_componentes=valor_componentes,
        penalty=penalty,
        factible=(n_violaciones == 0),
        grupos={
            "cobertura": f_cob,
            "laboral": g_laboral,
            "estructura": g_estructura,
            "acreditacion": f_acred,
            "balance": f_bal,
        },
        componentes={
            "cobertura": f_cob,
            "tiempo_optimo_posicion": f_pos,
            "tiempo_optimo_trabajo": f_trab,
            "porcentaje_ejecutivo": f_eje,
            "fragmentacion": f_frag,
            "intervalos_descanso": f_desc,
            "acreditacion": f_acred,
            "balance_carga": f_bal,
        },
        crudos={
            "cobertura_huecos": float(cob_huecos),
            "cobertura_demanda": float(cob_demanda),
            "tiempo_optimo_posicion": pos_crudo,
            "tiempo_optimo_posicion_cota": pos_cota,
            "tiempo_optimo_trabajo": trab_crudo,
            "tiempo_optimo_trabajo_cota": trab_cota,
            "porcentaje_ejecutivo": eje_crudo,
            "porcentaje_ejecutivo_cota": eje_cota,
            "fragmentacion": float(frag_crudo),
            "fragmentacion_vmin": float(frag_vmin),
            "fragmentacion_vmax": float(frag_vmax),
            "intervalos_descanso": float(desc_crudo),
            "intervalos_descanso_vmin": float(desc_vmin),
            "intervalos_descanso_vmax": float(desc_vmax),
            "acreditacion": float(acred_crudo),
            "acreditacion_vmin": float(acred_vmin),
            "acreditacion_vmax": float(acred_vmax),
            "balance_sigma": bal_sigma,
            "balance_sigma_max": bal_sigma_max,
        },
        violaciones=violaciones,
        n_violaciones_total=n_violaciones,
        penalty_por_restriccion=penalty_detalle,
    )
