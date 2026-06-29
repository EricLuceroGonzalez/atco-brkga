# 07_brkga_instance_decoder.py
"""

Ejecutar con:
    uv run python experiments/05_brkga_warmstart_analisis.py \\
        --decoder permutation --n-warm-seeds 25 --pop-size 100 \\
        --max-gens 200 --compare-cold
        # Versión rápida para verificar que funciona
        uv run python experiments/05_brkga_warmstart_analisis.py \
            --decoder permutation --n-warm-seeds 25 --pop-size 100 \
            --max-gens 50 --compare-cold

        # Probar el decoder bin-midpoint
        uv run python experiments/05_brkga_warmstart_analisis.py \
            --decoder bin_midpoint --n-warm-seeds 25 --pop-size 100 \
            --max-gens 100 --compare-cold

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
    abiertos_global = set()
    for t in range(len(entrada.get_sectorizacion())):
        for s in entrada.get_sectores_abiertos_en(t):
            abiertos_global.add((s.id, s.nombre))
    return _Shape(
        n=len(entrada.get_controladores()),
        T=len(sol_referencia.turnos[0]) // 3,
        n_sectores=len(abiertos_global),
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


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    args = parse_args()
    # stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPO_ROOT = Path(__file__).resolve().parent.parent
    out_dir = REPO_ROOT / "docs/logs" / "silly-test"
    out_dir.mkdir(parents=True, exist_ok=True)
    print("out_dir = ", out_dir)
    setup_logging(
        log_dir=str(out_dir / "logs"),
        log_filename="silly-test.log",
        level="INFO",
    )
    log = logging.getLogger(__name__)

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
    log.info("  Sectores abiertos en esta instancia:")

    # ── Geometría del problema ───────────────────────────────────────

    N = len(entrada.get_controladores())
    T = len(entrada.get_sectorizacion())
    S_total = len(entrada.get_lista_sectores())
    S_abiertos = len(entrada.get_sectores_abiertos_todo_el_dia())
    log.info(f"N={N}  T={T}  S_total={S_total}  S_abiertos={S_abiertos}")

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

    # === BinMidpoint ===
    alfabeto = construir_alfabeto(entrada)
    print(
        f"|alfabeto|={len(alfabeto)} (esperado {2 + 2*S_abiertos} si filtra a abiertos)"
    )

    bm = BinMidpointDecoder(n_controladores=N, longitud_t=T, alfabeto=alfabeto)
    print(f"BinMidpoint.num_genes = {bm.num_genes} (esperado {N*T})")

    # Round-trip
    sol0 = construir_solucion_heuristica(
        entrada=entrada, parametros=parametros, rng=random.Random(0)
    )
    chrom = encode_solucion(sol0, T, alfabeto)
    sol_back = bm.decode(np.asarray(chrom), entrada, parametros)
    identicas = sum(a == b for a, b in zip(sol0.turnos, sol_back.turnos))
    print(f"BinMidpoint round-trip: {identicas}/{N} filas idénticas")

    # === Permutation ===
    pm = PermutationDecoder(n_controladores=N, n_sectores=S_abiertos)
    print(f"Permutation.num_genes = {pm.num_genes} (esperado {N + S_abiertos})")
    sol_pm = pm.decode(
        np.random.default_rng(0).random(pm.num_genes), entrada, parametros
    )

    tokens_unicos = {
        t
        for fila in sol_pm.turnos
        for t in (fila[i : i + 3] for i in range(0, len(fila), 3))
    }
    fuera = tokens_unicos - set(alfabeto)
    print(
        f"Permutation produce {len(tokens_unicos)} tokens únicos, {len(fuera)} fuera del alfabeto"
    )

    # ── Test 2: diagnóstico del decoder ──────────────────────────────
    log.info("=" * 30)
    log.info("Test 2: ¿cromosomas distintos -> soluciones distintas?")
    # decoder_diag = _build_decoder(args.decoder, shape)
    # decoder_type = "permutation"
    decoder_type = "bin-midpoint"
    chrom_size = (
        shape.n + shape.n_sectores
        if decoder_type == "permutation"
        else shape.n * shape.T
    )
    print(f"Permutation chrom_size: {chrom_size}")
    chrom_a = np.random.default_rng(1).random(chrom_size)
    chrom_b = np.random.default_rng(2).random(chrom_size)
    chrom_c = np.random.default_rng(3).random(chrom_size)

    if decoder_type == "permutation":
        sol_a = pm.decode(chrom_a, entrada, parametros)
        sol_b = pm.decode(chrom_b, entrada, parametros)
        sol_c = pm.decode(chrom_c, entrada, parametros)
    else:
        sol_a = bm.decode(chrom_a, entrada, parametros)
        sol_b = bm.decode(chrom_b, entrada, parametros)
        sol_c = bm.decode(chrom_c, entrada, parametros)

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
    # ── Test 3: ¿el fitness discrimina entre cromosomas distintos? ──────────────────────────────
    log.info(
        "============Test 3: ¿el fitness discrimina entre cromosomas distintos?============"
    )

    fits = []
    componentes_por_chrom = []
    for k in range(30):
        chrom_k = np.random.default_rng(1000 + k).random(chrom_size)
        sol_k = (
            pm.decode(chrom_k, entrada, parametros)
            if decoder_type == "permutation"
            else bm.decode(chrom_k, entrada, parametros)
        )

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
    # # ============ Test 4 ==================
    log.info(
        "============Test 4: ¿son las soluciones permutaciones unas de otras?============"
    )
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
    # # ============ Test 5 ==================
    log.info(
        "============Test 5: ¿comparten plantilla temporal (ignorando identidad de sector)?============"
    )

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
    # # Fin de tests =======


if __name__ == "__main__":
    main()
