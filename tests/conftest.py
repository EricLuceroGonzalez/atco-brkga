"""Fixtures compartidos entre tests del proyecto."""

from __future__ import annotations

from pathlib import Path

import pytest

from atco.domain.models import Controlador, Propiedades, Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

# ----- Fixtures de paths --------------------------------------------------- #


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Raíz del repo (donde viven entrada/ y resources/)."""
    return Path(__file__).resolve().parent.parent


# ----- Fixtures de parámetros (mock) -------------------------------------- #


@pytest.fixture(scope="session")
def parametros_reales(repo_root: Path) -> Parametros:
    return Parametros.from_files(
        repo_root / "resources" / "problemParameters.properties",
        repo_root / "resources" / "options.properties",
    )


@pytest.fixture(scope="session")
def entrada_madN_M1(repo_root: Path, parametros_reales: Parametros) -> Entrada:
    return Entrada.leer_entrada(
        repo_root,
        parametros_reales,
        "madN_M1",
        "madN_M1-2019-02-12",
        "Madrid",
        estudio_estadillos=False,
    )


class _FakeParametros:
    """Stub mínimo de Parametros para tests que no quieren cargar properties."""

    def get_tamano_slots(self) -> int:
        return 5

    def get_porcent_descanso_noche(self) -> float:
        return 0.15

    def get_porcent_descanso_dia(self) -> float:
        return 0.10


@pytest.fixture
def fake_parametros() -> _FakeParametros:
    """Stub con los getters mínimos que Turno necesita en __post_init__."""
    return _FakeParametros()


# ----- Fixtures de modelos del dominio ------------------------------------ #


@pytest.fixture
def controlador_basico() -> Controlador:
    """Controlador típico de Madrid (núcleo Ruta 1, turno MC, CON-acreditado)."""
    return Controlador(
        id=1,
        turno="MC",
        nucleo="Madrid Ruta 1",
        ptd=False,
        con=True,
        baja_alta=Propiedades.ALTA,
        slot_alta=0,
        slot_baja=0,
    )


@pytest.fixture
def solucion_basica(controlador_basico: Controlador) -> Solucion:
    """Solucion mínima con 1 controlador y 1 fila de turnos."""
    return Solucion(
        turnos=["AAA111AAB"],
        controladores=[controlador_basico],
        longdescansos=0,
    )
