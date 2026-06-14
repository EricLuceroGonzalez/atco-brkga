"""Tests del generador heurístico (``atco.seeds.greedy``).

Comprueba las invariantes del contrato §2.2 del documento de diseño
(``docs/thesis/notes-design.md``) y los requisitos de reproducibilidad
y diversidad entre llamadas con semillas distintas.
"""

from __future__ import annotations

import random

import pytest

from atco.domain.constants import LONGITUD_CADENAS, STRING_DESCANSO, STRING_NO_TURNO
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros
from atco.seeds import construir_solucion_heuristica

# =============================================================================
# Invariantes operativas (§2.2 del documento de diseño)
# =============================================================================


def test_generador_cubre_toda_la_sectorizacion(
    entrada: Entrada,
    parametros: Parametros,
) -> None:
    """Cada sector abierto en cada slot debe tener al menos un ATCo asignado."""
    sol = construir_solucion_heuristica(entrada, parametros, rng=random.Random(0))
    sin_cubrir: list[tuple[int, str]] = []
    sectorizacion = entrada.get_sectorizacion()
    turnos = sol.get_turnos()
    for t, sectores_abiertos in enumerate(sectorizacion):
        for sigma in sectores_abiertos:
            asignaciones = sum(
                1
                for turno in turnos
                if turno[t * LONGITUD_CADENAS : (t + 1) * LONGITUD_CADENAS].lower()
                == sigma.lower()
            )
            if asignaciones < 1:
                sin_cubrir.append((t, sigma))
    assert not sin_cubrir, f"Sectores sin cubrir: {sin_cubrir[:5]}..."


def test_generador_respeta_licencia_con(
    entrada: Entrada,
    parametros: Parametros,
) -> None:
    """Un ATCo con flag CON solo trabaja sectores marcados como ruta."""
    sol = construir_solucion_heuristica(entrada, parametros, rng=random.Random(0))
    no_ruta_ids = {
        s.id.lower() for s in entrada.get_lista_sectores_abiertos() if not s.ruta
    }
    for controlador in sol.get_controladores():
        if not controlador.con:
            continue
        turno = sol.get_turnos()[controlador.turno_asignado]
        for i in range(0, len(turno), LONGITUD_CADENAS):
            token = turno[i : i + LONGITUD_CADENAS]
            if token in {STRING_DESCANSO, STRING_NO_TURNO}:
                continue
            assert token.lower() not in no_ruta_ids, (
                f"ATCo CON id={controlador.id} asignado a sector no-ruta " f"{token!r}"
            )


def test_generador_respeta_ventana_de_turno(
    entrada: Entrada,
    parametros: Parametros,
) -> None:
    """Fuera de la ventana de turno, las celdas deben ser STRING_NO_TURNO."""
    sol = construir_solucion_heuristica(entrada, parametros, rng=random.Random(0))
    turno_escenario = entrada.get_turno()
    ventana_corta = turno_escenario.get_tc()
    ventana_larga = turno_escenario.get_tl()

    for controlador in sol.get_controladores():
        es_corto = controlador.turno.upper() in {"TC", "MC"}
        ventana = ventana_corta if es_corto else ventana_larga
        turno = sol.get_turnos()[controlador.turno_asignado]
        n_slots = len(turno) // LONGITUD_CADENAS
        for t in range(n_slots):
            token = turno[t * LONGITUD_CADENAS : (t + 1) * LONGITUD_CADENAS]
            dentro = ventana[0] <= t < ventana[1]
            if not dentro:
                assert token == STRING_NO_TURNO, (
                    f"ATCo id={controlador.id} con token {token!r} fuera "
                    f"de su ventana en slot {t}"
                )


def test_generador_publica_biyeccion_atco_turno(
    entrada: Entrada,
    parametros: Parametros,
) -> None:
    """Cada ATCo apunta a su propia fila; todas las filas tienen dueño."""
    sol = construir_solucion_heuristica(entrada, parametros, rng=random.Random(0))
    asignaciones = [c.turno_asignado for c in sol.get_controladores()]
    assert len(set(asignaciones)) == len(asignaciones), "Hay dos ATCos en la misma fila"
    assert set(asignaciones) == set(range(len(sol.get_turnos())))


def test_generador_publica_slots_trabajados_consistente(
    entrada: Entrada,
    parametros: Parametros,
) -> None:
    """`slots_trabajados` coincide con el conteo real de la matriz."""
    sol = construir_solucion_heuristica(entrada, parametros, rng=random.Random(0))
    for controlador in sol.get_controladores():
        turno = sol.get_turnos()[controlador.turno_asignado]
        trabajados = sum(
            1
            for i in range(0, len(turno), LONGITUD_CADENAS)
            if turno[i : i + LONGITUD_CADENAS] not in {STRING_DESCANSO, STRING_NO_TURNO}
        )
        assert controlador.slots_trabajados == trabajados


# =============================================================================
# Reproducibilidad y diversidad
# =============================================================================


def test_generador_es_diverso_entre_llamadas(
    entrada: Entrada,
    parametros: Parametros,
) -> None:
    """Dos llamadas con semillas distintas producen soluciones distintas."""
    sol_a = construir_solucion_heuristica(entrada, parametros, rng=random.Random(1))
    sol_b = construir_solucion_heuristica(entrada, parametros, rng=random.Random(2))
    assert sol_a.get_turnos() != sol_b.get_turnos()


def test_generador_es_reproducible_con_misma_semilla(
    entrada: Entrada,
    parametros: Parametros,
) -> None:
    """Misma semilla, misma solución exacta."""
    sol_a = construir_solucion_heuristica(entrada, parametros, rng=random.Random(42))
    sol_b = construir_solucion_heuristica(entrada, parametros, rng=random.Random(42))
    assert sol_a.get_turnos() == sol_b.get_turnos()


# =============================================================================
# Casos límite
# =============================================================================


def test_generador_falla_con_controladores_vacios(
    entrada: Entrada,
    parametros: Parametros,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin ATCos no se puede construir solución; debe lanzar ValueError."""
    monkeypatch.setattr(entrada, "get_controladores", lambda: [])
    with pytest.raises(ValueError, match="controladores"):
        construir_solucion_heuristica(entrada, parametros, rng=random.Random(0))
