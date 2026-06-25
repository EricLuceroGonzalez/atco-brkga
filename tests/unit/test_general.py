import logging
from pathlib import Path
from atco.io.solution import load_solution_json
from atco.io.codec import codificar, decodificar
from atco.seeds import construir_solucion_heuristica
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
print(REPO_ROOT / "resources/problemParameters.properties")
p = Parametros.from_files(
    REPO_ROOT / "resources/problemParameters.properties",
    REPO_ROOT / "resources/options.properties",
)
e = Entrada.leer_entrada(REPO_ROOT, p, "madN_M1", "madN_M1-2019-02-12", "Madrid")
# Necesitas una Solucion mínima del dominio; con la del greedy basta:
sol = construir_solucion_heuristica(entrada=e, parametros=p)
x, vocab = codificar(sol)
sol_rec = decodificar(x, vocab, plantilla=sol)
assert sol_rec.get_turnos() == sol.get_turnos(), "round-trip roto"
print(f"OK: |x|={len(x)}, |V|={len(vocab)} -> {vocab}")

# Test para ver los sectores abiertos en el excel
sol = load_solution_json(
    REPO_ROOT / "/results/brkga_warmstart_20260625_172258/cold/" + "best_solution.json"
)
ids_en_solucion = set()
for fila in sol.get_turnos():
    for j in range(0, len(fila), LONGITUD_CADENAS):
        ids_en_solucion.add(fila[j : j + LONGITUD_CADENAS])
log.info(f"  Tokens en best: {sorted(ids_en_solucion - ids_abiertos)}")
log.info(f"  De ellos, fantasmas: {sorted(ids_en_solucion - ids_totales)}")
# import numpy as np

# # 1. Inicializar el generador aleatorio recomendado por NumPy
# rng = np.random.default_rng()

# # 2. Definir los sectores de origen
# random_sector = ["aaa", "bbb", "ccc", "ddd", "eee"]

# # 3. Crear el array de diccionarios (cada 's' es un diccionario plano)
# random_array = [{"id": random_sector[i]} for i in range(5)]
# genes = rng.random(5)
# # 4. Generar 5 números aleatorios flotantes en el intervalo porque 's' es un diccionario, no un objeto
# priority_sectores: dict[str, float] = {
#     s["id"]: float(genes[i]) for i, s in enumerate(random_array)
# }

# print("\nPrioridades asignadas (genes):")
# print(priority_sectores)

# # 6. Ordenar el array en base a las probabilidades de los genes
# # CORRECCIÓN: Reemplazamos la variable indefinida 'a' por 'priority_sectores'
# # Usamos 'reverse=True' para realizar una ordenación de mayor a menor probabilidad de forma limpia
# random_array.sort(key=lambda s: priority_sectores.get(s["id"], 0.0), reverse=True)

# print("\nArray ordenado por prioridad (descendente):")
# print(random_array)
