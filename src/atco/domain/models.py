from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Any
from atco.problem.parameters import Parametros


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
    baja_alta: Propiedades
    slot_alta: int
    slot_baja: int
    turno_asignado: int = -1
    turno_noche: int = 0
    slots_trabajados: int = 0

    def clone(self) -> Controlador:
        return Controlador(
            self.id,
            self.turno,
            self.nucleo,
            self.ptd,
            self.con,
            self.baja_alta,
            self.slot_alta,
            self.slot_baja,
            self.turno_asignado,
            self.turno_noche,
            self.slots_trabajados,
        )

    def get_slot_baja(self) -> int:
        return self.slot_baja

    def set_slot_baja(self, value: int) -> None:
        self.slot_baja = value

    def get_slot_alta(self) -> int:
        return self.slot_alta

    def set_slot_alta(self, value: int) -> None:
        self.slot_alta = value

    def get_id(self) -> int:
        return self.id

    def set_id(self, value: int) -> None:
        self.id = value

    def get_turno(self) -> str:
        return self.turno

    def set_turno(self, value: str) -> None:
        self.turno = value

    def get_nucleo(self) -> str:
        return self.nucleo

    def set_nucleo(self, value: str) -> None:
        self.nucleo = value

    def is_ptd(self) -> bool:
        return self.ptd

    def set_ptd(self, value: bool) -> None:
        self.ptd = value

    def is_con(self) -> bool:
        return self.con

    def set_con(self, value: bool) -> None:
        self.con = value

    def get_turno_asignado(self) -> int:
        return self.turno_asignado

    def set_turno_asignado(self, value: int) -> None:
        self.turno_asignado = value

    def get_turno_noche(self) -> int:
        return self.turno_noche

    def set_turno_noche(self, value: int) -> None:
        self.turno_noche = value

    def get_baja_alta(self) -> Propiedades:
        return self.baja_alta

    def set_baja_alta(self, value: Propiedades) -> None:
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

    def get_sectores_elementales(self) -> list[str]:
        return self.sectores_elementales

    def set_sectores_elementales(self, value: list[str]) -> None:
        self.sectores_elementales = value

    def get_nombre(self) -> str:
        return self.nombre

    def set_nombre(self, value: str) -> None:
        self.nombre = value

    def get_id(self) -> str:
        return self.id

    def set_id(self, value: str) -> None:
        self.id = value

    def is_ptd(self) -> bool:
        return self.pdt

    def set_ptd(self, value: bool) -> None:
        self.pdt = value

    def is_ruta(self) -> bool:
        return self.ruta

    def set_ruta(self, value: bool) -> None:
        self.ruta = value

    def get_noche(self) -> int:
        return self.noche

    def set_noche(self, value: int) -> None:
        self.noche = value


@dataclass
class Nucleo:
    nombre: str
    id: str
    sectores: list[Sector] = field(default_factory=list)

    def get_nombre(self) -> str:
        return self.nombre

    def set_nombre(self, value: str) -> None:
        self.nombre = value

    def get_id(self) -> str:
        return self.id

    def set_id(self, value: str) -> None:
        self.id = value

    def get_sectores(self) -> list[Sector]:
        return self.sectores

    def set_sectores(self, value: list[Sector]) -> None:
        self.sectores = value


@dataclass
class Turno:
    nombre: str
    inicio_tl: str
    fin_tl: str
    inicio_tc: str
    fin_tc: str
    parametros: Parametros
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
            self.parametros.get_porcent_descanso_noche()
            if self.nombre.lower() == "noche"
            else self.parametros.get_porcent_descanso_dia()
        )
        self.slots_des_tc = (
            ceil((self.tc[1] - self.tc[0]) * descanso)
            + self.tc[0]
            + (self.tl[1] - self.tc[1])
        )
        self.slots_des_tl = ceil((self.tl[1] - self.tl[0]) * descanso)

    @staticmethod
    def turnos_slots(
        inicio_tl: str, fin_tl: str, inicio_tc: str, fin_tc: str, parametros: Parametros
    ) -> list[int]:
        i_tch, i_tcm = _hour_minute(inicio_tc)
        f_tch, f_tcm = _hour_minute(fin_tc)
        i_tlh, i_tlm = _hour_minute(inicio_tl)
        f_tlh, f_tlm = _hour_minute(fin_tl)
        slot_size = parametros.get_tamano_slots()
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
            turnos[1] = (((24 - inicio_h) * 60 - inicio_m) // slot_size) + (
                (f_tlh * 60 + f_tlm) // slot_size
            )

        if i_tch <= f_tch:
            turnos[3] = ((f_tch - inicio_h) * 60 + (f_tcm - inicio_m)) // slot_size
        else:
            turnos[3] = (((24 - inicio_h) * 60 - inicio_m) // slot_size) + (
                (f_tch * 60 + f_tcm) // slot_size
            )

        return turnos

    def get_nombre(self) -> str:
        return self.nombre

    def get_inicio_tl(self) -> str:
        return self.inicio_tl

    def get_fin_tl(self) -> str:
        return self.fin_tl

    def get_inicio_tc(self) -> str:
        return self.inicio_tc

    def get_fin_tc(self) -> str:
        return self.fin_tc

    def get_tc(self) -> list[int]:
        return self.tc

    def get_tl(self) -> list[int]:
        return self.tl

    def get_slots_des_tc(self) -> int:
        return self.slots_des_tc

    def get_slots_des_tl(self) -> int:
        return self.slots_des_tl


@dataclass(eq=True)
class Solucion:
    turnos: list[str]
    controladores: list[Controlador]
    longdescansos: int = 0

    def clone(self) -> Solucion:
        return Solucion(
            list(self.turnos),
            [controlador.clone() for controlador in self.controladores],
            self.longdescansos,
        )

    def shallow_clone(self) -> Solucion:
        return Solucion(self.turnos, self.controladores, self.longdescansos)

    def get_long_descansos(self) -> int:
        return self.longdescansos

    def set_long_descansos(self, value: int) -> None:
        self.longdescansos = value

    def get_controladores(self) -> list[Controlador]:
        return self.controladores

    def set_controladores(self, value: list[Controlador]) -> None:
        self.controladores = value

    def get_turnos(self) -> list[str]:
        return self.turnos

    def set_turnos(self, value: list[str]) -> None:
        self.turnos = value


def _hour_minute(value: str) -> tuple[int, int]:
    parts = value.split(":")
    return int(parts[0]), int(parts[1])
