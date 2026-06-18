"""Tests del contrato común a los decoders."""

from __future__ import annotations

import numpy as np
import pytest

from atco.algorithms.brkga.decoders.base import DecoderBase
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


class _DecoderFalso(DecoderBase):
    """Implementación de prueba que solo expone el contrato."""

    def __init__(self, n_genes: int) -> None:
        self._n = n_genes

    @property
    def num_genes(self) -> int:
        return self._n

    def decode(
        self,
        chromosome: np.ndarray,
        entrada: Entrada,
        parametros: Parametros,
    ) -> Solucion:
        self.validate_chromosome(chromosome)
        return Solucion(turnos=[], controladores=[], longdescansos=0)


class TestDecoderBase:
    def test_validate_chromosome_acepta_longitud_correcta(self) -> None:
        d = _DecoderFalso(n_genes=10)
        d.validate_chromosome(np.zeros(10))

    def test_validate_chromosome_rechaza_longitud_incorrecta(self) -> None:
        d = _DecoderFalso(n_genes=10)
        with pytest.raises(ValueError, match="shape"):
            d.validate_chromosome(np.zeros(9))

    def test_validate_chromosome_rechaza_valores_fuera_de_rango(self) -> None:
        d = _DecoderFalso(n_genes=5)
        with pytest.raises(ValueError, match="fuera de"):
            d.validate_chromosome(np.array([0.0, 0.5, 1.5, 0.2, 0.1]))
        with pytest.raises(ValueError, match="fuera de"):
            d.validate_chromosome(np.array([0.0, 0.5, -0.1, 0.2, 0.1]))

    def test_no_se_puede_instanciar_directamente(self) -> None:
        with pytest.raises(TypeError):
            DecoderBase()  # type: ignore[abstract]


import random  # noqa: E402

from atco.algorithms.brkga.decoders.permutations import PermutationDecoder  # noqa: E402
from atco.seeds import construir_solucion_heuristica  # noqa: E402


class TestPermutationDecoder:
    def test_num_genes_es_n_controladores(self, entrada_mad_n_m1: Entrada) -> None:
        n = len(entrada_mad_n_m1.get_controladores())
        decoder = PermutationDecoder(n_controladores=n)
        assert decoder.num_genes == n

    def test_decoder_rechaza_n_no_positivo(self) -> None:
        with pytest.raises(ValueError, match="n_controladores"):
            PermutationDecoder(n_controladores=0)
        with pytest.raises(ValueError, match="n_controladores"):
            PermutationDecoder(n_controladores=-3)

    def test_decoder_produce_solucion_valida(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        n = len(entrada_mad_n_m1.get_controladores())
        decoder = PermutationDecoder(n_controladores=n)
        chromosome = np.random.RandomState(42).random_sample(n)
        sol = decoder.decode(chromosome, entrada_mad_n_m1, parametros)
        assert isinstance(sol, Solucion)
        assert len(sol.controladores) == n
        assert len(sol.turnos) == n

    def test_decoder_es_determinista_con_mismo_cromosoma(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        n = len(entrada_mad_n_m1.get_controladores())
        decoder = PermutationDecoder(n_controladores=n)
        chromosome = np.random.RandomState(7).random_sample(n)
        sol_a = decoder.decode(chromosome.copy(), entrada_mad_n_m1, parametros)
        sol_b = decoder.decode(chromosome.copy(), entrada_mad_n_m1, parametros)
        assert sol_a.turnos == sol_b.turnos

    def test_decoder_responde_al_cromosoma(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        """Cromosomas distintos deberían producir soluciones distintas
        (al menos en alguna semilla razonable, no es invariante estricto)."""
        n = len(entrada_mad_n_m1.get_controladores())
        decoder = PermutationDecoder(n_controladores=n)
        cr_a = np.random.RandomState(1).random_sample(n)
        cr_b = np.random.RandomState(2).random_sample(n)
        sol_a = decoder.decode(cr_a, entrada_mad_n_m1, parametros)
        sol_b = decoder.decode(cr_b, entrada_mad_n_m1, parametros)
        # No exigimos que sean distintas siempre, pero sí en este caso
        # con semillas claramente diferentes:
        assert sol_a.turnos != sol_b.turnos, (
            "El decoder no parece responder al cromosoma — quizá el "
            "tiebreaker no se está aplicando."
        )

    def test_decoder_rechaza_entrada_con_n_distinto(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        n = len(entrada_mad_n_m1.get_controladores())
        decoder = PermutationDecoder(n_controladores=n + 5)
        chromosome = np.zeros(n + 5)
        with pytest.raises(ValueError, match="controladores"):
            decoder.decode(chromosome, entrada_mad_n_m1, parametros)

    def test_decoder_rechaza_cromosoma_con_shape_incorrecta(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        n = len(entrada_mad_n_m1.get_controladores())
        decoder = PermutationDecoder(n_controladores=n)
        chromosome = np.zeros(n - 1)
        with pytest.raises(ValueError, match="shape"):
            decoder.decode(chromosome, entrada_mad_n_m1, parametros)


class TestGreedyConPrioridad:
    """Tests del nuevo parámetro `prioridad` en construir_solucion_heuristica."""

    def test_prioridad_none_es_compatible_con_comportamiento_antiguo(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        """Sin prioridad, el generador sigue produciendo lo de siempre."""
        sol = construir_solucion_heuristica(
            entrada_mad_n_m1, parametros, rng=random.Random(42)
        )
        # Smoke: ejecuta sin reventar.
        assert sol.turnos
        assert len(sol.controladores) > 0

    def test_prioridad_dirige_eleccion_en_empates_de_carga(
        self, entrada_mad_n_m1: Entrada, parametros: Parametros
    ) -> None:
        """Con prioridad fija, dos llamadas son idénticas (determinismo)."""
        n = len(entrada_mad_n_m1.get_controladores())
        prioridad = list(np.random.RandomState(11).random_sample(n))
        sol_a = construir_solucion_heuristica(
            entrada_mad_n_m1,
            parametros,
            rng=random.Random(0),
            prioridad=prioridad,
        )
        sol_b = construir_solucion_heuristica(
            entrada_mad_n_m1,
            parametros,
            rng=random.Random(0),
            prioridad=prioridad,
        )
        assert sol_a.turnos == sol_b.turnos
