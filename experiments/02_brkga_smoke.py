"""Smoke experiment del BRKGA: corre, persiste, grafica.

Uso:
    uv run python experiments/02_brkga_smoke.py
    uv run python experiments/02_brkga_smoke.py --max-gens 50 --pop-size 30
    uv run python experiments/02_brkga_smoke.py --max-gens 300 --pop-size 50 --seed 42
    uv run python experiments/02_brkga_smoke.py --max-gens 300 --pop-size 50 --seed 42 --stagnation 500
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
import random as _random


from atco.algorithms.brkga.decoders import chromosome_from_solucion
from atco.seeds import construir_solucion_heuristica
from atco.algorithms.brkga import (
    BRKGAConfig,
    BRKGAEngine,
    StoppingCriteria,
)
from atco.algorithms.brkga.decoders import PermutationDecoder
from atco.analysis.convergence import dump_run_result, plot_convergence
from atco.fitness import FitnessConfig
from atco.io.logging_setup import setup_logging
from atco.io.excel import _write_solution_xlsx_gantt
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Smoke del BRKGA sobre una instancia.")
    p.add_argument("--max-gens", type=int, default=30)
    p.add_argument("--max-seconds", type=float, default=180.0)
    p.add_argument("--stagnation", type=int, default=15)
    p.add_argument("--pop-size", type=int, default=30)
    p.add_argument("--elite-frac", type=float, default=0.20)
    p.add_argument("--mutant-frac", type=float, default=0.20)
    p.add_argument("--rho-elite", type=float, default=0.70)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--entrada-id",
        type=str,
        required=False,
        help="ID de la entrada, p. ej. 'madN_M1-2019-02-12'.",
        default="madN_M1-2019-02-12",
    )
    p.add_argument("--path", type=str, default="madN_M1")
    p.add_argument("--entorno", type=str, default="Madrid")
    p.add_argument(
        "--problem-props", type=str, default="resources/problemParameters.properties"
    )
    p.add_argument("--options-props", type=str, default="resources/options.properties")
    p.add_argument(
        "--n-warm-seeds",
        type=int,
        default=10,
        help="Cuántos cromosomas heurísticos sembrar en pop inicial.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Directorio de salida con timestamp
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "results" / f"brkga_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(log_dir=str(out_dir / "logs"), log_filename="brkga.log", level="INFO")
    log = logging.getLogger("brkga-smoke")

    # Carga instancia
    parametros = Parametros.from_files(args.problem_props, args.options_props)
    entrada = Entrada.leer_entrada(
        repo=repo_root,
        parametros=parametros,
        path=args.path,
        entrada_id=args.entrada_id,
        entorno=args.entorno,
    )

    n = len(entrada.get_controladores())
    n_sectores = len(entrada.get_lista_sectores())
    log.info("Instancia: %s | N=%d controladores", args.entrada_id, n)

    # Motor

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
    fitness_config = FitnessConfig()
    engine = BRKGAEngine(config=config, fitness_config=fitness_config, decoder=decoder)

    K = args.n_warm_seeds  # añade el flag a argparse
    # Mejor: derivarlo del primer turno generado
    seed_chromosomes: list = []
    for k in range(K):
        sol_k = construir_solucion_heuristica(
            entrada, parametros, rng=_random.Random(args.seed + k)
        )
        longitud_t = len(sol_k.turnos[0]) // 3
        seed_chromosomes.append(
            chromosome_from_solucion(
                sol_k, n_controladores=n, longitud_t=longitud_t, n_sectores=n_sectores
            )
        )
    log.info("Warm-start: inyectados %d cromosomas heurísticos", len(seed_chromosomes))

    # Corre
    result = engine.run(entrada, parametros)

    # Persistencia
    json_path = out_dir / "convergence.json"
    dump_run_result(result, json_path)
    log.info("Convergencia → %s", json_path)

    png_path = out_dir / "convergence.png"
    plot_convergence(
        result.history,
        png_path,
        title=f"BRKGA | {args.entrada_id} | pop={args.pop_size} ρ_e={args.rho_elite}",
    )
    log.info("Gráfico → %s", png_path)

    xlsx_path = out_dir / "best_solution.xlsx"
    _write_solution_xlsx_gantt(solution=result.best_solution, path=xlsx_path)
    log.info("Mejor solución → %s", xlsx_path)

    # Resumen final en log
    log.info("-" * 80)
    log.info("RESUMEN")
    log.info("  Semilla inicial : fitness = %.4f", result.seed_fitness)
    log.info("  Mejor encontrado: fitness = %.4f", result.best_individual.fitness)
    log.info("  Mejora relativa : %.2f%%", result.mejora_relativa * 100)
    log.info("  Generaciones    : %d", result.generations)
    log.info("  Evaluaciones    : %d", result.evaluations)
    log.info("  Tiempo total    : %.1f s", result.elapsed_seconds)
    log.info("  Componentes del mejor:")
    for nombre, valor in result.best_fitness_result.componentes.items():
        log.info("    %s = %.4f", nombre, valor)
    log.info(
        "  Restricciones violadas (%d):",
        len(result.best_fitness_result.restricciones_violadas),
    )
    for nombre in result.best_fitness_result.restricciones_violadas:
        log.info("    - %s", nombre)


if __name__ == "__main__":
    main()
