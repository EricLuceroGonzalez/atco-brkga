from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atco.domain.constants import STRING_DESCANSO
from atco.domain.models import Controlador, Nucleo, Sector, Solucion, Turno
from atco.problem.parameters import Parametros

IDS = [
    f"a{b}{c}"
    for b in "abcdefghijklmnopqrstuvwxyz"
    for c in "abcdefghijklmnopqrstuvwxyz"
]


@dataclass
class Entrada:
    controladores: list[Controlador]
    nucleos: list[Nucleo]
    turno: Turno
    lista_sectores: list[Sector]
    lista_sectores_abiertos: list[Sector]
    sectorizacion: list[set[str]]
    mapa_afinidad: dict[str, set[str]]
    volumes_of_sectors: dict[str, list[str]]
    distribucion_inicial: Solucion
    slot_momento_actual: int
    nucleos_abiertos: list[Nucleo]
    sectores_nocturnos: list[list[Sector]]

    @classmethod
    def leer_entrada(
        cls,
        repo: str | Path,
        parametros: Parametros,
        path: str,
        entrada_id: str,
        entorno: str,
        estudio_estadillos: bool = False,
    ) -> Entrada:
        repo = Path(repo)
        case_dir = repo / "entrada" / "Casos" / path
        print(f"case_dir = {case_dir}")
        print(f"path = {path}")
        print(f"entorno = {entorno}")
        print(f"entorno = {entrada_id}")
        (
            print("Apertura cool")
            if _listar(case_dir / f"AperturaSectorizaciones_{entrada_id}.csv")
            is not None
            else print("No apertura")
        )
        (
            print("Apertura cool")
            if _listar(case_dir / f"ListaSectoresElementales_{entrada_id}.csv")
            is not None
            else print("No apertura")
        )
        f_apertura = _listar(case_dir / f"AperturaSectorizaciones_{entrada_id}.csv")
        f_recursos = _listar(case_dir / f"RecursosDisponibles_{entrada_id}.csv")
        f_turno = _listar(case_dir / f"Turno_{entrada_id}.csv")
        # f_mod_sectores = _listar(
        #     case_dir / f"ModificacionSectorizaciones_{entrada_id}.csv", True
        # )
        # f_mod_recursos = _listar(
        #     case_dir / f"ModificacionRecursos_{entrada_id}.csv", True
        # )
        f_distribucion = _listar(case_dir / f"DistribucionInicial_{entrada_id}.csv")
        # TODO: Probar los otros casos Barcelona, Canarias, etc
        if estudio_estadillos:
            fecha = entrada_id.replace("-", "")[-8:]
            f_elementales = _listar(
                case_dir / f"ListaSectoresElementales_{entrada_id}.csv"
            )
            f_afinidad = _listar(
                repo
                / "entrada"
                / "Matrices de afinidad"
                / f"MatrizAfinidad_{entorno}_{fecha}.csv"
            )
            f_sectores_nucleos = _listar(
                case_dir / f"SectoresNucleos{entorno}_{entrada_id}.csv"
            )
            f_sector_vol = _listar(
                case_dir / f"SectorizacionesSectoresVolumenes_{entrada_id}.csv"
            )
        else:
            env_dir = repo / "entrada" / entorno
            f_elementales = _listar(env_dir / f"ListaSectoresElementales_{entorno}.csv")
            f_afinidad = _listar(env_dir / f"MatrizAfinidad_{entorno}.csv")
            f_sectores_nucleos = _listar(env_dir / f"SectoresNucleos_{entorno}.csv")
            f_sector_vol = _listar(
                env_dir / f"SectorizacionesSectoresVolumenes_{entorno}.csv"
            )

        controladores = crear_controladores(f_recursos)
        lista_sectores = crear_lista_sectores(f_sectores_nucleos, f_elementales)
        nucleos = crear_nucleos(f_sectores_nucleos, lista_sectores)
        mapa_afinidad = crear_mapa_afinidad(f_afinidad, lista_sectores)
        turno = crear_turno(f_turno, parametros)
        sectorizacion = crear_sectorizacion(
            f_apertura, f_sector_vol, turno, lista_sectores
        )
        print(f"tipo sctori: {type(sectorizacion)} con len: {len(sectorizacion)}")
        # for i, sec in enumerate(sectorizacion):
        #     print(f"slot {i+1}: {sec}")
        slot_momento_actual = crear_momento_actual(turno, f_distribucion, parametros)

        # sectorizacion_modificada = None
        # nuevos = None
        # print(f"f_mod_sectores({len(f_mod_sectores)}) = {f_mod_sectores}")
        # if len(f_mod_sectores) <= 1:
        #     sectorizacion_modificada = crear_sectorizacion(
        #         f_mod_sectores, f_sector_vol, turno, lista_sectores
        #     )
        #     nuevos = crear_lista_nuevos_sectores_abiertos(
        #         slot_momento_actual,
        #         sectorizacion,
        #         sectorizacion_modificada,
        #         lista_sectores,
        #     )
        # if f_mod_recursos:
        #     modificar_controladores(controladores, f_mod_recursos, turno, parametros)

        abiertos = crear_lista_sectores_abiertos(sectorizacion, lista_sectores)
        volumenes = crear_hashmap_sectores_volumenes(abiertos, f_sector_vol)
        distribucion = crear_solucion_inicial(
            f_distribucion, lista_sectores, controladores, parametros
        )
        calcular_carga_trabajo(sectorizacion)
        nucleos_abiertos = calculo_nuc_lista_sectores(nucleos, controladores)
        nocturnos = calculo_lista_sectores_nocturnos(abiertos)
        return cls(
            controladores,
            nucleos,
            turno,
            lista_sectores,
            abiertos,
            sectorizacion,
            mapa_afinidad,
            volumenes,
            distribucion,
            slot_momento_actual,
            nucleos_abiertos,
            nocturnos,
        )

    def get_distribucion_inicial(self) -> Solucion:
        return self.distribucion_inicial

    # def get_sectorizacion_modificada(self) -> list[set[str]] | None:
    #     return self.sectorizacion_modificada

    def get_controladores(self) -> list[Controlador]:
        return self.controladores

    def get_nucleos(self) -> list[Nucleo]:
        return self.nucleos

    def get_turno(self) -> Turno:
        return self.turno

    def get_lista_sectores(self) -> list[Sector]:
        return self.lista_sectores

    def get_sectorizacion_base(self) -> list[set[str]]:
        return self.sectorizacion

    def get_sectorizacion(self) -> list[set[str]]:
        """Sectorización efectiva: original hasta slot_momento_actual,
        modificada a partir de ahí. Coherente con cómo se cubren los slots
        en tiempo real."""
        return self.sectorizacion
        # t0 = self.slot_momento_actual
        # return self.sectorizacion[:t0] + self.sectorizacion_modificada[t0:]

    def get_lista_sectores_abiertos(self, t: int) -> list[Sector]:
        ids_t = self.sectorizacion[t]
        return [s for s in self.lista_sectores if s.id in ids_t]

    def get_volumns_of_sectors(self) -> dict[str, list[str]]:
        return self.volumes_of_sectors

    def get_slot_momento_actual(self) -> int:
        return self.slot_momento_actual

    def get_lista_nuevos_sectores_abiertos_tras_momento_actual(
        self,
    ) -> list[Sector] | None:
        return self.lista_nuevos_sectores_abiertos_tras_momento_actual

    def get_mapa_afinidad(self) -> dict[str, set[str]]:
        return self.mapa_afinidad

    def get_nucleos_abiertos(self) -> list[Nucleo]:
        return self.nucleos_abiertos

    def get_sectores_nocturnos(self) -> list[list[Sector]]:
        return self.sectores_nocturnos


def _listar(path: str | Path, opcional: bool = False) -> list[str]:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        if opcional:
            return []
        raise


def crear_controladores(lines: list[str]) -> list[Controlador]:
    """Parsea RecursosDisponibles.csv. Todos arrancan con disponibilidad completa."""
    controladores: list[Controlador] = []
    for raw in lines[1:]:
        cols = raw.split(";")
        if len(cols) < 4:
            continue
        is_con = cols[1] == "CON"
        is_ptd = cols[1] == "PTD"
        controladores.append(
            Controlador(
                id=int(cols[0][1:]),
                turno=cols[3],
                nucleo=cols[2],
                ptd=is_ptd,
                con=is_con,
                # disponibilidad: default VentanaDisponibilidad() (completa)
            )
        )
    return controladores


def crear_lista_sectores(
    lines: list[str], elementales_lines: list[str]
) -> list[Sector]:
    """Recorre la lista de sectores y compara con la lista de sectores y sus sectores elementales

    Crea el Array de sectores elementales.

    En cada iteración de la lista de sectores elementales crea una instancia del objeto
    Sector asignando un "id" de sector p.ej: ""aaa", "aab", "aac""

    Args:
        lines (list[str]): Toma la lista de sectores operativos (tipo de sector y ruta)
        del CSV: SectoresNucleos_id
        elementales_lines (list[str]): Lista de sectores y sus divisiones,
        mapea qué piezas pequeñas (elementales) forman cada sector grande
        del CSV: ListaSectoresElementales_id

    Returns:
        list[Sector]: listaSectores Lista del objeto Sector.
    """
    elementales_totales: set[str] = set()
    sectores: list[Sector] = []
    # i = 2 para saltarse el encabezado de la tabla SectoresNucleos...
    for idx, line in enumerate(lines[2:]):
        # print(f"{idx}: {line}")
        # Se separa cada fila del CSV SectoresNucles
        cols = line.split(";")
        if len(cols) < 2:
            continue
        elems = []
        # Se itera el CSV SectoresNucleos_id comparando cada fila con todas las filas
        # de ListaSectoresEmentales
        for raw in elementales_lines:
            parts = raw.split(";")
            if len(parts) > 1 and parts[0].lower() == cols[0].lower():
                elems.append(parts[1])
                elementales_totales.add(parts[1].lower())
        kind = cols[1].lower()

        # Si el Nucleo tiene "RUTA" en la columna 2 crea una instancia tipo RUTA,
        # sino crea una "APP" por defecto
        if kind == "ruta":
            # print(f"IDS[idx]: {IDS[idx]}")
            sectores.append(Sector(cols[0], IDS[idx], False, True, 0, elems))
        elif kind == "app":
            sectores.append(Sector(cols[0], IDS[idx], True, False, 0, elems))
    # TODO:  Ver esto
    # from .fitness import Fitness

    # Fitness.sectores_elementales_totales = len(elementales_totales)
    # Devuelve un objeto <Sector> con sus atributos
    # P.ej: Sector{nombre='LECMASI', id='aaa', pDT=false, ruta=true,
    # noche=0, sectoresElementales=[ASL, ASU]}
    return sectores


def crear_nucleos(lines: list[str], sectores: list[Sector]) -> list[Nucleo]:
    if len(lines) < 2:
        return []
    header = lines[1].split(";")
    nucleos: list[Nucleo] = []
    for idx in range(2, len(header)):
        nuc_sectores = []
        for raw in lines[2:]:
            cols = raw.split(";")
            if len(cols) > idx and cols[idx].lower() == "x":
                sector = find_sector_by_name(cols[0], sectores)
                if sector:
                    nuc_sectores.append(sector)
        nucleos.append(Nucleo(header[idx], str(idx - 2), nuc_sectores))
    return nucleos


def crear_mapa_afinidad(
    lines: list[str], sectores: list[Sector]
) -> dict[str, set[str]]:
    names = lines[0].replace("'", "").split(";")
    result: dict[str, set[str]] = {}
    for line in lines[1:]:
        row = line.replace("'", "").split(";")
        if not row or not row[0]:
            continue
        base = find_sector_by_name(row[0], sectores)
        afines = set()
        for idx in range(1, min(len(row), len(names))):
            if row[idx] and int(row[idx]) >= 1:
                afines.add(find_sector_by_name(names[idx], sectores).id)
        result[base.id] = afines
    return result


def crear_turno(lines: list[str], parametros: Parametros) -> Turno:
    first = lines[1].split(";")
    tipo = first[1].upper()
    if tipo == "N":
        name = "Noche"
    elif tipo in {"M", "MC", "ML"}:
        name = "Manana"
    else:
        name = "Tarde"
    if len(lines) > 2:
        second = lines[2].split(";")
        if tipo in {"ML", "TL"}:
            return Turno(name, first[2], first[3], second[2], second[3], parametros)
        if tipo in {"MC", "TC"}:
            return Turno(name, second[2], second[3], first[2], first[3], parametros)
    return Turno(name, first[2], first[3], first[2], first[3], parametros)


def crear_sectorizacion(
    lines: list[str], conf_lines: list[str], turno: Turno, sectores: list[Sector]
) -> list[set[str]]:
    temp = [[STRING_DESCANSO] for _ in range(turno.get_tl()[1])]
    print(f"\n\n\ncrear_sectorizacion() con {len(temp)}, {turno.get_tl()}")
    print(f"Turno: {turno}")
    for raw in lines[1:]:
        cols = raw.split(";")
        if len(cols) < 6:
            continue
        tipo = cols[1].upper()
        print(f"cols={cols}")
        if tipo == "SECTOR":
            introducir_sector(cols, temp, turno, sectores, False)
        elif tipo == "CONF":
            introducir_lista_sectores(cols, conf_lines, temp, turno, sectores)
        elif tipo == "SECTORNOCTURNO":
            introducir_sector(cols, temp, turno, sectores, True)
    result = []
    for _idx, slot in enumerate(temp):
        # print(f"slot {idx+1} = {slot}")
        result.append(set(x for x in slot if x != STRING_DESCANSO))
    return result


def introducir_lista_sectores(
    line: list[str],
    conf_lines: list[str],
    sectorizacion: list[list[str]],
    turno: Turno,
    sectores: list[Sector],
) -> None:
    """_summary_

    Args:
        line (list[str]): _description_
        conf_lines (list[str]): _description_
        sectorizacion (list[list[str]]): _description_
        turno (Turno): _description_
        sectores (list[Sector]): _description_
    """
    print("=====" * 20)
    print("introducir_lista_sectores()")
    ids = encontrar_configuracion(line, conf_lines, sectores)
    print(f"ids = {type(ids)}")
    ini_tl = turno.get_inicio_tl()
    length = obtener_longitud(line[4], line[5])
    print(f"Inicio de turno: {ini_tl}, Len = {length} slots de 5 min")
    if length < 0:
        length = obtener_longitud(line[4], "24:00:00") + obtener_longitud(
            "00:00:00", line[5]
        )
    offset = obtener_longitud(ini_tl, line[4])
    print(f"Offset = {offset}")
    if offset < 0:
        offset = obtener_longitud(ini_tl, "24:00:00") + obtener_longitud(
            "00:00:00", line[4]
        )
    for i in range(offset, offset + length):
        if i == len(sectorizacion):
            sectorizacion.append(list(ids))
        elif 0 <= i < len(sectorizacion):
            sectorizacion[i].extend(ids)
    print("^^^^^" * 20)


def introducir_sector(
    line: list[str],
    sectorizacion: list[list[str]],
    turno: Turno,
    sectores: list[Sector],
    nocturno: bool,
) -> None:
    print("+++" * 25)
    print("inside introducir_sector()")
    sector_id = ""
    print(f"sectores  {len(sectores)}")
    for sector in sectores:
        print(f"sector: {sector}")
        if line[3].lower() == sector.nombre.lower():
            sector_id = sector.id
            if nocturno:
                sector.noche = int(line[2].replace(" ", ""))
            break
    ini_tl = turno.get_inicio_tl()
    length = obtener_longitud(line[4], line[5])
    if length < 0:
        length = obtener_longitud(line[4], "24:00:00") + obtener_longitud(
            "00:00:00", line[5]
        )
    offset = obtener_longitud(ini_tl, line[4])
    if offset < 0:
        offset = obtener_longitud(ini_tl, "24:00:00") + obtener_longitud(
            "00:00:00", line[4]
        )
    for i in range(offset, offset + length):
        if i == len(sectorizacion):
            sectorizacion.append([sector_id])
        elif 0 <= i < len(sectorizacion):
            sectorizacion[i].append(sector_id)


def encontrar_configuracion(
    line: list[str], conf_lines: list[str], sectores: list[Sector]
) -> list[str]:
    config_name = line[3]
    nucleo = line[0]
    ids: list[str] = []
    print(f"nucleo = {nucleo}")
    print(f"conf = {config_name}")
    for raw in conf_lines[1:]:
        cols = raw.split(";")
        if (
            len(cols) > 3
            and cols[3].lower() == nucleo.lower()
            and cols[0].lower() == config_name.lower()
        ):
            sector = find_sector_by_name(cols[1], sectores)
            print(f"{cols[1]} is {sector.id}")
            if sector.id not in ids:
                ids.append(sector.id)
    return ids


def obtener_longitud(start: str, end: str) -> int:
    sh, sm = _hour_minute(start)
    eh, em = _hour_minute(end)
    print(f"horas: {(eh - sh)}, min: {(eh - sh) * 60}")
    print(f"minutos: {(em - sm)}")
    return ((eh - sh) * 60 + (em - sm)) // 5


def crear_momento_actual(
    turno: Turno, distribucion_lines: list[str], parametros: Parametros
) -> int:
    momento = distribucion_lines[0].split(";")[1]
    return calcular_slot(turno, momento, parametros)


def calcular_slot(turno: Turno, momento: str, parametros: Parametros) -> int:
    return Turno.turnos_slots(
        turno.get_inicio_tl(), turno.get_fin_tl(), momento, momento, parametros
    )[2]


def crear_solucion_inicial(
    lines: list[str],
    sectores: list[Sector],
    controladores: list[Controlador],
    parametros: Parametros,
) -> Solucion:
    turnos: list[str] = []
    intervalos: list[int] = []
    long_max = 0
    for raw in lines[1:]:
        cols = raw.split(";")
        if cols[0].find("-") >= 0:
            intervalos = actualizar_intervalos(cols)
        long_max = max(long_max, sum(intervalos))
    for raw in lines[1:]:
        cols = raw.split(";")
        if cols[0].find("-") >= 0:
            intervalos = actualizar_intervalos(cols)
        elif cols[0]:
            turno = crear_distribucion_del_turno(
                intervalos, cols, sectores, parametros, long_max
            )
            asignar_controlador(int(cols[0][1:]), len(turnos), controladores)
            turnos.append(turno)
    return Solucion(turnos, controladores, 0)


def actualizar_intervalos(cols: list[str]) -> list[int]:
    return [int(col) for col in cols[1:] if col.strip()]


def crear_distribucion_del_turno(
    intervalos: list[int],
    cols: list[str],
    sectores: list[Sector],
    parametros: Parametros,
    long_max: int,
) -> str:
    result = []
    long_actual = 0
    id_sector = STRING_DESCANSO
    for idx, col in enumerate(cols[1:]):
        if idx >= len(intervalos) or not col:
            continue
        intervalo = intervalos[idx]
        long_actual += intervalo
        id_sector = STRING_DESCANSO
        if STRING_DESCANSO not in col:
            id_sector = obtener_id_sector(col, sectores)
            if col[0].isupper():
                id_sector = id_sector.upper()
        result.append(id_sector * (intervalo // parametros.get_tamano_slots()))
    if long_actual < long_max:
        result.append(
            id_sector * ((long_max - long_actual) // parametros.get_tamano_slots())
        )
    return "".join(result)


def obtener_id_sector(nombre: str, sectores: list[Sector]) -> str:
    return find_sector_by_name(nombre, sectores).id


def asignar_controlador(
    id_controlador: int, indice: int, controladores: list[Controlador]
) -> None:
    for controlador in controladores:
        if controlador.id == id_controlador:
            controlador.turno_asignado = indice
            return


def crear_lista_sectores_abiertos(
    sectorizacion: list[set[str]],
    sectores: list[Sector],
) -> list[Sector]:
    abiertos: list[Sector] = []
    seen: set[str] = set()
    for slot in sectorizacion:
        for sid in java_hashset_order(slot):
            if sid not in seen:
                abiertos.append(find_sector_by_id(sectores, sid))
                seen.add(sid)
    return abiertos


def crear_hashmap_sectores_volumenes(
    abiertos: list[Sector], lines: list[str]
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {sector.id: [] for sector in abiertos}
    for sector in abiertos:
        for raw in lines[1:]:
            cols = raw.split(";")
            if (
                len(cols) > 2
                and sector.nombre.lower() == cols[1].lower()
                and cols[2] not in result[sector.id]
            ):
                result[sector.id].append(cols[2])
    return result


def calculo_nuc_lista_sectores(
    nucleos: list[Nucleo], controladores: list[Controlador]
) -> list[Nucleo]:
    return [
        nuc
        for nuc in nucleos
        if any(c.nucleo.lower() == nuc.nombre.lower() for c in controladores)
    ]


def calculo_lista_sectores_nocturnos(abiertos: list[Sector]) -> list[list[Sector]]:
    groups = []
    for value in [1, 2, 3, 4]:
        group = [sector for sector in abiertos if sector.noche == value]
        if group:
            groups.append(group)
    return groups


def calcular_carga_trabajo(sectorizacion: list[set[str]]) -> int:
    # TODO: Ver esto n
    # from .fitness import Fitness

    c = sum(len(slot) for slot in sectorizacion)
    # Fitness.ctrls_completos = (c * 2) / len(sectorizacion) if sectorizacion else 0
    return c * 2


def find_sector_by_name(name: str, sectores: list[Sector]) -> Sector:
    for sector in sectores:
        if sector.nombre.lower() == name.lower():
            return sector
    raise RuntimeError(f"No existe sector de nombre {name!r}")


def find_sector_by_id(sectores: list[Sector], sid: str) -> Sector:
    for sector in sectores:
        if sector.id == sid:
            return sector
    raise RuntimeError(f"No existe sector con id {sid!r}")


def es_afin(sector_a: str, sector_b: str, mapa: dict[str, set[str]]) -> bool:
    return sector_b in mapa.get(
        sector_a.lower(), set()
    ) or sector_b.lower() in mapa.get(sector_a.lower(), set())


def java_hashset_order(values: Any) -> list[str]:
    items = list(values)
    capacity = 16
    while capacity * 0.75 < len(items):
        capacity *= 2
    positions = {value: idx for idx, value in enumerate(items)}
    return sorted(
        items, key=lambda value: (_java_hash_bucket(value, capacity), positions[value])
    )


def _java_hash_bucket(value: str, capacity: int) -> int:
    h = 0
    for char in value:
        h = (31 * h + ord(char)) & 0xFFFFFFFF
    spread = h ^ (h >> 16)
    return spread & (capacity - 1)


def _hour_minute(value: str) -> tuple[int, int]:
    parts = value.split(":")
    return int(parts[0]), int(parts[1])
