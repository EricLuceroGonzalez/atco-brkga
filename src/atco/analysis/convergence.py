"""Carga, guarda y grafica el historial de convergencia del BRKGA."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atco.algorithms.brkga import ConvergenceRecord, RunResult


def dump_run_result(result: RunResult, path: Path) -> None:
    """Vuelca el resultado de una corrida a JSON.

    Estructura:
        {
            "meta": {...},
            "history": [{generation, best, avg, worst, ...}, ...]
        }

    Args:
        result: Resultado de `BRKGAEngine.run`.
        path: Ruta del archivo JSON destino. Se crea el directorio padre.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "meta": {
            "seed_fitness": result.seed_fitness,
            "best_fitness": result.best_individual.fitness,
            "mejora_relativa": result.mejora_relativa,
            "elapsed_seconds": result.elapsed_seconds,
            "generations": result.generations,
            "evaluations": result.evaluations,
            "best_componentes": result.best_fitness_result.componentes,
            "best_restricciones_violadas": result.best_fitness_result.restricciones_violadas,
        },
        "history": [asdict(rec) for rec in result.history],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_run_result(path: Path) -> tuple[dict, list[dict]]:
    """Carga un JSON de convergencia y devuelve `(meta, history)`.

    Args:
        path: Ruta al JSON producido por `dump_run_result`.

    Returns:
        Tupla `(meta, history)` con el dict de metadatos y la lista de
        records crudos como dicts.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["meta"], data["history"]


def plot_convergence(
    history: list[ConvergenceRecord] | list[dict],
    out_path: Path,
    title: str | None = None,
) -> None:
    """Grafica best/avg/worst fitness vs generación.

    Acepta una lista de `ConvergenceRecord` (objetos) o lista de dicts
    (cargados desde JSON).

    Args:
        history: Lista de records de convergencia.
        out_path: PNG destino.
        title: Título opcional para la figura.
    """
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gens = [_get(r, "generation") for r in history]
    best = [_get(r, "best_fitness") for r in history]
    avg = [_get(r, "avg_fitness") for r in history]
    worst = [_get(r, "worst_fitness") for r in history]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(gens, best, label="best", linewidth=2)
    ax.plot(gens, avg, label="avg", linestyle="--")
    ax.plot(gens, worst, label="worst", linestyle=":")
    ax.set_xlabel("generación")
    ax.set_ylabel("fitness")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    if title:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def _get(record: object, key: str) -> object:
    """Accede a un campo tanto si `record` es dict como si es dataclass."""
    if isinstance(record, dict):
        return record[key]
    return getattr(record, key)
