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

    def getPesoObj1(self) -> float:
        return self.peso_obj1

    def getPesoObj2(self) -> float:
        return self.peso_obj2

    def getPesoObj3(self) -> float:
        return self.peso_obj3

    def getPesoObj4(self) -> float:
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
    def from_files(cls, problem_parameters: str | Path, options: str | Path) -> Parametros:
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

    def getPorcentDescansoDia(self) -> float:
        return self.porcent_descanso_dia

    def getPorcentDescansoNoche(self) -> float:
        return self.porcent_descanso_noche

    def getTiempoTrabMax(self) -> int:
        return self.tiempo_trab_max

    def getTiempoTrabMin(self) -> int:
        return self.tiempo_trab_min

    def getTiempoDesMin(self) -> int:
        return self.tiempo_des_min

    def getTiempoDesPorTrabajo(self) -> int:
        return self.tiempo_des_por_trabajo

    def getTiempoPosMin(self) -> int:
        return self.tiempo_pos_min

    def getTiempoPosOpt(self) -> int:
        return self.tiempo_pos_opt

    def getTiempoTrabOpt(self) -> int:
        return self.tiempo_trab_opt

    def getNumSctrsMax(self) -> int:
        return self.num_sctrs_max

    def getPorcentPosMax(self) -> float:
        return self.porcent_pos_max

    def getPorcentPosMin(self) -> float:
        return self.porcent_pos_min

    def getTamanoSlots(self) -> int:
        return self.tamano_slots

    def getPesosObjetivos(self) -> PesosObjetivos:
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

    def getTemperaturaInicial(self) -> float:
        return self.temperatura_inicial

    def getDescensoTemperatura(self) -> float:
        return self.descenso_temperatura

    def getIteracionesTemperaturaL(self) -> int:
        return self.iteraciones_temperatura_l

    def getMovimientosEntorno(self) -> str:
        return self.movimientos_entorno

    def getCondicionParadaPorcent(self) -> float:
        return self.condicion_parada_porcent

    def getCondicionParadaCiclos(self) -> int:
        return self.condicion_parada_ciclos

    def getCondicionParadaNumeroMejoras(self) -> float:
        return self.condicion_parada_numero_mejoras

    def getTamanoMaxMov(self) -> int:
        return self.tamano_max_mov

    def getTamanoMinMov(self) -> int:
        return self.tamano_min_mov

    def getPorcentajeEleccionMov(self) -> float:
        return self.porcentaje_eleccion_mov

    def setPorcentajeEleccionMov(self, value: float) -> None:
        self.porcentaje_eleccion_mov = value

    def getMove15_min(self) -> int:
        return self.move15_min

    def getMove15_max(self) -> int:
        return self.move15_max

    def isMove17_adapt_max(self) -> bool:
        return self.move17_adapt_max

    def setMove17_adapt_max(self, value: bool) -> None:
        self.move17_adapt_max = value


@dataclass
class VNSParameters:
    num_max_iteraciones_sin_mejora_busqueda_local: int
    porcentaje_minimo_mejoria: float
    num_iteraciones_para_comprobar_condicion_parada_porcentaje: int
    tipo_vns: str
    alpha: float
    funcion_distancia: str
    neighbor_structures_string: str

    @classmethod
    def from_properties(cls, props: dict[str, str]) -> VNSParameters:
        porcentaje = props["porcentajeMinimoMejoria"]
        return cls(
            _int(props, "numMaxIteracionesSinMejoraBusquedaLocal"),
            float("inf") if porcentaje.lower() == "inf" else float(porcentaje),
            _int(props, "numIteracionesParaComprobarCondicionParadaPorcentaje"),
            props["tipoVNS"],
            _float(props, "skewed.alpha"),
            props["skewed.funcionDistancia"],
            props["neighborStructures"],
        )

    def getNeighborStructuresString(self) -> str:
        return self.neighbor_structures_string

    def getNumMaxIteracionesSinMejoraBusquedaLocal(self) -> int:
        return self.num_max_iteraciones_sin_mejora_busqueda_local

    def getPorcentajeMinimoMejoria(self) -> float:
        return self.porcentaje_minimo_mejoria

    def getAlpha(self) -> float:
        return self.alpha

    def getTipoVNS(self) -> str:
        return self.tipo_vns

    def getFuncionDistancia(self) -> str:
        return self.funcion_distancia


@dataclass
class ParametrosAlgoritmo:
    algoritmo: str
    funcion_fitness_fase2: str
    max_miliseconds_allowed: int
    max_iterations_allowed: int
    ponderacion_fitness1: float
    ponderacion_fitness2: float
    ponderacion_fitness3: float
    ponderacion_fitness4: float
    SA: SAParameters
    VNS: VNSParameters

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
            VNSParameters.from_properties(props),
        )

    def getAlgoritmo(self) -> str:
        return self.algoritmo

    def getFuncionFitnessFase2(self) -> str:
        return self.funcion_fitness_fase2

    def getMaxMilisecondsAllowed(self) -> int:
        return self.max_miliseconds_allowed

    def getPonderacionFitness1(self) -> float:
        return self.ponderacion_fitness1

    def getPonderacionFitness2(self) -> float:
        return self.ponderacion_fitness2

    def getPonderacionFitness3(self) -> float:
        return self.ponderacion_fitness3

    def getPonderacionFitness4(self) -> float:
        return self.ponderacion_fitness4
