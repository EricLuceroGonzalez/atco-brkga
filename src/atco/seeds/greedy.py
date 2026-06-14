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
from atco.domain.models import Controlador, Nucleo, Sector, Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros


def construir_solucion_heuristica(
    entrada: Entrada,
    parametros: Parametros,
    rng: random.Random | None = None,
) -> Solucion:
    """Construye una solución factible por heurística greedy menos-cargado.

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
    * **Biyección**: cada controlador apunta a su propia fila del horario
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

    controladores: list[Controlador] = [c.clone() for c in entrada.get_controladores()]
    n_controladores: int = len(controladores)
    sectorizacion: list[set[str]] = entrada.get_sectorizacion()
    n_slots: int = len(sectorizacion)

    if n_controladores == 0:
        raise ValueError("entrada.get_controladores() está vacío")
    if n_slots == 0:
        raise ValueError("entrada.get_sectorizacion() está vacía")

    # Tabla turnos × slots inicializada con `STRING_NO_TURNO` (fuera de turno).
    matriz: list[list[str]] = [
        [STRING_NO_TURNO] * n_slots for _ in range(n_controladores)
    ]

    # Marca los slots dentro de la ventana de cada controlador como
    # `STRING_DESCANSO` por defecto: el resto del algoritmo sólo
    # sobrescribe estas celdas, nunca las de `STRING_NO_TURNO`.
    _marcar_ventana_de_turno(matriz, controladores, entrada)

    # Caches de licencia para evaluación O(1) por par (ATCo, sector).
    ruta_ids, nucleo_a_sectores = _cachear_licencias(entrada)

    # Vector de carga acumulada por controlador, paralelo a `controladores`.
    slots_trabajados: list[int] = [0] * n_controladores

    # Recorrido cronológico, asignando sectores al ATCo menos cargado.
    for t in range(n_slots):
        sectores_en_t: list[str] = sorted(sectorizacion[t])
        rng.shuffle(sectores_en_t)  # diversidad en el orden de recorrido

        asignados_en_t: set[int] = set()
        for sigma in sectores_en_t:
            elegido: int | None = _elegir_atco_menos_cargado(
                sigma=sigma,
                t=t,
                controladores=controladores,
                matriz=matriz,
                slots_trabajados=slots_trabajados,
                asignados_en_t=asignados_en_t,
                ruta_ids=ruta_ids,
                nucleo_a_sectores=nucleo_a_sectores,
                rng=rng,
            )
            if elegido is None:
                # Sector sin cubrir: ningún ATCo elegible disponible.
                # Aceptado como caso degradado; F2 lo penalizará.
                continue
            matriz[elegido][t] = sigma.upper()
            asignados_en_t.add(elegido)
            slots_trabajados[elegido] += 1

    # Publicar contadores en los controladores y construir la Solucion final.
    turnos_strings: list[str] = ["".join(fila) for fila in matriz]
    for c_idx, controlador in enumerate(controladores):
        controlador.turno_asignado = c_idx
        controlador.slots_trabajados = slots_trabajados[c_idx]

    return Solucion(
        turnos=turnos_strings,
        controladores=controladores,
        longdescansos=0,
    )


def _marcar_ventana_de_turno(
    matriz: list[list[str]],
    controladores: list[Controlador],
    entrada: Entrada,
) -> None:
    """Marca los slots dentro de la ventana laboral como ``STRING_DESCANSO``.

    El controlador con turno ``TC`` o ``MC`` opera dentro de la ventana
    corta; el resto (``TL``, ``ML``, ``N``) en la ventana larga. Fuera
    de su ventana, su celda permanece como ``STRING_NO_TURNO``.

    Muta ``matriz`` in-place.
    """
    turno = entrada.get_turno()
    ventana_corta: list[int] = turno.get_tc()  # [inicio, fin)
    ventana_larga: list[int] = turno.get_tl()
    n_slots: int = len(matriz[0]) if matriz else 0

    for c_idx, controlador in enumerate(controladores):
        es_corto: bool = controlador.turno.upper() in {"TC", "MC"}
        ventana: list[int] = ventana_corta if es_corto else ventana_larga
        inicio: int = max(0, ventana[0])
        fin: int = min(n_slots, ventana[1])
        for t in range(inicio, fin):
            matriz[c_idx][t] = STRING_DESCANSO


def _cachear_licencias(entrada: Entrada) -> tuple[set[str], dict[str, set[str]]]:
    """Precalcula las estructuras de búsqueda O(1) para chequeos de licencia.

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
    }
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
    sigma: str,
    t: int,
    controladores: list[Controlador],
    matriz: list[list[str]],
    slots_trabajados: list[int],
    asignados_en_t: set[int],
    ruta_ids: set[str],
    nucleo_a_sectores: dict[str, set[str]],
    rng: random.Random,
) -> int | None:
    """Elige el ATCo con menor carga acumulada elegible para ``(sigma, t)``.

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
        if not _tiene_licencia(controlador, sigma, ruta_ids, nucleo_a_sectores):
            continue
        candidatos.append(c_idx)

    if not candidatos:
        return None

    # Romper empates al azar: barajar candidatos antes del min() asegura
    # que el primero con carga mínima sea elegido, pero ese "primero"
    # cambia entre llamadas con `rng` distinto.
    rng.shuffle(candidatos)
    return min(candidatos, key=lambda i: slots_trabajados[i])


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
