from __future__ import annotations

from functools import lru_cache
from itertools import pairwise
from typing import Any

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO

from ...domain.models import Sector, Solucion, Turno
from ...problem.instance import Entrada
from ...problem.parameters import Parametros
from ...problem.restrictions.weights import (
    PENALIZACION,
    PESO_POR_RESTRICCION,
    REST_SLOTS,
    restricciones_no_cumplidas,
)

# =============================================================================
# CORRESPONDENCIA CON CÓDIGO JAVA
# =============================================================================
# Archivo Java:
#   - src/main/patrones/Restricciones.java
#       -> penalizacion_por_restricciones()  ≡  Restricciones.penalizacionPorRestricciones()
#       -> comprobar_restricciones_en_paralelo()  ≡  Restricciones.comprobarRestriccionesEnParalelo()
#       -> restricciones_sin_pesos()  (utilidad Python; sin equivalente directo)
#       -> Las 14 funciones de comprobación (comprobar_nucleo_trabajo, etc.)
#
# Restricciones implementadas (por orden en PESO_POR_RESTRICCION):
#   [0] comprobar_nucleo_trabajo          -> R1: acreditación de núcleo
#   [1] comprobar_tipo_sector             -> R2: acreditación de tipo (CON/PTD)
#   [2] comprobar_porcentaje_descanso     -> R3: descanso mínimo diurno
#   [3] comprobar_sectores_abiertos_noche -> R4: cobertura nocturna
# ?  [4] comprobar_trabajo_maximo_consecutivo -> R4 primera - R5: trabajo continuo máximo
# ! [5] comprobar_controlador_turno_corto -> R6: tipo de turno (TC/TL)
# ! [6] comprobar_ventana_trabajo_descanso -> (R5) R7: ventana 2h30m
# ! [7] comprobar_cambio_posicion         -> (R6) R8: cambio de posición ejecutiva
# ! [8] comprobar_trabajo_minimo_consecutivo -> (R7) R9: trabajo continuo mínimo
# ! [9] comprobar_descanso_minimo_consecutivo -> (R8) R10: descanso mínimo
# ! [10] comprobar_trabajo_posicion_minimo_consecutivo_no_regex -> (R9) R11: permanencia en posición
# ! [11] comprobar_num_maximo_sectores     -> (R10) R12: límite de sectores distintos
# ! [12] comprobar_controlador_asignado    -> (R11) R13: asignación completa
# ! [13] comprobar_turno_vacio             -> (R12) R14: trabajo mínimo
# =============================================================================
NOMBRES_RESTRICCIONES: tuple[str, ...] = (
    "comprobar_nucleo_trabajo",
    "comprobar_tipo_sector",
    "comprobar_porcentaje_descanso",
    "comprobar_sectores_abiertos_noche",
    "comprobar_trabajo_maximo_consecutivo",
    "comprobar_controlador_turno_corto",
    "comprobar_ventana_trabajo_descanso",
    "comprobar_cambio_posicion",
    "comprobar_trabajo_minimo_consecutivo",
    "comprobar_descanso_minimo_consecutivo",
    "comprobar_trabajo_posicion_minimo_consecutivo_no_regex",
    "comprobar_num_maximo_sectores",
    "comprobar_controlador_asignado",
    "comprobar_turno_vacio",
)
N_RESTRICCIONES: int = len(NOMBRES_RESTRICCIONES)


def penalizacion_por_restricciones(
    individuo: Solucion, entrada: Entrada, parametros: Parametros
) -> float:
    """Penalización ponderada con publicación del vector de violaciones.

    Idéntica a :func:`comprobar_restricciones_en_paralelo` salvo dos
    diferencias:

    1. Publica el vector de violaciones detalladas en la global
       :data:`restricciones_no_cumplidas` (índice por restricción, ver
       la tabla de la cabecera del módulo). Útil para diagnóstico
       posterior - el caller puede leer ese vector justo después.
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


def comprobar_restricciones_en_paralelo(
    individuo: Solucion, entrada: Entrada, parametros: Parametros
) -> float:
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


def restricciones_sin_pesos(
    individuo: Solucion, entrada: Entrada, parametros: Parametros
) -> float:
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


def _checks(
    individuo: Solucion, entrada: Entrada, parametros: Parametros
) -> list[float]:
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
    ensure_fast_cache(entrada)
    return [
        comprobar_nucleo_trabajo(individuo, entrada),
        comprobar_tipo_sector(individuo, entrada),
        comprobar_porcentaje_descanso(
            individuo, entrada, entrada.get_turno(), parametros
        ),
        comprobar_sectores_abiertos_noche(individuo, entrada),
        comprobar_trabajo_maximo_consecutivo(individuo.get_turnos(), parametros),
        comprobar_controlador_turno_corto(individuo, entrada),
        comprobar_ventana_trabajo_descanso(individuo.get_turnos(), parametros),
        comprobar_cambio_posicion(
            individuo.get_turnos(),
            entrada.get_mapa_afinidad(),
            entrada.get_lista_sectores(),
        ),
        comprobar_trabajo_minimo_consecutivo(individuo.get_turnos(), parametros),
        comprobar_descanso_minimo_consecutivo(individuo.get_turnos(), parametros),
        comprobar_trabajo_posicion_minimo_consecutivo_no_regex(
            individuo.get_turnos(), parametros
        ),
        comprobar_num_maximo_sectores(individuo.get_turnos(), entrada, parametros),
        comprobar_controlador_asignado(individuo),
        comprobar_turno_vacio(individuo),
    ]


def es_factible(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
) -> bool:
    """True si la solución no viola ninguna restricción dura.

    Útil para diagnóstico y para activar/desactivar la penalización en
    modo "puro" sin recalcular el desglose completo. Si necesitas el
    detalle, usa `contar_violaciones` (que devuelve también la
    información de factibilidad implícita en `sum(values) == 0`).

    Notas de rendimiento:
        Actualmente reutiliza ``_checks`` y por tanto evalúa las 14
        restricciones aunque la primera ya devuelva > 0. Si esto se
        vuelve cuello de botella en el bucle del BRKGA, refactorizar
        `_checks` para que devuelva un generador y aquí hacer
        `any(v > 0 for v in _checks_gen(...))`.
    """
    return not any(v > 0 for v in _checks(solucion, entrada, parametros))


def contar_violaciones(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
) -> dict[str, float]:
    """Conteo crudo por restricción para tracking / graficado.

    Las restricciones sin violaciones aparecen explícitamente con valor
    `0.0` para que las series temporales tengan siempre las 14 claves
    (útil al volcar a DataFrame o CSV).

    Returns:
        Dict ``{nombre_restriccion: valor_crudo}``. El valor es la
        cantidad de violaciones detectadas - entero para las
        restricciones binarias (R13, R14...) y float para las que
        acumulan micro-penalizaciones (R5, R7, R8...).
    """
    valores = _checks(solucion, entrada, parametros)
    return dict(zip(NOMBRES_RESTRICCIONES, valores, strict=True))


def _is_rest(slot: str) -> bool:
    """Indica si un token de 3 chars representa descanso o fuera-de-turno.

    Args:
        slot: Token de 3 caracteres (``STRING_DESCANSO``,
            ``STRING_NO_TURNO`` o un sector).

    Returns:
        ``True`` si el slot no representa trabajo en sector.
    """
    return slot in (STRING_DESCANSO, STRING_NO_TURNO)


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


def comprobar_num_maximo_sectores(
    turnos: list[str], entrada: Entrada, parametros: Parametros
) -> int:
    # R10 Los controladores aéreos no pueden trabajar en más de tres sectores no anes en un
    # único turno.
    p = 0
    # TODO: Verificar estos metodos en Entrada
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
        if value > parametros.get_num_sctrs_max():
            p += 1
    return p


def lista_de_sectores_turno(
    turno: str, sector_by_id: dict[str, Sector]
) -> list[Sector]:
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


def calculate(sectors: list[Any], volumes: dict[Any, Any]) -> int:
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
    volume: str, sectors: list[Any], volumes: dict[str, list[str]]
) -> int:
    hits = 0
    volume_l = volume.lower()
    for sector in sectors:
        for vol in volumes.get(sector.id.lower(), []):
            if vol.lower() == volume_l:
                hits += 1
    return hits


def comprobar_trabajo_posicion_minimo_consecutivo_no_regex(
    turnos: list[str], parametros: Parametros
) -> float:
    # R9: 15 min en sector/posición
    # Los controladores aéreos deben permanecer en el mismo sector y posición, un mínimo
    # de quince minutos, antes de poder cambiar a otro sector o posición.
    p = 0.0
    p_min = parametros.get_tiempo_pos_min() // parametros.get_tamano_slots()
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
                if prev is None or slot == prev or cnt == 0:
                    cnt += 1
                elif cnt < p_min:
                    p += 1 if t1 == 0 else 0.05
                    t1 = 1
                    cnt = 1
                else:
                    cnt = 1
            prev = slot
    return p


def comprobar_descanso_minimo_consecutivo(
    turnos: list[str], parametros: Parametros
) -> float:
    # R8: ≥15 min descanso
    p = 0.0
    d_min = parametros.get_tiempo_des_min() // parametros.get_tamano_slots()
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


def comprobar_trabajo_minimo_consecutivo(
    turnos: list[str], parametros: Parametros
) -> float:
    # R7
    p = 0.0
    t_min = parametros.get_tiempo_trab_min() // parametros.get_tamano_slots()
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


def comprobar_turno_vacio(individuo: Solucion) -> int:
    p = 0
    for turno in individuo.get_turnos():
        # R12 Ningún controlador aéreo puede descansar durante el turno completo, por lo que
        # como mínimo trabajará quince minutos.
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


def comprobar_controlador_asignado(individuo: Solucion) -> int:
    # R11
    # Los controladores aéreos (todos) deben tener un turno de trabajo asignado y todos
    # los turnos de trabajo deben estar asignados a un controlador.
    p = sum(1 for c in individuo.get_controladores() if c.turno_asignado == -1)
    assigned = {c.turno_asignado for c in individuo.get_controladores()}
    p += sum(1 for idx in range(len(individuo.get_turnos())) if idx not in assigned)
    return p


def comprobar_ventana_trabajo_descanso(
    turnos: list[str], parametros: Parametros
) -> float:
    # R5
    # Los controladores aéreos deben descansar un mínimo de treinta minutos cada dos
    # horas de trabajo. Estas no tienen porqué ser consecutivas, lo que quiere decir que, en
    # una ventana de trabajo de dos horas y media, se tiene que descansar como mínimo
    # media hora.
    p = 0.0
    ventana = (
        (parametros.get_tiempo_trab_max() + parametros.get_tiempo_des_por_turno())
        * 3
        // parametros.get_tamano_slots()
    )
    d_min = parametros.get_tiempo_des_por_turno() // parametros.get_tamano_slots()
    t_max = parametros.get_tiempo_trab_max() // parametros.get_tamano_slots()
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
    turnos: list[str], mapa_afinidad: dict[str, set[str]], lista_sec: list[Sector]
) -> float:
    # R6
    # Los cambios de los controladores entre sectores cuando se encuentran trabajando en
    # posición de ejecutivo, no están permitidos sin un descanso excepto que se produzca
    # un cambio de conguración y los sectores sean afines
    p = 0.0
    for turno in turnos:
        x = 0.0
        slots = list(_slots(turno))
        for current, nxt in pairwise(
            slots
        ):  # <- era zip(slots, slots[1:], strict=True)
            if (
                current not in REST_SLOTS
                and nxt not in REST_SLOTS
                and current != nxt
                and (
                    current.isupper()
                    and nxt.isupper()
                    and not comprobar_afinidad(current, nxt, mapa_afinidad)
                )
            ):
                x += PENALIZACION
        if x:
            p = p + 1 + x
    return p


def comprobar_afinidad(a: str, b: str, mapa_afinidad: dict[str, set[str]]) -> bool:
    return b in mapa_afinidad.get(a, set())


def comprobar_tipo_sector(individuo: Solucion, entrada: Entrada) -> float:
    # R2
    # Los controladores aéreos con acreditación CON solo pueden operar en sectores de
    # tipo ruta.
    p = 0.0
    ruta_ids = entrada._fast_ruta_ids
    for controlador in individuo.get_controladores():
        if not controlador.con or controlador.turno_asignado == -1:
            continue
        x = 0.0
        turno = individuo.get_turnos()[controlador.turno_asignado]
        for slot in _slots(turno):
            ok = slot in REST_SLOTS or slot.lower() in ruta_ids
            if not ok:
                x += PENALIZACION
        if x:
            p = p + 1 + x
    return p


def comprobar_nucleo_trabajo(individuo: Solucion, entrada: Entrada) -> float:
    # R1
    # Los controladores aéreos solo pueden operar en sectores que pertenezcan al núcleo
    # en el que estén acreditados.
    if len(entrada.get_nucleos_abiertos()) == 1:
        return 0.0
    p = 0.0
    sector_ids = entrada._fast_sector_ids
    for controlador in individuo.get_controladores():
        num_turno = controlador.turno_asignado
        if num_turno == -1:
            p += 1
            continue
        x = 0.0
        turno = individuo.get_turnos()[num_turno]
        for slot in _slots(turno):
            if slot not in REST_SLOTS:
                ok = slot.lower() in sector_ids
                if not ok:
                    x += PENALIZACION
        if x:
            p += 1 + x
    return p


def comprobar_controlador_turno_corto(individuo: Solucion, entrada: Entrada) -> float:
    # R?

    p = 0.0
    resto = entrada.get_turno().get_tl()[1] - entrada.get_turno().get_tc()[1]
    inicio_corto = entrada.get_turno().get_tc()[0]
    for controlador in individuo.get_controladores():
        if controlador.turno.upper() != "TC" or controlador.turno_asignado == -1:
            continue
        turno = individuo.get_turnos()[controlador.turno_asignado]
        slots = list(_slots(turno))
        zone = slots[-resto:] if inicio_corto == 0 else slots[:inicio_corto]
        t1 = 0
        for slot in zone:
            if slot not in REST_SLOTS:
                p += 1 if t1 == 0 else 0.05
                t1 = 1
    return p


def comprobar_trabajo_maximo_consecutivo(
    turnos: list[str], parametros: Parametros
) -> float:
    # R4 de primera aprox (pag. 27)
    p = 0.0
    t_max = parametros.get_tiempo_trab_max() // parametros.get_tamano_slots()
    for turno in turnos:
        t = 0
        cnt = 0
        for slot in _slots(turno):
            if slot not in REST_SLOTS:
                cnt += 1
            else:
                if cnt > t_max:
                    if t == 0:
                        # TODO Verificar esto
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


def comprobar_sectores_abiertos_noche(individuo: Solucion, entrada: Entrada) -> int:
    # R4
    p = 0
    controladores = individuo.get_controladores()
    # TODO: Ver esto de _fast en Entrada
    sector_ids = entrada._fast_sector_ids
    for controlador in controladores:
        if controlador.turno_noche != 0 and controlador.turno_asignado != -1:
            turno = individuo.get_turnos()[controlador.turno_asignado]
            x: float = 0.0
            for slot in _slots(turno):
                if slot.lower() not in sector_ids:
                    x += PENALIZACION
            if x:
                p += 1
    for idx, controlador in enumerate(controladores):
        if (
            controlador.turno_noche != 0
            and sum(1 for c in controladores if c.turno_noche == idx) < 4
        ):
            p += 1
    return p


def ensure_fast_cache(entrada: Entrada) -> None:
    if hasattr(entrada, "_fast_sector_ids"):
        return
    sectores = entrada.get_sectores_abiertos_todo_el_dia()
    entrada._fast_sector_ids = {sector.id.lower() for sector in sectores}
    entrada._fast_ruta_ids = {sector.id.lower() for sector in sectores if sector.ruta}
    entrada._fast_sector_by_id = {sector.id.lower(): sector for sector in sectores}
    entrada._fast_volumes_by_id = {
        sector_id.lower(): list(volumes)
        for sector_id, volumes in entrada.get_volumns_of_sectors().items()
    }
    entrada._fast_num_max_sectores_cache = {}


def comprobar_porcentaje_descanso(
    individuo: Solucion, entrada: Entrada, turno: Turno, parametros: Parametros
) -> int:
    # R3
    # Los controladores aéreos deben descansar un 25 % de su turno cuando este es un
    # turno de día (TT, TTL, TM, TML). En el turno de noche estos deben descansar
    # un 33 %.
    p = 0
    slots_des_tl = turno.get_slots_des_tl()
    slots_des_tc = turno.get_slots_des_tc()
    for controlador in individuo.get_controladores():
        ok = True
        num_turno = controlador.turno_asignado
        if num_turno != -1:
            assigned = individuo.get_turnos()[num_turno]
            cnt = sum(1 for slot in _slots(assigned) if slot in REST_SLOTS)
            if (
                controlador.turno.upper() in {"TL", "ML", "N"}
                and slots_des_tl > cnt
                or controlador.turno.upper() in {"TC", "MC"}
                and slots_des_tc > cnt
            ):
                ok = False
        if not ok or num_turno == -1:
            p += 1
    return p
