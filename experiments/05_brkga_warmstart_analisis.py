"""BRKGA bin-midpoint sembrado con K semillas heurísticas + análisis gráfico completo.
Ejecutar con:
-uv run python experiments/05_brkga_warmstart_analisis.py --n-warm-seeds 25 --pop-size 100 --max-gens 50
-uv run python experiments/05_brkga_warmstart_analisis.py --n-warm-seeds 25 --pop-size 100 --max-gens 5000
"""

from __future__ import annotations

import argparse
import logging
import random
from datetime import datetime
from pathlib import Path

import numpy as np

from atco.algorithms.brkga import BRKGAConfig, BRKGAEngine, StoppingCriteria
from atco.algorithms.brkga.decoders import (
    BinMidpointDecoder,
    PermutationDecoder,
    construir_alfabeto,
    encode_solucion,
)
from atco.analysis.convergence import (
    dump_run_result,
    plot_components_evolution,
    plot_convergence,
    plot_violaciones_final_breakdown,
    plot_violaciones_por_generacion,
)
from atco.fitness import FitnessConfig
from atco.io.excel import _write_solution_xlsx_gantt
from atco.io.logging_setup import setup_logging
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds import construir_solucion_heuristica


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--n-warm-seeds", type=int, default=20)
    p.add_argument("--pop-size", type=int, default=100)
    p.add_argument("--max-gens", type=int, default=100)
    p.add_argument("--max-seconds", type=float, default=6000.0)
    p.add_argument("--stagnation", type=int, default=100)
    p.add_argument("--elite-frac", type=float, default=0.20)
    p.add_argument("--mutant-frac", type=float, default=0.30)
    p.add_argument("--rho-elite", type=float, default=0.65)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPO_ROOT = Path(__file__).resolve().parent.parent
    out_dir = REPO_ROOT / "results" / f"brkga_warmstart_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(
        log_dir=str(out_dir / "logs"), log_filename="brkga.log", level="DEBUG"
    )
    log = logging.getLogger("brkga-warmstart")

    p = Parametros.from_files(
        REPO_ROOT / "resources/problemParameters.properties",
        REPO_ROOT / "resources/options.properties",
    )
    e = Entrada.leer_entrada(REPO_ROOT, p, "madN_M1", "madN_M1-2019-02-12", "Madrid")

    n = len(e.get_controladores())
    sol_referencia = construir_solucion_heuristica(
        entrada=e, parametros=p, rng=random.Random(args.seed)
    )

    slots_n = (
        len(sol_referencia.turnos[0]) // 3
    )  # Divide la cadena de caracteres de 3 en 3

    alfabeto = construir_alfabeto(e)
    # Descomentar para probar salida del constructor
    # _write_solution_xlsx_gantt(out_dir / "first_solution.xlsx", sol_referencia)
    log.info(
        "Instancia | N=%d, T=%d, alfabeto=%d, L=N·T=%d",
        n,
        slots_n,
        len(alfabeto),
        n * slots_n,
    )

    # ── Warm-start: K semillas heurísticas codificadas ───────────────────
    log.info(
        "Generando %d semillas heurísticas con seeds %d..%d",
        args.n_warm_seeds,
        args.seed,
        args.seed + args.n_warm_seeds - 1,
    )
    seed_chromosomes: list[np.ndarray] = []
    for k in range(args.n_warm_seeds):
        sol_k = construir_solucion_heuristica(
            entrada=e, parametros=p, rng=random.Random(args.seed + k)
        )
        ch_k = encode_solucion(sol_k, slots_n, alfabeto)
        seed_chromosomes.append(ch_k)

    # ── Motor ───────────────────────────────────────────────────────────
    # decoder = BinMidpointDecoder(
    #     n_controladores=n, longitud_t=slots_n, alfabeto=alfabeto
    # )
    n_sectores = 0
    decoder = PermutationDecoder(n_controladores=n, n_sectores=n_sectores)
    config = BRKGAConfig(
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
    engine = BRKGAEngine(config, FitnessConfig(), decoder)
    result = engine.run(e, p, seed_chromosomes=seed_chromosomes)

    # ── Persistencia ────────────────────────────────────────────────────
    dump_run_result(result, out_dir / "convergence.json")
    title = (
        f"BRKGA bin-midpoint | madN_M1 | "
        f"pop={args.pop_size} K={args.n_warm_seeds} gens={result.generations}"
    )

    plot_convergence(result.history, out_dir / "convergence.png", title=title)
    plot_components_evolution(result.history, out_dir / "components.png", title=title)
    plot_violaciones_por_generacion(
        result.history,
        out_dir / "violaciones_por_gen.png",
        title=title,
    )
    plot_violaciones_final_breakdown(
        result.best_fitness_result.restricciones_violadas,
        out_dir / "violaciones_final.png",
        title=f"Mejor final | {len(result.best_fitness_result.restricciones_violadas)} violadas",
    )

    _write_solution_xlsx_gantt(out_dir / "best_solution.xlsx", result.best_solution)

    log.info("=" * 60)
    log.info("Semilla mejor : %.6f", result.seed_fitness)
    log.info("Mejor final   : %.6f", result.best_individual.fitness)
    log.info("Mejora        : %.2f%%", result.mejora_relativa * 100)
    log.info("Componentes del mejor:")
    for nombre, valor in result.best_fitness_result.componentes.items():
        log.info("  %-25s = %.4f", nombre, valor)
    log.info(
        "Restricciones violadas (%d):",
        len(result.best_fitness_result.restricciones_violadas),
    )
    for nombre in result.best_fitness_result.restricciones_violadas:
        log.info("  - %s", nombre)
    log.info("Salida → %s", out_dir)


if __name__ == "__main__":
    main()
