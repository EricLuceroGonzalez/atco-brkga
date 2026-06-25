"""BRKGA con arranque en caliente y comparativa cold-vs-warm.

Compara la convergencia del BRKGA bajo dos políticas de inicialización:
    cold = población 100% aleatoria
    warm = K cromosomas-semilla heurísticos + (pop_size - K) aleatorios

Métricas reportadas (gracias a la arquitectura 2-bloques del fitness):
    valor          = alpha·f_factibilidad + (1-alpha)·f_rendimiento  ∈ [0, 1]
    f_factibilidad = restricciones violadas (Tello §6.3.3)    ∈ [0, 1]
    f_rendimiento  = 4 objetivos Tello (cobertura como aux)   ∈ [0, 1]

Ejecutar con:
    uv run python experiments/05_brkga_warmstart_analisis.py \\
        --decoder permutation --n-warm-seeds 25 --pop-size 100 \\
        --max-gens 200 --compare-cold
        # Versión rápida para verificar que funciona
        uv run python experiments/05_brkga_warmstart_analisis.py \
            --decoder permutation --n-warm-seeds 25 --pop-size 100 \
            --max-gens 50 --compare-cold

        # Corrida larga
        uv run python experiments/05_brkga_warmstart_analisis.py \
            --decoder permutation --n-warm-seeds 25 --pop-size 100 \
            --max-gens 5000 --max-seconds 600 --compare-cold

        # Probar el decoder bin-midpoint
        uv run python experiments/05_brkga_warmstart_analisis.py \
            --decoder bin_midpoint --n-warm-seeds 25 --pop-size 100 \
            --max-gens 100 --compare-cold

Salida en results/brkga_warmstart_<timestamp>/:
    cold/  warm/  cada uno con convergence.png, objetivos.png, violaciones.png,
                  best_solution.xlsx, convergence.json
    comparativa.png  con las dos curvas superpuestas
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np

from atco.algorithms.brkga import BRKGAConfig, BRKGAEngine, StoppingCriteria
from atco.algorithms.brkga.decoders import (
    BinMidpointDecoder,
    PermutationDecoder,
    chromosome_from_solucion,
    construir_alfabeto,
    encode_solucion,
)
from atco.analysis.convergence import (
    dump_run_result,
    plot_components_evolution,
    plot_convergence,
    plot_violaciones_final_breakdown,
    plot_violaciones_por_generacion,
    plot_objetivos_evolution,
    plot_r_evolution,
    plot_violaciones_magnitud,
)
from atco.fitness import FitnessConfig
from atco.io.solution import load_solution_json
from atco.io.excel import _write_solution_xlsx_gantt
from atco.io.logging_setup import setup_logging
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds.greedy_cohorte import construir_solucion_heuristica
from atco.domain.constants import LONGITUD_CADENAS

# ============================================================================
# CLI
# ============================================================================


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])

    g_brkga = p.add_argument_group("BRKGA")
    g_brkga.add_argument("--pop-size", type=int, default=100)
    g_brkga.add_argument("--max-gens", type=int, default=200)
    g_brkga.add_argument("--max-seconds", type=float, default=6000.0)
    g_brkga.add_argument("--stagnation", type=int, default=100)
    g_brkga.add_argument("--elite-frac", type=float, default=0.20)
    g_brkga.add_argument("--mutant-frac", type=float, default=0.30)
    g_brkga.add_argument("--rho-elite", type=float, default=0.65)
    g_brkga.add_argument("--seed", type=int, default=42)

    g_decoder = p.add_argument_group("Decoder y warm-start")
    g_decoder.add_argument(
        "--decoder",
        choices=["permutation", "bin_midpoint"],
        default="permutation",
        help="permutation: clásico BRKGA. bin_midpoint: codec exacto (sólo para tests).",
    )
    g_decoder.add_argument("--n-warm-seeds", type=int, default=20)

    g_compare = p.add_argument_group("Comparativa")
    g_compare.add_argument(
        "--compare-cold",
        action="store_true",
        help="Corre además la versión 100% aleatoria para comparar.",
    )

    g_io = p.add_argument_group("Entrada / Salida")
    g_io.add_argument("--case", default="madN_M1")
    g_io.add_argument("--entrada-id", default="madN_M1-2019-02-12")
    g_io.add_argument("--entorno", default="Madrid")

    return p.parse_args()


# ============================================================================
# Helpers
# ============================================================================


@dataclass(frozen=True)
class _Shape:
    """Tamaños usados por el decoder y la codificación."""

    n: int  # número de controladores
    T: int  # número de slots
    n_sectores: int  # tamaño del catálogo de sectores
    alfabeto: list  # alfabeto de tokens (sólo si bin_midpoint)


def _calcular_shape(entrada: Entrada, sol_referencia) -> _Shape:
    """Extrae N, T, |S| y alfabeto de la instancia."""
    return _Shape(
        n=len(entrada.get_controladores()),
        T=len(sol_referencia.turnos[0]) // 3,
        n_sectores=len(entrada.get_lista_sectores()),
        alfabeto=construir_alfabeto(entrada),
    )


def _build_decoder(decoder_type: Literal["permutation", "bin_midpoint"], shape: _Shape):
    """Instancia el decoder pedido."""
    if decoder_type == "permutation":
        return PermutationDecoder(
            n_controladores=shape.n,
            n_sectores=shape.n_sectores,
        )
    return BinMidpointDecoder(
        n_controladores=shape.n,
        longitud_t=shape.T,
        alfabeto=shape.alfabeto,
    )


def _build_warm_seeds(
    decoder_type: Literal["permutation", "bin_midpoint"],
    shape: _Shape,
    entrada: Entrada,
    parametros: Parametros,
    base_seed: int,
    n_seeds: int,
    log: logging.Logger,
) -> list[np.ndarray]:
    """Genera n_seeds heurísticas y las codifica para el decoder dado.

    Cada decoder usa una codificación distinta:
      - permutation:  chromosome_from_solucion -> tamaño N + |S|
      - bin_midpoint: encode_solucion          -> tamaño N · T
    """
    log.info(
        "Generando %d semillas heurísticas (seeds %d..%d) para decoder=%s",
        n_seeds,
        base_seed,
        base_seed + n_seeds - 1,
        decoder_type,
    )
    semillas: list[np.ndarray] = []
    for k in range(n_seeds):
        sol_k = construir_solucion_heuristica(
            entrada=entrada,
            parametros=parametros,
            rng=random.Random(base_seed + k),
        )
        if decoder_type == "permutation":
            ch = chromosome_from_solucion(
                sol_k,
                n_controladores=shape.n,
                longitud_t=shape.T,
                n_sectores=shape.n_sectores,
            )
        else:
            ch = encode_solucion(sol_k, shape.T, shape.alfabeto)
        semillas.append(ch)
    log.info(
        "Semillas listas: %d cromosomas de longitud %d", len(semillas), len(semillas[0])
    )
    return semillas


def _make_config(args: argparse.Namespace) -> BRKGAConfig:
    return BRKGAConfig(
        population_size=args.pop_size,
        elite_fraction=args.elite_frac,
        mutant_fraction=args.mutant_frac,
        rho_elite=args.rho_elite,
        seed=args.seed,
        stopping=StoppingCriteria(
            max_generations=args.max_gens,
            max_seconds=args.max_seconds,
            stagnation_generations=args.stagnation,
            max_evaluations=None,
        ),
    )


def _run_and_dump(
    label: str,
    out_dir: Path,
    args: argparse.Namespace,
    shape: _Shape,
    entrada: Entrada,
    parametros: Parametros,
    seed_chromosomes: list[np.ndarray] | None,
    log: logging.Logger,
):
    """Corre BRKGA y vuelca los outputs estándar al sub-directorio `label/`."""
    sub = out_dir / label
    sub.mkdir(parents=True, exist_ok=True)

    decoder = _build_decoder(args.decoder, shape)
    engine = BRKGAEngine(_make_config(args), FitnessConfig(), decoder)
    log.info(
        "[%s] Lanzando BRKGA con %d semillas inyectadas",
        label,
        len(seed_chromosomes or []),
    )
    result = engine.run(entrada, parametros, seed_chromosomes=seed_chromosomes)

    title = (
        f"BRKGA {args.decoder} ({label}) | {args.case} | "
        f"pop={args.pop_size} K={len(seed_chromosomes or [])} "
        f"gens={result.generations}"
    )
    # ------------- Probando salida
    #
    violaciones_por_gen = [
        tuple(sorted(h.best_restricciones_violadas or [])) for h in result.history
    ]
    unicos = set(violaciones_por_gen)
    log.info("Variantes distintas a lo largo de la corrida: %d", len(unicos))
    for v in sorted(unicos, key=len):
        log.info("  → %s", list(v))

    unicos = set(violaciones_por_gen)
    log.info(
        "Variantes distintas de 'restricciones_violadas' a lo largo de la corrida: %d",
        len(unicos),
    )
    for v in unicos:
        log.info("  → %s", v)
    # ------------- Probando salida
    dump_run_result(result, sub / "convergence.json")
    plot_objetivos_evolution(result.history, sub / "objetivos_4.png", title=title)
    plot_components_evolution(result.history, sub / "componentes_7.png", title=title)
    plot_violaciones_magnitud(
        result.history, sub / "violaciones_magnitud.png", title=title
    )
    plot_r_evolution(result.history, sub / "r_evolution.png", title=title)
    plot_convergence(result.history, sub / "convergence.png", title=title)
    plot_components_evolution(result.history, sub / "objetivos.png", title=title)
    plot_violaciones_por_generacion(
        result.history,
        sub / "violaciones_por_gen.png",
        title=title,
    )
    n_violadas = len(result.best_fitness_result.restricciones_violadas)
    plot_violaciones_final_breakdown(
        result.best_fitness_result.restricciones_violadas,
        sub / "violaciones_final.png",
        title=f"{label} — Mejor final | {n_violadas} violadas",
    )
    _write_solution_xlsx_gantt(sub / "best_solution.xlsx", result.best_solution)

    return result


def _resumen_log(label: str, result, log: logging.Logger) -> None:
    """Imprime un resumen estándar al log."""
    fr = result.best_fitness_result
    log.info("=" * 60)
    log.info("[%s] valor          = %.6f", label, result.best_individual.fitness)
    log.info(
        "[%s] f_factibilidad = %.6f", label, getattr(fr, "f_factibilidad", float("nan"))
    )
    log.info(
        "[%s] f_rendimiento  = %.6f", label, getattr(fr, "f_rendimiento", float("nan"))
    )
    log.info("[%s] factible       = %s", label, getattr(fr, "factible", "?"))
    log.info(
        "[%s] cobertura_ratio = %.4f",
        label,
        getattr(fr, "cobertura_ratio", float("nan")),
    )
    log.info("[%s] semilla mejor  = %.6f", label, result.seed_fitness)
    log.info("[%s] mejora rel.    = %.2f%%", label, result.mejora_relativa * 100)
    log.info("[%s] generaciones   = %d", label, result.generations)

    log.info("[%s] Objetivos Tello:", label)
    for nombre, valor in getattr(fr, "objetivos", {}).items():
        log.info("  %-32s = %.4f", nombre, valor)

    log.info("[%s] Componentes individuales:", label)
    for nombre, valor in fr.componentes.items():
        log.info("  %-32s = %.4f", nombre, valor)

    n_viol = len(fr.restricciones_violadas)
    log.info("[%s] Restricciones violadas (%d):", label, n_viol)
    for nombre in fr.restricciones_violadas:
        log.info("  - %s", nombre)


def _plot_comparativa(
    out_dir: Path,
    runs: dict[str, object],
    log: logging.Logger,
) -> None:
    """Superpone las curvas valor/factibilidad/rendimiento de las dos corridas."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib no disponible; salto la comparativa.")
        return

    fig, axs = plt.subplots(1, 3, figsize=(18, 5), sharex=True)
    colores = {"cold": "tab:gray", "warm": "tab:blue"}

    for ax, metrica, titulo in zip(
        axs,
        ["valor", "f_factibilidad", "f_rendimiento"],
        ["Valor (fitness total)", "Bloque A — Factibilidad", "Bloque B — Rendimiento"],
    ):
        for label, result in runs.items():
            xs = [h.generation for h in result.history]
            ys = [getattr(h, metrica, float("nan")) for h in result.history]
            ax.plot(xs, ys, label=label, color=colores.get(label, None), lw=2)
        ax.set_title(titulo)
        ax.set_xlabel("Generación")
        ax.set_ylabel(metrica)
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend()

    fig.suptitle("Comparativa cold-vs-warm", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "comparativa.png", dpi=120)
    plt.close(fig)
    log.info("Comparativa guardada -> %s", out_dir / "comparativa.png")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPO_ROOT = Path(__file__).resolve().parent.parent
    out_dir = REPO_ROOT / "results" / f"brkga_warmstart_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(
        log_dir=str(out_dir / "logs"),
        log_filename="brkga.log",
        level="INFO",
    )
    log = logging.getLogger("brkga-warmstart")

    # ── Carga instancia ──────────────────────────────────────────────
    parametros = Parametros.from_files(
        REPO_ROOT / "resources/problemParameters.properties",
        REPO_ROOT / "resources/options.properties",
    )
    entrada = Entrada.leer_entrada(
        REPO_ROOT,
        parametros,
        args.case,
        args.entrada_id,
        args.entorno,
    )
    # ── Inicio del chekeo ───────────────────────────────────────
    log.info("Diagnóstico de sectores")
    log.info("  Total en lista_sectores: %d", len(entrada.get_lista_sectores()))
    log.info("  Sectores abiertos en algún slot:")

    abiertos_global = set()
    for t in range(len(entrada.get_sectorizacion())):
        for s in entrada.get_sectores_abiertos_en(t):
            abiertos_global.add((s.id, s.nombre))

    for sid, nombre in sorted(abiertos_global):
        log.info("    %s  ->  %s", sid, nombre)

    # Y verifica que las cadenas que viste en best_solution.xlsx coinciden:
    sospechosos = {"aea", "abd", "adg"}  # los que te llamaron la atención
    for sid, nombre in sorted(abiertos_global):
        if sid in sospechosos:
            log.info("  ✓ %s ESTÁ abierto, nombre real = %s", sid, nombre)

    ids_totales = {s.id for s in entrada.get_lista_sectores()}
    ids_abiertos = set()  # tu construcción actual
    sospechosos = {"aea", "abd", "adg"}

    for tok in sospechosos:
        if tok in ids_abiertos:
            estado = "ABIERTO ✓"
        elif tok in ids_totales:
            estado = "VÁLIDO pero CERRADO ✗"
        else:
            estado = "INEXISTENTE (fantasma) ✗✗"
        log.info(f"  {tok}  →  {estado}")

    # # Test para ver los sectores abiertos en el excel
    # sol = load_solution_json(
    #     REPO_ROOT / "results/brkga_warmstart_20260625_172258/cold/best_solution.xlsx"
    # )
    # ids_en_solucion = set()
    # for fila in sol.get_turnos():
    #     for j in range(0, len(fila), LONGITUD_CADENAS):
    #         ids_en_solucion.add(fila[j : j + LONGITUD_CADENAS])
    # log.info(f"  Tokens en best: {sorted(ids_en_solucion - ids_abiertos)}")
    # log.info(f"  De ellos, fantasmas: {sorted(ids_en_solucion - ids_totales)}")
    # import numpy as np
    # ── Fin del chekeo ───────────────────────────────────────
    # ── Geometría del problema ───────────────────────────────────────
    sol_referencia = construir_solucion_heuristica(
        entrada=entrada,
        parametros=parametros,
        rng=random.Random(args.seed),
    )
    shape = _calcular_shape(entrada, sol_referencia)
    log.info(
        "Instancia | N=%d, T=%d, |sectores|=%d, |alfabeto|=%d, decoder=%s",
        shape.n,
        shape.T,
        shape.n_sectores,
        len(shape.alfabeto),
        args.decoder,
    )
    log.info(
        "Longitud cromosoma | permutation: %d, bin_midpoint: %d -> uso: %d",
        shape.n + shape.n_sectores,
        shape.n * shape.T,
        (
            (shape.n + shape.n_sectores)
            if args.decoder == "permutation"
            else (shape.n * shape.T)
        ),
    )
    # ── Test 2: diagnóstico del decoder ──────────────────────────────
    log.info("─" * 60)
    log.info("Test 2: ¿cromosomas distintos -> soluciones distintas?")
    decoder_diag = _build_decoder(args.decoder, shape)
    chrom_size = (
        shape.n + shape.n_sectores
        if args.decoder == "permutation"
        else shape.n * shape.T
    )
    chrom_a = np.random.default_rng(1).random(chrom_size)
    chrom_b = np.random.default_rng(2).random(chrom_size)
    chrom_c = np.random.default_rng(3).random(chrom_size)

    sol_a = decoder_diag.decode(chrom_a, entrada, parametros)
    sol_b = decoder_diag.decode(chrom_b, entrada, parametros)
    sol_c = decoder_diag.decode(chrom_c, entrada, parametros)

    def _filas_iguales(s1, s2) -> int:
        return sum(1 for ta, tb in zip(s1.turnos, s2.turnos) if ta == tb)

    n_filas = len(sol_a.turnos)
    iguales_ab = _filas_iguales(sol_a, sol_b)
    iguales_ac = _filas_iguales(sol_a, sol_c)
    iguales_bc = _filas_iguales(sol_b, sol_c)

    log.info("  L2(chrom_a, chrom_b) = %.4f", float(np.linalg.norm(chrom_a - chrom_b)))
    log.info(
        "  Filas idénticas sol_a vs sol_b: %d / %d (%.1f%%)",
        iguales_ab,
        n_filas,
        100 * iguales_ab / n_filas,
    )
    log.info(
        "  Filas idénticas sol_a vs sol_c: %d / %d (%.1f%%)",
        iguales_ac,
        n_filas,
        100 * iguales_ac / n_filas,
    )
    log.info(
        "  Filas idénticas sol_b vs sol_c: %d / %d (%.1f%%)",
        iguales_bc,
        n_filas,
        100 * iguales_bc / n_filas,
    )

    if iguales_ab == n_filas and iguales_ac == n_filas:
        log.warning(
            "  ⚠ DECODER DEGENERADO: cromosomas distintos producen soluciones idénticas. "
            "Aplica el Fix 1 (RNG_SEED_INTERNO derivado del cromosoma).",
        )
    else:
        log.info("  ✓ Decoder produce soluciones distintas.")
    log.info("─" * 60)
    # ── Test 3: ¿soluciones distintas tienen fitness distinto? ───────
    from atco.fitness import evaluar_fitness

    log.info("─" * 60)
    log.info("Test 3: ¿el fitness discrimina entre cromosomas distintos?")

    fits = []
    componentes_por_chrom = []
    for k in range(30):
        chrom_k = np.random.default_rng(1000 + k).random(chrom_size)
        sol_k = decoder_diag.decode(chrom_k, entrada, parametros)
        res_k = evaluar_fitness(sol_k, entrada, parametros)
        fits.append(res_k.valor)
        componentes_por_chrom.append(res_k.componentes)

    import statistics as stats

    fits_arr = np.array(fits)
    log.info("  Fitness sobre 30 cromosomas aleatorios:")
    log.info("    min   = %.10f", float(fits_arr.min()))
    log.info("    max   = %.10f", float(fits_arr.max()))
    log.info("    media = %.10f", float(fits_arr.mean()))
    log.info("    std   = %.10f", float(fits_arr.std()))
    log.info("    rango = %.10f", float(fits_arr.max() - fits_arr.min()))

    # Std por componente para ver cuáles realmente se mueven
    log.info("  Variabilidad por componente:")
    nombres = list(componentes_por_chrom[0].keys())
    for n in nombres:
        vals = [c[n] for c in componentes_por_chrom]
        log.info(
            "    %-32s std=%.6f rango=%.6f",
            n,
            float(np.std(vals)),
            float(max(vals) - min(vals)),
        )

    if fits_arr.std() < 1e-6:
        log.warning(
            "  ⚠ FITNESS DEGENERADO: cromosomas distintos producen el mismo fitness. "
            "El BRKGA no puede optimizar porque no hay gradiente.",
        )
    elif fits_arr.std() < 0.01:
        log.warning(
            "  △ FITNESS CASI PLANO: variabilidad muy baja. "
            "El BRKGA mejorará lentamente.",
        )
    else:
        log.info("  ✓ Fitness discrimina bien (std=%.4f).", float(fits_arr.std()))
    log.info("─" * 60)
    log.info("─" * 60)
    log.info("Test 4: ¿son las soluciones permutaciones unas de otras?")
    filas_a = set(sol_a.turnos)
    filas_b = set(sol_b.turnos)
    filas_c = set(sol_c.turnos)
    log.info("  |filas únicas sol_a|: %d / %d", len(filas_a), len(sol_a.turnos))
    log.info("  |filas únicas sol_b|: %d / %d", len(filas_b), len(sol_b.turnos))
    log.info("  |filas únicas sol_c|: %d / %d", len(filas_c), len(sol_c.turnos))
    log.info("  intersección a ∩ b: %d filas", len(filas_a & filas_b))
    log.info("  intersección a ∩ b ∩ c: %d filas", len(filas_a & filas_b & filas_c))
    if filas_a == filas_b == filas_c:
        log.warning(
            "  ⚠ INVARIANCIA PERMUTACIONAL: las tres soluciones son permutaciones "
            "del mismo conjunto de filas. El BRKGA no puede mejorar."
        )
    log.info("─" * 60)
    log.info("─" * 60)
    log.info("Test 5: ¿comparten plantilla temporal (ignorando identidad de sector)?")

    def estructura_temporal(cadena: str) -> str:
        """Reduce cada slot a un símbolo: E = ejecutivo, P = planificador, R = descanso, N = no-turno."""
        out = []
        for i in range(0, len(cadena), 3):
            tok = cadena[i : i + 3]
            if tok == "111":
                out.append("R")
            elif tok == "000":
                out.append("N")
            elif tok[0].isupper():
                out.append("E")
            else:
                out.append("P")
        return "".join(out)

    estr_a = sorted(estructura_temporal(f) for f in sol_a.turnos)
    estr_b = sorted(estructura_temporal(f) for f in sol_b.turnos)
    estr_c = sorted(estructura_temporal(f) for f in sol_c.turnos)

    log.info("  Plantillas idénticas estr_a vs estr_b: %s", estr_a == estr_b)
    log.info("  Plantillas idénticas estr_a vs estr_c: %s", estr_a == estr_c)

    # Si las plantillas son idénticas (como conjuntos ordenados), las soluciones
    # son indistinguibles para la fitness función actual.
    if estr_a == estr_b == estr_c:
        log.warning(
            "  ⚠ MISMAS PLANTILLAS TEMPORALES: las tres soluciones difieren sólo "
            "en QUÉ sector ocupa cada celda. La fitness es ciega a esto."
        )
    log.info("─" * 60)
    # Fin de tests =======
    runs: dict[str, object] = {}

    # ── Cold start (opcional) ────────────────────────────────────────
    if args.compare_cold:
        log.info("─" * 60)
        log.info("Ejecutando COLD start (sin semillas)")
        runs["cold"] = _run_and_dump(
            "cold",
            out_dir,
            args,
            shape,
            entrada,
            parametros,
            seed_chromosomes=None,
            log=log,
        )
        _resumen_log("cold", runs["cold"], log)

    # ── Warm start ───────────────────────────────────────────────────
    log.info("─" * 60)
    log.info("Ejecutando WARM start con %d semillas", args.n_warm_seeds)
    semillas = _build_warm_seeds(
        decoder_type=args.decoder,
        shape=shape,
        entrada=entrada,
        parametros=parametros,
        base_seed=args.seed,
        n_seeds=args.n_warm_seeds,
        log=log,
    )

    diffs = [np.linalg.norm(semillas[0] - semillas[k]) for k in range(1, len(semillas))]
    log.info("Distancia L2 de semilla[0] a las demás:")
    log.info(
        "  min=%.4f, max=%.4f, media=%.4f",
        min(diffs),
        max(diffs),
        float(np.mean(diffs)),
    )

    runs["warm"] = _run_and_dump(
        "warm",
        out_dir,
        args,
        shape,
        entrada,
        parametros,
        seed_chromosomes=semillas,
        log=log,
    )
    _resumen_log("warm", runs["warm"], log)

    # ── Comparativa visual ───────────────────────────────────────────
    if args.compare_cold:
        _plot_comparativa(out_dir, runs, log)

    # ── Resumen final ────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("Salida -> %s", out_dir)
    if args.compare_cold:
        delta_valor = (
            runs["warm"].best_individual.fitness - runs["cold"].best_individual.fitness
        )
        delta_pct = delta_valor / max(runs["cold"].best_individual.fitness, 1e-9) * 100
        log.info(
            "Δ warm vs cold | valor: %+.6f (%+.2f%%)",
            delta_valor,
            delta_pct,
        )


if __name__ == "__main__":
    main()
