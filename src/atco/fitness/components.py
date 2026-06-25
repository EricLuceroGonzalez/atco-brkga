"""Componentes puras de la función objetivo: R, C, B, F, L.

Cada función recibe la solución (y la entrada/parámetros cuando aplica) y
devuelve valores **crudos**, sin normalizar. La normalización a [0, 1] y
la combinación ponderada las hace `objective.evaluar_fitness`.
"""

from __future__ import annotations

from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO
from atco.domain.models import Solucion
from atco.problem.instance import Entrada
from atco.problem.parameters import Parametros

# from atco.problem.restrictions import checks as _checks
from atco.problem.restrictions.checks import (
    _checks,
    NOMBRES_RESTRICCIONES,
    N_RESTRICCIONES,
)


def restricciones_violadas(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,
) -> list[str]:
    """Devuelve los nombres de las comprobaciones con ≥1 violación.

    Delega en `_checks(...)` del módulo `restrictions.checks`, que ya
    sabe cómo invocar cada `comprobar_*` con sus argumentos específicos
    (incluido el `Turno` para R3 o el mapa de afinidad para R8).
    """
    violaciones = _checks(solucion, entrada, parametros)
    return [
        nombre
        for nombre, violacion in zip(NOMBRES_RESTRICCIONES, violaciones, strict=True)
        if violacion > 0
    ]


def _longitud_t(solucion: Solucion) -> int:
    """Número de slots T deducido de la primera cadena.

    Cada slot ocupa 3 caracteres en la codificación (tokens como `"AAX"`,
    `"111"`, `"000"`).
    """
    if not solucion.turnos:
        return 0
    return len(solucion.turnos[0]) // 3


def _slot(cadena: str, t: int) -> str:
    """Token de 3 caracteres del slot `t` en la cadena."""
    return cadena[t * 3 : (t + 1) * 3]


def _es_trabajo(token: str) -> bool:
    """True si el token contiene un id de sector (no descanso ni fuera)."""
    return token not in (STRING_DESCANSO, STRING_NO_TURNO)


def _ventana_de_cadena(cadena: str, longitud_t: int) -> tuple[int, int]:
    """Devuelve `[a, b)`: primer slot in-ventana y siguiente al último.

    La "ventana" son los slots cuyo token no es `STRING_NO_TURNO`.
    Si la cadena está toda fuera de turno, devuelve `(0, 0)`.
    """
    a: int | None = None
    b = 0
    for t in range(longitud_t):
        if _slot(cadena, t) != STRING_NO_TURNO:
            if a is None:
                a = t
            b = t + 1
    return (0, 0) if a is None else (a, b)


def cobertura_insatisfecha(
    solucion: Solucion,
    entrada: Entrada,
    parametros: Parametros,  # noqa: ARG001
) -> tuple[int, int]:
    """Cuenta posiciones (EJ o PL) sin cubrir respetando la sectorización por slot.

    Para cada slot ``t``, la demanda de cobertura es exactamente
    ``2 · |sectores_abiertos_en(t)|`` (un ejecutivo en mayúsculas y un
    planificador en minúsculas por cada sector abierto). El método
    ``entrada.get_sectores_abiertos_en(t)`` refleja la sectorización
    **dinámica** del espacio aéreo: el número de sectores abiertos varía
    a lo largo del día según la configuración operativa.

    Convención de tokens:
      - ``sector.id.upper()`` → posición ejecutivo (EJ).
      - ``sector.id.lower()`` → posición planificador (PL).

    Args:
        solucion: Horario a evaluar (matriz codificada como cadenas de
            ``3 · T`` caracteres por fila).
        entrada: Instancia del problema; aporta ``get_sectores_abiertos_en``.
        parametros: No se consulta directamente; se acepta por
            uniformidad de signatura entre componentes.

    Returns:
        Tupla ``(crudo, cota)``:
          - ``crudo``: número total de posiciones (EJ o PL) sin cubrir,
            sumadas sobre todos los slots. Cada hueco cuenta exactamente 1.
          - ``cota``: número total de posiciones a cubrir,
            ``Σ_t 2 · |sectores_abiertos_en(t)|``. Cero si ningún sector
            está abierto en ningún slot.
    """
    cadenas = solucion.turnos
    n_filas = len(cadenas)
    T = _longitud_t(solucion)

    huecos = 0
    demanda = 0
    for t in range(T):
        abiertos_t = entrada.get_sectores_abiertos_en(t)
        demanda += 2 * len(abiertos_t)
        if not abiertos_t:
            continue

        tokens_t = {
            _slot(cadenas[i], t)
            for i in range(n_filas)
            if _es_trabajo(_slot(cadenas[i], t))
        }

        for sector in abiertos_t:
            if sector.id.upper() not in tokens_t:
                huecos += 1  # falta ejecutivo
            if sector.id.lower() not in tokens_t:
                huecos += 1  # falta planificador

    return huecos, demanda


def fragmentacion(solucion: Solucion) -> tuple[int, int, int]:
    """Cuenta bloques (trabajo|descanso) por fila dentro de su ventana de turno.

    Un *bloque* es una racha maximal de slots consecutivos en el mismo
    estado (trabajo o descanso). Un horario más compacto tiene menos
    bloques por fila — idealmente uno solo de trabajo y otro de descanso.

    Esta versión sustituye a la anterior, que contaba transiciones
    (cambios entre slots adyacentes). Ambas son linealmente equivalentes
    (``bloques = transiciones + 1`` por fila no vacía), pero la cuenta
    por bloques se interpreta mejor: responde "cuántos arranques de
    estado distintos tiene cada controlador".

    Args:
        solucion: Horario a evaluar.

    Returns:
        ``(crudo, v_min, v_max)``:
          - ``crudo``: Σ_k B_k, donde B_k es el nº de bloques en la
            ventana de la fila k.
          - ``v_min``: nº de filas con ventana no vacía (mínimo absoluto:
            cada fila aporta al menos 1 bloque).
          - ``v_max``: Σ_k (b_k − a_k), alternancia máxima slot a slot.

        La normalización a [0, 1] del orquestador será
        ``(v_max − crudo) / (v_max − v_min)`` (más compacto ⟹ mejor).
    """
    T = _longitud_t(solucion)
    crudo = 0
    v_min = 0
    v_max = 0

    for cadena in solucion.turnos:
        a, b = _ventana_de_cadena(cadena, T)
        if b - a == 0:
            continue

        v_min += 1
        v_max += b - a

        bloques = 1
        es_trabajo_prev = _es_trabajo(_slot(cadena, a))
        for t in range(a + 1, b):
            es_trabajo_curr = _es_trabajo(_slot(cadena, t))
            if es_trabajo_curr != es_trabajo_prev:
                bloques += 1
                es_trabajo_prev = es_trabajo_curr
        crudo += bloques

    return crudo, v_min, v_max


def intervalos_descanso(solucion: Solucion) -> tuple[int, int, int]:
    """Cuenta bloques de descanso por fila dentro de la ventana de turno.

    Un *bloque de descanso* es una racha maximal de slots ``"111"``
    dentro de la ventana operativa de cada controlador. La intuición de
    Tello §6.3.3.3.1: minimizar el número de descansos individuales
    fomenta agruparlos en pocos descansos largos, reduciendo "cambios
    de sala" y mejorando la legibilidad del estadillo.

    Sustituye a ``descansos_largos`` (que contaba rachas ≥ umbral). La
    nueva fórmula no necesita umbral: simplemente cuenta cuántos
    descansos hay y deja que el orquestador penalice un valor alto.

    Slots ``"000"`` (fuera-de-turno) no aparecen dentro de la ventana
    por construcción, así que sólo cuentan los ``"111"``.

    Args:
        solucion: Horario a evaluar.

    Returns:
        ``(crudo, v_min, v_max)``:
          - ``crudo``: Σ_k D_k, nº total de bloques de descanso.
          - ``v_min``: nº de filas con ventana no vacía (cada controlador
            activo debería tener al menos un descanso → mínimo 1 por
            fila).
          - ``v_max``: ``T · n_activos // 6`` siguiendo Tello (6 slots =
            mínimo trabajo + mínimo descanso, máximo teórico de
            alternancias).
    """
    T = _longitud_t(solucion)
    crudo = 0
    n_activos = 0

    for cadena in solucion.turnos:
        a, b = _ventana_de_cadena(cadena, T)
        if b - a == 0:
            continue
        n_activos += 1

        en_descanso = False
        for t in range(a, b):
            tok = _slot(cadena, t)
            es_descanso = tok == STRING_DESCANSO
            if es_descanso and not en_descanso:
                crudo += 1
                en_descanso = True
            elif not es_descanso:
                en_descanso = False

    v_min = n_activos
    v_max = (T * n_activos) // 6
    return crudo, v_min, v_max


def balance_carga(solucion: Solucion) -> tuple[float, float]:
    """Desviación estándar (poblacional) de la carga de trabajo entre controladores.

    Sustituye a ``desbalance_carga`` (que usaba ``max − min``). La σ refleja
    mejor la dispersión global cuando hay más de 2 controladores: un único
    atípico estira el rango pero apenas mueve la σ; en cambio, una
    desigualdad sistemática entre la mayoría sí la mueve.

    La cota teórica de Tello §6.3.3.4 es:

        σ_max = media(cargas)

    derivada del peor caso donde la mitad de los controladores trabaja
    ``2 × media`` y la otra mitad no trabaja nada.

    Args:
        solucion: Horario a evaluar. Requiere que cada
            ``Controlador.slots_trabajados`` esté poblado (lo hace
            ``construir_solucion_heuristica`` al final, y también los
            decoders del BRKGA).

    Returns:
        ``(sigma, sigma_max)``:
          - ``sigma``: desviación estándar poblacional de
            ``[c.slots_trabajados for c in solucion.controladores]``.
            Cero si todos trabajan lo mismo o si no hay controladores.
          - ``sigma_max``: media de las cargas (= cota máxima teórica).
            Cero si nadie trabaja, lo que el orquestador interpretará
            como ``f_balance = 1.0`` por convención (degenerado).
    """
    if not solucion.controladores:
        return (0.0, 0.0)

    cargas = [c.slots_trabajados for c in solucion.controladores]
    n = len(cargas)
    media = sum(cargas) / n

    if media == 0:
        # Nadie trabaja → todos iguales en cero → balance trivial.
        return (0.0, 0.0)

    varianza = sum((c - media) ** 2 for c in cargas) / n
    sigma = varianza**0.5

    return (sigma, media)


def acreditacion(
    solucion: Solucion,
    entrada: Entrada,
) -> tuple[int, int, int]:
    """Cuenta pares únicos (controlador, sector_elemental) cubiertos.

    Para cada controlador, identifica el conjunto de sectores elementales
    que ha cubierto al menos una vez durante el turno (al trabajar
    cualquier sector de control que los contenga). Suma sobre todos los
    controladores.

    Sólo cuentan los elementales pertenecientes a **sectores que se abren
    en algún slot del turno** (operacionalmente disponibles). Trabajar un
    sector cerrado no contribuye a la acreditación — la elección de
    cubrir un sector fuera de su ventana operacional es un problema de
    restricciones, no de acreditación.

    Convención: EJ (token en mayúsculas) y PL (token en minúsculas) del
    mismo sector aportan los mismos elementales — el elemental
    pertenece al sector, no al rol.

    Args:
        solucion: Horario a evaluar.
        entrada: Instancia del problema; aporta ``get_lista_sectores()`` y
            ``get_sectores_abiertos_en(t)``.

    Returns:
        Tupla ``(crudo, v_min, v_max)``:
          - ``crudo``: Σ_k |E_k|, donde E_k es el conjunto de elementales
            que el controlador k ha cubierto en algún slot del turno.
          - ``v_min``: N (cada controlador debería cubrir al menos 1).
          - ``v_max``: N · |E_global|, donde E_global son los elementales
            de los sectores que se abren al menos una vez en el turno.

        La normalización a [0, 1] la hace el orquestador
        (``objective.evaluar_fitness``) usando una fórmula tipo
        ``(crudo - v_min) / (v_max - v_min)`` con cap en ``crudo ≥ v_min``.
    """
    # Lookup sector_id → conjunto de sus elementales
    sector_to_elementales: dict[str, set[str]] = {
        s.id.lower(): set(s.sectores_elementales) for s in entrada.get_lista_sectores()
    }

    # Sectores operacionalmente abiertos en algún slot del turno
    T = _longitud_t(solucion)
    sectores_abiertos: set[str] = set()
    for t in range(T):
        for s in entrada.get_sectores_abiertos_en(t):
            sectores_abiertos.add(s.id.lower())

    # Elementales globalmente cubrebles (los de sectores abiertos)
    elementales_globales: set[str] = set()
    for sid in sectores_abiertos:
        elementales_globales.update(sector_to_elementales.get(sid, set()))

    n_atcos = len(solucion.turnos)
    n_elementales = len(elementales_globales)

    # Conteo crudo
    crudo = 0
    for cadena in solucion.turnos:
        cubiertos_k: set[str] = set()
        for t in range(T):
            tok = _slot(cadena, t)
            if not _es_trabajo(tok):
                continue
            sector_id = tok.lower()
            if sector_id in sectores_abiertos:
                cubiertos_k.update(sector_to_elementales.get(sector_id, set()))
        crudo += len(cubiertos_k)

    return (crudo, n_atcos, n_atcos * n_elementales)


def tiempo_optimo_posicion(
    solucion: Solucion,
    parametros: Parametros,
    pos_opt_min: int = 45,
    pos_min_min: int = 15,
) -> tuple[float, float]:
    """Suma promediada de desviaciones del tiempo óptimo en la misma posición.

    Para cada controlador y cada bloque de slots consecutivos en el
    mismo (sector + posición), mide |``pos_opt_min`` − duración|. Suma
    sobre todos los intervalos y divide entre el número de controladores.

    Args:
        solucion: Horario a evaluar.
        parametros: Aporta ``tamano_slots`` para convertir slots a minutos.
        pos_opt_min: Tiempo óptimo en posición, en minutos (Tello: 45).
        pos_min_min: Tiempo mínimo legal en posición, en minutos (15).

    Returns:
        ``(crudo, cota)``:
          - ``crudo``: media (por controlador) de la suma de desviaciones
            absolutas, en minutos.
          - ``cota``: cota máxima teórica de Tello §6.3.3.1.a:
            ``|pos_opt − pos_min| · 8 · (T / 30)``.
        Para maximización, el orquestador calcula
        ``f = (cota − crudo) / cota``.
    """
    if not solucion.turnos:
        return (0.0, 0.0)

    T = _longitud_t(solucion)
    n_atcos = len(solucion.turnos)
    slot_min = parametros.tamano_slots

    suma_desviaciones = 0.0
    for cadena in solucion.turnos:
        for inicio, fin, _tok in _intervalos_misma_posicion(cadena, T):
            duracion_min = (fin - inicio) * slot_min
            suma_desviaciones += abs(pos_opt_min - duracion_min)

    crudo = suma_desviaciones / n_atcos
    cota = abs(pos_opt_min - pos_min_min) * 8 * (T / 30)
    return (crudo, cota)


def tiempo_optimo_trabajo(
    solucion: Solucion,
    parametros: Parametros,
    trab_opt_min: int = 90,
    trab_min_min: int = 15,
) -> tuple[float, float]:
    """Suma promediada de desviaciones del tiempo óptimo entre descansos.

    Para cada controlador y cada bloque de trabajo continuo (cualquier
    sector/posición, hasta el siguiente descanso o fin de ventana), mide
    |``trab_opt_min`` − duración|. Suma sobre intervalos y divide entre N.

    Args:
        solucion: Horario a evaluar.
        parametros: Aporta ``tamano_slots``.
        trab_opt_min: Trabajo continuo óptimo, en minutos (Tello: 90).
        trab_min_min: Trabajo mínimo sin violación, en minutos (15).

    Returns:
        ``(crudo, cota)`` con cota Tello §6.3.3.1.b:
        ``|trab_opt − trab_min| · (T / 6)``.
    """
    if not solucion.turnos:
        return (0.0, 0.0)

    T = _longitud_t(solucion)
    n_atcos = len(solucion.turnos)
    slot_min = parametros.tamano_slots

    suma_desviaciones = 0.0
    for cadena in solucion.turnos:
        for inicio, fin in _intervalos_trabajo(cadena, T):
            duracion_min = (fin - inicio) * slot_min
            suma_desviaciones += abs(trab_opt_min - duracion_min)

    crudo = suma_desviaciones / n_atcos
    cota = abs(trab_opt_min - trab_min_min) * (T / 6)
    return (crudo, cota)


def porcentaje_ejecutivo(
    solucion: Solucion,
    pct_min: float = 0.40,
    pct_max: float = 0.60,
) -> tuple[float, float]:
    """Suma de penalizaciones por desbalance EJ/PL fuera del rango deseado.

    Para cada controlador con al menos un slot trabajado, calcula la
    fracción ``pEje_k = slots_EJ_k / slots_trabajo_k``. Si está fuera del
    rango ``[pct_min, pct_max]``, suma la distancia al borde más cercano.
    Controladores que no trabajaron se excluyen de la cuenta y de la cota.

    Convención de tokens: EJ ⇔ token en mayúsculas; PL ⇔ minúsculas.

    Args:
        solucion: Horario a evaluar.
        pct_min: Fracción mínima de EJ deseada (Tello: 0.40).
        pct_max: Fracción máxima de EJ deseada (Tello: 0.60).

    Returns:
        ``(crudo, cota)``:
          - ``crudo``: Σ_k δ_k, con
            δ_k = max(0, pct_min − pEje_k, pEje_k − pct_max).
          - ``cota``: ``max(pct_min, 1 − pct_max) · n_activos``,
            penalización máxima posible.
    """
    if not solucion.turnos:
        return (0.0, 0.0)

    T = _longitud_t(solucion)
    crudo = 0.0
    n_activos = 0

    for cadena in solucion.turnos:
        slots_ej = 0
        slots_pl = 0
        for t in range(T):
            tok = _slot(cadena, t)
            if not _es_trabajo(tok):
                continue
            if tok.isupper():
                slots_ej += 1
            else:
                slots_pl += 1

        slots_total = slots_ej + slots_pl
        if slots_total == 0:
            continue  # no trabajó, se excluye

        n_activos += 1
        pct_eje = slots_ej / slots_total

        if pct_eje < pct_min:
            crudo += pct_min - pct_eje
        elif pct_eje > pct_max:
            crudo += pct_eje - pct_max
        # else: dentro de [pct_min, pct_max], no penaliza

    max_delta = max(pct_min, 1.0 - pct_max)
    cota = max_delta * n_activos
    return (crudo, cota)


def _intervalos_misma_posicion(cadena: str, T: int) -> list[tuple[int, int, str]]:
    """Devuelve los intervalos maximales de trabajo en la misma (sector + posición).

    Un *intervalo de misma posición* es una racha de slots consecutivos donde
    el controlador trabaja **exactamente el mismo token** (mismo sector y
    misma posición ejecutivo/planificador). Cualquier cambio de token —
    cambio de sector, cambio de rol, o entrada en descanso/fuera-de-turno —
    cierra el intervalo.

    Args:
        cadena: Fila completa de la matriz (string de longitud ``T*3``).
        T: Número de slots de la fila.

    Returns:
        Lista de tuplas ``(slot_inicio, slot_fin_exclusivo, token)`` ordenadas
        cronológicamente. El intervalo es ``[slot_inicio, slot_fin_exclusivo)``
        — es decir, su duración en slots es ``slot_fin_exclusivo - slot_inicio``.
        Los slots de descanso (``"111"``) y fuera-de-turno (``"000"``) **no**
        aparecen en la lista.

    Ejemplo:
        >>> _intervalos_misma_posicion("aaaaaaaab111aaa", 5)
        [(0, 2, 'aaa'), (2, 3, 'aab'), (4, 5, 'aaa')]
    """
    intervalos: list[tuple[int, int, str]] = []
    inicio: int | None = None
    token_actual: str | None = None

    for t in range(T):
        tok = _slot(cadena, t)
        if not _es_trabajo(tok):
            # Cierre forzado por descanso o fuera-de-turno
            if inicio is not None:
                intervalos.append((inicio, t, token_actual))
                inicio = None
                token_actual = None
            continue

        if inicio is None:
            # Arranque de intervalo nuevo
            inicio = t
            token_actual = tok
        elif tok != token_actual:
            # Cambio de token → cierra el anterior y abre uno nuevo
            intervalos.append((inicio, t, token_actual))
            inicio = t
            token_actual = tok
        # else: continuación del mismo token, no se hace nada

    # Cierre del último intervalo si quedó abierto hasta el final
    if inicio is not None:
        intervalos.append((inicio, T, token_actual))

    return intervalos


def _intervalos_trabajo(cadena: str, T: int) -> list[tuple[int, int]]:
    """Devuelve los intervalos maximales de trabajo (cualquier sector/posición).

    Un *intervalo de trabajo* es una racha de slots consecutivos donde el
    controlador está trabajando **algo** — independientemente del sector o
    rol. Los cambios entre sectores distintos o entre EJ/PL **no** cortan
    el intervalo; sólo el descanso (``"111"``) o el fuera-de-turno (``"000"``)
    lo cierran.

    Args:
        cadena: Fila completa de la matriz (string de longitud ``T*3``).
        T: Número de slots de la fila.

    Returns:
        Lista de tuplas ``(slot_inicio, slot_fin_exclusivo)`` ordenadas
        cronológicamente. Duración del intervalo en slots:
        ``slot_fin_exclusivo - slot_inicio``.

    Ejemplo:
        >>> _intervalos_trabajo("aaaaaaaab111aab", 5)
        [(0, 3), (4, 5)]
    """
    intervalos: list[tuple[int, int]] = []
    inicio: int | None = None

    for t in range(T):
        tok = _slot(cadena, t)
        if _es_trabajo(tok) and inicio is None:
            inicio = t
        elif not _es_trabajo(tok) and inicio is not None:
            intervalos.append((inicio, t))
            inicio = None

    if inicio is not None:
        intervalos.append((inicio, T))

    return intervalos
