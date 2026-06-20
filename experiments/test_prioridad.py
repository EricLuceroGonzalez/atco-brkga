"""Diagnóstico: ¿el parámetro `prioridad` afecta al greedy?"""

import random
from pathlib import Path

import numpy as np

from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds import construir_solucion_heuristica

REPO_ROOT = Path(__file__).resolve().parent.parent
parametros = Parametros.from_files(
    "resources/problemParameters.properties",
    "resources/options.properties",
)
entrada = Entrada.leer_entrada(
    repo=REPO_ROOT,
    parametros=parametros,
    path="madN_M1",
    entrada_id="madN_M1-2019-02-12",
    entorno="Madrid",
)

n = len(entrada.get_controladores())
print(f"N controladores = {n}")

# Dos cromosomas radicalmente distintos
prioridad_A = [1.0] * n  # todos prioridad máxima
prioridad_B = [0.0] * n  # todos prioridad mínima
prioridad_C = list(np.linspace(0, 1, n))  # gradiente
prioridad_D = list(np.linspace(1, 0, n))  # gradiente invertido

for nombre, p in [("A", prioridad_A), ("C", prioridad_C), ("D", prioridad_D)]:
    sol = construir_solucion_heuristica(
        entrada,
        parametros,
        rng=random.Random(0),
        prioridad=p,
    )
    print(f"prioridad={nombre}: turnos[0][:30] = {sol.turnos[0][:30]!r}")
    print(
        f"            slots_trabajados[:5] = {[c.slots_trabajados for c in sol.controladores[:5]]}"
    )
