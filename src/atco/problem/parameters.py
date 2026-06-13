from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .properties import load_properties

# =============================================================================
# CORRESPONDENCIA CON CÓDIGO JAVA
# =============================================================================
# Archivos Java (todos en src/main/estructurasDatos/):
#   - Parametros.java          → clase Parametros (parámetros del problema)
#   - ParametrosAlgoritmo.java → clase ParametrosAlgoritmo + SAParameters
#                                (en Java los parámetros SA son atributos directos
#                                 de ParametrosAlgoritmo; aquí se separan en SAParameters)
#   - PesosObjetivos.java      → clase PesosObjetivos
#   - Opciones.java            → absorbido en Parametros.from_files() (tamanoSlots)
#
# NOTA: VNSParameters está implementado pero no se usa en el flujo SA.
# =============================================================================


def _float(props: dict[str, str], key: str) -> float:
    return float(props[key])


def _int(props: dict[str, str], key: str) -> int:
    return int(props[key])


@dataclass
class PesosObjetivos:
    peso_obj1: float
    peso_obj2: float
    peso_obj3: float
    peso_obj4: float
    peso_obj1_sub1: float = 0.0
    peso_obj1_sub2: float = 0.0
    peso_obj1_sub3: float = 0.0
    peso_obj3_sub1: float = 0.0
    peso_obj3_sub2: float = 0.0

    @classmethod
    def from_properties_file(cls, path: str | Path) -> PesosObjetivos:
        props = load_properties(path)
        return cls(
            _float(props, "Obj1"),
            _float(props, "Obj2"),
            _float(props, "Obj3"),
            _float(props, "Obj4"),
            _float(props, "Obj1Sub1"),
            _float(props, "Obj1Sub2"),
            _float(props, "Obj1Sub3"),
            _float(props, "Obj3Sub1"),
            _float(props, "Obj3Sub2"),
        )

    def get_peso_obj1(self) -> float:
        return self.peso_obj1

    def get_peso_obj2(self) -> float:
        return self.peso_obj2

    def get_peso_obj3(self) -> float:
        return self.peso_obj3

    def get_peso_obj4(self) -> float:
        return self.peso_obj4


@dataclass
class Parametros:
    porcent_descanso_dia: float
    porcent_descanso_noche: float
    tiempo_trab_max: int
    tiempo_trab_min: int
    tiempo_des_min: int
    tiempo_des_por_trabajo: int
    tiempo_pos_min: int
    tiempo_pos_opt: int
    tiempo_trab_opt: int
    num_sctrs_max: int
    porcent_pos_max: float
    porcent_pos_min: float
    tamano_slots: int
    pesos_objetivos: PesosObjetivos

    @classmethod
    def from_files(
        cls, problem_parameters: str | Path, options: str | Path
    ) -> Parametros:
        props = load_properties(problem_parameters)
        opts = load_properties(options)
        return cls(
            _float(props, "porcentajeDeDescansoDuranteDia"),
            _float(props, "porcentajeDeDescansoDuranteNoche"),
            _int(props, "tiempoDeTrabajoMaximo"),
            _int(props, "tiempoDeTrabajoMinimo"),
            _int(props, "tiempoDeDescansoMinimo"),
            _int(props, "tiempoDeDescansoNoContinuoMinimo"),
            _int(props, "tiempoDeTrabajoEnPosicionMinimo"),
            _int(props, "tiempoDeTrabajoEnPosicionOptimo"),
            _int(props, "tiempoDeTrabajoOptimo"),
            _int(props, "numeroDeSectoresDistintosMaximo"),
            _float(props, "porcentajeDeTrabajoMaximoEnPosicion"),
            _float(props, "porcentajeDeTrabajoMinimoEnPosicion"),
            _int(opts, "tamanoDeSlots"),
            PesosObjetivos.from_properties_file(problem_parameters),
        )

    def get_porcent_descanso_dia(self) -> float:
        return self.porcent_descanso_dia

    def get_porcent_descanso_noche(self) -> float:
        return self.porcent_descanso_noche

    def get_tiempo_trab_max(self) -> int:
        return self.tiempo_trab_max

    def get_tiempo_trab_min(self) -> int:
        return self.tiempo_trab_min

    def get_tiempo_des_min(self) -> int:
        return self.tiempo_des_min

    def get_tiempo_des_por_trabajo(self) -> int:
        return self.tiempo_des_por_trabajo

    def get_tiempo_pos_min(self) -> int:
        return self.tiempo_pos_min

    def get_tiempo_pos_opt(self) -> int:
        return self.tiempo_pos_opt

    def get_tiempo_trab_opt(self) -> int:
        return self.tiempo_trab_opt

    def get_num_sctrs_max(self) -> int:
        return self.num_sctrs_max

    def get_porcent_pos_max(self) -> float:
        return self.porcent_pos_max

    def get_porcent_pos_min(self) -> float:
        return self.porcent_pos_min

    def get_tamano_slots(self) -> int:
        return self.tamano_slots

    def get_pesos_objetivos(self) -> PesosObjetivos:
        return self.pesos_objetivos


@dataclass
class SAParameters:
    metodo_temperatura_inicial: str
    metodo_descenso_temperatura: str
    metodo_descenso_iteraciones: str
    temperatura_inicial: float
    descenso_temperatura: float
    iteraciones_temperatura_l: int
    condicion_parada_porcent: float
    condicion_parada_ciclos: int
    condicion_parada_numero_mejoras: float
    tamano_max_mov: int
    tamano_min_mov: int
    movimientos_entorno: str
    porcentaje_eleccion_mov: float
    movimientos_entorno_greedy: str
    move15_min: int
    move15_max: int
    move17_adapt_max: bool
    ciclo_refinar_grid: int

    @classmethod
    def from_properties(cls, props: dict[str, str]) -> SAParameters:
        return cls(
            props["Metodo_De_Temperatura_Inicial"],
            props["Metodo_De_Calculo_Del_Descenso"],
            props["Metodo_De_Calculo_De_Iteraciones"],
            _float(props, "temperaturaInicial"),
            _float(props, "descensoTemperatura"),
            _int(props, "iteracionesTemperatura"),
            _float(props, "condicionParadaPorcent"),
            _int(props, "condicionParadaCiclos"),
            _float(props, "condicionParadaNumeroMejoras"),
            _int(props, "tamanoMaxMov"),
            _int(props, "tamanoMinMov"),
            props["movimientosEntorno"],
            _float(props, "porcentajeEleccionMov"),
            props["movimientosEntornoGreedy"],
            int(props.get("move15_min", "1")),
            _int(props, "move15_max"),
            props.get("move17_adapt_max", "false").lower() == "true",
            int(props.get("cicloRefinarGrid", "0")),
        )

    def get_movimientos_entorno(self) -> str:
        return self.movimientos_entorno

    def get_condicion_parada_porcent(self) -> float:
        return self.condicion_parada_porcent

    def get_condicion_parada_ciclos(self) -> int:
        return self.condicion_parada_ciclos

    def get_condicion_parada_numero_mejoras(self) -> float:
        return self.condicion_parada_numero_mejoras

    def get_tamano_max_mov(self) -> int:
        return self.tamano_max_mov

    def get_tamano_min_mov(self) -> int:
        return self.tamano_min_mov

    def get_move15_min(self) -> int:
        return self.move15_min

    def get_move15_max(self) -> int:
        return self.move15_max

    def is_move17_adapt_max(self) -> bool:
        return self.move17_adapt_max

    def set_move17_adapt_max(self, value: bool) -> None:
        self.move17_adapt_max = value


@dataclass
class ParametrosAlgoritmo:
    algoritmo: str
    funcion_fitness: str
    max_miliseconds_allowed: int
    max_iterations_allowed: int
    ponderacion_fitness1: float
    ponderacion_fitness2: float
    ponderacion_fitness3: float
    ponderacion_fitness4: float
    SA: SAParameters

    @classmethod
    def from_file(cls, path: str | Path) -> ParametrosAlgoritmo:
        props = load_properties(path)
        return cls(
            props["algoritmo"],
            props["funcionFitnessFase2"],
            _int(props, "maxTimeAllowed") * 60 * 1000,
            _int(props, "maxIterationsAllowed"),
            _float(props, "ponderacionFitness1"),
            _float(props, "ponderacionFitness2"),
            _float(props, "ponderacionFitness3"),
            _float(props, "ponderacionFitness4"),
            SAParameters.from_properties(props),
        )

    def get_algoritmo(self) -> str:
        return self.algoritmo

    def get_funcion_fitness(self) -> str:
        return self.funcion_fitness

    def get_max_miliseconds_allowed(self) -> int:
        return self.max_miliseconds_allowed

    def get_ponderacion_fitness1(self) -> float:
        return self.ponderacion_fitness1

    def get_ponderacion_fitness2(self) -> float:
        return self.ponderacion_fitness2

    def get_ponderacion_fitness3(self) -> float:
        return self.ponderacion_fitness3

    def get_ponderacion_fitness4(self) -> float:
        return self.ponderacion_fitness4
