from __future__ import annotations

from functools import lru_cache

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO

# =============================================================================
# CORRESPONDENCIA CON CÓDIGO JAVA
# =============================================================================
# Archivo Java:
#   - src/main/patrones/Restricciones.java
#       → penalizacion_por_restricciones()  ≡  Restricciones.penalizacionPorRestricciones()
#       → comprobar_restricciones_en_paralelo()  ≡  Restricciones.comprobarRestriccionesEnParalelo()
#       → restricciones_sin_pesos()  (utilidad Python; sin equivalente directo)
#       → Las 14 funciones de comprobación (comprobar_nucleo_trabajo, etc.)
#
# Restricciones implementadas (por orden en PESO_POR_RESTRICCION):
#   [0] comprobar_nucleo_trabajo          → R1: acreditación de núcleo
#   [1] comprobar_tipo_sector             → R2: acreditación de tipo (CON/PTD)
#   [2] comprobar_porcentaje_descanso     → R3: descanso mínimo diurno
#   [3] comprobar_sectores_abiertos_noche → R4: cobertura nocturna
#   [4] comprobar_trabajo_maximo_consecutivo → R5: trabajo continuo máximo
#   [5] comprobar_controlador_turno_corto → R6: tipo de turno (TC/TL)
#   [6] comprobar_ventana_trabajo_descanso → R7: ventana 2h30m
#   [7] comprobar_cambio_posicion         → R8: cambio de posición ejecutiva
#   [8] comprobar_trabajo_minimo_consecutivo → R9: trabajo continuo mínimo
#   [9] comprobar_descanso_minimo_consecutivo → R10: descanso mínimo
#  [10] comprobar_trabajo_posicion_minimo_consecutivo_no_regex → R11: permanencia en posición
#  [11] comprobar_num_maximo_sectores     → R12: límite de sectores distintos
#  [12] comprobar_controlador_asignado    → R13: asignación completa
#  [13] comprobar_turno_vacio             → R14: trabajo mínimo
# =============================================================================


PESO_POR_RESTRICCION = [2, 2, 3, 2, 3, 2, 3, 0.9, 3, 2, 0.85, 0.5, 5, 5]
PENALIZACION = 0.001
REST_SLOTS = {STRING_DESCANSO, STRING_NO_TURNO}
restricciones_no_cumplidas = [0.0] * 14


def penalizacion_por_restricciones(individuo, entrada, parametros) -> float:
    """Penalización ponderada con publicación del vector de violaciones.

    Idéntica a :func:`comprobar_restricciones_en_paralelo` salvo dos
    diferencias:

    1. Publica el vector de violaciones detalladas en la global
       :data:`restricciones_no_cumplidas` (índice por restricción, ver
       la tabla de la cabecera del módulo). Útil para diagnóstico
       posterior — el caller puede leer ese vector justo después.
    2. Mantiene un **quirk del Java original**: la restricción [6]
       (ventana trabajo/descanso) se suma sin aplicar
       ``PESO_POR_RESTRICCION[6]``. Esto difiere de
       :func:`comprobar_restricciones_en_paralelo`, que sí aplica todos
       los pesos. La discrepancia se preserva por compatibilidad con
       la implementación Java.

    Args:
        individuo: ``Solucion`` a evaluar.
        entrada: ``Entrada`` con la lista de sectores abiertos, núcleos
            y mapa de afinidad.
        parametros: ``Parametros`` del dominio (tiempos mínimos/máximos).

    Returns:
        Penalización total (más alto = más violaciones). Sin cota
        superior teórica.
    """
    checks = _checks(individuo, entrada, parametros)
    total = 0.0
    for idx, value in enumerate(checks):
        restricciones_no_cumplidas[idx] = value
        # Restricciones.penalizacionPorRestricciones() in Java adds restriction
        # 7 without applying pesoPorRestriccion[6]. The parallel checker still
        # applies the weight, so keep this quirk local to the traced penalty.
        total += value if idx == 6 else value * PESO_POR_RESTRICCION[idx]
    return total


def comprobar_restricciones_en_paralelo(individuo, entrada, parametros) -> float:
    """Suma ponderada de violaciones (versión "oficial" usada por F2).

    Recoge el vector de 14 violaciones devuelto por :func:`_checks` y
    lo combina linealmente con :data:`PESO_POR_RESTRICCION`. Es la
    función que :func:`fitness.fit_ponderado_...` usa internamente como
    ``r`` para calcular F2.

    Args:
        individuo: ``Solucion`` a evaluar.
        entrada: ``Entrada`` del escenario.
        parametros: ``Parametros`` del dominio.

    Returns:
        ``sum(violaciones[i] * PESO_POR_RESTRICCION[i])`` para
        ``i = 0..13``. Más alto = más violaciones.
    """
    total = 0.0
    for idx, value in enumerate(_checks(individuo, entrada, parametros)):
        total += value * PESO_POR_RESTRICCION[idx]
    return total


def restricciones_sin_pesos(individuo, entrada, parametros) -> float:
    """Suma directa de violaciones, sin aplicar ``PESO_POR_RESTRICCION``.

    Pensada para diagnóstico (`logs, dashboards`): da una visión
    "democrática" de cuántas violaciones hay en total, independientemente
    de cuánto pese cada una. No se usa para el fitness.

    Args:
        individuo: ``Solucion`` a evaluar.
        entrada: ``Entrada`` del escenario.
        parametros: ``Parametros`` del dominio.

    Returns:
        ``sum(violaciones[i])`` para ``i = 0..13``.
    """
    total = 0.0
    for value in _checks(individuo, entrada, parametros):
        total += value
    return total


def _checks(individuo, entrada, parametros) -> list[float]:
    """Ejecuta las 14 comprobaciones de restricciones y devuelve el vector.

    Es el corazón del módulo: encadena las 14 funciones ``comprobar_*`` en
    el orden canónico definido por :data:`PESO_POR_RESTRICCION` (ver la
    tabla de la cabecera del módulo para la correspondencia
    índice ↔ restricción). Antes, garantiza que la entrada tiene
    pobladas las cachés rápidas (núcleos, IDs de sector,
    volúmenes…) que algunas comprobaciones consultan directamente.

    Args:
        individuo: ``Solucion`` a evaluar.
        entrada: ``Entrada`` del escenario.
        parametros: ``Parametros`` del dominio.

    Returns:
        Lista de 14 floats con el "número de violaciones" (puede ser
        fraccionario por el patrón "1 + ε" de algunas comprobaciones,
        ver módulo). El índice ``i`` corresponde a la restricción
        ``R(i+1)`` de la tabla del módulo.
    """
    _ensure_fast_cache(entrada)
    return [
        comprobar_nucleo_trabajo(individuo, entrada),
        comprobar_tipo_sector(individuo, entrada),
        comprobar_porcentaje_descanso(
            individuo, entrada, entrada.getTurno(), parametros
        ),
        comprobar_sectores_abiertos_noche(individuo, entrada),
        comprobar_trabajo_maximo_consecutivo(individuo.getTurnos(), parametros),
        comprobar_controlador_turno_corto(individuo, entrada),
        comprobar_ventana_trabajo_descanso(individuo.getTurnos(), parametros),
        comprobar_cambio_posicion(
            individuo.getTurnos(), entrada.getMapaAfinidad(), entrada.getListaSectores()
        ),
        comprobar_trabajo_minimo_consecutivo(individuo.getTurnos(), parametros),
        comprobar_descanso_minimo_consecutivo(individuo.getTurnos(), parametros),
        comprobar_trabajo_posicion_minimo_consecutivo_no_regex(
            individuo.getTurnos(), parametros
        ),
        comprobar_num_maximo_sectores(individuo.getTurnos(), entrada, parametros),
        comprobar_controlador_asignado(individuo),
        comprobar_turno_vacio(individuo),
    ]


def _is_rest(slot: str) -> bool:
    """Indica si un token de 3 chars representa descanso o fuera-de-turno.

    Args:
        slot: Token de 3 caracteres (``STRING_DESCANSO``,
            ``STRING_NO_TURNO`` o un sector).

    Returns:
        ``True`` si el slot no representa trabajo en sector.
    """
    return slot == STRING_DESCANSO or slot == STRING_NO_TURNO


@lru_cache(maxsize=50000)
def _slots(turno: str) -> tuple[str, ...]:
    """Trocea una cadena de turno en sus tokens de 3 caracteres (cacheado).

    Equivalente a ``[turno[i:i+3] for i in range(0, len(turno), 3)]`` pero
    cacheado por ``turno`` con LRU de 50k entradas. Como muchas
    comprobaciones recorren el mismo turno varias veces (una por
    restricción), el cache amortiza el coste del troceado en cada
    iteración del solver.

    Args:
        turno: Cadena de turno (longitud múltiplo de 3).

    Returns:
        Tupla inmutable con los tokens. Se devuelve tupla y no lista
        para que sea hashable y `lru_cache` pueda reutilizarla.
    """
    return tuple(turno[idx : idx + 3] for idx in range(0, len(turno), 3))


def comprobar_num_maximo_sectores(turnos: list[str], entrada, parametros) -> int:
    p = 0
    volumes = entrada._fast_volumes_by_id
    sector_by_id = entrada._fast_sector_by_id
    cache = entrada._fast_num_max_sectores_cache
    for turno in turnos:
        sectores = lista_de_sectores_turno(turno, sector_by_id)
        key = tuple(sector.id for sector in sectores)
        value = cache.get(key)
        if value is None:
            value = calculate(sectores, volumes)
            cache[key] = value
        if value > parametros.getNumSctrsMax():
            p += 1
    return p


def lista_de_sectores_turno(turno: str, sector_by_id: dict) -> list:
    result = []
    result_ids = set()
    prev_l = ""
    for slot in _slots(turno):
        slot_l = slot.lower()
        if slot_l != prev_l and slot not in REST_SLOTS:
            sector = sector_by_id.get(slot_l)
            if sector is not None and sector.id not in result_ids:
                result.append(sector)
                result_ids.add(sector.id)
        prev_l = slot_l
    return result


def calculate(sectors: list, volumes: dict) -> int:
    counter = 0
    rest = list(sectors)
    to_delete = set()
    for sector in rest:
        if sector.id in to_delete:
            continue
        temp_volumes = []
        for sector1 in rest:
            if sector1.id in to_delete:
                continue
            for vol in volumes.get(sector1.id.lower(), []):
                if vol not in temp_volumes:
                    temp_volumes.append(vol)
        pivot = None
        max_hits = 0
        for vol in temp_volumes:
            hits = count_hits_per_sector(vol, rest, volumes)
            if hits > max_hits:
                pivot = vol
                max_hits = hits
        for sector2 in rest:
            if pivot in volumes.get(sector2.id.lower(), []):
                to_delete.add(sector2.id)
        counter += 1
    return counter


def count_hits_per_sector(
    volume: str, sectors: list, volumes: dict[str, list[str]]
) -> int:
    hits = 0
    volume_l = volume.lower()
    for sector in sectors:
        for vol in volumes.get(sector.id.lower(), []):
            if vol.lower() == volume_l:
                hits += 1
    return hits


def comprobar_trabajo_posicion_minimo_consecutivo_no_regex(
    turnos: list[str], parametros
) -> float:
    p = 0.0
    p_min = parametros.getTiempoPosMin() // parametros.getTamanoSlots()
    for turno in turnos:
        t1 = 0
        cnt = 0
        prev = None
        for slot in _slots(turno):
            is_rest = slot in REST_SLOTS
            if is_rest and cnt == 0:
                pass
            elif is_rest and cnt < p_min:
                p += 1 if t1 == 0 else 0.05
                t1 = 1
            elif is_rest and cnt >= p_min:
                cnt = 0
            elif not is_rest:
                if prev is None:
                    cnt += 1
                elif slot == prev:
                    cnt += 1
                elif cnt == 0:
                    cnt += 1
                elif cnt < p_min:
                    p += 1 if t1 == 0 else 0.05
                    t1 = 1
                    cnt = 1
                else:
                    cnt = 1
            prev = slot
    return p


def comprobar_descanso_minimo_consecutivo(turnos: list[str], parametros) -> float:
    p = 0.0
    d_min = parametros.getTiempoDesMin() // parametros.getTamanoSlots()
    for turno in turnos:
        t1 = 0
        cnt = 0
        for slot in _slots(turno):
            if slot == STRING_DESCANSO:
                cnt += 1
            else:
                if cnt < d_min and cnt != 0 and slot != STRING_NO_TURNO:
                    p += 1 if t1 == 0 else 0.05
                    t1 = 1
                cnt = 0
    return p


def comprobar_trabajo_minimo_consecutivo(turnos: list[str], parametros) -> float:
    p = 0.0
    t_min = parametros.getTiempoTrabMin() // parametros.getTamanoSlots()
    for turno in turnos:
        cnt = 0
        t1 = 0
        for slot in _slots(turno):
            if slot not in REST_SLOTS:
                cnt += 1
            else:
                if cnt < t_min and cnt != 0:
                    p += 1 if t1 == 0 else 0.05
                    t1 = 1
                cnt = 0
        if cnt < t_min and cnt != 0:
            p += 1 if t1 == 0 else 0.05
    return p


def comprobar_turno_vacio(individuo) -> int:
    p = 0
    for turno in individuo.getTurnos():
        work = 0
        rest = 0
        for slot in _slots(turno):
            if slot == STRING_DESCANSO:
                rest += 1
            elif slot != STRING_NO_TURNO:
                work += 1
                if rest:
                    break
        if work == 0 and rest:
            p += 1
    return p


def comprobar_controlador_asignado(individuo) -> int:
    p = sum(1 for c in individuo.getControladores() if c.turno_asignado == -1)
    assigned = {c.turno_asignado for c in individuo.getControladores()}
    p += sum(1 for idx in range(len(individuo.getTurnos())) if idx not in assigned)
    return p


def comprobar_ventana_trabajo_descanso(turnos: list[str], parametros) -> float:
    p = 0.0
    ventana = (
        (parametros.getTiempoTrabMax() + parametros.getTiempoDesPorTrabajo())
        * 3
        // parametros.getTamanoSlots()
    )
    d_min = parametros.getTiempoDesPorTrabajo() // parametros.getTamanoSlots()
    t_max = parametros.getTiempoTrabMax() // parametros.getTamanoSlots()
    for turno in turnos:
        ds = tr = 0
        x = 0.0
        slots = list(_slots(turno))
        for j, slot in enumerate(slots):
            if slot == STRING_DESCANSO:
                ds += 1
            elif slot != STRING_NO_TURNO:
                tr += 1
            char_j = j * 3
            if char_j >= ventana and (ds + tr) * 3 >= ventana:
                leaving = slots[(char_j - ventana) // 3]
                if leaving == STRING_DESCANSO:
                    ds -= 1
                elif leaving != STRING_NO_TURNO:
                    tr -= 1
                if ds < d_min and tr > t_max:
                    x += PENALIZACION
        if x:
            p = p + x + 1
    return p


def comprobar_cambio_posicion(
    turnos: list[str], mapa_afinidad: dict[str, set[str]], lista_sec
) -> float:
    p = 0.0
    for turno in turnos:
        x = 0.0
        slots = list(_slots(turno))
        for current, nxt in zip(slots, slots[1:]):
            if current not in REST_SLOTS and nxt not in REST_SLOTS and current != nxt:
                if (
                    current.isupper()
                    and nxt.isupper()
                    and not comprobar_afinidad(current, nxt, mapa_afinidad)
                ):
                    x += PENALIZACION
        if x:
            p = p + 1 + x
    return p


def comprobar_afinidad(a: str, b: str, mapa_afinidad: dict[str, set[str]]) -> bool:
    return b in mapa_afinidad.get(a, set())


def comprobar_tipo_sector(individuo, entrada) -> float:
    p = 0.0
    ruta_ids = entrada._fast_ruta_ids
    for controlador in individuo.getControladores():
        if not controlador.con or controlador.turno_asignado == -1:
            continue
        x = 0.0
        turno = individuo.getTurnos()[controlador.turno_asignado]
        for slot in _slots(turno):
            ok = slot in REST_SLOTS or slot.lower() in ruta_ids
            if not ok:
                x += PENALIZACION
        if x:
            p = p + 1 + x
    return p


def comprobar_nucleo_trabajo(individuo, entrada) -> float:
    if len(entrada.getNucleosAbiertos()) == 1:
        return 0.0
    p = 0.0
    sector_ids = entrada._fast_sector_ids
    for controlador in individuo.getControladores():
        num_turno = controlador.turno_asignado
        if num_turno == -1:
            p += 1
            continue
        x = 0.0
        turno = individuo.getTurnos()[num_turno]
        for slot in _slots(turno):
            if slot not in REST_SLOTS:
                ok = slot.lower() in sector_ids
                if not ok:
                    x += PENALIZACION
        if x:
            p += 1 + x
    return p


def comprobar_controlador_turno_corto(individuo, entrada) -> float:
    p = 0.0
    resto = entrada.getTurno().getTl()[1] - entrada.getTurno().getTc()[1]
    inicio_corto = entrada.getTurno().getTc()[0]
    for controlador in individuo.getControladores():
        if controlador.turno.upper() != "TC" or controlador.turno_asignado == -1:
            continue
        turno = individuo.getTurnos()[controlador.turno_asignado]
        slots = list(_slots(turno))
        zone = slots[-resto:] if inicio_corto == 0 else slots[:inicio_corto]
        t1 = 0
        for slot in zone:
            if slot not in REST_SLOTS:
                p += 1 if t1 == 0 else 0.05
                t1 = 1
    return p


def comprobar_trabajo_maximo_consecutivo(turnos: list[str], parametros) -> float:
    p = 0.0
    t_max = parametros.getTiempoTrabMax() // parametros.getTamanoSlots()
    for turno in turnos:
        t = 0
        cnt = 0
        for slot in _slots(turno):
            if slot not in REST_SLOTS:
                cnt += 1
            else:
                if cnt > t_max:
                    if t == 0:
                        p += 1
                        p += (cnt - t_max) * 0.025
                        t = 1
                    else:
                        p += 0.2
                cnt = 0
        if cnt > t_max:
            if t == 0:
                p += 1
                p += (cnt - t_max) * 0.025
            else:
                p += 0.2
    return p


def comprobar_sectores_abiertos_noche(individuo, entrada) -> int:
    p = 0
    controladores = individuo.getControladores()
    sector_ids = entrada._fast_sector_ids
    for controlador in controladores:
        if controlador.turno_noche != 0 and controlador.turno_asignado != -1:
            turno = individuo.getTurnos()[controlador.turno_asignado]
            x = 0
            for slot in _slots(turno):
                if slot.lower() not in sector_ids:
                    x += PENALIZACION
            if x:
                p += 1
    for idx, controlador in enumerate(controladores):
        if controlador.turno_noche != 0:
            if sum(1 for c in controladores if c.turno_noche == idx) < 4:
                p += 1
    return p


def _ensure_fast_cache(entrada) -> None:
    if hasattr(entrada, "_fast_sector_ids"):
        return
    sectores = entrada.getListaSectoresAbiertos()
    entrada._fast_sector_ids = {sector.id.lower() for sector in sectores}
    entrada._fast_ruta_ids = {sector.id.lower() for sector in sectores if sector.ruta}
    entrada._fast_sector_by_id = {sector.id.lower(): sector for sector in sectores}
    entrada._fast_volumes_by_id = {
        sector_id.lower(): list(volumes)
        for sector_id, volumes in entrada.getVolumnsOfSectors().items()
    }
    entrada._fast_num_max_sectores_cache = {}


def comprobar_porcentaje_descanso(individuo, entrada, turno, parametros) -> int:
    p = 0
    slots_des_tl = turno.getSlotsDesTL()
    slots_des_tc = turno.getSlotsDesTC()
    for controlador in individuo.getControladores():
        ok = True
        num_turno = controlador.turno_asignado
        if num_turno != -1:
            assigned = individuo.getTurnos()[num_turno]
            cnt = sum(1 for slot in _slots(assigned) if slot in REST_SLOTS)
            if controlador.turno.upper() in {"TL", "ML", "N"} and slots_des_tl > cnt:
                ok = False
            elif controlador.turno.upper() in {"TC", "MC"} and slots_des_tc > cnt:
                ok = False
        if not ok or num_turno == -1:
            p += 1
    return p
