"""Función objetivo escalar: compone las componentes y aplica pesos."""

from __future__ import annotations

from dataclasses import dataclass

from atco.domain.models import Solucion
from atco.fitness.components import (
    # fragmentacion,
    similitud_estadillos,
    acreditacion,
    balance_carga,
    cobertura_insatisfecha,
    intervalos_descanso,
    porcentaje_ejecutivo,
    tiempo_optimo_posicion,
    tiempo_optimo_trabajo,
)
from atco.fitness.config import FitnessConfig
from atco.fitness.penalizacion import (
    calcular_factibilidad_normalizada,
    desglose_penalizacion,
)
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.problem.restrictions.checks import contar_violaciones

# ============================================================================
# Normalizadores privados — todos a [0, 1] con MAXIMIZACIÓN
# ============================================================================


def _norm_estadillos(v: float, v_max: float) -> float:
    """f₂ Tello §6.3.3.2: f2 = v / v_max ∈ [0, 1]."""
    if v_max == 0:
        return 1.0
    return max(0.0, min(1.0, v / v_max))


def _norm_cobertura(huecos: int, demanda: int) -> float:
    if demanda == 0:
        return 1.0
    return (demanda - huecos) / demanda


def _norm_desviacion_t(crudo: float, cota: float) -> float:
    """Para vn_1, vn_2, vn_3 y balance: ``(cota - crudo) / cota`` con clamp."""
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
    """Desglose del fitness con dos bloques (factibilidad + rendimiento).

    Convenciones:
      - ``valor`` ∈ [0, 1], a maximizar. Igual a
        ``alpha · f_factibilidad + (1-alpha) · f_rendimiento``.
      - Los 4 objetivos en ``objetivos`` siguen la nomenclatura de Tello sec 6.3.3.
      - La cobertura insatisfecha se reporta como ``cobertura_ratio`` para
        tracking pero **no** participa en el cálculo del valor.
    """

    valor: float
    f_factibilidad: float
    f_rendimiento: float
    factible: bool

    # Desglose del bloque de rendimiento (Tello sec 6.3.3)
    objetivos: dict[str, float]  # 4 claves: obj1, obj2, obj3, obj4
    componentes: dict[str, float]  # 7 sub-componentes individuales
    crudos: dict[str, float]  # valores pre-normalización

    # Métrica auxiliar (fuera del fitness)
    cobertura_ratio: float  # (demanda - huecos) / demanda

    # Desglose del bloque de factibilidad
    violaciones: dict[str, float]
    restricciones_violadas: list[str]
    n_violaciones_total: float
    penalty_por_restriccion: dict[str, float]
    r_actual: float
    r_max: float

    def __float__(self) -> float:
        return self.valor


def evaluar_fitness(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
    config: FitnessConfig | None = None,
) -> FitnessResult:
    """Evalúa el fitness como ``alpha · f_fact + (1-alpha) · f_rend``, ambos ∈ [0, 1].

    Arquitectura:
      - **Bloque A** (factibilidad): normalización Tello de las 14
        restricciones con cap ``κ · N`` (κ ∈ {18, 20} según turno).
      - **Bloque B** (rendimiento): 4 objetivos de Tello sec 6.3.3 con pesos
        ROC, todos normalizados a [0, 1].

    La cobertura insatisfecha se calcula y se reporta como métrica
    auxiliar en ``cobertura_ratio``, pero NO entra en el valor.
    """
    if config is None:
        config = FitnessConfig()

    # ─── Bloque B — Rendimiento (Tello sec 6.3.3) ───────────────────────
    f_rendimiento, objetivos, componentes, crudos = _calcular_bloque_rendimiento(
        solucion,
        entrada,
        parametros,
        config,
    )

    # ─── Bloque A — Factibilidad ─────────────────────────────────────
    violaciones = contar_violaciones(solucion, entrada, parametros)
    restricciones_violadas = [
        nombre for nombre, conteo in violaciones.items() if conteo > 0
    ]
    es_noche = entrada.get_turno().get_nombre().lower() == "noche"
    n_ctrls = max(1, len(solucion.turnos))
    f_factibilidad, r_actual, r_max = calcular_factibilidad_normalizada(
        violaciones,
        config.pesos_penalizacion,
        n_ctrls,
        es_noche,
    )
    penalty_detalle = desglose_penalizacion(violaciones, config.pesos_penalizacion)
    n_viol_total = sum(violaciones.values())

    # ─── Métrica auxiliar: cobertura (NO entra al fitness) ───────────
    cob_huecos, cob_demanda = cobertura_insatisfecha(solucion, entrada, parametros)
    cobertura_ratio = (
        (cob_demanda - cob_huecos) / cob_demanda if cob_demanda > 0 else 1.0
    )
    crudos["cobertura_huecos"] = float(cob_huecos)
    crudos["cobertura_demanda"] = float(cob_demanda)

    # ─── Combinación final: alpha · f_fact + (1-alpha) · f_rend ──────────────
    pb = config.pesos_bloques
    valor = pb.peso_factibilidad * f_factibilidad + pb.peso_rendimiento * f_rendimiento

    return FitnessResult(
        valor=valor,
        f_factibilidad=f_factibilidad,
        f_rendimiento=f_rendimiento,
        factible=(n_viol_total == 0),
        objetivos=objetivos,
        componentes=componentes,
        crudos=crudos,
        cobertura_ratio=cobertura_ratio,
        violaciones=violaciones,
        restricciones_violadas=restricciones_violadas,
        n_violaciones_total=n_viol_total,
        penalty_por_restriccion=penalty_detalle,
        r_actual=r_actual,
        r_max=r_max,
    )


def _calcular_bloque_rendimiento(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
    config: FitnessConfig,
) -> tuple[float, dict[str, float], dict[str, float], dict[str, float]]:
    """Calcula el bloque de rendimiento siguiendo Tello sec 6.3.3.

    Compone 4 objetivos (con sub-objetivos donde aplica), todos normalizados
    a [0, 1] y combinados con pesos ROC. La cobertura **no** entra en este
    cálculo; el orquestador la añade como métrica de tracking aparte.

    Returns:
        ``(f_rendimiento, objetivos, componentes, crudos)``:
          - ``f_rendimiento``: escalar agregado en [0, 1] (suma ponderada
            de los 4 objetivos).
          - ``objetivos``: dict con los 4 objetivos ya normalizados.
          - ``componentes``: dict con los 7 sub-componentes individuales,
            útil para inspección y gráficos.
          - ``crudos``: dict con los valores pre-normalización.
    """
    p = config.pesos
    u = config.umbrales

    # ─── Obj 1 — Condiciones laborales (vn_1, vn_2, vn_3) ────────────────
    pos_crudo, pos_cota = tiempo_optimo_posicion(
        solucion,
        parametros,
        pos_opt_min=u.pos_opt_min,
        pos_min_min=u.pos_min_min,
    )
    f_vn1 = _norm_desviacion_t(pos_crudo, pos_cota)

    trab_crudo, trab_cota = tiempo_optimo_trabajo(
        solucion,
        parametros,
        trab_opt_min=u.trab_opt_min,
        trab_min_min=u.trab_min_min,
    )
    f_vn2 = _norm_desviacion_t(trab_crudo, trab_cota)

    eje_crudo, eje_cota = porcentaje_ejecutivo(
        solucion,
        pct_min=u.pct_ejecutivo_min,
        pct_max=u.pct_ejecutivo_max,
    )
    f_vn3 = _norm_desviacion_t(eje_crudo, eje_cota)

    obj1 = p.mu_1_1 * f_vn1 + p.mu_1_2 * f_vn2 + p.mu_1_3 * f_vn3

    # ─── Obj 2 — Compactación (fragmentación) ─────────────────────────
    # frag_crudo, frag_vmin, frag_vmax = fragmentacion(solucion)
    # obj2 = _norm_fragmentacion(frag_crudo, frag_vmin, frag_vmax)
    sim_v, sim_vmax = similitud_estadillos(solucion, momento_actual=0)
    obj2 = _norm_estadillos(sim_v, sim_vmax)

    # ─── Obj 3 — Intervalos de descanso + Acreditación ────────────────
    desc_crudo, desc_vmin, desc_vmax = intervalos_descanso(solucion)
    f_3_1 = _norm_intervalos_descanso(desc_crudo, desc_vmin, desc_vmax)

    acred_crudo, acred_vmin, acred_vmax = acreditacion(solucion, entrada)
    f_3_2 = _norm_acreditacion(acred_crudo, acred_vmin, acred_vmax)

    obj3 = p.mu_3_1 * f_3_1 + p.mu_3_2 * f_3_2

    # ─── Obj 4 — Balance de carga ─────────────────────────────────────
    bal_sigma, bal_sigma_max = balance_carga(solucion)
    obj4 = _norm_desviacion_t(bal_sigma, bal_sigma_max)

    # ─── Suma ponderada de los 4 objetivos (ROC) ──────────────────────
    f_rendimiento = (
        p.w_obj1 * obj1 + p.w_obj2 * obj2 + p.w_obj3 * obj3 + p.w_obj4 * obj4
    )

    # ─── Empaquetado de diccionarios de trazabilidad ──────────────────
    objetivos = {
        "obj1_condiciones_laborales": obj1,
        # "obj2_compactacion": obj2,
        "obj2_similitud_estadillos": obj2,
        "obj3_descansos_y_acreditacion": obj3,
        "obj4_balance_carga": obj4,
    }
    componentes = {
        "vn1_tiempo_optimo_posicion": f_vn1,
        "vn2_tiempo_optimo_trabajo": f_vn2,
        "vn3_porcentaje_ejecutivo": f_vn3,
        # "fragmentacion": obj2,
        "similitud_estadillos": obj2,
        "intervalos_descanso": f_3_1,
        "acreditacion": f_3_2,
        "balance_carga": obj4,
    }
    crudos = {
        "vn1_crudo": pos_crudo,
        "vn1_cota": pos_cota,
        "vn2_crudo": trab_crudo,
        "vn2_cota": trab_cota,
        "vn3_crudo": eje_crudo,
        "vn3_cota": eje_cota,
        # "fragmentacion_crudo": float(frag_crudo),
        # "fragmentacion_vmin": float(frag_vmin),
        # "fragmentacion_vmax": float(frag_vmax),
        "similitud_estadillos_v": sim_v,
        "similitud_estadillos_vmax": sim_vmax,
        "intervalos_descanso_crudo": float(desc_crudo),
        "intervalos_descanso_vmin": float(desc_vmin),
        "intervalos_descanso_vmax": float(desc_vmax),
        "acreditacion_crudo": float(acred_crudo),
        "acreditacion_vmin": float(acred_vmin),
        "acreditacion_vmax": float(acred_vmax),
        "balance_sigma": bal_sigma,
        "balance_sigma_max": bal_sigma_max,
    }

    return f_rendimiento, objetivos, componentes, crudos
