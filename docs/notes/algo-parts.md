# Componentes del fitness, generador de semillas y evolución del BRKGA

> Documento de referencia técnico-académico. Cubre las tres piezas
> principales del optimizador de horarios ATCo: las funciones que
> miden la calidad de una solución, el generador heurístico que produce
> la población semilla, y el ciclo evolutivo del BRKGA.

---

## 1. Componentes del fitness

El fitness escalariza la calidad de un horario $s$ como una **suma ponderada de cinco déficits operativos**, cada uno normalizado al intervalo $[0, 1]$. Todos los componentes son errores: cero es ideal, valores altos son malos. El motor minimiza.

$$
f(s) = \alpha_R \tilde R(s) + \alpha_C \tilde C(s) + \alpha_B \tilde B(s) + \alpha_F \tilde F(s) + \alpha_L \tilde L(s)
$$

<!-- donde los pesos $\alpha_k$ viven en el simplex: $\sum_k \alpha_k = 1,\ \alpha_k \geq 0$. -->

### 1.1. Restricciones — $R$

**Qué mide.** Cuántas de las catorce reglas operativas del dominio están violadas en al menos un punto del horario.

**Cómo se calcula.** Modo *paralelo*: cardinalidad del conjunto de comprobaciones que devuelven al menos una violación, sin distinguir cuántas violaciones tiene cada una.

$$
R(s) = \bigl\lvert \{\, i \in [1, 14] : \mathrm{comprobar}_i(s) > 0 \,\} \bigr\rvert
$$

**Cota natural.** $14$ (todas las restricciones violadas simultáneamente).

**Normalización.** $\tilde R(s) = R(s) / 14 \in [0, 1]$.

**Qué cubre operativamente.**

- Continuidad mínima de trabajo (R9).
- Descansos mínimos por bloque (R3, R5, R7).
- Licencias por sector (R1, R2).
- Ventana de turno (R6).
- Máximos de sectores distintos por ATCo (R12).
- Cobertura sectorial nocturna (R4).

**Interpretación para defensa.** $R$ codifica el **cumplimiento normativo**. Cada una de las catorce reglas viene del convenio Enaire-USCA y de los protocolos operativos del control aéreo. La normalización por catorce permite comparar la severidad de la violación entre instancias distintas con el mismo conjunto de reglas.

---

### 1.2. Cobertura — $C$

**Qué mide.** Cuántas posiciones de trabajo quedan sin asignar respecto a la demanda operativa.

**Modelo de cobertura.** Cada sector abierto en un slot demanda **dos posiciones**:

- Un controlador en **posición ejecutiva** (token en mayúsculas, habla con los pilotos).
- Un controlador en **posición planificadora** (token en minúsculas).

**Cómo se calcula.** Sumando, sobre todos los slots, las posiciones ausentes (ejecutiva o planificadora) de cada sector abierto en ese slot:

$$
C(s) = \sum_{t=0}^{T-1} \Bigl[\,\lvert\{\sigma \in \mathcal{S}_t : \sigma^{\uparrow} \notin \mathcal{K}_t\}\rvert + \lvert\{\sigma \in \mathcal{S}_t : \sigma^{\downarrow} \notin \mathcal{K}_t\}\rvert\,\Bigr]
$$

donde:
- $\mathcal{S}_t$ es el conjunto de sectores abiertos en el slot $t$ (sectorización dinámica),
- $\sigma^{\uparrow}$ y $\sigma^{\downarrow}$ son los identificadores del sector $\sigma$ en mayúsculas (EJ) y minúsculas (PL),
- $\mathcal{K}_t$ es el conjunto de tokens de trabajo presentes en la columna $t$ de la matriz de asignaciones.

**Cota natural.** $\sum_t 2 \lvert \mathcal{S}_t \rvert$ (toda posición de todo sector sin cubrir).

**Normalización.** $\tilde C(s) = C(s) / \sum_t 2\lvert\mathcal{S}_t\rvert \in [0, 1]$.

**Interpretación para defensa.** $C$ mide la **fracción de posiciones de control descubiertas**. Es la métrica de **servicio**: si $C > 0$, hay momentos del día donde algún sector estaba operacional pero no había controlador asignado. La cota dinámica $\sum_t 2|\mathcal{S}_t|$ respeta la sectorización variable del espacio aéreo a lo largo del día.

---

### 1.3. Balance — $B$

**Qué mide.** La desigualdad de carga de trabajo entre los controladores.

**Cómo se calcula.**

$$
B(s) = \max_i (\mathrm{slots\_trabajados}_i) - \min_i (\mathrm{slots\_trabajados}_i)
$$

**Cota natural.** $T$ (un ATCo trabaja todo el turno, otro no trabaja nada).

**Normalización.** $\tilde B(s) = B(s) / T \in [0, 1]$.

**Por qué rango absoluto y no coeficiente de variación.** El rango tiene una **interpretación operativa directa**: "$\tilde B = 0.3$" significa que el reparto entre el ATCo más cargado y el menos cargado difiere en el 30% del turno completo. Es la métrica que el comité de personal mirará primero.

**Interpretación para defensa.** $B$ es la **equidad** entre el personal. Un horario donde un ATCo trabaja 60 slots y otro trabaja 30 puede ser legal (R = 0), cubrir todo (C = 0), pero es injusto. La equidad es un objetivo operacional explícito del convenio.

---

### 1.4. Fragmentación — $F$

**Qué mide.** Cuántas veces los controladores **cambian de estado** (trabajar↔descansar) dentro de su ventana de turno.

**Cómo se calcula.**

$$
F(s) = \sum_{i=0}^{N-1} \sum_{t = a_i}^{b_i - 2} \mathbb{1}\bigl[\mathrm{estado}(i, t) \neq \mathrm{estado}(i, t+1)\bigr]
$$

donde:
- $[a_i, b_i)$ es la ventana de turno efectiva del controlador $i$ (combinación de ventana del turno y ventana de disponibilidad),
- $\mathrm{estado}(i, t) \in \{\textsc{Trabajo}, \textsc{Descanso}\}$ ignorando celdas fuera de ventana.

**Cota natural.** $\sum_i (\lvert\mathrm{ventana}_i\rvert - 1)$ (alternancia máxima, cada par consecutivo cambia de estado).

**Normalización.** $\tilde F(s) = F(s) / \sum_i (\lvert\mathrm{ventana}_i\rvert - 1) \in [0, 1]$.

**Interpretación para defensa.** $F$ es la **estabilidad operativa** del horario. Cada transición entre trabajo y descanso exige un *handover* completo entre el controlador entrante y el saliente, lo que distrae y puede causar errores. Penalizar la fragmentación premia bloques continuos de trabajo y de descanso, que es lo que la operativa real demanda.

---

### 1.5. Descansos largos — $L$

**Qué mide.** Cuántas rachas de descanso continuo de longitud $\geq u$ slots aparecen en el horario.

**Cómo se calcula.** Para cada controlador, recorrer su cadena contando rachas de `STRING_DESCANSO` cuya longitud iguale o supere el umbral $u$ (por defecto $u = 18$ slots = 90 min):

$$
L(s) = \sum_{i=0}^{N-1} \mathrm{num\_rachas\_largas}(i, u)
$$

**Cota natural.** $N$ (al menos una racha larga por controlador como peor caso "razonable").

**Normalización.** $\tilde L(s) = \min(L(s)/N,\ 1.0)$, **clampada** porque el numerador puede superar la cota si varios controladores tienen varias rachas cada uno.

**Estado en el diseño.** Por defecto $\alpha_L = 0$ — la componente se calcula pero **no entra en el escalar**. Queda como métrica de observación, lista para activarse si la dirección lo decide.

**Interpretación para defensa.** $L$ es la **eficiencia económica** del horario. Un controlador con 90 minutos seguidos en descanso está infrautilizado. Penalizar descansos largos premia la distribución equilibrada del descanso requerido por R5 ("30 minutos por cada 2h de trabajo") en chorros breves, en lugar de en un único bloque al final del turno.

---

### 1.6. Tabla resumen

| Componente | Mide | Cota | Sentido operativo |
|---|---|---|---|
| $\tilde R$ | Legalidad | 14 restricciones | Cumplimiento del convenio |
| $\tilde C$ | Servicio | $\sum_t 2\lvert\mathcal{S}_t\rvert$ posiciones | Cobertura sectorial |
| $\tilde B$ | Equidad | $T$ slots | Reparto entre controladores |
| $\tilde F$ | Estabilidad | $\sum_i (\lvert\mathrm{ventana}_i\rvert - 1)$ transiciones | Continuidad del trabajo |
| $\tilde L$ | Eficiencia | $N$ rachas | Utilización del recurso |

---

## 2. Generador de población semilla

### 2.1. Naturaleza del generador

Es un **greedy *menos-cargado-primero*** que produce, en tiempo $\mathcal{O}(N \cdot T \cdot |\mathcal{S}|)$, una solución base factible en cinco dimensiones del dominio:

- Biyección controlador↔fila del horario.
- Respeto de ventana de turno y ventana de disponibilidad.
- Respeto de licencias (acreditación CON, núcleo).
- Cap de trabajo continuo (máximo 2h sin descanso).
- Descanso obligatorio tras el cap (mínimo 30 min antes de reincorporarse).

La factibilidad operativa **plena** (todas las restricciones cumplidas, cobertura 100%) no se garantiza; es exactamente lo que el BRKGA mejora a partir de esta semilla.

### 2.2. Estrategia: dos fases por slot

Para cada slot $t \in [0, T)$ el algoritmo ejecuta dos fases consecutivas, seguidas de una fase de bookkeeping.

#### Fase 1 — Extender bloques desde $t-1$

Para cada (sector $\sigma$, posición $p \in \{\mathrm{EJ}, \mathrm{PL}\}$) abierta en el slot $t$:

1. Buscar qué controlador estaba ocupando ese (sector, posición) en el slot $t-1$.
2. Si existe y **puede continuar**:
   - Está en su ventana de turno y disponibilidad en $t$.
   - No tiene descanso obligatorio activo.
   - No ha alcanzado el cap de trabajo continuo.

   Entonces se le **mantiene** en su posición: la celda $\mathrm{matriz}[i][t]$ se rellena con el token correspondiente (mayúsculas para EJ, minúsculas para PL) y se incrementa su contador `slots_trabajados`.
3. Si no puede continuar, esa (sector, posición) queda **pendiente** para la Fase 2.

La Fase 1 es la responsable de la **continuidad** del horario y reduce drásticamente las violaciones de R9 (15 min mínimos en la misma posición).

#### Fase 2 — Rellenar pendientes con fresh-pick

Para cada (sector, posición) pendiente, en orden barajado:

1. **Filtrar candidatos**:
   - ATCos cuya celda en $t$ es `STRING_DESCANSO` (en ventana, libres).
   - Sin descanso obligatorio activo.
   - Con licencia para el sector $\sigma$.
2. **Ordenar por carga acumulada**, ascendente. El menos cargado va primero. El tiebreaker es aleatorio (shuffle previo al sort estable).
3. **Asignar** el primer candidato. Incrementar su `slots_trabajados`. Si tras la asignación el contador `consecutivos[i]` alcanza el cap, activar `descanso_pendiente[i]`.

La Fase 2 es la responsable del **balance** del horario y del fresh-pick cuando la continuidad no puede aplicarse (slot 0, sector recién abierto, controlador que ha dejado su ventana).

#### Fase 3 — Bookkeeping fin de slot

Para cada controlador $i$:

- Si su celda en $t$ es `STRING_DESCANSO` o `STRING_NO_TURNO` (descansa o está fuera de turno):
  - Resetear `consecutivos[i] = 0`.
  - Decrementar `descanso_pendiente[i]` si es positivo (un slot más de descanso obligatorio cumplido).

### 2.3. Mecanismos de autorregulación

| Mecanismo | Cuándo se activa | Qué hace |
|---|---|---|
| **Cap de trabajo continuo** | $\mathrm{consecutivos}[i] = \mathrm{MAX\_CONSEC}$ (= 24 slots = 2h) | Marca `descanso_pendiente[i] = MIN_REST` (= 6 slots = 30 min). El ATCo queda excluido como candidato hasta que el contador llegue a 0. Implementa R7. |
| **Continuidad inteligente** | Fase 1 de cada slot | Mantiene al controlador en su (sector, posición) anterior si puede. Reduce R9 violations. |
| **Tiebreaker por carga** | Fase 2 de cada slot | El menos cargado se prioriza. Promueve balance natural. |
| **Filtro por disponibilidad** | Inicialización + Fase 1 + Fase 2 | Garantiza el respeto de `VentanaDisponibilidad`. |

### 2.4. Garantías formales del generador

| Garantiza | No garantiza |
|---|---|
| Biyección controlador↔fila ($\mathrm{turno\_asignado}_i = i$) | Cobertura completa de la sectorización |
| Respeto de ventana de turno (R6) | Cero violaciones de las 14 restricciones |
| Respeto de ventana de disponibilidad estratégica | Distribución óptima del descanso (R5 distribuido) |
| Respeto de licencias CON y de núcleo (R1, R2) | Optimalidad de ningún criterio del fitness |
| Cap de trabajo continuo ≤ 2h (R7) | |
| Descanso mínimo 30 min tras cap (R5 parcial) | |
| `slots_trabajados` consistente con la matriz | |
| Reproducibilidad con misma semilla `random.Random(seed)` | |
| Diversidad entre semillas distintas | |

### 2.5. Filosofía de diseño

> El generador semilla no busca optimalidad. Busca producir una solución **factible en la mayor cantidad de dimensiones posibles** con coste computacional barato. Las restricciones que el greedy no consigue cerrar de oficio son precisamente las que el BRKGA debe atacar evolutivamente. La semilla es el **punto de partida** del motor; el motor mejora lo que el greedy no cierra.

---

## 3. Evolución del BRKGA generación a generación

### 3.1. Anatomía de una generación

La población de tamaño $p$ se divide en tres clases disjuntas:

$$
\text{Gen}_g = \underbrace{[\,\text{élite}\,]}_{p_e} \cup \underbrace{[\,\text{hijos de crossover}\,]}_{p_h} \cup \underbrace{[\,\text{mutantes aleatorios}\,]}_{p_m}
$$

con cardinalidades:

$$
p_e = \alpha_e \cdot p,\quad p_m = \alpha_m \cdot p,\quad p_h = p - p_e - p_m
$$

Valores típicos: $\alpha_e = 0.20$, $\alpha_m = 0.20$ (deja $p_h = 0.60\,p$).

### 3.2. Las cinco operaciones del ciclo

#### Operación 1 — Decodificar y evaluar

Cada individuo es un cromosoma $c \in [0, 1]^L$. El decodificador $\mathcal{D}$ lo transforma en una solución del dominio:

$$
s = \mathcal{D}(c, E, P)
$$

donde $E$ es la instancia (entrada) y $P$ son los parámetros. La solución se evalúa con el fitness:

$$
\mathrm{fitness}(c) = f(\mathcal{D}(c, E, P))
$$

El decodificador es la **única pieza específica del dominio** dentro del BRKGA. El resto del motor (operadores, población, ciclo evolutivo) es genérico y reutilizable para cualquier problema.

#### Operación 2 — Ordenar y particionar

Se ordena la población por fitness ascendente:

$$
c_{(1)}, c_{(2)}, \ldots, c_{(p)} \quad \text{con } f(c_{(1)}) \leq f(c_{(2)}) \leq \cdots \leq f(c_{(p)})
$$

- **Élite**: los $p_e$ primeros (mejores).
- **No-élite**: los $p - p_e$ restantes.

#### Operación 3 — Conservar la élite (elitismo)

Los $p_e$ individuos élite **pasan intactos** a la siguiente generación, sin sufrir cruce ni mutación. Esta es la propiedad distintiva del BRKGA y de los algoritmos genéticos elitistas: garantiza que **nunca se pierde la mejor solución encontrada hasta el momento**.

#### Operación 4 — Generar mutantes

Se generan $p_m$ cromosomas **completamente aleatorios** con valores en $[0, 1]^L$. No heredan nada de la población actual. Sirven para **exploración pura** del espacio de búsqueda: son el mecanismo de escape de mínimos locales.

#### Operación 5 — Crossover sesgado

Para cada uno de los $p_h$ nuevos hijos:

1. Seleccionar un padre aleatorio de la élite: $c^{(e)} \in \text{Élite}$.
2. Seleccionar un padre aleatorio de la no-élite: $c^{(n)} \in \text{NoÉlite}$.
3. Para cada gen $j \in [0, L)$, herencia sesgada por la probabilidad $\rho_e$:

$$
\mathrm{hijo}[j] = \begin{cases} c^{(e)}[j] & \text{si } u_j < \rho_e \\ c^{(n)}[j] & \text{si } u_j \geq \rho_e \end{cases}, \quad u_j \sim \mathcal{U}(0, 1)
$$

El parámetro $\rho_e \in [0.5, 1]$ controla el sesgo. Por convención y según la literatura, $\rho_e = 0.7$. El sesgo hacia el padre élite es la propiedad que da nombre a "**Biased** Random-Key Genetic Algorithm".

### 3.3. Por qué BRKGA funciona

El motor combina tres mecanismos complementarios:

| Mecanismo | Función | Análogo |
|---|---|---|
| **Elitismo** | Preserva el progreso | "Backup" de la mejor solución |
| **Mutantes aleatorios** | Explora el espacio | "Resetear" exploración |
| **Crossover sesgado** | Refina lo prometedor | "Continuar la dirección de búsqueda" |

La proporción $\rho_e$ controla el balance entre **exploración** (entrada de nueva información) y **explotación** (refinamiento de lo conocido):

- $\rho_e \to 0.5$: exploración pura. Cada gen es igualmente probable de venir de élite o no-élite. El hijo es una mezcla agnóstica.
- $\rho_e \to 1.0$: explotación pura. El hijo se parece cada vez más al padre élite. El motor refina alrededor de la mejor solución pero pierde diversidad.

El valor $0.7$ es el compromiso reportado como robusto en Resende & Gonçalves (2011): el hijo se parece más al élite (70%) pero conserva un 30% de información del no-élite, lo que mantiene diversidad y permite escapar de mínimos locales sin perder la dirección hacia el óptimo.

### 3.4. Pseudocódigo del ciclo

```
Inicializar población P_0 con p cromosomas aleatorios
Evaluar fitness de cada individuo
g ← 0

Mientras no se cumpla ningún criterio de parada:
    Ordenar P_g por fitness ascendente
    Élite     ← primeros p_e de P_g
    NoÉlite   ← restantes
    
    P_{g+1} ← Élite                        # elitismo
    
    Para i = 1, ..., p_m:                  # mutantes
        m_i ← cromosoma aleatorio en [0,1]^L
        Añadir m_i a P_{g+1}
    
    Para j = 1, ..., p_h:                  # crossover sesgado
        padre_e ← uniforme(Élite)
        padre_n ← uniforme(NoÉlite)
        hijo ← []
        Para cada gen k:
            si U(0,1) < ρ_e:
                hijo[k] ← padre_e[k]
            si no:
                hijo[k] ← padre_n[k]
        Añadir hijo a P_{g+1}
    
    Evaluar fitness de P_{g+1}
    g ← g + 1

Devolver el mejor de P_g
```

### 3.5. Criterios de parada (combinación OR)

El motor termina cuando **cualquiera** de estos criterios se cumple:

| Criterio | Default | Significado |
|---|---|---|
| `max_generations` | 200 | Tope de iteraciones del bucle exterior. |
| `max_evaluations` | None | Tope total de llamadas a `evaluar_fitness`. |
| `max_seconds` | 300 | Tope wall-clock. |
| `stagnation_generations` | 30 | Generaciones consecutivas sin mejora del best. |

Pasar `None` desactiva el criterio. Al menos uno debe estar activo (lo valida el constructor `StoppingCriteria`).

### 3.6. Métricas de rendimiento del motor

Distintas del fitness (que mide calidad de la solución), las métricas de rendimiento miden eficiencia del **algoritmo**:

- **Tiempo wall-clock total**.
- **Número total de evaluaciones de fitness**.
- **Número de generaciones ejecutadas**.
- **Mejora relativa**: $(\mathrm{seed\_fitness} - \mathrm{best\_fitness}) / \mathrm{seed\_fitness}$.
- **Robustez**: $\bar f \pm \sigma$ del best fitness sobre $K$ corridas con semillas distintas.
- **Tasa de éxito**: porcentaje de corridas que alcanzan un umbral objetivo.

Estas viven en `RunResult` y `ConvergenceRecord`, **nunca** dentro del fitness. Es importante mantener la distinción para no contaminar la medida de calidad con la medida de coste computacional.

---