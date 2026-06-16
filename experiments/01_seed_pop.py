"""Smoke experiment: genera K semillas y reporta su fitness.

Uso:
    uv run python experiments/01_seed_population.py
    uv run python experiments/01_seed_population.py --n-seeds 20 --case madN_M1
"""

from __future__ import annotations

import argparse
import logging
import random

from pathlib import Path

from atco.fitness import FitnessConfig, evaluar_fitness
from atco.io.logging_setup import setup_logging
from atco.io.excel import _write_solution_xlsx_gantt
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.problem.properties import load_properties
from atco.seeds import construir_solucion_heuristica


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(...)
    p.add_argument("--n-seeds", type=int, default=10)
    p.add_argument("--seed-base", type=int, default=42)
    p.add_argument(
        "--path",
        type=str,
        default="madN_M1",
        help="Subdirectorio dentro de entrada/Casos/",
    )
    p.add_argument(
        "--entrada-id",
        type=str,
        required=False,
        help="ID de la entrada, p. ej. '2024-04-09'.",
        default="madN_M1-2019-02-12",
    )
    p.add_argument("--entorno", type=str, default="Madrid")
    p.add_argument(
        "--properties", type=str, default="resources/problemParameters.properties"
    )
    p.add_argument(
        "--problem-props",
        type=str,
        default="resources/problemParameters.properties",
        help="Properties con los parámetros del problema.",
    )
    p.add_argument(
        "--options-props",
        type=str,
        default="resources/problemParameters.properties",
        # default="entrada/opciones.properties",
        help="Properties con las opciones del algoritmo.",
    )
    return p.parse_args()


from pathlib import Path

from atco.problem.instance import Entrada


def cargar_caso(args: argparse.Namespace, parametros) -> Entrada:
    """Construye la Entrada igual que la fixture de los tests.

    Ajusta los argumentos a lo que tu conftest pasa a `Entrada.leer_entrada`.
    """
    repo = Path(__file__).resolve().parent.parent  # raíz del proyecto
    return Entrada.leer_entrada(
        repo=repo,
        parametros=parametros,
        path=args.path,
        entrada_id=args.entrada_id,
        entorno=args.entorno,
        estudio_estadillos=True,
    )


def main() -> None:
    args = parse_args()
    setup_logging(level="INFO")
    log = logging.getLogger("seed-population")
    log.info("=== === === === === === === === ===")
    log.info("args:")
    log.info(args)
    log.info("=== === === === === === === === ===")
    # ! === === === === === === === === ===
    # parametros = load_properties(args.properties)
    parametros = Parametros.from_files(args.problem_props, args.options_props)
    entrada = cargar_caso(args, parametros=parametros)
    cfg = FitnessConfig()

    log.info(
        "Caso: %s | N=%d controladores", args.entrada_id, len(entrada.controladores)
    )
    log.info(
        "Pesos fitness: R=%.2f C=%.2f B=%.2f F=%.2f L=%.2f",
        cfg.alpha_r,
        cfg.alpha_c,
        cfg.alpha_b,
        cfg.alpha_f,
        cfg.alpha_l,
    )
    log.info("Generando %d semillas con base=%d", args.n_seeds, args.seed_base)
    log.info("-" * 80)

    resultados: list[tuple[int, float, dict[str, float], int]] = []
    for k in range(args.n_seeds):
        rng = random.Random(args.seed_base + k)
        sol = construir_solucion_heuristica(entrada, parametros, rng)
        res = evaluar_fitness(sol, entrada, parametros, cfg)
        resultados.append(
            (k, res.valor, res.componentes, len(res.restricciones_violadas))
        )
        log.info(
            "seed %2d | valor=%.4f | R=%.3f C=%.3f B=%.3f F=%.3f L=%.3f | violadas=%d",
            k,
            res.valor,
            res.componentes["R"],
            res.componentes["C"],
            res.componentes["B"],
            res.componentes["F"],
            res.componentes["L"],
            len(res.restricciones_violadas),
        )

    log.info("-" * 80)
    valores = [v for _, v, _, _ in resultados]
    log.info(
        "Resumen: best=%.4f | avg=%.4f | worst=%.4f | std=%.4f",
        min(valores),
        sum(valores) / len(valores),
        max(valores),
        _std(valores),
    )

    mejor_k = min(range(len(resultados)), key=lambda i: resultados[i][1])
    log.info(
        "Mejor semilla: #%d (valor=%.4f)",
        resultados[mejor_k][0],
        resultados[mejor_k][1],
    )

    # Re-genera la mejor para enseñar restricciones violadas con nombre
    rng_mejor = random.Random(args.seed_base + mejor_k)
    sol_mejor = construir_solucion_heuristica(entrada, parametros, rng_mejor)
    res_mejor = evaluar_fitness(sol_mejor, entrada, parametros, cfg)
    # print(Path(__file__).resolve().parent.parent)
    _write_solution_xlsx_gantt(
        path=f"{Path(__file__).resolve().parent.parent}/experiments/seed_{k:02d}.xlsx",
        solution=sol_mejor,
    )
    log.info(
        "  restricciones violadas (%d):",
        len(res_mejor.restricciones_violadas) or "ninguna",
    )
    for idx, res in enumerate(res_mejor.restricciones_violadas):
        print(f"{idx+1}: {res}")


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mu = sum(xs) / len(xs)
    return (sum((x - mu) ** 2 for x in xs) / len(xs)) ** 0.5


if __name__ == "__main__":
    main()
