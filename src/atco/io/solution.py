"""Lectura y escritura de objetos `Solucion`.

Centraliza todas las funciones de E/S para soluciones, separándolas del
punto de entrada CLI (`__main__.py`).

Formatos soportados:
  - TXT:    `write_solution_txt`        (humano, parseable)
  - XLSX:   `write_solution_xlsx`       (auditoría tabular)
  - XLSX:   `write_solution_xlsx_gantt` (visualización tipo Gantt con colores)
  - Pickle: `write_solution_pickle`     +  `load_solution_pickle`
  - JSON:   `write_solution_json`       +  `load_solution_json`

Las versiones Pickle/JSON son ideales para sembrar el BRKGA con una
solución de alta calidad obtenida en una corrida previa (p. ej. el
mejor individuo de SA).
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from atco.domain.models import Controlador, Propiedades, Solucion

# =============================================================================
# Pickle (round-trip exacto, formato binario)
# =============================================================================


def write_solution_pickle(path: Path, solution: Solucion) -> None:
    """Serializa una `Solucion` completa (turnos + controladores + fitness)."""
    with open(path, "wb") as f:
        pickle.dump(solution, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_solution_pickle(path: Path) -> Solucion:
    """Recarga una `Solucion` previamente persistida con `write_solution_pickle`."""
    with open(path, "rb") as f:
        return pickle.load(f)


# =============================================================================
# JSON (portable, inspección humana)
# =============================================================================


def write_solution_json(path: Path, solution: Solucion) -> None:
    """Serializa una `Solucion` en JSON (incluye fitness_score si está presente)."""
    data = {
        "turnos": list(solution.getTurnos()),
        "longdescansos": solution.getLongdescansos(),
        "fitness_score": getattr(solution, "fitness_score", None),
        "fitness_details": getattr(solution, "fitness_details", None),
        "controladores": [
            {
                "id": c.id,
                "turno": c.turno,
                "nucleo": c.nucleo,
                "ptd": c.ptd,
                "con": c.con,
                "turno_asignado": c.turno_asignado,
                "turno_noche": c.turno_noche,
                "slots_trabajados": c.slots_trabajados,
            }
            for c in solution.getControladores()
        ],
    }
    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_solution_json(path: Path) -> Solucion:
    """Recarga una `Solucion` previamente persistida con `write_solution_json`."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ctrls = [
        Controlador(
            d["id"],
            d["turno"],
            d["nucleo"],
            d["ptd"],
            d["con"],
            d["turno_asignado"],
            d["turno_noche"],
            d["slots_trabajados"],
        )
        for d in data["controladores"]
    ]
    sol = Solucion(data["turnos"], ctrls, data["longdescansos"])
    if data.get("fitness_score") is not None:
        sol.fitness_score = data["fitness_score"]
        sol.fitness_details = data.get("fitness_details") or []
    return sol
