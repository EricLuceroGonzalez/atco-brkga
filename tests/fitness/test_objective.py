"""Tests del orquestador `evaluar_fitness` con arquitectura de dos bloques.

Cubre:
  - Normalizadores privados (uno por cada componente).
  - `_calcular_bloque_rendimiento` aislado (sin restricciones).
  - `calcular_factibilidad_normalizada` con cap Tello (κ·N).
  - Aritmética del orquestador: `valor = alpha·f_fact + (1-alpha)·f_rend`.
  - Estructura del `FitnessResult` y trazabilidad.
  - Cobertura como métrica auxiliar (fuera del valor).
  - Configuración personalizada y validación de pesos.
  - Helpers `pesos_roc`, `pesos_iguales` y la factoría `con_orden`.

Los componentes individuales se parchean con `monkeypatch` para aislar la
lógica de orquestación; cada componente tiene su propio archivo de tests
unitarios (`test_acreditacion.py`, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from atco.fitness import objective as obj_mod
from atco.fitness.config import (
    FitnessConfig,
    PesosBloques,
    PesosFitness,
    pesos_iguales,
    pesos_roc,
)
from atco.fitness.objective import (
    FitnessResult,
    _calcular_bloque_rendimiento,
    _norm_acreditacion,
    _norm_cobertura,
    _norm_desviacion_t,
    _norm_fragmentacion,
    _norm_intervalos_descanso,
    evaluar_fitness,
)
from atco.fitness.penalizacion import (
    PesosPenalizacion,
    calcular_factibilidad_normalizada,
)
from atco.problem.restrictions import checks as checks_mod
from atco.problem.restrictions.checks import NOMBRES_RESTRICCIONES

# ============================================================================
# Mocks
# ============================================================================


@dataclass
class _TurnoMock:
    nombre: str = "Manana"

    def get_nombre(self) -> str:
        return self.nombre


@dataclass
class _EntradaMock:
    """Entrada mínima con sólo el método que `evaluar_fitness` consulta."""

    nombre_turno: str = "Manana"

    def get_turno(self) -> _TurnoMock:
        return _TurnoMock(self.nombre_turno)


@dataclass
class _SolucionMock:
    """Solucion mínima con `len(turnos)` válido para el cálculo de N."""

    turnos: list[str]


# Instancias dummy reutilizables
_SOL = _SolucionMock(turnos=["aaa" * 10] * 3)  # N = 3
_ENT_DIA = _EntradaMock(nombre_turno="Manana")
_ENT_NOCHE = _EntradaMock(nombre_turno="Noche")
_PAR = object()


def _parchear_componentes(
    monkeypatch,
    *,
    cobertura: tuple[int, int] = (0, 10),
    vn1: tuple[float, float] = (0.0, 100.0),
    vn2: tuple[float, float] = (0.0, 100.0),
    vn3: tuple[float, float] = (0.0, 1.0),
    frag: tuple[int, int, int] = (1, 1, 10),
    desc: tuple[int, int, int] = (1, 1, 10),
    acred: tuple[int, int, int] = (10, 2, 10),
    balance: tuple[float, float] = (0.0, 50.0),
    violaciones: list[float] | None = None,
) -> None:
    """Parchea TODOS los componentes y `_checks` con valores controlados."""
    monkeypatch.setattr(obj_mod, "cobertura_insatisfecha", lambda *a, **k: cobertura)
    monkeypatch.setattr(obj_mod, "tiempo_optimo_posicion", lambda *a, **k: vn1)
    monkeypatch.setattr(obj_mod, "tiempo_optimo_trabajo", lambda *a, **k: vn2)
    monkeypatch.setattr(obj_mod, "porcentaje_ejecutivo", lambda *a, **k: vn3)
    monkeypatch.setattr(obj_mod, "fragmentacion", lambda *a, **k: frag)
    monkeypatch.setattr(obj_mod, "intervalos_descanso", lambda *a, **k: desc)
    monkeypatch.setattr(obj_mod, "acreditacion", lambda *a, **k: acred)
    monkeypatch.setattr(obj_mod, "balance_carga", lambda *a, **k: balance)
    monkeypatch.setattr(
        checks_mod,
        "_checks",
        lambda *a, **k: list(violaciones if violaciones is not None else [0.0] * 14),
    )


# ============================================================================
# Normalizadores privados
# ============================================================================


class TestNormalizadores:
    def test_cobertura_perfecta_es_1(self) -> None:
        assert _norm_cobertura(0, 10) == 1.0

    def test_cobertura_total_descubierta_es_0(self) -> None:
        assert _norm_cobertura(10, 10) == 0.0

    def test_cobertura_sin_demanda_es_1(self) -> None:
        assert _norm_cobertura(0, 0) == 1.0

    def test_desviacion_clamp_inferior(self) -> None:
        assert _norm_desviacion_t(100.0, 50.0) == 0.0

    def test_desviacion_clamp_superior(self) -> None:
        assert _norm_desviacion_t(-10.0, 50.0) == 1.0

    def test_desviacion_cota_cero_es_1(self) -> None:
        assert _norm_desviacion_t(0.0, 0.0) == 1.0

    def test_acreditacion_min_da_cero(self) -> None:
        assert _norm_acreditacion(2, 2, 10) == 0.0

    def test_acreditacion_max_da_uno(self) -> None:
        assert _norm_acreditacion(10, 2, 10) == 1.0

    def test_fragmentacion_min_da_uno(self) -> None:
        assert _norm_fragmentacion(2, 2, 10) == 1.0

    def test_intervalos_descanso_min_da_uno(self) -> None:
        assert _norm_intervalos_descanso(2, 2, 10) == 1.0


# ============================================================================
# Bloque A — Factibilidad (calcular_factibilidad_normalizada)
# ============================================================================


class TestCalcularFactibilidad:
    def test_sin_violaciones_da_uno(self) -> None:
        v = {n: 0.0 for n in NOMBRES_RESTRICCIONES}
        f, r, r_max = calcular_factibilidad_normalizada(
            v,
            PesosPenalizacion(),
            n_controladores=10,
            es_turno_noche=False,
        )
        assert f == 1.0
        assert r == 0.0
        assert r_max == 18 * 10

    def test_cap_dia_es_18N(self) -> None:
        v = {n: 0.0 for n in NOMBRES_RESTRICCIONES}
        _, _, r_max = calcular_factibilidad_normalizada(
            v,
            PesosPenalizacion(),
            n_controladores=5,
            es_turno_noche=False,
        )
        assert r_max == 18 * 5

    def test_cap_noche_es_20N(self) -> None:
        v = {n: 0.0 for n in NOMBRES_RESTRICCIONES}
        _, _, r_max = calcular_factibilidad_normalizada(
            v,
            PesosPenalizacion(),
            n_controladores=5,
            es_turno_noche=True,
        )
        assert r_max == 20 * 5

    def test_saturacion_da_cero(self) -> None:
        # Con N=2, r_max=36; si r ≥ 36 -> f_fact = 0
        v = {n: 0.0 for n in NOMBRES_RESTRICCIONES}
        v[NOMBRES_RESTRICCIONES[0]] = 50.0  # mucho más que r_max
        f, _, _ = calcular_factibilidad_normalizada(
            v,
            PesosPenalizacion(),
            n_controladores=2,
            es_turno_noche=False,
        )
        assert f == 0.0

    def test_violacion_parcial_es_proporcional(self) -> None:
        # N=10 -> r_max = 180. Una violación de peso 1 -> f = (180-1)/180 ≈ 0.9944
        v = {n: 0.0 for n in NOMBRES_RESTRICCIONES}
        v[NOMBRES_RESTRICCIONES[0]] = 1.0
        f, r, _ = calcular_factibilidad_normalizada(
            v,
            PesosPenalizacion(),
            n_controladores=10,
            es_turno_noche=False,
        )
        assert r == 1.0
        assert f == pytest.approx((180.0 - 1.0) / 180.0)

    def test_pesos_por_restriccion_se_aplican(self) -> None:
        # Si una restricción tiene peso 10, una violación cuenta como 10
        pesos_dict = {n: 1.0 for n in NOMBRES_RESTRICCIONES}
        pesos_dict[NOMBRES_RESTRICCIONES[0]] = 10.0
        pp = PesosPenalizacion(pesos_por_restriccion=pesos_dict)

        v = {n: 0.0 for n in NOMBRES_RESTRICCIONES}
        v[NOMBRES_RESTRICCIONES[0]] = 1.0  # vale 10 efectivo

        _, r, _ = calcular_factibilidad_normalizada(
            v,
            pp,
            n_controladores=10,
            es_turno_noche=False,
        )
        assert r == pytest.approx(10.0)


# ============================================================================
# Bloque B — Rendimiento (`_calcular_bloque_rendimiento`)
# ============================================================================


class TestCalcularRendimiento:
    def test_todo_perfecto_da_uno(self, monkeypatch) -> None:
        _parchear_componentes(
            monkeypatch,
            vn1=(0.0, 100.0),
            vn2=(0.0, 100.0),
            vn3=(0.0, 1.0),
            frag=(2, 2, 10),
            desc=(2, 2, 10),
            acred=(10, 2, 10),
            balance=(0.0, 50.0),
        )
        f_rend, objetivos, componentes, crudos = _calcular_bloque_rendimiento(
            _SOL,
            _ENT_DIA,
            _PAR,
            FitnessConfig(),
        )
        assert f_rend == pytest.approx(1.0)
        assert all(v == pytest.approx(1.0) for v in objetivos.values())

    def test_todo_pesimo_da_cero(self, monkeypatch) -> None:
        _parchear_componentes(
            monkeypatch,
            vn1=(100.0, 100.0),
            vn2=(100.0, 100.0),
            vn3=(1.0, 1.0),
            frag=(10, 2, 10),
            desc=(10, 2, 10),
            acred=(2, 2, 10),
            balance=(50.0, 50.0),
        )
        f_rend, objetivos, _, _ = _calcular_bloque_rendimiento(
            _SOL,
            _ENT_DIA,
            _PAR,
            FitnessConfig(),
        )
        assert f_rend == pytest.approx(0.0)
        assert all(v == pytest.approx(0.0) for v in objetivos.values())

    def test_solo_obj1_perfecto(self, monkeypatch) -> None:
        # vn1, vn2, vn3 perfectos -> obj1=1; resto en cero -> f_rend = w_obj1
        _parchear_componentes(
            monkeypatch,
            vn1=(0.0, 100.0),
            vn2=(0.0, 100.0),
            vn3=(0.0, 1.0),
            frag=(10, 2, 10),
            desc=(10, 2, 10),
            acred=(2, 2, 10),
            balance=(50.0, 50.0),
        )
        cfg = FitnessConfig()
        f_rend, _, _, _ = _calcular_bloque_rendimiento(_SOL, _ENT_DIA, _PAR, cfg)
        assert f_rend == pytest.approx(cfg.pesos.w_obj1)

    def test_obj3_es_promedio_de_subobjetivos(self, monkeypatch) -> None:
        # Sólo acred perfecto, desc pésimo -> obj3 = 0.5 con sub-pesos por defecto
        _parchear_componentes(
            monkeypatch,
            vn1=(100.0, 100.0),
            vn2=(100.0, 100.0),
            vn3=(1.0, 1.0),
            frag=(10, 2, 10),
            desc=(10, 2, 10),
            acred=(10, 2, 10),
            balance=(50.0, 50.0),
        )
        _, objetivos, _, _ = _calcular_bloque_rendimiento(
            _SOL,
            _ENT_DIA,
            _PAR,
            FitnessConfig(),
        )
        assert objetivos["obj3_descansos_y_acreditacion"] == pytest.approx(0.5)

    def test_diccionario_componentes_tiene_7_claves(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        _, _, componentes, _ = _calcular_bloque_rendimiento(
            _SOL,
            _ENT_DIA,
            _PAR,
            FitnessConfig(),
        )
        assert set(componentes) == {
            "vn1_tiempo_optimo_posicion",
            "vn2_tiempo_optimo_trabajo",
            "vn3_porcentaje_ejecutivo",
            "fragmentacion",
            "intervalos_descanso",
            "acreditacion",
            "balance_carga",
        }


# ============================================================================
# Arquitectura de dos bloques: valor = alpha·f_fact + (1-alpha)·f_rend
# ============================================================================


class TestArquitectura2Bloques:
    def test_perfecto_factible_da_uno(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)  # defaults dan f_rend=1, f_fact=1
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.valor == pytest.approx(1.0)
        assert res.f_factibilidad == pytest.approx(1.0)
        assert res.f_rendimiento == pytest.approx(1.0)
        assert res.factible is True

    def test_perfecto_factibilidad_pesimo_rendimiento(self, monkeypatch) -> None:
        # f_fact=1, f_rend=0 -> valor = 0.7·1 + 0.3·0 = 0.7
        _parchear_componentes(
            monkeypatch,
            vn1=(100.0, 100.0),
            vn2=(100.0, 100.0),
            vn3=(1.0, 1.0),
            frag=(10, 2, 10),
            desc=(10, 2, 10),
            acred=(2, 2, 10),
            balance=(50.0, 50.0),
        )
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.valor == pytest.approx(0.7)
        assert res.f_factibilidad == 1.0
        assert res.f_rendimiento == pytest.approx(0.0)

    def test_pesimo_factibilidad_perfecto_rendimiento(self, monkeypatch) -> None:
        # Saturar restricciones para que f_fact=0; componentes perfectos.
        viol = [0.0] * 14
        viol[0] = 1000.0  # mucho más que r_max
        _parchear_componentes(monkeypatch, violaciones=viol)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.f_factibilidad == 0.0
        assert res.f_rendimiento == pytest.approx(1.0)
        assert res.valor == pytest.approx(0.3)

    def test_valor_siempre_en_0_1(self, monkeypatch) -> None:
        # Mezcla extrema: nada perfecto, todo violado
        viol = [50.0] * 14
        _parchear_componentes(
            monkeypatch,
            vn1=(100.0, 100.0),
            vn2=(100.0, 100.0),
            vn3=(1.0, 1.0),
            frag=(10, 2, 10),
            desc=(10, 2, 10),
            acred=(2, 2, 10),
            balance=(50.0, 50.0),
            violaciones=viol,
        )
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert 0.0 <= res.valor <= 1.0

    def test_pesos_bloques_personalizados_se_aplican(self, monkeypatch) -> None:
        _parchear_componentes(
            monkeypatch,
            vn1=(100.0, 100.0),
            vn2=(100.0, 100.0),
            vn3=(1.0, 1.0),
            frag=(10, 2, 10),
            desc=(10, 2, 10),
            acred=(2, 2, 10),
            balance=(50.0, 50.0),
        )
        # 50/50 en lugar de 70/30
        cfg = FitnessConfig(pesos_bloques=PesosBloques(0.5, 0.5))
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR, cfg)
        # f_fact=1, f_rend=0 -> 0.5·1 + 0.5·0 = 0.5
        assert res.valor == pytest.approx(0.5)


# ============================================================================
# Cobertura como métrica auxiliar (no entra al fitness)
# ============================================================================


class TestCoberturaAuxiliar:
    def test_cobertura_no_esta_en_componentes(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert "cobertura" not in res.componentes
        assert "cobertura_huecos" not in res.componentes
        assert "cobertura_ratio" not in res.componentes

    def test_cobertura_se_reporta_como_ratio(self, monkeypatch) -> None:
        # 2 huecos sobre 10 demanda -> ratio = 0.8
        _parchear_componentes(monkeypatch, cobertura=(2, 10))
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.cobertura_ratio == pytest.approx(0.8)

    def test_cobertura_sin_demanda_da_ratio_uno(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch, cobertura=(0, 0))
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.cobertura_ratio == 1.0

    def test_cobertura_no_afecta_al_valor(self, monkeypatch) -> None:
        # Cambiar cobertura no debe alterar el valor del fitness
        _parchear_componentes(monkeypatch, cobertura=(0, 0))
        v1 = evaluar_fitness(_SOL, _ENT_DIA, _PAR).valor
        _parchear_componentes(monkeypatch, cobertura=(10, 10))  # 100% descubierta
        v2 = evaluar_fitness(_SOL, _ENT_DIA, _PAR).valor
        assert v1 == pytest.approx(v2)

    def test_crudos_contiene_cobertura(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch, cobertura=(3, 12))
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.crudos["cobertura_huecos"] == 3.0
        assert res.crudos["cobertura_demanda"] == 12.0


# ============================================================================
# Estructura del FitnessResult
# ============================================================================


class TestEstructuraResultado:
    def test_objetivos_tiene_4_claves(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert set(res.objetivos) == {
            "obj1_condiciones_laborales",
            "obj2_compactacion",
            "obj3_descansos_y_acreditacion",
            "obj4_balance_carga",
        }

    def test_componentes_tiene_7_claves(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert len(res.componentes) == 7

    def test_violaciones_tiene_14_claves(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert set(res.violaciones) == set(NOMBRES_RESTRICCIONES)

    def test_objetivos_y_componentes_en_0_1(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        for nombre, val in res.objetivos.items():
            assert 0.0 <= val <= 1.0, f"obj {nombre} = {val}"
        for nombre, val in res.componentes.items():
            assert 0.0 <= val <= 1.0, f"comp {nombre} = {val}"

    def test_r_actual_y_r_max_se_exponen(self, monkeypatch) -> None:
        viol = [0.0] * 14
        viol[0] = 5.0
        _parchear_componentes(monkeypatch, violaciones=viol)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.r_actual == 5.0
        assert res.r_max == 18 * len(_SOL.turnos)  # 18·N en turno día

    def test_n_violaciones_total(self, monkeypatch) -> None:
        viol = [0.0] * 14
        viol[3] = 2.0
        viol[7] = 1.5
        _parchear_componentes(monkeypatch, violaciones=viol)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert res.n_violaciones_total == pytest.approx(3.5)

    def test_penalty_por_restriccion_suma_a_total_ponderado(self, monkeypatch) -> None:
        viol = [0.0] * 14
        viol[2] = 3.0
        _parchear_componentes(monkeypatch, violaciones=viol)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        # La suma del desglose por restricción debe coincidir con el
        # producto coef·peso·viol acumulado
        assert sum(res.penalty_por_restriccion.values()) >= 0

    def test_float_dunder_devuelve_valor(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR)
        assert float(res) == res.valor


# ============================================================================
# Configuración personalizada
# ============================================================================


class TestConfigPersonalizada:
    def test_pesos_obj_personalizados(self, monkeypatch) -> None:
        # Mover todo el peso a obj4 (balance)
        pesos = PesosFitness(w_obj1=0.0, w_obj2=0.0, w_obj3=0.0, w_obj4=1.0)
        cfg = FitnessConfig(pesos=pesos)
        _parchear_componentes(
            monkeypatch,
            vn1=(100.0, 100.0),
            vn2=(100.0, 100.0),
            vn3=(1.0, 1.0),
            frag=(10, 2, 10),
            desc=(10, 2, 10),
            acred=(2, 2, 10),
            balance=(0.0, 50.0),  # balance perfecto
        )
        res = evaluar_fitness(_SOL, _ENT_DIA, _PAR, cfg)
        # f_rend = 1·obj4 = 1, f_fact = 1 -> valor = 0.7 + 0.3 = 1.0
        assert res.valor == pytest.approx(1.0)

    def test_turno_noche_usa_cap_20N(self, monkeypatch) -> None:
        _parchear_componentes(monkeypatch)
        res = evaluar_fitness(_SOL, _ENT_NOCHE, _PAR)
        assert res.r_max == 20 * len(_SOL.turnos)


# ============================================================================
# Validación de pesos
# ============================================================================


class TestValidacionPesos:
    def test_pesos_obj_no_suman_1_falla(self) -> None:
        with pytest.raises(ValueError, match="w_obj"):
            PesosFitness(w_obj1=0.5, w_obj2=0.5, w_obj3=0.5, w_obj4=0.0)

    def test_sub_pesos_obj1_no_suman_1_falla(self) -> None:
        with pytest.raises(ValueError, match="Obj 1"):
            PesosFitness(mu_1_1=0.5, mu_1_2=0.5, mu_1_3=0.5)

    def test_sub_pesos_obj3_no_suman_1_falla(self) -> None:
        with pytest.raises(ValueError, match="Obj 3"):
            PesosFitness(mu_3_1=0.7, mu_3_2=0.7)

    def test_peso_negativo_falla(self) -> None:
        with pytest.raises(ValueError, match="no negativos"):
            PesosFitness(w_obj1=-0.1, w_obj2=0.5, w_obj3=0.4, w_obj4=0.2)

    def test_pesos_bloques_no_suman_1_falla(self) -> None:
        with pytest.raises(ValueError, match="bloque"):
            PesosBloques(peso_factibilidad=0.5, peso_rendimiento=0.6)

    def test_pesos_bloques_negativo_falla(self) -> None:
        with pytest.raises(ValueError, match="negativos"):
            PesosBloques(peso_factibilidad=-0.1, peso_rendimiento=1.1)


# ============================================================================
# pesos_roc
# ============================================================================


class TestPesosROC:
    def test_pesos_roc_n1_es_uno(self) -> None:
        assert pesos_roc(1) == [1.0]

    def test_pesos_roc_n4_suma_uno(self) -> None:
        assert sum(pesos_roc(4)) == pytest.approx(1.0)

    def test_pesos_roc_n4_valores_tello(self) -> None:
        """Comprueba que coincide con los pesos publicados por Tello sec 6.3.3."""
        p = pesos_roc(4)
        assert p[0] == pytest.approx(25 / 48)  # 0.521
        assert p[1] == pytest.approx(13 / 48)  # 0.271
        assert p[2] == pytest.approx(7 / 48)  # 0.146
        assert p[3] == pytest.approx(3 / 48)  # 0.0625

    def test_pesos_roc_son_decrecientes(self) -> None:
        for n in (2, 3, 4, 5, 10):
            p = pesos_roc(n)
            for i in range(len(p) - 1):
                assert p[i] >= p[i + 1], f"Falló monotonía en n={n}, i={i}"

    def test_pesos_roc_n_invalido_falla(self) -> None:
        with pytest.raises(ValueError):
            pesos_roc(0)
        with pytest.raises(ValueError):
            pesos_roc(-2)

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 7, 10, 20])
    def test_pesos_roc_suma_uno_para_cualquier_n(self, n: int) -> None:
        assert sum(pesos_roc(n)) == pytest.approx(1.0)


# ============================================================================
# pesos_iguales
# ============================================================================


class TestPesosIguales:
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 10])
    def test_pesos_iguales_suma_uno(self, n: int) -> None:
        assert sum(pesos_iguales(n)) == pytest.approx(1.0)

    def test_pesos_iguales_n3(self) -> None:
        assert pesos_iguales(3) == [pytest.approx(1 / 3)] * 3

    def test_pesos_iguales_n_invalido(self) -> None:
        with pytest.raises(ValueError):
            pesos_iguales(0)


# ============================================================================
# Factoría PesosFitness.con_orden
# ============================================================================


class TestPesosFitnessConOrden:
    def test_orden_default_es_obj1_obj2_obj3_obj4(self) -> None:
        p = PesosFitness.con_orden(["obj1", "obj2", "obj3", "obj4"])
        default = PesosFitness()
        assert p.w_obj1 == pytest.approx(default.w_obj1)
        assert p.w_obj4 == pytest.approx(default.w_obj4)

    def test_orden_inverso_invierte_pesos(self) -> None:
        p_dir = PesosFitness.con_orden(["obj1", "obj2", "obj3", "obj4"])
        p_inv = PesosFitness.con_orden(["obj4", "obj3", "obj2", "obj1"])
        assert p_dir.w_obj1 == pytest.approx(p_inv.w_obj4)
        assert p_dir.w_obj4 == pytest.approx(p_inv.w_obj1)

    def test_orden_con_nombre_invalido_falla(self) -> None:
        with pytest.raises(ValueError):
            PesosFitness.con_orden(["obj1", "obj2", "obj3", "RARO"])

    def test_orden_con_longitud_incorrecta_falla(self) -> None:
        with pytest.raises(ValueError, match="4 objetivos"):
            PesosFitness.con_orden(["obj1", "obj2"])

    def test_orden_con_objetivo_repetido_falla(self) -> None:
        with pytest.raises(ValueError):
            PesosFitness.con_orden(["obj1", "obj1", "obj3", "obj4"])
