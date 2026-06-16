"""Generador heurístico greedy con asignación al ATCo menos cargado.

Este módulo implementa el primer generador de la tesis: un constructor
voraz que recorre la sectorización slot a slot y asigna cada sector
abierto al controlador disponible con menor carga acumulada hasta el
momento. Esta política produce horarios equilibrados y operativamente
sensatos, perfectos como semilla del BRKGA.

Referencia: ``docs/thesis/notes-design.md`` §2.4.
"""

from __future__ import annotations

import random

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Controlador, Nucleo, Sector, Solucion, Turno
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


def construir_solucion_heuristica(
    entrada: Entrada,
    parametros: Parametros,
    rng: random.Random | None = None,
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

    if n_atcos == 0:
        raise ValueError("entrada.get_controladores() está vacío")
    if n_slots == 0:
        raise ValueError("entrada.get_sectorizacion() está vacía")

    # Tabla turnos × slots inicializada con `STRING_NO_TURNO` (fuera de turno '000').
    matriz: list[list[str]] = [[STRING_NO_TURNO] * n_slots for _ in range(n_atcos)]

    # Marca los slots dentro de la ventana de cada controlador como
    # `STRING_DESCANSO` por defecto: luego sólo se trabaja
    # sobre estas celdas, nunca las de `STRING_NO_TURNO`.
    _marcar_ventana_de_turno(matriz, atcos, entrada)  # Inicialización de la matriz

    # Caches de licencia para evaluación por par (ATCo, sector).
    ruta_ids, nucleo_a_sectores = _cachear_licencias(entrada)

    # Carga acumulada por controlador, paralelo a `atcos`.
    slots_trabajados: list[int] = [0] * n_atcos  # Inicializar el contador de carga

    # Recorrido cronológico, asignando sectores al ATCo menos cargado.
    for t in range(n_slots):
        sectores_en_t = list(entrada.get_lista_sectores_abiertos(t))
        rng.shuffle(sectores_en_t)  # diversidad en el orden de recorrido

        for sector_t in sectores_en_t:
            candidatos = [
                i
                for i in range(n_atcos)
                if matriz[i][t] == STRING_DESCANSO
                and _tiene_licencia(atcos[i], sector_t, ruta_ids, nucleo_a_sectores)
            ]
            if not candidatos:
                continue  # EJ y PL no cubiertos

            i_ej, i_pl = _elegir_pareja_ej_pl(candidatos, slots_trabajados, rng)

            matriz[i_ej][t] = sector_t.id.upper()
            slots_trabajados[i_ej] += 1

            if i_pl is not None:
                matriz[i_pl][t] = sector_t.id.lower()
                slots_trabajados[i_pl] += 1
            # si i_pl is None: PL queda descubierto (lo registra el fitness)

    # Instanciar contadores en los controladores y construir la Solucion final.
    turnos_strings: list[str] = ["".join(fila) for fila in matriz]
    for c_idx, controlador in enumerate(atcos):
        controlador.turno_asignado = c_idx
        controlador.slots_trabajados = slots_trabajados[c_idx]

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
        * ``nucleo_a_sectores``: mapeo ``nombre_núcleo_lower → set de
          IDs de sector pertenecientes a ese núcleo``. Lo consulta el
          chequeo de núcleo.
    """
    ruta_ids: set[str] = {
        s.id.lower() for s in entrada.get_lista_sectores_abiertos() if s.ruta
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
    )  # sort estable: preserva shuffle en empates

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
