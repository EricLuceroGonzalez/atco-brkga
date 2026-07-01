"""Generador heurístico greedy con asignación al ATCo menos cargado.

Este módulo implementa el primer generador de la tesis: un constructor
voraz que recorre la sectorización slot a slot y asigna cada sector
abierto al controlador disponible con menor carga acumulada hasta el
momento. Esta política produce horarios equilibrados y operativamente
sensatos, perfectos como semilla del BRKGA.

Referencia: ``docs/thesis/notes-design.md`` §2.4.
"""

from __future__ import annotations

import logging
import random

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Controlador, Nucleo, Sector, Solucion, Turno
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

log = logging.getLogger(__name__)


def construir_solucion_heuristica(
    entrada: Entrada,
    parametros: Parametros,
    rng: random.Random | None = None,
    prioridad_atco: list[float] | None = None,
    prioridad_sectores: dict[str, float] | None = None,
    prioridad_rotacion: list[float] | None = None,
    # offsets_atcos: list[int] | None = None,
) -> Solucion:
    """Construye una solución factible por heurística greedy al ATCo menos-cargado.

    Recorre cada slot del día y, para cada sector abierto en ese slot,
    asigna el controlador elegible con menor carga acumulada hasta el
    momento. Los empates entre candidatos con la misma carga se rompen
    aleatoriamente usando el `rng` proporcionado: esto permite que `N`
    llamadas con semillas distintas produzcan `N` soluciones distintas,
    requisito necesario para diversificar la población inicial del BRKGA.

    El generador respeta tres invariantes operativas:

    * **Licencia**: un controlador CON sólo se asigna a sectores ruta;
      todo controlador sólo trabaja sectores de su núcleo.
    * **Ventana de turno**: los slots fuera de la ventana laboral del
      controlador (TC vs TL/N) quedan marcados con ``STRING_NO_TURNO``.
    * **Fila única**: cada controlador a su propia fila del horario
      vía ``turno_asignado``.

    No garantiza otras restricciones operativas (trabajo continuo mínimo,
    cambios entre sectores afines, ventana 2h30 con 30 min descanso, etc.).
    Estas quedan como espacio de mejora para el solver y como términos
    penalizables en el fitness.

    Args:
        entrada: Instancia del problema (sectorización, controladores,
            núcleos, turno, distribución inicial).
        parametros: Parámetros del dominio. Se acepta para uniformidad
            con el resto de la API; el generador greedy actual no lo
            usa, pero versiones futuras pueden consultarlo.
        rng: Generador aleatorio para reproducibilidad. Si es ``None``,
            se instancia un ``random.Random()`` nuevo (no reproducible).
        prioridad_atco: Vector opcional de prioridades por controlador,
            normalmente `chromosome` del BRKGA. Si se proporciona, se
            usa como **tiebreaker** tras ordenar por `slots_trabajados`
            (mayor prioridad gana el empate). Si es None, se usa shuffle
            aleatorio para romper empates.
    Returns:
        ``Solucion`` con la matriz de turnos completa, los controladores
        clonados con su ``turno_asignado`` y ``slots_trabajados``
        poblados, y ``longdescansos = 0``.

    Raises:
        ValueError: Si ``entrada.get_sectorizacion()`` está vacía o si
            ``entrada.get_controladores()`` no tiene al menos un
            controlador.
    """
    if rng is None:
        rng = random.Random()

    atcos: list[Controlador] = [c.clone() for c in entrada.get_controladores()]
    sectorizacion: list[set[str]] = entrada.get_sectorizacion()
    n_atcos: int = len(atcos)  # Cantidad de atcos
    n_slots: int = len(sectorizacion)  # Cantidad de atcos
    log.debug(
        "✅ dentro de construir_solucion_heuristica() N = %d, T = %d",
        n_atcos,
        n_slots,
    )

    if n_atcos == 0:
        raise ValueError("entrada.get_controladores() está vacío")
    if n_slots == 0:
        raise ValueError("entrada.get_sectorizacion() está vacía")

    # Tabla turnos × slots inicializada con `STRING_NO_TURNO` (fuera de turno '000').
    matriz: list[list[str]] = [[STRING_NO_TURNO] * n_slots for _ in range(n_atcos)]

    # Marca los slots dentro de la ventana de cada controlador como
    # `STRING_DESCANSO (111)` por defecto: luego sólo se trabaja
    # sobre estas celdas, nunca las de `STRING_NO_TURNO`.
    _marcar_ventana_de_turno(matriz, atcos, entrada)  # Inicialización de la matriz

    # Caches de licencia para evaluación por par (ATCo, sector).
    ruta_ids, nucleo_a_sectores = _cachear_licencias(entrada)

    log.debug("✅ ruta_ids: %s", ruta_ids)
    log.debug("✅ nucleo_a_sectores: %s", nucleo_a_sectores)

    # Carga acumulada por controlador, paralelo a `atcos`.
    # Inicializar el contador de carga de trabajo (cada idx del vector es un atco)
    slots_trabajados: list[int] = [0] * n_atcos
    consecutivos: list[int] = [0] * n_atcos  # slots seguidos trabajando
    descanso_pendiente: list[int] = [0] * n_atcos  # slots de descanso obligatorio

    # ── NUEVO: contadores de tiempo en posición ─────────────────────────
    # `slots_en_posicion[i]` cuenta cuántos slots seguidos lleva el ATCo
    # `i` en su (sector, posición) actual. Se resetea cuando rota o descansa.
    slots_en_posicion: list[int] = [0] * n_atcos
    # `target_pos_slots[i]` es el umbral aleatorio (centrado en
    # `optimo_posicion`) tras el cual se fuerza a la fase 2 para que rote.
    # Se sortea al entrar en una nueva posición.
    target_pos_slots: list[int] = [0] * n_atcos

    maximo_consecutivo: int = parametros.tiempo_trab_max // parametros.tamano_slots
    minimo_consecutivo: int = parametros.tiempo_des_por_turno // parametros.tamano_slots
    optimo_posicion: int = (
        parametros.tiempo_pos_opt // parametros.tamano_slots
    )  # 45/5 = 9
    log.debug("✅ Tiempo tiempo_des_por_turno: %d", parametros.tiempo_des_por_turno)

    # Jitter alrededor del óptimo. ±2 slots = ±10 min. Configurable.
    JITTER_POSICION: int = 2
    UMBRAL_ROTACION_CROMOSOMA: float = 0.3

    def _sortear_target_posicion() -> int:
        """Devuelve un umbral aleatorio centrado en `optimo_posicion`.

        Permite variabilidad entre bloques: ATCos distintos rotan a tiempos
        ligeramente diferentes y semillas con `rng` distinto producen
        soluciones estructuralmente diferentes.
        """
        return optimo_posicion + rng.randint(-JITTER_POSICION, JITTER_POSICION)

    # Recorrido cronológico, asignando sectores al ATCo
    # 1. menos cargado y 2. asegurando pareja ejecutivo/planificador.
    for t in range(n_slots):
        sectores_t = list(entrada.get_sectores_abiertos_en(t))
        log.debug("✅ Slot # %d", t)
        log.debug("trabs: %s", list(slots_trabajados))
        log.debug("consc: %s", list(consecutivos))
        log.debug("desca: %s", list(descanso_pendiente))
        if prioridad_sectores is not None:
            # Sectores ordenados según el vector de llaves aleatorias
            sectores_t.sort(key=lambda s: -prioridad_sectores.get(s.id, 0.0))
        else:
            # Aleatorio
            rng.shuffle(sectores_t)

        # Primer bucle
        pendientes: list[tuple[Sector, str]] = []
        rotados_de: dict[tuple[str, str], set[int]] = {}
        for sector_t in sectores_t:
            # TODO: Cuando t = 24 se atienden solo 6 sectores.
            # TODO: Desestimar las dos horas continuas de trabajo
            # Para cada sector en slot se recorren las posiciones EJ y PL
            for posicion in ("EJ", "PL"):
                # Se crean los ids en mayúscula y minúscula
                token = sector_t.id.upper() if posicion == "EJ" else sector_t.id.lower()
                if t == 0:
                    log.debug(
                        "✅ t = %d,  pos = %s, sec = %s", t, posicion, sector_t.nombre
                    )
                    pendientes.append((sector_t, posicion))
                    continue
                # Se verifica el atco en sector anterior en este slot para este sector
                i_prev = _atco_en_slot_anterior(matriz, t - 1, token)

                if i_prev is not None:
                    log.debug("✅ i_prev = %d en %s", i_prev, token)
                if i_prev is None:
                    log.debug("✅ i_prev = NO HAY ANTERIOR en %s", token)
                atco_puede = (
                    i_prev is not None
                    and _puede_continuar(i_prev, t, matriz)
                    and descanso_pendiente[i_prev] == 0
                    and consecutivos[i_prev] < maximo_consecutivo
                )
                if atco_puede and i_prev is not None:
                    # Razón 1: ha pasado el óptimo de tiempo en esta posición
                    target = target_pos_slots[i_prev]
                    if target > 0 and slots_en_posicion[i_prev] >= target:
                        atco_puede = False
                        rotados_de.setdefault((sector_t.id, posicion), set()).add(
                            i_prev
                        )
                        log.debug(
                            "    🔀 i_prev=%d sale por óptimo (slots_pos=%d >= target=%d)",
                            i_prev,
                            slots_en_posicion[i_prev],
                            target,
                        )
                    # Razón 2: el cromosoma le ha asignado baja prioridad de
                    # continuidad → forzar rotación temprana
                    elif (
                        prioridad_rotacion is not None
                        and prioridad_rotacion[i_prev] < UMBRAL_ROTACION_CROMOSOMA
                    ):
                        atco_puede = False
                        rotados_de.setdefault((sector_t.id, posicion), set()).add(
                            i_prev
                        )
                        log.debug(
                            "    🔀 i_prev=%d sale por cromosoma (prioridad_rotacion=%.3f < %.3f)",
                            i_prev,
                            prioridad_rotacion[i_prev],
                            UMBRAL_ROTACION_CROMOSOMA,
                        )
                if atco_puede:
                    matriz[i_prev][t] = token
                    slots_trabajados[i_prev] += 1
                    consecutivos[i_prev] += 1
                    slots_en_posicion[i_prev] += 1
                    if consecutivos[i_prev] >= maximo_consecutivo:
                        descanso_pendiente[i_prev] = minimo_consecutivo
                    log.debug(
                        "     ✅ i_prev puede en [%d][%d]: %s [trab: %d, cons: %d]",
                        i_prev,
                        t,
                        token,
                        slots_trabajados[i_prev],
                        consecutivos[i_prev],
                    )
                else:
                    pendientes.append((sector_t, posicion))

        log.debug("✅ Pendientes (%d)", len(pendientes))
        # Segundo bucle: Se elige a los pendientes para rellenar con el atco menos cargado
        for sector_t, posicion in pendientes:
            log.debug("✅ Sector: (%s)", sector_t.id)
            excluidos = rotados_de.get((sector_t.id, posicion), set())
            candidatos = [
                i
                for i in range(n_atcos)
                if matriz[i][t] == STRING_DESCANSO
                and descanso_pendiente[i] == 0
                and i not in excluidos
                and _tiene_licencia(atcos[i], sector_t.id, ruta_ids, nucleo_a_sectores)
            ]
            log.debug("✅ Pos: (%s), candidatos = %d", posicion, len(candidatos))
            if not candidatos:
                continue  # posición descubierta (sector sin atco en este slot)

            if prioridad_atco is not None:
                # Cromosoma del BRKGA como criterio primario; carga como
                # tiebreaker para preservar algo de balance natural.
                # candidatos.sort(key=lambda i: (-prioridad_atco[i], slots_trabajados[i]))
                candidatos.sort(key=lambda i: (slots_trabajados[i], -prioridad_atco[i]))
            else:
                # Greedy puro: menos cargado, shuffle como tiebreaker.
                rng.shuffle(candidatos)
                candidatos.sort(key=lambda i: slots_trabajados[i])
            # Si no hay `prioridad_atco` se elige el que menos trabajo tiene
            # Si hay `prioridad_atco` se elige el primero en el orden prioritario
            i_elegido = candidatos[0]  # posición de la fila en matriz

            token = sector_t.id.upper() if posicion == "EJ" else sector_t.id.lower()
            log.debug("✅ Elegido: (%d) en %d, sector: %s", i_elegido, t, token)
            matriz[i_elegido][t] = token
            slots_trabajados[i_elegido] += 1
            consecutivos[i_elegido] += 1
            slots_en_posicion[i_elegido] = 1
            target_pos_slots[i_elegido] = _sortear_target_posicion()
            if consecutivos[i_elegido] >= maximo_consecutivo:
                descanso_pendiente[i_elegido] = minimo_consecutivo

        # Quienes no fueron asignados en este slot descansan: reseteamos
        # su contador de consecutivos y descontamos el descanso pendiente.
        for i in range(n_atcos):
            cell = matriz[i][t]
            if cell in (STRING_DESCANSO, STRING_NO_TURNO):
                consecutivos[i] = 0
                slots_en_posicion[i] = 0
                target_pos_slots[i] = 0
                if descanso_pendiente[i] > 0:
                    descanso_pendiente[i] -= 1
            # si i_pl is None: PL queda descubierto (lo registra el fitness)

    # Instanciar filas de matriz en los atco y construir Solucion final.
    turnos_strings: list[str] = ["".join(fila) for fila in matriz]
    for c_idx, controlador in enumerate(atcos):
        controlador.turno_asignado = c_idx
        controlador.slots_trabajados = slots_trabajados[c_idx]
    log.debug("ATCos = %s", [i.slots_trabajados for i in atcos])
    # Al final de construir_solucion_heuristica, antes de retornar:
    tokens_validos_lower = {s.id.lower() for s in entrada.get_lista_sectores()}
    for k, fila in enumerate(matriz):
        for t, tok in enumerate(fila):
            if tok in (STRING_DESCANSO, STRING_NO_TURNO):
                continue
            if tok.lower() not in tokens_validos_lower:
                raise RuntimeError(
                    f"Token desconocido '{tok}' en fila={k}, slot={t}. "
                    f"No pertenece a entrada.get_lista_sectores()."
                )
    return Solucion(
        turnos=turnos_strings,
        controladores=atcos,
        longdescansos=0,  # cuántos descansos largos tiene la solución
    )


def _marcar_ventana_de_turno(
    matriz: list[list[str]],
    atcos: list[Controlador],
    entrada: Entrada,
) -> None:
    """Marca cada celda como ``STRING_DESCANSO`` si el controlador puede trabajar en ese slot.

    Combina dos restricciones:

    - **Ventana de turno**: depende del tipo de turno del controlador
      (corta ``TC``/``MC`` o larga ``TL``/``ML``/``N``).
    - **Ventana de disponibilidad** (`c.disponibilidad`): restricción
      estratégica del plan de turnos (alta tardía, baja temprana,
      ambas, o completa por defecto).

    Las celdas fuera de cualquiera de las dos quedan como
    ``STRING_NO_TURNO`` (el valor por defecto de la matriz).
    """
    turno: Turno = entrada.turno
    ventana_corta: list[int] = turno.get_tc()
    ventana_larga: list[int] = turno.get_tl()
    n_slots: int = len(matriz[0]) if matriz else 0

    # TODO: toma todo el turno como disponibilidad del atco. Verificar.
    for i, c in enumerate(atcos):
        es_corto = c.turno in ("TC", "MC")
        ventana = ventana_corta if es_corto else ventana_larga
        inicio = max(0, ventana[0])
        fin = min(n_slots, ventana[1])
        for t in range(inicio, fin):
            if c.disponibilidad.contiene(t):
                matriz[i][t] = STRING_DESCANSO
            # else: queda STRING_NO_TURNO por default


def _cachear_licencias(entrada: Entrada) -> tuple[set[str], dict[str, set[str]]]:
    """Precalcula las estructuras de búsqueda para chequeos de licencia.

    Returns:
        Tupla ``(ruta_ids, nucleo_a_sectores)`` donde:

        * ``ruta_ids``: conjunto de IDs (en minúsculas) de los sectores
          marcados como ``ruta=True``. Lo consulta el chequeo CON.
        * ``nucleo_a_sectores``: mapeo ``nombre_núcleo_lower --> set de
          IDs de sector pertenecientes a ese núcleo``. Lo consulta el
          chequeo de núcleo.
    """
    ruta_ids: set[str] = {
        s.id.lower() for s in entrada.get_lista_sectores() if s.ruta
    }  # Si el sector del slot s es ruta se anota.

    # Registra los ids de los sectores de un núcleo
    nucleo_a_sectores: dict[str, set[str]] = {}
    nucleos: list[Nucleo] = entrada.get_nucleos_abiertos()
    for nucleo in nucleos:
        sectores_del_nucleo: list[Sector] = nucleo.get_sectores()
        nucleo_a_sectores[nucleo.nombre.lower()] = {
            s.id.lower() for s in sectores_del_nucleo
        }
    return ruta_ids, nucleo_a_sectores


def _elegir_atco_menos_cargado(
    *,
    sector_t: str,
    t: int,
    controladores: list[Controlador],
    matriz: list[list[str]],
    slots_trabajados: list[int],
    asignados_en_t: set[int],
    ruta_ids: set[str],
    nucleo_a_sectores: dict[str, set[str]],
    rng: random.Random,
) -> int | None:
    """Elige el ATCo con menor carga acumulada elegible para ``(sector_t, t)``.

    Un ATCo es elegible si: (a) no ha sido asignado en este mismo slot,
    (b) está dentro de su ventana de turno, (c) tiene licencia para el
    sector. Los empates por carga se rompen aleatoriamente para
    diversificar entre individuos.

    Returns:
        El índice del controlador elegido, o ``None`` si no hay candidatos.
    """
    candidatos: list[int] = []
    for c_idx, controlador in enumerate(controladores):
        if c_idx in asignados_en_t:
            continue
        if matriz[c_idx][t] == STRING_NO_TURNO:
            continue
        if not _tiene_licencia(controlador, sector_t, ruta_ids, nucleo_a_sectores):
            continue
        candidatos.append(c_idx)  # Si no viola las anteriores se le asigna sector_t

    if not candidatos:
        return None

    # Romper empates al azar: barajar candidatos antes del min() asegura
    # que el primero con carga mínima sea elegido.
    rng.shuffle(candidatos)
    return min(candidatos, key=lambda i: slots_trabajados[i])


def _elegir_pareja_ej_pl(
    candidatos: list[int],
    cargas: list[int],
    rng: random.Random,
) -> tuple[int, int | None]:
    """Selecciona ejecutivo y planificador entre los candidatos elegibles.

    Política (decisión P1 + P2 del diseño):
    - Si hay ≥ 2 candidatos: el menos cargado es EJ, el segundo menos
      cargado entre los restantes es PL. Empates se rompen al azar.
    - Si hay exactamente 1 candidato: se asigna a EJ; PL queda
      descubierto (devuelve `(i_ej, None)`).
    - Mismo controlador en EJ y PL: imposible por construcción (PL se
      elige solo entre los restantes tras quitar EJ).

    Args:
        candidatos: índices de controladores elegibles para este
            (slot, sector).
        cargas: vector `slots_trabajados` por controlador, mutable.
        rng: generador aleatorio para desempates.

    Returns:
        `(i_ej, i_pl)` con `i_pl is None` si solo hay un candidato.
    """
    if not candidatos:
        raise ValueError("Se llamó a _elegir_pareja_ej_pl con lista vacía")

    rng.shuffle(candidatos)
    candidatos.sort(
        key=lambda i: cargas[i]
    )  # sort estable: preserva random shuffle en empates

    i_ej = candidatos[0]
    if len(candidatos) == 1:
        return i_ej, None

    i_pl = candidatos[1]
    return i_ej, i_pl


def _tiene_licencia(
    controlador: Controlador,
    sector_id: str,
    ruta_ids: set[str],
    nucleo_a_sectores: dict[str, set[str]],
) -> bool:
    """Indica si ``controlador`` puede trabajar legalmente ``sector_id``.

    Aplica dos reglas:

    * Si ``controlador.con``, el sector debe ser ruta (``sector_id`` en
      ``ruta_ids``).
    * El sector debe pertenecer al núcleo del controlador. Si su núcleo
      no aparece en el mapa, se acepta por defecto (no se castiga).
    """
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
    """Devuelve el índice del controlador que tenía `token` en el slot `t_prev`, o None.

    Recorre la columna `t_prev` de la matriz buscando el token (id en
    mayúsculas si es ejecutivo, minúsculas si es planificador). Se usa
    para extender la asignación de un bloque (sector, posición) de un
    slot al siguiente.

    Args:
        matriz: matriz N×T de tokens de 3 caracteres.
        t_prev: índice del slot anterior (debe ser ≥ 0).
        token: token de 3 caracteres a buscar.

    Returns:
        Índice del controlador que tenía `token` en `t_prev`, o `None`
        si ningún controlador lo tenía.
    """
    for i, fila in enumerate(matriz):
        if fila[t_prev] == token:
            return i
    return None


def _puede_continuar(i: int, t: int, matriz: list[list[str]]) -> bool:
    """True si el controlador i puede continuar su bloque en el slot `t`.

    Por construcción, la celda `matriz[i][t]` arranca con
    ``STRING_DESCANSO`` si el controlador está en su ventana de turno
    y en su ventana de disponibilidad. Cualquier otro valor
    (``STRING_NO_TURNO`` o un id de sector) significa que no puede
    continuar: fuera de turno, fuera de disponibilidad, o ya asignado.
    """
    return matriz[i][t] == STRING_DESCANSO


def _pre_escalonar_cohortes(
    n_atcos: int,
    t_opt: int,
    d_min: int,
    descanso_pendiente: list[int],
    offsets_atcos: list[int] | None = None,  # <- NUEVO
) -> int:
    """Reparte los ATCos en cohortes desfasadas para evitar el cliff.

    Si `offsets_atcos` se proporciona (cromosoma del BRKGA), se usan esos
    offsets explícitamente. Si es None, se aplica el round-robin
    determinista por defecto.
    """
    if n_atcos == 0:
        return 0
    L = t_opt + d_min
    k = max(1, L // d_min) if d_min > 0 else 1
    stagger = L // k

    if offsets_atcos is None:
        # Round-robin determinista
        for i in range(n_atcos):
            descanso_pendiente[i] = (i % k) * stagger
    else:
        # Offsets del cromosoma
        for i in range(n_atcos):
            descanso_pendiente[i] = offsets_atcos[i] % L  # clamp defensivo
    return k
