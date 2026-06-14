# Notas de diseño — Generador de población inicial y fitness

## 1 · Contexto

Este documento fija el **contrato** de dos piezas centrales del solver antes de
escribirlas:

1. **Generador heurístico de soluciones-semilla**, que produce los individuos
   que rellenan la población inicial del BRKGA.
2. **Función de fitness (esqueleto)**, que permite evaluar dichas soluciones y
   ejecutar el motor BRKGA end-to-end mientras se diseña la versión final.


### 1.1 · Posicionamiento metodológico

En la formulación BRKGA pura (Resende & Gonçalves, 2011), los individuos
iniciales son vectores `[0, 1)^k` aleatorios. Esta tesis añade un **mecanismo
de sembrado**: una fracción de la población inicial proviene de soluciones
codificadas con un heurístico operacional. Es práctica habitual en BRKGA
aplicado a problemas con muchas restricciones duras: arranca el motor con
diversidad real (los keys aleatorios) **y** con calidad operativa (las
semillas codificadas).

Las semillas **no son la población inicial**: son soluciones reales que se
codifican como cromosomas y ocupan las primeras posiciones del pool inicial.
El resto se completa con keys aleatorias.

### Generador heurístico

**Firma**:
    `construir_solucion_heuristica(entrada, parametros) -> Solucion`

```python
def construir_solucion_heuristica(
    entrada: Entrada,
    parametros: Parametros,
    rng: random.Random | None = None,
) -> Solucion    
# Devuelve una Solucion completa con turnos, controladores clonados y
# longdescansos = 0. El RNG opcional permite reproducibilidad: cada llamada
# con la misma semilla produce la misma solución.
```

**Invariantes que GARANTIZA**:

- Cobertura: cada sector abierto en cada slot tiene un ATCo asignado.
- Licencia: cada ATCo solo trabaja sectores compatibles con su `con`/`ptd`/`nucleo`.
- Turno: cada ATCo solo trabaja dentro de su ventana (tc o tl).
- Núcleo respetado	Cada ATCo solo trabaja sectores de su núcleo declarado.
- Ventana de turno	ATCo TC solo trabaja dentro de la ventana corta; TL dentro de la larga. Fuera de ventana, marca STRING_NO_TURNO.
- Biyección plantilla ↔ controladores	Cada ATCo tiene exactamente un turno_asignado con valor en [0, len(turnos)); cada fila de la matriz tiene exactamente un ATCo apuntando a ella.

**Invariantes que NO garantiza** (las pasa al fitness):

- Balance de carga entre ATCos.
- Mínimo de trabajo continuo.
- Cambios de posición con afinidad.
- Permanencia mínima en sector.

### Heurística

Greedy con asignación al ATCo menos cargado.
Para cada slot `t = 0..T-1`, para cada sector s abierto en t:
  1. Construir lista de candidatos: ATCos en ventana de turno + con licencia
  para s + no asignados aún en t.
  2. Si vacía → marcar s como STRING_DESCANSO en alguna fila (rompe
    cobertura; ver §2.5).
  3. Si no vacía → elegir el candidato con menor slots_trabajados acumulado
  hasta el momento. Empates se rompen por orden aleatorio (semilla del RNG)
  para diversificar entre individuos.
  1. Asignar y actualizar controlador.slots_trabajados += 1.
  Los ATCos no asignados en un slot que están en ventana de turno reciben
  STRING_DESCANSO. Los que están fuera de ventana reciben STRING_NO_TURNO.

## Contrato del fitness (a diseñar)

**Firma**:
    `evaluar(sol, entrada, parametros) -> dict[str, float]`

```python
    def evaluar_fitness(
    sol: Solucion,
    entrada: Entrada,
    parametros: Parametros,
) -> FitnessResult
```
Donde FitnessResult es un dataclass:
```python
@dataclass(frozen=True)
class FitnessResult:
    total: float                  # métrica que el motor BRKGA optimiza
    componentes: dict[str, float] # descomposición: {"F1": ..., "F2": ..., ...}
    feasible: bool                # True si todas las hard constraints se cumplen
```


**Devuelve**: diccionario con los Fi separados y el agregado total.