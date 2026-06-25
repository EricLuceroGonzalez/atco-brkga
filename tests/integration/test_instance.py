"""Smoke test del cargador Entrada.leer_entrada.

Carga el caso `madN_M1` (que vive en entrada/Casos/) y verifica
invariantes mínimas. Si este test pasa, sabemos que toda la cadena
de parsing CSV -> dataclasses sobrevivió a la migración.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atco.domain.models import Solucion, Turno
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


@pytest.fixture(scope="module")
def parametros_reales(repo_root: Path) -> Parametros:
    return Parametros.from_files(
        repo_root / "resources" / "problemParameters.properties",
        repo_root / "resources" / "options.properties",
    )


@pytest.fixture(scope="module")
def entrada_caso(repo_root: Path, parametros_reales: Parametros) -> Entrada:
    return Entrada.leer_entrada(
        repo_root,
        parametros_reales,
        "madN_M1",
        "madN_M1-2019-02-12",
        "Madrid",
        estudio_estadillos=False,
    )


def test_leer_entrada_caso_carga_sin_errores(entrada_caso: Entrada) -> None:
    """La carga del caso produce una Entrada con sus invariantes mínimas."""
    # Hay al menos un controlador en la plantilla.
    assert len(entrada_caso.get_controladores()) >= 1

    # La sectorización es una lista no vacía de sets de IDs de sector.
    sec = entrada_caso.get_sectorizacion()
    assert len(sec) >= 1
    assert all(isinstance(slot, set) for slot in sec)

    # La distribución inicial existe y tiene la forma esperada.
    distribucion = entrada_caso.get_distribucion_inicial()
    assert isinstance(distribucion, Solucion)
    assert len(distribucion.get_turnos()) >= 1

    # El turno del escenario está construido (las ventanas TL/TC son tuplas válidas).
    turno = entrada_caso.get_turno()
    assert isinstance(turno, Turno)
    assert turno.get_tl()[1] > turno.get_tl()[0]  # fin > inicio
