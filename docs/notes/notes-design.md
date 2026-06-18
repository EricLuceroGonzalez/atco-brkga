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

- Slot = **5 minutos** (T ≈ 99 slots para 8h15 de turno).
- Cada slot en la cadena ocupa **3 caracteres**: id de sector (3 letras) en mayúsculas (ejecutivo) o minúsculas (planificador), `"111"` (descanso), `"000"` (fuera de turno).
- Cobertura del dominio: cada sector abierto en cada slot requiere **dos posiciones** — ejecutivo (token upper, habla con pilotos) y planificador (token lower).
- Sectorización **dinámica**: el conjunto de sectores abiertos varía por slot.
- Disponibilidad parcial del controlador modelada como `VentanaDisponibilidad` (frozen, embebida en `Controlador.disponibilidad`). Default = completa.
- Modo de combinación de restricciones: **paralelo** (cardinalidad de las 14 violadas).
- Fitness escalar, minimización.

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

### Estrategia

Greedy *menos-cargado-primero*, asignando una **pareja ejecutivo+planificador** por (sector, slot).

Política de selección:

- Para cada slot $t$, los sectores abiertos en $t$ se barajan.
- Para cada sector, candidatos = controladores en ventana de turno **y** ventana de disponibilidad **y** con licencia.
- Si $|\text{cand}| \geq 2$: el menos cargado → EJ (token upper), el segundo menos cargado entre los restantes → PL (token lower). Empates por random.
- Si $|\text{cand}| = 1$: solo EJ, PL queda descubierto (penalizado por fitness).
- Si $|\text{cand}| = 0$: EJ y PL descubiertos.


Garantías:

- Biyección 1 controlador --> 1 fila (`turno_asignado = i`).
- Respeto de ventana de turno + ventana de disponibilidad.
- Respeto de licencias (CON para sectores ruta, núcleo para no-ruta).
- Mismo controlador nunca como EJ y PL del mismo (sector, slot).
- `slots_trabajados` poblado fielmente.
- Reproducibilidad con misma semilla; diversidad con semillas distintas.

## 3. Función objetivo (`fitness/`)

Decisiones cerradas:

- D1 escalar a minimizar,
- D2 cuatro componentes activas + una en sombra,
- D3 paralelo,
- D4 normalización a [0,1] y combinación ponderada,
- D5 `FitnessResult` con desglose.

| Símbolo | Mide | Cota |
|---|---|---|
| $R$ | restricciones violadas (cardinalidad de 14) | $14$ |
| $C$ | déficit de cobertura **EJ+PL por slot** sobre sectorización dinámica | $\sum_t 2|\mathcal{S}_t|$ |
| $B$ | desbalance de carga (max−min `slots_trabajados`) | $T$ |
| $F$ | fragmentación trabajo↔descanso en ventana | $\sum_i (|\text{vent}_i|-1)$ |
| $L$ | descansos largos $\geq u$, $u=18$ slots (off por defecto) | $N$ |

Pesos por defecto: $\alpha_R=0.45,\ \alpha_C=0.30,\ \alpha_B=0.15,\ \alpha_F=0.10,\ \alpha_L=0.00$.

`FitnessResult(valor, componentes, crudos, restricciones_violadas)` con `__float__ → valor`.

## 4. Integración con BRKGA (pendiente)

Métricas de **rendimiento** separadas del fitness, almacenadas en `RunResult` / `ConvergenceRecord`: tiempo wall-clock, n_evaluaciones, generaciones, mejora_relativa = (seed − final)/seed, robustez ($\bar f \pm \sigma$ sobre K corridas), tasa de éxito.

### Esquemas de codificación implementados

| Decoder | L (genes) | Semántica | Uso |
|---|---|---|---|
| `PermutationDecoder` | $L = N$ | Cada gen es la prioridad global del ATCo $i$ para la fase 2 del greedy. Se usa como **tiebreaker** tras ordenar por carga. | **Principal** |
| `ParametricDecoder` | $L \approx 5$ | Cada gen mapea a un hiperparámetro del greedy (peso del balance, peso de continuidad, softness del cap, etc.). | Comparativa académica |

Ambos comparten la ABC `DecoderBase` con contrato `decode(chromosome, entrada, parametros) → Solucion`.

### Política de parada

Combinación `OR` de cuatro criterios:

- Máximo de generaciones (default 200).
- Máximo de evaluaciones de fitness (default sin tope).
- Tiempo wall-clock máximo (default 300 s).
- Generaciones consecutivas sin mejora del best (default 30).

Cualquier criterio activo dispara la parada. Pasar `None` lo desactiva.

## 5. Decisiones pendientes

| ID | Tema | Estado |
|---|---|---|
| D6 | Esquema de codificación cromosoma-Solución  | Cerrado |
| D7 | Política de parada del BRKGA | Cerrado |
| D8 | Calibración de pesos $\alpha_i$: a priori vs sensitivity sweep vs AHP | A priori; sweep tras línea base |
| D9 | Migración de `paralelo` a `ponderada_clasica` | Diferida |
| D10 | Encendido de $L$ | Off; revisable tras experimentos |
| D11 | API de sectores: separación `get_lista_sectores` / `get_sectores_abiertos_en` / `get_sectores_abiertos_todo_el_dia` | Pendiente refactor |

## 6. Plan de tests

Generador y fitness con tests parametrizados al día. Próximos:

- Validación de bipartición EJ/PL en instancias mini.
- Cobertura dinámica con sectorización variable.

## 7. Referencias

Resende & Gonçalves (2011). *Handbook of Metaheuristics*, capítulo sobre BRKGA.

## 8. Change log

| Fecha | Cambio |
|---|---|
| 2026-06-15 | Generador greedy y fitness escalar cerrados con 4 componentes activas. |
| 2026-06-16 | Refactor modelo: `Propiedades` retirado, `VentanaDisponibilidad` introducida, `crear_controladores` simplificado, `ModificacionRecursos` no leído. |
| 2026-06-16 | Cobertura del dominio: pareja EJ+PL por (sector, slot). Generador y `cobertura_insatisfecha` adaptados. |
| 2026-06-16 | Convención de tokens: upper=EJ, lower=PL. |
| 2026-06-16 | API de sectores marcada como pendiente refactor (D11). |
| 2026-06-18 | D6 cerrada: `PermutationDecoder` (N genes, prioridad global como tiebreaker) y `ParametricDecoder` (K genes, hiperparámetros). D7 cerrada: parada por OR de cuatro criterios. |