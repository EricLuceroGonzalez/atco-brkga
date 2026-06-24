"""Generador heurístico greedy con asignación al ATCo menos cargado.

Este módulo implementa el primer generador de la tesis: un constructor
voraz que recorre la sectorización slot a slot y asigna cada sector
abierto al controlador disponible con menor carga acumulada hasta el
momento, respetando un objetivo de ciclo de trabajo de 90 minutos
(T_opt) y un techo legal de 120 minutos (T_max).

Política de bloques:
    - Cada bloque de trabajo se intenta cerrar al alcanzar T_opt si
      existe un relevo válido (soft cap).
    - Si no hay relevo, se extiende la continuidad hasta T_max como
      último recurso.
    - Tras cerrar el bloque (por T_opt voluntario o T_max forzado), el
      ATCo descansa D_min slots obligatorios.
    - Antes del bucle principal, los ATCos se reparten en k cohortes
      con stagger D_min para desincronizar la entrada/salida del
      régimen estacionario y evitar el "cliff" del slot 25.

Referencia: ``docs/thesis/notes-design.md`` §2.4.
"""

from __future__ import annotations

import logging
import random

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Controlador, Sector, Solucion, Turno
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

log = logging.getLogger(__name__)


def construir_solucion_heuristica(
    entrada: Entrada,
    parametros: Parametros,
    rng: random.Random | None = None,
    prioridad: list[float] | None = None,
    prioridad_sectores: dict[str, float] | None = None,
) -> Solucion:
    """Construye una solución factible por heurística greedy en dos fases.

    Fase 1 (continuidad): por cada sector abierto, intenta mantener al
    mismo ATCo que cubría ese sector/posición en el slot anterior.
    Aplica un soft cap: si el ATCo ha alcanzado T_opt y existe un relevo
    válido, libera al ATCo (programa su descanso) y deriva la posición a
    Fase 2. Si no hay relevo, extiende hasta T_max.

    Fase 2 (relleno): para las posiciones no cubiertas por continuidad,
    elige el ATCo con menor carga acumulada entre los elegibles. Los
    empates se rompen con `rng` (greedy puro) o con `prioridad` (cuando
    actúa como decoder del BRKGA).

    Args:
        entrada: Instancia del problema.
        parametros: Parámetros del dominio. Lee `tiempo_trab_max`,
            `tiempo_trab_opt`, `tiempo_des_por_turno` y `tamano_slots`.
        rng: Generador aleatorio para reproducibilidad. Si es ``None``,
            se instancia uno nuevo.
        prioridad: Vector opcional de prioridad por ATCo (cromosoma del
            BRKGA). Si se proporciona, se usa como criterio primario en
            Fase 2, con `slots_trabajados` como tiebreaker.
        prioridad_sectores: Mapeo opcional `sector_id -> prioridad`. Si
            se proporciona, dirige el orden de visita de los sectores en
            cada slot.

    Returns:
        `Solucion` con la matriz de turnos completa, los controladores
        con su `turno_asignado` y `slots_trabajados` poblados, y
        `longdescansos = 0`.

    Raises:
        ValueError: si la entrada no tiene controladores o sectorización.
    """
    if rng is None:
        rng = random.Random()
    atcos: list[Controlador] = [c.clone() for c in entrada.get_controladores()]
    sectorizacion: list[set[str]] = entrada.get_sectorizacion()
    n_atcos: int = len(atcos)
    n_slots: int = len(sectorizacion)
    log.debug(
        "✅ dentro de construir_solucion_heuristica() N = %d, T = %d",
        n_atcos,
        n_slots,
    )

    if n_atcos == 0:
        raise ValueError("entrada.get_controladores() está vacío")
    if n_slots == 0:
        raise ValueError("entrada.get_sectorizacion() está vacía")

    # --- Umbrales temporales en slots ---
    t_max: int = (
        parametros.tiempo_trab_max // parametros.tamano_slots
    )  # techo legal (24)
    t_opt: int = parametros.tiempo_trab_opt // parametros.tamano_slots  # objetivo (18)
    d_min: int = (
        parametros.tiempo_des_por_turno // parametros.tamano_slots
    )  # descanso obligatorio (6)
    log.debug("✅ T_max=%d  T_opt=%d  D_min=%d", t_max, t_opt, d_min)

    # --- Matriz inicial: fuera de turno '000', ventana laboral '111' ---
    matriz: list[list[str]] = [[STRING_NO_TURNO] * n_slots for _ in range(n_atcos)]
    _marcar_ventana_de_turno(matriz, atcos, entrada)

    # --- Caches de licencia ---
    ruta_ids, nucleo_a_sectores = _cachear_licencias(entrada)
    log.debug("✅ ruta_ids: %s", ruta_ids)
    log.debug("✅ nucleo_a_sectores: %s", nucleo_a_sectores)

    # --- Contadores por ATCo ---
    slots_trabajados: list[int] = [0] * n_atcos
    consecutivos: list[int] = [0] * n_atcos
    descanso_pendiente: list[int] = [0] * n_atcos

    # --- Pre-escalonamiento: reparte ATCos en k cohortes con stagger D_min ---
    k_cohortes = _pre_escalonar_cohortes(n_atcos, t_opt, d_min, descanso_pendiente)
    log.debug("✅ Pre-escalonamiento: %d cohortes", k_cohortes)

    # --- Recorrido cronológico, slot a slot ---
    for t in range(n_slots):
        sectores_t = list(entrada.get_sectores_abiertos_en(t))
        log.debug("✅ Slot # %d", t)
        log.debug("trabs: %s", list(slots_trabajados))
        log.debug("consc: %s", list(consecutivos))
        log.debug("desca: %s", list(descanso_pendiente))

        # Orden de visita de los sectores
        if prioridad_sectores is not None:
            sectores_t.sort(key=lambda s: -prioridad_sectores.get(s.id, 0.0))
        else:
            rng.shuffle(sectores_t)

        # ----- Fase 1: continuidad con soft cap -----
        pendientes: list[tuple[Sector, str]] = []
        for sector_t in sectores_t:
            for posicion in ("EJ", "PL"):
                token = sector_t.id.upper() if posicion == "EJ" else sector_t.id.lower()

                if t == 0:
                    # Sin slot anterior: todo va a Fase 2
                    pendientes.append((sector_t, posicion))
                    continue

                i_prev = _atco_en_slot_anterior(matriz, t - 1, token)
                if i_prev is None:
                    pendientes.append((sector_t, posicion))
                    continue

                # Condiciones duras para continuar
                puede_continuar = (
                    _puede_continuar(i_prev, t, matriz)
                    and descanso_pendiente[i_prev] == 0
                    and consecutivos[i_prev] < t_max
                )
                if not puede_continuar:
                    pendientes.append((sector_t, posicion))
                    continue

                # Soft cap: si ya alcanzó T_opt y hay relevo, lo soltamos
                en_zona_opcional = consecutivos[i_prev] >= t_opt
                if en_zona_opcional and _hay_relevo(
                    t,
                    sector_t.id,
                    atcos,
                    matriz,
                    descanso_pendiente,
                    ruta_ids,
                    nucleo_a_sectores,
                ):
                    descanso_pendiente[i_prev] = d_min
                    pendientes.append((sector_t, posicion))
                    log.debug(
                        "     ↪ soft cap en [%d][%d]: %s libera por relevo (cons=%d)",
                        i_prev,
                        t,
                        token,
                        consecutivos[i_prev],
                    )
                    continue

                # Extender el bloque
                matriz[i_prev][t] = token
                slots_trabajados[i_prev] += 1
                consecutivos[i_prev] += 1
                if consecutivos[i_prev] >= t_max:
                    descanso_pendiente[i_prev] = d_min
                log.debug(
                    "     ✅ continuidad en [%d][%d]: %s [trab=%d, cons=%d]",
                    i_prev,
                    t,
                    token,
                    slots_trabajados[i_prev],
                    consecutivos[i_prev],
                )

        # ----- Fase 2: relleno por menos cargado -----
        log.debug("✅ Pendientes: %d", len(pendientes))
        for sector_t, posicion in pendientes:
            candidatos = [
                i
                for i in range(n_atcos)
                if matriz[i][t] == STRING_DESCANSO
                and descanso_pendiente[i] == 0
                and _tiene_licencia(atcos[i], sector_t.id, ruta_ids, nucleo_a_sectores)
            ]
            log.debug("   ✅ Pos: %s, candidatos = %d", posicion, len(candidatos))
            if not candidatos:
                continue  # posición descubierta: el fitness penalizará

            if prioridad is not None:
                # BRKGA dirige el orden; carga como tiebreaker
                candidatos.sort(key=lambda i: (-prioridad[i], slots_trabajados[i]))
            else:
                # Greedy puro: menor carga, shuffle como tiebreaker (estable)
                rng.shuffle(candidatos)
                candidatos.sort(key=lambda i: slots_trabajados[i])

            i_elegido = candidatos[0]
            token = sector_t.id.upper() if posicion == "EJ" else sector_t.id.lower()
            log.debug("   ✅ Elegido: %d en %d -> %s", i_elegido, t, token)

            matriz[i_elegido][t] = token
            slots_trabajados[i_elegido] += 1
            consecutivos[i_elegido] += 1
            if consecutivos[i_elegido] >= t_max:
                descanso_pendiente[i_elegido] = d_min

        # ----- Cierre del slot: recuperación de no asignados -----
        for i in range(n_atcos):
            cell = matriz[i][t]
            if cell in (STRING_DESCANSO, STRING_NO_TURNO):
                consecutivos[i] = 0
                if descanso_pendiente[i] > 0:
                    descanso_pendiente[i] -= 1

    # --- Empaquetado de la Solucion ---
    turnos_strings: list[str] = ["".join(fila) for fila in matriz]
    for c_idx, controlador in enumerate(atcos):
        controlador.turno_asignado = c_idx
        controlador.slots_trabajados = slots_trabajados[c_idx]
    log.debug("ATCos = %s", [i.slots_trabajados for i in atcos])
    return Solucion(
        turnos=turnos_strings,
        controladores=atcos,
        longdescansos=0,
    )


def _pre_escalonar_cohortes(
    n_atcos: int,
    t_opt: int,
    d_min: int,
    descanso_pendiente: list[int],
) -> int:
    """Reparte los ATCos en k cohortes desfasadas para evitar el "cliff".

    Con el ciclo natural ``L = T_opt + D_min`` y ``k = L // D_min``
    cohortes, el stagger ``δ = L // k = D_min`` garantiza que en régimen
    estacionario siempre hay ``k - 1`` cohortes trabajando y exactamente
    una descansando.

    El reparto es round-robin: ATCo ``i`` va a la cohorte ``i mod k``,
    con offset inicial ``cohorte · δ``. Se siembra ``descanso_pendiente``
    para que sólo la cohorte 0 esté disponible en ``t = 0``.

    Args:
        n_atcos: número de ATCos disponibles.
        t_opt: tiempo de trabajo óptimo en slots.
        d_min: descanso mínimo continuo en slots.
        descanso_pendiente: vector mutable de descansos pendientes
            (se modifica in place).

    Returns:
        El número de cohortes ``k`` usado.
    """
    if n_atcos == 0:
        return 0
    L = t_opt + d_min
    k = max(1, L // d_min) if d_min > 0 else 1
    stagger = L // k
    for i in range(n_atcos):
        cohorte = i % k
        descanso_pendiente[i] = cohorte * stagger
    return k


def _hay_relevo(
    t: int,
    sector_id: str,
    atcos: list[Controlador],
    matriz: list[list[str]],
    descanso_pendiente: list[int],
    ruta_ids: set[str],
    nucleo_a_sectores: dict[str, set[str]],
) -> bool:
    """Indica si existe algún ATCo libre con licencia para ``sector_id`` en ``t``.

    Un ATCo es relevo válido si:
      - está dentro de su ventana de turno (celda actual = STRING_DESCANSO),
      - no tiene descanso pendiente,
      - tiene licencia (núcleo + CON⟹ruta).

    Args:
        t: slot actual.
        sector_id: id del sector a cubrir.
        atcos: lista de controladores.
        matriz: matriz N×T de tokens.
        descanso_pendiente: vector de descansos pendientes.
        ruta_ids: cache de IDs de sectores ruta.
        nucleo_a_sectores: cache de núcleos a sectores.

    Returns:
        True si existe al menos un relevo válido.
    """
    for j, c in enumerate(atcos):
        if matriz[j][t] != STRING_DESCANSO:
            continue
        if descanso_pendiente[j] != 0:
            continue
        if not _tiene_licencia(c, sector_id, ruta_ids, nucleo_a_sectores):
            continue
        return True
    return False


def _marcar_ventana_de_turno(
    matriz: list[list[str]],
    atcos: list[Controlador],
    entrada: Entrada,
) -> None:
    """Marca como ``STRING_DESCANSO`` los slots dentro de la ventana del ATCo."""
    turno: Turno = entrada.turno
    ventana_corta: list[int] = turno.get_tc()
    ventana_larga: list[int] = turno.get_tl()
    n_slots: int = len(matriz[0]) if matriz else 0

    for i, c in enumerate(atcos):
        es_corto = c.turno in ("TC", "MC")
        ventana = ventana_corta if es_corto else ventana_larga
        inicio = max(0, ventana[0])
        fin = min(n_slots, ventana[1])
        for t in range(inicio, fin):
            if c.disponibilidad.contiene(t):
                matriz[i][t] = STRING_DESCANSO


def _cachear_licencias(entrada: Entrada) -> tuple[set[str], dict[str, set[str]]]:
    """Precalcula búsquedas de licencia: ids de sectores ruta + mapa núcleo→sectores."""
    ruta_ids: set[str] = {s.id.lower() for s in entrada.get_lista_sectores() if s.ruta}
    nucleo_a_sectores: dict[str, set[str]] = {}
    for nucleo in entrada.get_nucleos_abiertos():
        nucleo_a_sectores[nucleo.nombre.lower()] = {
            s.id.lower() for s in nucleo.get_sectores()
        }
    return ruta_ids, nucleo_a_sectores


def _tiene_licencia(
    controlador: Controlador,
    sector_id: str,
    ruta_ids: set[str],
    nucleo_a_sectores: dict[str, set[str]],
) -> bool:
    """Aplica reglas CON⟹ruta + pertenencia a núcleo."""
    sid: str = sector_id.lower()
    if controlador.con and sid not in ruta_ids:
        return False
    nucleo_key: str = controlador.nucleo.lower()
    sectores_del_nucleo: set[str] | None = nucleo_a_sectores.get(nucleo_key)
    return sectores_del_nucleo is None or sid in sectores_del_nucleo


def _atco_en_slot_anterior(
    matriz: list[list[str]],
    t_prev: int,
    token: str,
) -> int | None:
    """Índice del ATCo que tenía exactamente ``token`` en el slot ``t_prev``."""
    for i, fila in enumerate(matriz):
        if fila[t_prev] == token:
            return i
    return None


def _puede_continuar(i: int, t: int, matriz: list[list[str]]) -> bool:
    """True si el ATCo i está libre en ``t`` (celda = STRING_DESCANSO)."""
    return matriz[i][t] == STRING_DESCANSO
