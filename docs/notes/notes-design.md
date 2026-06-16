# Bitácora de diseño — proyecto ABACO/BRKGA

Documento vivo de decisiones de diseño. Cada sección registra el **contrato** acordado entre módulos, no la implementación. Si una decisión cambia, se actualiza aquí y se anota en el §8 (change log).

---

## 1. Contexto

Tesis doctoral sobre optimización de horarios de controladores aéreos (ATCo) mediante BRKGA (Biased Random-Key Genetic Algorithm). El proyecto se reescribe desde cero conservando solo:

- Modelos de dominio (`Solucion`, `Controlador`, `Sector`, `Nucleo`, `Turno`, `Propiedades`).
- Las 14 restricciones `comprobar_*` migradas a `problem/restrictions/checks.py`.
- Carga de instancias (`problem/instance.py`) y parámetros (`problem/parameters.py`, `problem/properties.py`).
- Persistencia y logging (`io/`).

Se reescribe desde cero: generación de semillas, función objetivo, motor BRKGA, decoders, CLI y análisis.

**Convenciones globales**:

- Tamaño de slot: **5 minutos** (un día = 288 slots).
- Estados de celda: `STRING_DESCANSO = "111"`, `STRING_NO_TURNO = "000"`, o un `id` de sector.
- Minimización: todos los fitness son **menor = mejor**.
- Modo de combinación de restricciones por defecto: **paralelo** (cardinalidad de restricciones violadas).

---

## 2. Generador de semillas (`seeds/greedy.py`)

### Contrato

```python
construir_solucion_heuristica(
    entrada: Entrada,
    parametros: Parametros,
    rng: random.Random,
) -> Solucion
```

### Garantías

1. **Biyección controlador↔fila**: `sol.turnos[i]` corresponde a `sol.controladores[i]`. Los índices `0..N-1` están cubiertos exactamente una vez.
2. **Respeto de ventana de turno**: cada celda fuera de la ventana del turno del controlador es `STRING_NO_TURNO`.
3. **Respeto de licencias**:
   - Sectores con `ruta=True` solo se asignan a controladores con `CON=True`.
   - Sectores no-ruta solo a controladores cuyo núcleo los licencia (o sin restricción si el núcleo no tiene lista).
4. **`slots_trabajados` consistente**: el contador final de cada `Controlador` coincide con la cuenta real de celdas con id de sector en su fila.
5. **Diversidad**: dos llamadas con el mismo `rng` semilla distinto producen soluciones distintas.
6. **Reproducibilidad**: dos llamadas con el mismo `rng` semilla idéntico producen la misma solución.
7. **Robustez**: lanza `ValueError` si la entrada tiene 0 controladores.

### Estrategia interna

Greedy *menos-cargado-primero*. Por cada slot, se barajan los sectores abiertos y para cada uno se elige el controlador elegible con menor carga acumulada (empate roto por shuffle).

### Lo que **no** garantiza

- Cobertura completa: si en un slot no hay candidatos elegibles para un sector, queda descubierto.
- Cero violaciones de restricciones: las 14 `comprobar_*` se evalúan en `fitness`, no aquí.
- `longdescansos` rellenado: se deja en `0` como sentinela, lo calcula el fitness.

---

## 3. Función objetivo (`fitness/`)

### Decisiones cerradas

| ID | Decisión | Valor |
|---|---|---|
| D1 | Forma de la objetivo | Escalar a minimizar |
| D2 | Términos | $R$ (restricciones), $C$ (cobertura), $B$ (balance), $F$ (fragmentación), $L$ (descansos largos, off por defecto) |
| D3 | Modo de combinación de restricciones | `paralelo` (cardinalidad) |
| D4 | Normalización | Cada término a $[0,1]$ y luego ponderación |
| D5 | Tipo de retorno | `FitnessResult` con desglose; `__float__` devuelve el escalar |

### Definición formal de cada componente

| Símbolo | Mide | Fórmula cruda | Normalización |
|---|---|---|---|
| $R(s)$ | restricciones violadas | $\lvert\{i \in [1..14] : \text{comprobar}_i(s) > 0\}\rvert$ | $/14$ |
| $C(s)$ | cobertura insatisfecha | $\sum_t \lvert\text{sectores\_abiertos}(t) \setminus \text{cubiertos}(s,t)\rvert$ | $/\sum_t \lvert\text{sectores\_abiertos}(t)\rvert$ |
| $B(s)$ | desbalance de carga | $\max_i \text{slots\_trabajados}_i - \min_i \text{slots\_trabajados}_i$ | $/T$ |
| $F(s)$ | fragmentación trabajo↔descanso | $\sum_i \#\{t \in \text{ventana}_i : \text{estado}(i,t) \neq \text{estado}(i,t{+}1)\}$ | $/\sum_i (\lvert\text{ventana}_i\rvert - 1)$ |
| $L(s)$ | descansos largos *(off por defecto)* | $\sum_i \#\{\text{rachas de "111" con longitud} \geq u\}$ | $/N$ |

Definición de **estado** (para $F$): dentro de la ventana del turno, una celda es `TRABAJO` si contiene un id de sector, o `DESCANSO` si es `STRING_DESCANSO`. Las celdas `STRING_NO_TURNO` son `FUERA` y se ignoran.

### Combinación

$$
\text{fitness}(s) = \alpha_R \tilde R + \alpha_C \tilde C + \alpha_B \tilde B + \alpha_F \tilde F + \alpha_L \tilde L
$$

### Pesos y parámetros por defecto

| Parámetro | Valor | Configurable desde |
|---|---|---|
| $\alpha_R$ | 0.45 | `.properties` |
| $\alpha_C$ | 0.30 | `.properties` |
| $\alpha_B$ | 0.15 | `.properties` |
| $\alpha_F$ | 0.10 | `.properties` |
| $\alpha_L$ | 0.00 | `.properties` |
| $u$ (umbral $L$) | 18 slots (90 min) | `.properties` |

Validación: el constructor de `FitnessConfig` exige $\sum \alpha_i = 1 \pm \varepsilon$ y $\alpha_i \geq 0$.

### Contrato de `FitnessResult`

```python
@dataclass(frozen=True)
class FitnessResult:
    valor: float                          # escalar a minimizar
    componentes: dict[str, float]         # normalizados, claves: "R","C","B","F","L"
    crudos: dict[str, float]              # antes de normalizar, mismas claves
    restricciones_violadas: list[str]     # nombres de las comprobar_* violadas

    def __float__(self) -> float:
        return self.valor
```

### Estructura de módulos

```
src/atco/fitness/
├── __init__.py        # reexporta evaluar_fitness, FitnessResult, FitnessConfig
├── components.py      # R, C, B, F, L como funciones puras
├── objective.py       # evaluar_fitness(s, entrada, parametros, config) -> FitnessResult
└── config.py          # FitnessConfig: pesos + umbral + validación
```

### Coste

$\mathcal{O}(N \cdot T)$ por componente más el coste de las 14 `comprobar_*`. En `madN_M1` con $N \approx 50$, $T = 288$, el cuello de botella son las comprobaciones.

---

## 4. Integración con BRKGA

Apuntes para cuando se implemente el motor; no parte del diseño actual.

### Métricas de **rendimiento** del algoritmo (distintas del fitness)

Se almacenan en `RunResult` / `ConvergenceRecord`, **nunca** en `FitnessResult`:

- `elapsed_seconds`: wall-clock total.
- `n_evaluations`: nº de llamadas a `evaluar_fitness`.
- `n_generations`: generaciones hasta parada.
- `best_history`: lista de `(generation, best_fitness, componentes)` para plots.
- `seed_fitness`, `final_fitness`: ganancia absoluta del BRKGA sobre la semilla.
- `mejora_relativa = (seed - final) / seed`.
- Para K corridas: $\bar f \pm \sigma$ del best fitness (robustez) y tasa de éxito a umbral.

### Codificación bin-midpoint

Pendiente de cerrar el contrato en §5 (D6).

---

## 5. Decisiones pendientes

| ID | Tema | Opciones | Estado |
|---|---|---|---|
| D6 | Esquema de codificación cromosoma↔Solucion | bin-midpoint vs permutación implícita | Abierta |
| D7 | Política de parada del BRKGA | nº generaciones / tiempo / estancamiento / combinada | Abierta |
| D8 | Calibración de pesos $\alpha_i$ | a priori vs sensitivity sweep vs AHP | A priori por ahora; sweep tras línea base |
| D9 | Modo de combinación de restricciones | `paralelo` vs `ponderada_clasica` | `paralelo` ahora; previsto migrar a `ponderada_clasica` |
| D10 | Encendido de $L$ | $\alpha_L = 0$ permanente vs activar tras línea base | Off; revisable tras experimentos |

---

## 6. Plan de tests

### Generador (`tests/unit/test_seed.py`) — cerrado

- Cobertura de la sectorización.
- Respeto de licencia `CON`.
- Respeto de ventana de turno.
- Biyección controlador↔fila.
- `slots_trabajados` consistente.
- Diversidad entre semillas distintas.
- Reproducibilidad con la misma semilla.
- Falla con controladores vacíos.

### Fitness (`tests/unit/test_fitness.py`) — pendiente

- Cada componente probado en aislamiento con un caso pasante y uno fallante.
- $R$: solución sin violaciones → $R = 0$. Solución con violación conocida → $R = 1/14$.
- $C$: solución con cobertura total → $C = 0$. Solución con un sector descubierto → valor esperado.
- $B$: cargas $[10, 10, 10]$ → $B = 0$. Cargas $[0, T]$ → $B = 1$.
- $F$: fila $[\text{S1}, \text{S1}, \text{S1}]$ → 0 transiciones. Fila $[\text{S1}, 111, \text{S1}, 111]$ → 3 transiciones.
- $L$: ninguna racha de descanso $\geq u$ → $L = 0$. Una racha = $u$ slots → $L = 1$.
- `FitnessConfig`: pesos que no suman 1 → `ValueError`.
- `FitnessResult.__float__` devuelve `valor` exacto.
- `evaluar_fitness` con $\alpha_L = 0$ produce el mismo `valor` con o sin descansos largos.

---

## 7. Referencias

- Resende, M. G. C., & Gonçalves, J. F. (2011). **BRKGA**: biased random-key genetic algorithms. *Handbook of Metaheuristics*.
- Plan original de reestructuración: ver chat con dirección de tesis (2026-06-XX).

---

## 8. Change log

| Fecha | Cambio |
|---|---|
| 2026-06-15 | §2 cerrado. Contrato del generador greedy validado por 8 tests. |
| 2026-06-15 | §3 cerrado. Decisiones D1–D5 fijadas. Componentes $R,C,B,F$ activas, $L$ en sombra. $u = 18$ slots. Pesos por defecto registrados. |
| 2026-06-15 | §5 abierto con D6–D10 para cerrar en bloques posteriores. |
| 2026-06-16 | §1: modelo refactorizado. Eliminado enum `Propiedades` y los campos `baja_alta`/`slot_alta`/`slot_baja` de `Controlador`. Introducido `VentanaDisponibilidad` (frozen, validado en `__post_init__`) como campo `disponibilidad` con default = completa. `crear_controladores` simplificado; lectura de `ModificacionRecursos_*.csv` retirada (queda para futuro). |