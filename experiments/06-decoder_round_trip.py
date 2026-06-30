# 06-decoder_round_trip.py
"""Test de coherencia y reversibilidad de los decoders del BRKGA.

Verifica que, partiendo de una solución factible producida por
`construir_solucion_heuristica`, ambos codificadores son capaces de:

  1. Convertir el horario en un cromosoma de claves aleatorias.
  2. Decodificar ese cromosoma en una nueva `Solucion`.

Para el codec **bin-midpoint** (`codec.codificar`/`codec.decodificar`)
la decodificación debe reproducir el horario original slot a slot.
Para el **PermutationDecoder** la decodificación NO es inversa exacta
por diseño (el tramo de sectores del cromosoma es ruido); el test
reporta el porcentaje de slots coincidentes como medida de coherencia.

Salidas:
    output_dir/01_inicial.xlsx          <- horario greedy de partida
    output_dir/02_permutation.xlsx      <- horario tras decode permutación
    output_dir/03_bin_midpoint.xlsx     <- horario tras decode bin-midpoint
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

# Ajusta los imports al árbol de tu refactor si difieren.
from atco.io.codec import codificar, decodificar
from atco.algorithms.brkga.decoders.permutations import (
    PermutationDecoder,
    chromosome_from_solucion,
)
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds import construir_solucion_heuristica
from atco.io.excel import _write_solution_xlsx_gantt

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _comparar_horarios(a: Solucion, b: Solucion) -> tuple[int, int]:
    """Cuenta slots de 3 chars idénticos entre dos soluciones.

    Returns:
        ``(iguales, total)``. Si los horarios tienen tamaños distintos se
        usa el mínimo común por fila.
    """
    iguales = total = 0
    for fila_a, fila_b in zip(a.turnos, b.turnos):
        n = min(len(fila_a), len(fila_b))
        for k in range(0, n, 3):
            total += 1
            if fila_a[k : k + 3] == fila_b[k : k + 3]:
                iguales += 1
    return iguales, total


def _imprimir_cromosoma(nombre: str, x) -> None:
    """Resumen compacto de un cromosoma: longitud, head/tail, estadísticos."""
    arr = np.asarray(x, dtype=float)
    print(f"  [{nombre}] longitud = {arr.size}")
    print(f"    head : {np.round(arr[:6], 4).tolist()}")
    print(f"    tail : {np.round(arr[-6:], 4).tolist()}")
    print(
        f"    stats: min={arr.min():.4f}  max={arr.max():.4f}  "
        f"mean={arr.mean():.4f}  std={arr.std():.4f}"
    )


# ---------------------------------------------------------------------------
# Test principal
# ---------------------------------------------------------------------------


def test_codecs_round_trip(
    entrada: Entrada,
    parametros: Parametros,
    output_dir: Path,
) -> None:
    """Comprueba reversibilidad de PermutationDecoder y codec bin-midpoint.

    Genera un horario inicial con la heurística greedy, lo codifica con
    ambos esquemas, decodifica los cromosomas resultantes y reporta el
    porcentaje de slots idénticos en cada caso. Exporta los tres
    horarios como Excel Gantt para inspección visual.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Solución inicial vía heurística greedy --------------------
    print("\n[1] construir_solucion_heuristica()")
    sol_ini = construir_solucion_heuristica(entrada, parametros)
    n_ctrls = len(sol_ini.controladores)
    n_slots = len(entrada.get_sectorizacion())
    n_sectores = len(entrada.get_sectores_abiertos_todo_el_dia())
    print(f"    N = {n_ctrls}  |  T = {n_slots}  |  |S| = {n_sectores}")
    out_ini = output_dir / "01_inicial.xlsx"
    _write_solution_xlsx_gantt(out_ini, sol_ini)
    print(f"    -> {out_ini.name}")

    # ---- 2. PermutationDecoder (no es inverso exacto) ----------------
    print("\n[2] PermutationDecoder")
    permutation_decoder = PermutationDecoder(
        n_controladores=n_ctrls, n_sectores=n_sectores
    )
    permutation_chromosome = chromosome_from_solucion(
        sol_ini,
        n_controladores=n_ctrls,
        longitud_t=n_slots,
        n_sectores=n_sectores,
    )
    _imprimir_cromosoma("permutation", permutation_chromosome)

    sol_perm = permutation_decoder.decode(permutation_chromosome, entrada, parametros)
    out_perm = output_dir / "02_permutation.xlsx"
    _write_solution_xlsx_gantt(out_perm, sol_perm)
    iguales, total = _comparar_horarios(sol_ini, sol_perm)
    pct_perm = 100.0 * iguales / total if total else 0.0
    print(f"    similitud con original: {iguales}/{total} ({pct_perm:.1f} %)")
    print(
        "    NOTA: PermutationDecoder no es inverso exacto por diseño "
        "(tramo de sectores = ruido)."
    )
    print(f"    -> {out_perm.name}")

    # ---- 3. codec bin-midpoint (inverso exacto) ----------------------
    print("\n[3] codec.codificar (bin-midpoint)")
    x_bm, vocabulario = codificar(sol_ini)
    _imprimir_cromosoma("bin-midpoint", x_bm)
    print(f"    vocabulario: {len(vocabulario)} tokens -> {vocabulario}")

    sol_bm = decodificar(
        cromosoma=x_bm,
        vocabulario=vocabulario,
        plantilla=sol_ini,
    )
    out_bm = output_dir / "03_bin_midpoint.xlsx"
    _write_solution_xlsx_gantt(out_bm, sol_bm)
    iguales, total = _comparar_horarios(sol_ini, sol_bm)
    pct_bm = 100.0 * iguales / total if total else 0.0
    marca = "✓ round-trip exacto" if pct_bm == 100.0 else "✗ revisar codec/vocabulario"
    print(f"    similitud con original: {iguales}/{total} ({pct_bm:.1f} %)  {marca}")
    print(f"    -> {out_bm.name}")

    # ---- Resumen ----------------------------------------------------
    print("\n" + "─" * 50)
    print(f"PermutationDecoder : {pct_perm:6.1f} %  (aproximado por diseño)")
    print(f"codec bin-midpoint : {pct_bm:6.1f} %  (debe ser 100 %)")
    print("─" * 50)

    # Aserciones para integración con pytest:
    assert pct_bm == 100.0, "El codec bin-midpoint debería ser inverso exacto."
    assert pct_perm > 0.0, "PermutationDecoder debería producir una solución no vacía."


# ---------------------------------------------------------------------------
# Driver CLI
# ---------------------------------------------------------------------------


def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--case", default="madN_M1")
    parser.add_argument("--out", type=Path, default=Path("results/test_codecs"))
    args = parser.parse_args()

    # Adapta a la API real de tu Parametros/Entrada si difiere de esto:
    parametros = Parametros.from_files(
        args.repo / "resources" / "problemParameters.properties",
        args.repo / "resources" / "options.properties",
    )
    print("leyendo entrada...")
    entrada = Entrada.leer_entrada(
        args.repo, parametros, args.case, "madN_M1-2019-02-12", "Madrid"
    )

    test_codecs_round_trip(entrada, parametros, args.out)

    print("✅ Finalizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
