from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Any

# =============================================================================
# CORRESPONDENCIA CON CÓDIGO JAVA
# =============================================================================
# Archivos Java (todos en src/main/estructurasDatos/):
#   - DominioDelProblema/Controlador.java  → clase Controlador
#   - DominioDelProblema/Sector.java       → clase Sector
#   - DominioDelProblema/Nucleo.java       → clase Nucleo
#   - DominioDelProblema/Turno.java        → clase Turno (+ turnos_slots)
#   - DominioDelProblema/Propiedades.java  → enum Propiedades (ALTA/BAJA/ALTABAJA)
#   - Solucion.java                        → clase Solucion
# =============================================================================


class Propiedades(Enum):
    ALTA = "ALTA"
    BAJA = "BAJA"
    ALTABAJA = "ALTABAJA"


@dataclass(eq=True)
class Controlador:
    id: int
    turno: str
    nucleo: str
    ptd: bool
    con: bool
    imaginario: bool
    baja_alta: Propiedades
    slot_alta: int
    slot_baja: int
    turno_asignado: int = -1
    turno_noche: int = 0

    def clone(self) -> "Controlador":
        return Controlador(
            self.id,
            self.turno,
            self.nucleo,
            self.ptd,
            self.con,
            self.imaginario,
            self.baja_alta,
            self.slot_alta,
            self.slot_baja,
            self.turno_asignado,
            self.turno_noche,
        )

    def isImaginario(self) -> bool:
        return self.imaginario

    def setImaginario(self, value: bool) -> None:
        self.imaginario = value

    def getSlotBaja(self) -> int:
        return self.slot_baja

    def setSlotBaja(self, value: int) -> None:
        self.slot_baja = value

    def getSlotAlta(self) -> int:
        return self.slot_alta

    def setSlotAlta(self, value: int) -> None:
        self.slot_alta = value

    def getId(self) -> int:
        return self.id

    def setId(self, value: int) -> None:
        self.id = value

    def getTurno(self) -> str:
        return self.turno

    def setTurno(self, value: str) -> None:
        self.turno = value

    def getNucleo(self) -> str:
        return self.nucleo

    def setNucleo(self, value: str) -> None:
        self.nucleo = value

    def isPTD(self) -> bool:
        return self.ptd

    def setPTD(self, value: bool) -> None:
        self.ptd = value

    def isCON(self) -> bool:
        return self.con

    def setCON(self, value: bool) -> None:
        self.con = value

    def getTurnoAsignado(self) -> int:
        return self.turno_asignado

    def setTurnoAsignado(self, value: int) -> None:
        self.turno_asignado = value

    def getTurnoNoche(self) -> int:
        return self.turno_noche

    def setTurnoNoche(self, value: int) -> None:
        self.turno_noche = value

    def getBajaAlta(self) -> Propiedades:
        return self.baja_alta

    def setBajaAlta(self, value: Propiedades) -> None:
        self.baja_alta = value


@dataclass
class Sector:
    nombre: str
    id: str
    pdt: bool
    ruta: bool
    noche: int
    sectores_elementales: list[str]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Sector) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def getSectoresElementales(self) -> list[str]:
        return self.sectores_elementales

    def setSectoresElementales(self, value: list[str]) -> None:
        self.sectores_elementales = value

    def getNombre(self) -> str:
        return self.nombre

    def setNombre(self, value: str) -> None:
        self.nombre = value

    def getId(self) -> str:
        return self.id

    def setId(self, value: str) -> None:
        self.id = value

    def isPDT(self) -> bool:
        return self.pdt

    def setPDT(self, value: bool) -> None:
        self.pdt = value

    def isRuta(self) -> bool:
        return self.ruta

    def setRuta(self, value: bool) -> None:
        self.ruta = value

    def getNoche(self) -> int:
        return self.noche

    def setNoche(self, value: int) -> None:
        self.noche = value


@dataclass
class Nucleo:
    nombre: str
    id: str
    sectores: list[Sector] = field(default_factory=list)

    def getNombre(self) -> str:
        return self.nombre

    def setNombre(self, value: str) -> None:
        self.nombre = value

    def getId(self) -> str:
        return self.id

    def setId(self, value: str) -> None:
        self.id = value

    def getSectores(self) -> list[Sector]:
        return self.sectores

    def setSectores(self, value: list[Sector]) -> None:
        self.sectores = value


@dataclass
class Turno:
    nombre: str
    inicio_tl: str
    fin_tl: str
    inicio_tc: str
    fin_tc: str
    parametros: Any
    tc: list[int] = field(init=False)
    tl: list[int] = field(init=False)
    slots_des_tc: int = field(init=False)
    slots_des_tl: int = field(init=False)

    def __post_init__(self) -> None:
        slots = self.turnos_slots(
            self.inicio_tl,
            self.fin_tl,
            self.inicio_tc,
            self.fin_tc,
            self.parametros,
        )
        self.tl = [slots[0], slots[1]]
        self.tc = [slots[2], slots[3]]
        descanso = (
            self.parametros.getPorcentDescansoNoche()
            if self.nombre.lower() == "noche"
            else self.parametros.getPorcentDescansoDia()
        )
        self.slots_des_tc = ceil((self.tc[1] - self.tc[0]) * descanso) + self.tc[0] + (self.tl[1] - self.tc[1])
        self.slots_des_tl = ceil((self.tl[1] - self.tl[0]) * descanso)

    @staticmethod
    def turnos_slots(inicio_tl: str, fin_tl: str, inicio_tc: str, fin_tc: str, parametros: Any) -> list[int]:
        i_tch, i_tcm = _hour_minute(inicio_tc)
        f_tch, f_tcm = _hour_minute(fin_tc)
        i_tlh, i_tlm = _hour_minute(inicio_tl)
        f_tlh, f_tlm = _hour_minute(fin_tl)
        slot_size = parametros.getTamanoSlots()
        turnos = [-1, -1, -1, -1]

        if i_tch == i_tlh:
            if i_tcm == i_tlm:
                turnos[0] = 0
                turnos[2] = 0
            elif i_tcm < i_tlm:
                turnos[2] = 0
                turnos[0] = (i_tlm - i_tcm) // slot_size
            else:
                turnos[0] = 0
                turnos[2] = (i_tcm - i_tlm) // slot_size
        elif i_tch < i_tlh:
            turnos[0] = ((i_tlh - i_tch) * 60 + (i_tlm - i_tcm)) // slot_size
            turnos[2] = 0
        else:
            turnos[0] = 0
            turnos[2] = ((i_tch - i_tlh) * 60 + (i_tcm - i_tlm)) // slot_size

        if turnos[2] >= turnos[0]:
            inicio_h, inicio_m = i_tlh, i_tlm
        else:
            inicio_h, inicio_m = i_tch, i_tcm

        if i_tlh <= f_tlh:
            turnos[1] = ((f_tlh - inicio_h) * 60 + (f_tlm - inicio_m)) // slot_size
        else:
            turnos[1] = (((24 - inicio_h) * 60 - inicio_m) // slot_size) + ((f_tlh * 60 + f_tlm) // slot_size)

        if i_tch <= f_tch:
            turnos[3] = ((f_tch - inicio_h) * 60 + (f_tcm - inicio_m)) // slot_size
        else:
            turnos[3] = (((24 - inicio_h) * 60 - inicio_m) // slot_size) + ((f_tch * 60 + f_tcm) // slot_size)

        return turnos

    def getNombre(self) -> str:
        return self.nombre

    def getInicioTL(self) -> str:
        return self.inicio_tl

    def getFinTL(self) -> str:
        return self.fin_tl

    def getInicioTC(self) -> str:
        return self.inicio_tc

    def getFinTC(self) -> str:
        return self.fin_tc

    def getTc(self) -> list[int]:
        return self.tc

    def getTl(self) -> list[int]:
        return self.tl

    def getSlotsDesTC(self) -> int:
        return self.slots_des_tc

    def getSlotsDesTL(self) -> int:
        return self.slots_des_tl


@dataclass(eq=True)
class Solucion:
    turnos: list[str]
    controladores: list[Controlador]
    longdescansos: int = 0

    def clone(self) -> "Solucion":
        return Solucion(list(self.turnos), [controlador.clone() for controlador in self.controladores], self.longdescansos)

    def shallowClone(self) -> "Solucion":
        return Solucion(self.turnos, self.controladores, self.longdescansos)

    def getLongdescansos(self) -> int:
        return self.longdescansos

    def setLongdescansos(self, value: int) -> None:
        self.longdescansos = value

    def getControladores(self) -> list[Controlador]:
        return self.controladores

    def setControladores(self, value: list[Controlador]) -> None:
        self.controladores = value

    def getTurnos(self) -> list[str]:
        return self.turnos

    def setTurnos(self, value: list[str]) -> None:
        self.turnos = value


def _hour_minute(value: str) -> tuple[int, int]:
    parts = value.split(":")
    return int(parts[0]), int(parts[1])
