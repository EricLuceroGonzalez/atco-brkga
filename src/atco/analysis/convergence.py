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


def plot_components_evolution(
    history: list[ConvergenceRecord] | list[dict],
    out_path: Path,
    title: str | None = None,
) -> None:
    """Evolución de cada componente del fitness del mejor individuo por generación.

    Útil para diagnosticar qué término del fitness ponderado está
    dominando y cuál ya está minimizado. Si una curva se aplana en
    valor bajo mientras otra sigue alta, el motor está atacando lo
    primero pero no consigue mover lo segundo.

    Args:
        history: Lista de records de convergencia.
        out_path: PNG destino.
        title: Título opcional.
    """
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gens = [_get(r, "generation") for r in history]
    series: dict[str, list[float]] = {}
    for r in history:
        comps = _get(r, "best_components")
        if not comps:
            continue
        for k, v in comps.items():
            series.setdefault(k, []).append(v)

    if not series:
        raise ValueError(
            "No hay datos de componentes en el historial. Verifica que el "
            "engine esté poblando `best_components`."
        )

    fig, ax = plt.subplots(figsize=(10, 6))
    for nombre, valores in series.items():
        ax.plot(gens[: len(valores)], valores, label=nombre, linewidth=1.7)
    ax.set_xlabel("generación")
    ax.set_ylabel("valor del componente (best individual)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    if title:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_objetivos_evolution(history, out_path, title=None):
    import matplotlib.pyplot as plt

    nombres_orden = [
        "obj1_condiciones_laborales",
        "obj2_estadillos",
        "obj3_descansos_acred",
        "obj4_balance",
    ]
    gens = [_get(r, "generation") for r in history]
    series = {n: [] for n in nombres_orden}
    for r in history:
        objs = _get(r, "best_objetivos") or {}
        for n in nombres_orden:
            series[n].append(objs.get(n, float("nan")))

    fig, ax = plt.subplots(figsize=(10, 5))
    for n in nombres_orden:
        ax.plot(gens, series[n], label=n, lw=2)
    ax.set_xlabel("generación")
    ax.set_ylabel("valor del objetivo ∈ [0, 1]")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    if title:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_violaciones_por_generacion(
    history: list[ConvergenceRecord] | list[dict],
    out_path: Path,
    title: str | None = None,
) -> None:
    """Número de restricciones violadas por el best individual a lo largo del run.

    Es una visión de "cuántas reglas operativas seguimos rompiendo"
    a medida que evolucionan las generaciones. Idealmente baja monótonamente.

    Args:
        history: Lista de records de convergencia.
        out_path: PNG destino.
        title: Título opcional.
    """
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gens: list[int] = []
    n_violadas: list[int] = []
    for r in history:
        violaciones = _get(r, "best_restricciones_violadas")
        if violaciones is None:
            continue
        gens.append(_get(r, "generation"))
        n_violadas.append(len(violaciones))

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.step(gens, n_violadas, where="post", linewidth=2, color="tab:red")
    ax.set_xlabel("generación")
    ax.set_ylabel("nº de restricciones violadas por el mejor")
    ax.grid(True, alpha=0.3)
    if title:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_violaciones_final_breakdown(
    restricciones_violadas: list[str],
    out_path: Path,
    title: str | None = None,
) -> None:
    """Bar chart de qué restricciones específicas viola la solución final.

    Args:
        restricciones_violadas: Lista de nombres de restricciones violadas
            (campo `result.best_fitness_result.restricciones_violadas`).
        out_path: PNG destino.
        title: Título opcional.
    """
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not restricciones_violadas:
        # Crea un gráfico vacío con mensaje
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "Sin restricciones violadas",
            ha="center",
            va="center",
            fontsize=14,
            color="green",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        if title:
            ax.set_title(title)
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        return

    fig, ax = plt.subplots(figsize=(9, max(4, 0.4 * len(restricciones_violadas))))
    y_pos = list(range(len(restricciones_violadas)))
    ax.barh(y_pos, [1] * len(restricciones_violadas), color="tab:red")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(restricciones_violadas, fontsize=9)
    ax.set_xlabel("(violada)")
    ax.set_xticks([])
    if title:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_violaciones_magnitud(history, out_path, title=None):
    import matplotlib.pyplot as plt

    gens = [_get(r, "generation") for r in history]
    series: dict[str, list[float]] = {}
    for r in history:
        viol = _get(r, "best_violaciones") or {}
        for n, v in viol.items():
            series.setdefault(n, []).append(v)

    if not series:
        return

    fig, ax = plt.subplots(figsize=(11, 6))
    for nombre, valores in series.items():
        if max(valores) > 0:
            ax.plot(gens[: len(valores)], valores, label=nombre, lw=1.5)
    ax.set_xlabel("generación")
    ax.set_ylabel("magnitud de violación (cuenta cruda)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    if title:
        ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_r_evolution(history, out_path, title=None):
    """r ponderada y f_factibilidad por generación."""
    import matplotlib.pyplot as plt

    gens = [_get(r, "generation") for r in history]
    r_vals = [_get(r, "best_r") for r in history]
    f_fact = [_get(r, "best_f_factibilidad") for r in history]
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(gens, r_vals, "r-", lw=2, label="r (suma ponderada)")
    ax1.set_xlabel("generación")
    ax1.set_ylabel("r", color="r")
    ax2 = ax1.twinx()
    ax2.plot(gens, f_fact, "g-", lw=2, label="f_factibilidad")
    ax2.set_ylabel("f_factibilidad ∈ [0, 1]", color="g")
    if title:
        ax1.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
