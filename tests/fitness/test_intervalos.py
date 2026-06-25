"""Tests unitarios de los helpers de intervalos de `atco.fitness.components`.
Ejecutar: pipenv run pytest tests/fitness/test_intervalos.py -v
"""

from __future__ import annotations

import pytest

from atco.fitness.components import _intervalos_misma_posicion, _intervalos_trabajo

# ============================================================================
# _intervalos_misma_posicion
# ============================================================================


class TestIntervalosMismaPosicion:
    def test_cadena_vacia(self) -> None:
        assert _intervalos_misma_posicion("", 0) == []

    def test_todo_descanso(self) -> None:
        assert _intervalos_misma_posicion("111" * 5, 5) == []

    def test_todo_no_turno(self) -> None:
        assert _intervalos_misma_posicion("000" * 5, 5) == []

    def test_un_solo_intervalo_unico_token(self) -> None:
        # 4 slots seguidos del mismo (sector + posición)
        assert _intervalos_misma_posicion("aaa" * 4, 4) == [(0, 4, "aaa")]

    def test_dos_tokens_distintos_contiguos(self) -> None:
        # aaa, aaa, aab, aab -> cambio de sector corta el intervalo
        cadena = "aaa" "aaa" "aab" "aab"
        assert _intervalos_misma_posicion(cadena, 4) == [
            (0, 2, "aaa"),
            (2, 4, "aab"),
        ]

    def test_descanso_corta_intervalo(self) -> None:
        # aaa, 111, aaa -> dos intervalos del mismo token con hueco
        cadena = "aaa" "111" "aaa"
        assert _intervalos_misma_posicion(cadena, 3) == [
            (0, 1, "aaa"),
            (2, 3, "aaa"),
        ]

    def test_no_turno_corta_intervalo(self) -> None:
        # aaa, 000, aaa -> mismo comportamiento que descanso
        cadena = "aaa" "000" "aaa"
        assert _intervalos_misma_posicion(cadena, 3) == [
            (0, 1, "aaa"),
            (2, 3, "aaa"),
        ]

    def test_no_turno_borde_inicio_y_fin(self) -> None:
        # 000, aaa, aaa, 000 -> un único intervalo "interior"
        cadena = "000" "aaa" "aaa" "000"
        assert _intervalos_misma_posicion(cadena, 4) == [(1, 3, "aaa")]

    def test_ej_y_pl_se_consideran_tokens_distintos(self) -> None:
        # aaa (PL), AAA (EJ) -> mismo sector pero distinto rol corta
        cadena = "aaa" "AAA" "aaa"
        assert _intervalos_misma_posicion(cadena, 3) == [
            (0, 1, "aaa"),
            (1, 2, "AAA"),
            (2, 3, "aaa"),
        ]

    def test_caso_compuesto_de_docstring(self) -> None:
        # aaa, aaa, aab, 111, aaa -> tres intervalos (dos de aaa, uno de aab)
        cadena = "aaa" "aaa" "aab" "111" "aaa"
        assert _intervalos_misma_posicion(cadena, 5) == [
            (0, 2, "aaa"),
            (2, 3, "aab"),
            (4, 5, "aaa"),
        ]

    def test_intervalo_se_cierra_al_final_de_la_cadena(self) -> None:
        # Asegura que no se pierda un intervalo abierto en el último slot
        cadena = "111" "aaa" "aaa"
        assert _intervalos_misma_posicion(cadena, 3) == [(1, 3, "aaa")]


# ============================================================================
# _intervalos_trabajo
# ============================================================================


class TestIntervalosTrabajo:
    def test_cadena_vacia(self) -> None:
        assert _intervalos_trabajo("", 0) == []

    def test_todo_descanso(self) -> None:
        assert _intervalos_trabajo("111" * 5, 5) == []

    def test_todo_no_turno(self) -> None:
        assert _intervalos_trabajo("000" * 5, 5) == []

    def test_un_intervalo_unico_token(self) -> None:
        assert _intervalos_trabajo("aaa" * 4, 4) == [(0, 4)]

    def test_cambios_de_sector_no_cortan(self) -> None:
        # aaa, aab, aac -> un solo intervalo de trabajo de 3 slots
        cadena = "aaa" "aab" "aac"
        assert _intervalos_trabajo(cadena, 3) == [(0, 3)]

    def test_cambios_ej_pl_no_cortan(self) -> None:
        # aaa (PL), AAA (EJ), aaa (PL) -> un solo intervalo de trabajo
        cadena = "aaa" "AAA" "aaa"
        assert _intervalos_trabajo(cadena, 3) == [(0, 3)]

    def test_descanso_corta(self) -> None:
        cadena = "aaa" "111" "aaa"
        assert _intervalos_trabajo(cadena, 3) == [(0, 1), (2, 3)]

    def test_no_turno_corta(self) -> None:
        cadena = "aaa" "000" "aaa"
        assert _intervalos_trabajo(cadena, 3) == [(0, 1), (2, 3)]

    def test_no_turno_borde(self) -> None:
        # 000, aaa, aaa, 000 -> un intervalo interior de 2 slots
        cadena = "000" "aaa" "aaa" "000"
        assert _intervalos_trabajo(cadena, 4) == [(1, 3)]

    def test_caso_compuesto_de_docstring(self) -> None:
        # aaa, aaa, aab, 111, aab -> dos intervalos: 3 slots y 1 slot
        cadena = "aaa" "aaa" "aab" "111" "aab"
        assert _intervalos_trabajo(cadena, 5) == [(0, 3), (4, 5)]

    def test_intervalo_se_cierra_al_final_de_la_cadena(self) -> None:
        cadena = "111" "aaa" "aaa"
        assert _intervalos_trabajo(cadena, 3) == [(1, 3)]


# ============================================================================
# Propiedades cruzadas (sanity)
# ============================================================================


class TestPropiedadesCruzadas:
    """Invariantes que ambos helpers deberían cumplir simultáneamente."""

    @pytest.mark.parametrize(
        "cadena,T",
        [
            ("aaa" * 10, 10),
            ("aaaaab111aaaAAA", 5),
            ("000aaa111AAB000aaa", 6),
            ("111" * 3 + "AAA" * 3 + "111" * 3, 9),
        ],
    )
    def test_intervalos_misma_posicion_son_subdivision_de_trabajo(
        self, cadena: str, T: int
    ) -> None:
        """Cada intervalo de misma-posición está contenido en algún intervalo de trabajo."""
        misma_pos = _intervalos_misma_posicion(cadena, T)
        trabajo = _intervalos_trabajo(cadena, T)

        for ini_mp, fin_mp, _tok in misma_pos:
            assert any(
                ini_t <= ini_mp and fin_mp <= fin_t for ini_t, fin_t in trabajo
            ), f"Intervalo misma-pos ({ini_mp}, {fin_mp}) no cabe en ningún trabajo"

    @pytest.mark.parametrize(
        "cadena,T",
        [
            ("aaa" * 10, 10),
            ("aaaaab111aaaAAA", 5),
            ("000aaa111AAB000aaa", 6),
        ],
    )
    def test_suma_duraciones_misma_posicion_igual_trabajo(
        self, cadena: str, T: int
    ) -> None:
        """La suma de duraciones (en slots) de misma-pos == suma de duraciones de trabajo."""
        suma_mp = sum(
            fin - ini for ini, fin, _ in _intervalos_misma_posicion(cadena, T)
        )
        suma_tr = sum(fin - ini for ini, fin in _intervalos_trabajo(cadena, T))
        assert suma_mp == suma_tr
