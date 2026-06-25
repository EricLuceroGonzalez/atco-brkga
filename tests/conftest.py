"""Fixtures compartidos entre tests del proyecto."""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
import pytest

from atco.domain.models import Controlador, Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

# ----- Fixtures de paths --------------------------------------------------- #


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Raíz del repo (donde viven entrada/ y resources/)."""
    return Path(__file__).resolve().parent.parent


# ----- Fixtures de parámetros (mock) -------------------------------------- #


@pytest.fixture(scope="session")
def parametros(repo_root: Path) -> Parametros:
    return Parametros.from_files(
        repo_root / "resources" / "problemParameters.properties",
        repo_root / "resources" / "options.properties",
    )


@pytest.fixture(scope="session")
def entrada_mad_n_m1(repo_root: Path, parametros: Parametros) -> Entrada:
    return Entrada.leer_entrada(
        repo_root,
        parametros,
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
    )


@pytest.fixture
def solucion_basica(controlador_basico: Controlador) -> Solucion:
    """Solucion mínima con 1 controlador y 1 fila de turnos."""
    return Solucion(
        turnos=["AAA111AAB"],
        controladores=[controlador_basico],
        longdescansos=0,
    )


# ============================================================================
# Mocks minimalistas del dominio
# ============================================================================


@dataclass
class _SectorMock:
    """Sector mínimo: sólo `id` y, opcionalmente, sus elementales."""

    id: str
    ruta: bool = False
    sectores_elementales: list[str] = field(default_factory=list)


@dataclass
class _TurnoMock:
    """Mock de Turno con ventanas TC y TL fijas."""

    tc: list[int] = field(default_factory=lambda: [0, 99])
    tl: list[int] = field(default_factory=lambda: [0, 99])
    nombre: str = "Manana"

    def get_tc(self) -> list[int]:
        return self.tc

    def get_tl(self) -> list[int]:
        return self.tl

    def getTc(self) -> list[int]:
        return self.tc  # alias por si tu codigo

    def getTl(self) -> list[int]:
        return self.tl  # mezcla snake/camelCase

    def getNombre(self) -> str:
        return self.nombre


@dataclass
class _NucleoMock:
    nombre: str
    sectores: list[_SectorMock] = field(default_factory=list)

    def get_sectores(self) -> list[_SectorMock]:
        return self.sectores


@dataclass
class _EntradaMock:
    """Entrada mínima parametrizable por slot."""

    sectores_por_slot: dict[int, list[_SectorMock]] = field(default_factory=dict)
    lista_sectores: list[_SectorMock] = field(default_factory=list)
    nucleos_abiertos: list[_NucleoMock] = field(default_factory=list)
    turno: _TurnoMock = field(default_factory=_TurnoMock)

    # Distintos nombres porque tu código original mezcla convenciones.
    def get_sectores_abiertos_en(self, t: int) -> list[_SectorMock]:
        return self.sectores_por_slot.get(t, [])

    def get_lista_sectores(self) -> list[_SectorMock]:
        return self.lista_sectores

    def get_nucleos_abiertos(self) -> list[_NucleoMock]:
        return self.nucleos_abiertos


@dataclass
class _ParametrosMock:
    """Parametros mínimos con los umbrales más usados."""

    tamano_slots: int = 5
    tiempo_trab_max: int = 120
    tiempo_trab_min: int = 15
    tiempo_trab_opt: int = 90
    tiempo_des_min: int = 30
    tiempo_des_por_turno: int = 30
    tiempo_pos_opt: int = 45
    tiempo_pos_min: int = 15
    num_sctrs_max: int = 4


@dataclass
class _SolucionMock:
    """Solucion mínima: sólo `turnos` y `controladores`."""

    turnos: list[str] = field(default_factory=list)
    controladores: list = field(default_factory=list)
    longdescansos: int = 0


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def entrada_min() -> _EntradaMock:
    """Entrada vacía: sin sectores abiertos, sin núcleos."""
    return _EntradaMock()


@pytest.fixture
def parametros_min() -> _ParametrosMock:
    """Parametros con valores típicos del caso `madN_M1`."""
    return _ParametrosMock()


@pytest.fixture
def solucion_min() -> _SolucionMock:
    """Solucion vacía con 1 controlador descansando en 10 slots."""
    return _SolucionMock(turnos=["111" * 10])


# ============================================================================
# Factories útiles dentro de tests
# ============================================================================


@pytest.fixture
def make_sector():
    """Devuelve una función para fabricar sectores ad-hoc."""

    def _make(sid: str, *, ruta: bool = False, elementales: list[str] | None = None):
        return _SectorMock(id=sid, ruta=ruta, sectores_elementales=elementales or [])

    return _make


@pytest.fixture
def make_solucion():
    """Devuelve una función para fabricar Soluciones con N filas y T slots de descanso."""

    def _make(turnos: list[str], controladores: list | None = None):
        return _SolucionMock(turnos=turnos, controladores=controladores or [])

    return _make
