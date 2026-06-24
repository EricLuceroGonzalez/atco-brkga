# experiments/03_brkga_asimetria.py
import random
from pathlib import Path
import numpy as np

from atco.algorithms.brkga import BRKGAConfig, BRKGAEngine, StoppingCriteria
from atco.algorithms.brkga.decoders import PermutationDecoder
from atco.domain.models import VentanaDisponibilidad
from atco.fitness import FitnessConfig
from atco.io.logging_setup import setup_logging
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


def main() -> None:
    setup_logging(level="INFO")
    REPO_ROOT = Path(__file__).resolve().parent.parent
    p = Parametros.from_files(
        REPO_ROOT / "resources/problemParameters.properties",
        REPO_ROOT / "resources/options.properties",
    )
    e = Entrada.leer_entrada(REPO_ROOT, p, "madN_M1", "madN_M1-2019-02-12", "Madrid")

    # ── ASIMETRÍA SINTÉTICA ──────────────────────────────────────
    # 1/3 de los ATCos empiezan tarde, 1/3 acaban pronto, 1/3 día completo
    for i, c in enumerate(e.get_controladores()):
        if i % 3 == 0:
            c.disponibilidad = VentanaDisponibilidad(slot_inicio_disponibilidad=24)
        elif i % 3 == 1:
            c.disponibilidad = VentanaDisponibilidad(slot_fin_disponibilidad=75)
        # i % 3 == 2: ventana completa por defecto

    n = len(e.get_controladores())
    s = len(e.get_lista_sectores())
    decoder = PermutationDecoder(n_controladores=n, n_sectores=s)
    config = BRKGAConfig(
        population_size=100,
        elite_fraction=0.20,
        mutant_fraction=0.30,  # más exploración
        rho_elite=0.60,  # menos sesgo a élite
        seed=42,
        stopping=StoppingCriteria(
            max_generations=100,
            max_seconds=120.0,
            stagnation_generations=15,
            max_evaluations=None,
        ),
    )
    engine = BRKGAEngine(config, FitnessConfig(), decoder)
    result = engine.run(e, p)

    print(f"\nSemilla : {result.seed_fitness:.6f}")
    print(f"Mejor  : {result.best_individual.fitness:.6f}")
    print(f"Mejora : {result.mejora_relativa*100:.2f}%")


if __name__ == "__main__":
    main()
