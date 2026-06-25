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

### Propósito

Constructor voraz que genera una `Solucion` factible a partir de la
sectorización del turno. Implementa una política **"continuidad primero,
ATCo menos cargado después"** con seguimiento explícito de fatiga.

Se diseñó como **generador de la semilla inicial** del BRKGA, no como
decoder: el cromosoma del BRKGA se inyecta opcionalmente vía los
parámetros `prioridad` (orden de ATCos) y `prioridad_sectores` (orden de
sectores), y cuando ambos son `None` la función funciona como heurística
autónoma usando `rng` para diversificar.

### Convenciones de codificación

| Posición | Token | Ejemplo |
|---|---|---|
| Ejecutivo (`EJ`) | sector en **MAYÚSCULAS** | `AAB` |
| Planificador (`PL`) | sector en **minúsculas** | `aab` |
| Descanso | `"111"` | celda en ventana sin asignar |
| Fuera de turno | `"000"` | celda fuera de la ventana del ATCo |

### Firma

```python
    construir_solucion_heuristica(
        entrada: Entrada,
        parametros: Parametros,
        rng: random.Random,
        prioridad: list[float] | None = None, # orden de ATCOs
        prioridad_sectores: dict[str, float] | None = None, # orden de sectores
    ) -> Solucion
```

### Estrategia

Greedy *menos-cargado-primero*, asignando una **pareja ejecutivo+planificador** por (sector, slot), para un sector dado `t` busca al ATCO que lo tenía asignado en `t-1`

Política de selección:

- Para cada slot $t$, los sectores abiertos en $t$ se barajan.
- Para cada sector en slot `t` se recorren las posiciones `EJ` y `PL`
- Se crea la lista `pendientes` para aquellos sectores no asignados.
- Se verifica en ATCO en slot anterior (`t-1`) con `_atco_en_slot_anterior()`
- Si este slot en esta posición estaba atendido por el `ATCO_n`, se verifica que este ATCO pueda atenderlo en `t`, sino puede se adjunta en la lista `pendientes`
- Para cada sector y posición en `pendientes`, se definen los `candidatos` en ventana de turno **y** ventana de disponibilidad **y** con licencia.
- Se ordenan los candidatos por orden de carga de trabajo. 
- Se elige el primero (el menos cargado)
 
 ### Algoritmo en dos fases por slot

Para cada slot `t ∈ [0, T):`

#### Fase 0 — orden de sectores
`sectores_t` se ordena según prioridad_sectores (descendente) si se
proporciona; en caso contrario se baraja con `rng`. Determina el orden
en que se intenta cubrir cada sector.

#### Fase 1 — continuidad

Para cada par `(sector, posición)` con posición `∈ {EJ, PL}`:

1. Se busca en la columna `t-1` el ATCo `i_prev` que tenía exactamente
el mismo token (`_atco_en_slot_anterior`).
2. Se valida que `i_prev` puede continuar: dentro de ventana
(`_puede_continuar`), sin descanso pendiente, y consecutivos `< T_max`.
3. Si pasa, se extiende el bloque: `H[i_prev][t]` ← `token`,
`consecutivos[i_prev]` += 1, y si toca el techo se programa
`descanso_pendiente[i_prev]` ← D_min.
4. Si no pasa, el par `(sector, posición)` se acumula en pendientes.

>Caso especial t = 0. No hay t-1, así que todo va directo a
>pendientes. Este es el origen del cliff (§9).

#### Fase 2 — relleno por menos-cargado

Para cada `(sector, posición)` en `pendientes`:

1. Candidatos: ATCos con celda "111" (en ventana, no asignados aún en
t), `descanso_pendiente == 0` y licencia válida.
2. Orden:
   - Si hay prioridad: ordenar por (`-prioridad[i], slots_trabajados[i]`).
   - Si no: rng.shuffle + sort estable por slots_trabajados[i].
3. Asignar el primero. Actualizar slots_trabajados, consecutivos,
descanso_pendiente.

#### Cierre de slot — recuperación

Para cada ATCo no asignado en t:

- `consecutivos[i]` <- 0,
- si `descanso_pendiente[i]` > 0, decrementar en 1.

### Garantías:

- Biyección 1 controlador --> 1 fila (`turno_asignado = i`).
- Respeto de ventana de turno + ventana de disponibilidad.
- Respeto de licencias (CON para sectores ruta, núcleo para no-ruta).
- Mismo controlador nunca como EJ y PL del mismo (sector, slot).
- `slots_trabajados` poblado fielmente.
- Reproducibilidad con misma semilla; diversidad con semillas distintas.

💀 Problemas:
>Cuando se genera la primera solución, atiende todos los sectores en
ambas posiciones hasta 24 slots; en el Slot 25 la mayoría de los
sectores queda sin cobertura, hasta que se recuperen los controladores
y cumplan con su descanso mínimo (6 slots).

- Asigna por definición de parámetros los  `24 slots` de trabajo continuo.
- Cuando estamos en el slot `t = 24` se atienden solo `6` u `8` sectores.

## 3. Permutation Decoder

### 1. Propósito y posición en la arquitectura

`PermutationDecoder` es el decoder por defecto del BRKGA. Su responsabilidad
es **traducir un cromosoma de claves aleatorias en una `Solucion` factible**
delegando toda la construcción del horario en `construir_solucion_heuristica`.

No toma decisiones de asignación slot-a-slot. Sólo separa el cromosoma en
**dos vectores de prioridad** y los inyecta como guía al constructor greedy:

- `prioridad_atco` -> criterio primario en la Fase 2 (relleno) del greedy.
- `prioridad_sectores` -> orden de visita de los sectores en cada slot.

Esto es el patrón clásico de Gonçalves & Resende: el cromosoma encapsula
**permutaciones implícitas**, no decisiones de asignación. El espacio de
búsqueda del BRKGA queda definido sobre los `argsort` de cada bloque.

### 2. Estructura del cromosoma

| Tramo | Índices | Longitud | Semántica |
|---|---|---:|---|
| ATCos | `[0, N)` | `N` | `chrom[i]` = prioridad del controlador `i` |
| Sectores | `[N, N+|S|)` | `|S|` | `chrom[N + k]` = prioridad del sector `k`-ésimo |

Longitud total: **`L = N + |S|`** (donde `|S|` es el número de sectores
globales de la entrada, no sólo los abiertos en un slot concreto).

> **Compacidad.** Para `madN_M1` con `N ≈ 22` y `|S| ≈ 13`, `L ≈ 43`. Esto
> contrasta con el decoder slot-a-slot (`N · T ≈ 2940`). El espacio de
> búsqueda es ~70 veces más pequeño, lo que acelera enormemente la
> exploración del BRKGA.

### 3. Por qué dos permutaciones

Cada bloque rompe una simetría distinta del problema:

- **Permutación de ATCos.** Sin ella, todas las soluciones que permuten
  controladores intercambiables (mismo núcleo, misma acreditación) serían
  equivalentes para el fitness. El BRKGA no podría aprender diferencias.
- **Permutación de sectores.** Sin ella, el constructor greedy resolvería
  los sectores en un orden fijo (o aleatorio) en cada slot, perdiendo la
  capacidad del BRKGA de privilegiar la cobertura de ciertos sectores
  (p. ej. los más críticos o los que tienen menos relevos).

Combinadas, dan al BRKGA dos *grados de libertad* ortogonales: a quién
asignar antes y qué cubrir antes.

### 4. Flujo de `decode(chromosome, entrada, parametros)`

1. **Validación.** Llamadas heredadas de `DecoderBase`:
   - `validate_chromosome(chromosome)` — comprueba longitud y rango.
   - `validate_controllers(entrada, self.n_controladores)` — coherencia
     con la instancia del problema.
   - `validate_sectores(entrada, self.n_sectores)` — coherencia y devuelve
     el listado de sectores globales en orden determinista.
2. **Partición del cromosoma.**
   - `priority_atcos = chromosome[:N].tolist()` — lista de floats por
     controlador.
   - `sector_genes = chromosome[N:]` — slice de numpy.
3. **Mapeo sector -> prioridad.** Se construye un `dict[str, float]`
   indexado por `sector.id`:

   ```python
    priority_sectores = {s.id: float(sector_genes[i]) for i, s in enumerate(all_sectores)}
    ```

El orden de `all_sectores` determina **qué gen va con qué sector**.
Si ese orden cambiase entre llamadas, dos cromosomas idénticos
producirían soluciones distintas. Es por eso que `validate_sectores`
tiene que devolver el listado en orden determinista (típicamente
alfabético por `id`).

1. **Delegación.** Se invoca `construir_solucion_heuristica` con:

- `entrada`, `parametros` (sin tocar),
- `rng = random.Random(self._RNG_SEED_INTERNO)` ⟹ rng **fijo** entre
  llamadas (ver §7),
- `prioridad_atco = priority_atcos`,
- `prioridad_sectores = priority_sectores`.

### 5. `chromosome_from_solucion()` — codificación inversa parcial

Helper para sembrar el BRKGA con una `Solucion` conocida (típicamente la
distribución inicial o un best de SA).

Genera el cromosoma con dos partes:

- **Parte ATCo** (`[0, N)`): mapea la carga del controlador a una prioridad
inversamente proporcional:

```python
atco_part[i] = 1 - slots_trabajados[i] / longitud_t (clip [0,1])
```

ATCos poco cargados ⟹ prioridad alta ⟹ se favorece su elección en
Fase 2. Es el "sesgo de relevo".
- **Parte sector** (`[N, N+|S|)`): valores **aleatorios** generados con un
RNG fijo (seed=0). No hay forma de derivar la prioridad de sectores
desde una solución terminada porque el orden de visita es interno al
constructor, no observable en el horario final.

**Limitación importante.** No es un round-trip exacto. Si codificas una
`Solucion` con esta función y luego la decodificas con
`PermutationDecoder.decode`, **no recuperarás la misma solución**:

- la parte de sectores es aleatoria,
- el constructor greedy puede tomar caminos distintos según empates,
- el `RNG_SEED_INTERNO=0` desempata de forma fija pero esa decisión no es
reversible.

El uso correcto es **sembrar la población** con una solución "razonable"
como punto de partida, no como mecanismo de persistencia.


## 4. Función objetivo (`fitness/`)

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
| $B$ | desbalance de carga (max-min `slots_trabajados`) | $T$ |
| $F$ | fragmentación trabajo↔descanso en ventana | $\sum_i (|\text{vent}_i|-1)$ |
| $L$ | descansos largos $\geq u$, $u=18$ slots (off por defecto) | $N$ |

Pesos por defecto: $\alpha_R=0.45,\ \alpha_C=0.30,\ \alpha_B=0.15,\ \alpha_F=0.10,\ \alpha_L=0.00$.

`FitnessResult(valor, componentes, crudos, restricciones_violadas)` con `__float__ -> valor`.

## 4. Integración con BRKGA (pendiente)

Métricas de **rendimiento** separadas del fitness, almacenadas en `RunResult` / `ConvergenceRecord`: tiempo wall-clock, n_evaluaciones, generaciones, mejora_relativa = (seed - final)/seed, robustez ($\bar f \pm \sigma$ sobre K corridas), tasa de éxito.

### Esquemas de codificación implementados

| Decoder | L (genes) | Semántica | Uso |
|---|---|---|---|
| `PermutationDecoder` | $L = N$ | Cada gen es la prioridad global del ATCo $i$ para la fase 2 del greedy. Se usa como **tiebreaker** tras ordenar por carga. | **Principal** |
| `ParametricDecoder` | $L \approx 5$ | Cada gen mapea a un hiperparámetro del greedy (peso del balance, peso de continuidad, softness del cap, etc.). | Comparativa académica |

Ambos comparten la ABC `DecoderBase` con contrato `decode(chromosome, entrada, parametros) -> Solucion`.

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

## 7. Documentación y logs

Se ha creado una carpeta llamada `/docs` para documentar algunas salidas de prueba, apuntes o imprimir diagramas. Contiene las carpetas:
  1. `diagrams`: Muestras los diagramas UML y dependencias. Se ejecuta con:
  
        ```bash
        # Muestra src/atco y guarda .png en docs/diagrams
        uv run pyreverse -o png -p atco -d docs/diagrams src/atco
        
        # Muestra src/atco/domain src/atco/problem y guarda .png en docs/diagrams
        uv run pyreverse -o png -p atco -d docs/diagrams src/atco/domain src/atco/problem
        ```

  2. `logs` Los de prints y logger para documentar todo el recorrido.
  3. `notes` Markdowns para documentar cambios, funcionamiento y cualquier anotación tipo bitácora.

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