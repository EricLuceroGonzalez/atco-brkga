# Función Objetivo del Problema ATCo Scheduling

## 1. Filosofía y arquitectura

La función objetivo es un **escalar a maximizar** compuesto por dos sumandos:

$$
\text{valor}\;=\;\underbrace{\sum_{g} w_g \cdot f_g(H)}_{\text{calidad}} \;-\; \underbrace{\lambda \sum_{r} \omega_r \cdot v_r(H)}_{\text{penalty}}
$$

donde $H$ es la matriz de horarios de la solución, $f_g \in [0, 1]$ son los **grupos de objetivos**, $v_r$ son los **conteos de violaciones** de las 14 restricciones, $w_g$ son los pesos ROC y $\lambda$ el coeficiente global de penalización.

**Decisiones de diseño clave**

| Decisión | Justificación |
|---|---|
| Maximización (no minimización) | Alineado con la fórmula ROC de Tello sec 6.3.3 y permite que `valor = 1` represente "perfecto" intuitivamente. |
| 8 componentes agrupados en 5 grupos | Reduce el espacio de tuning a 5 dimensiones (los pesos $w_g$) sin perder granularidad de inspección. |
| Restricciones fuera del valor positivo | Se **cuentan** para tracking (gráficos) y se **restan** como penalty, en lugar de rechazar la solución. El BRKGA explora libremente regiones infactibles. |
| Pesos ROC computados por fórmula | Suma exacta a 1, sin redondeos manuales; añadir o reordenar grupos es una línea. |
| Cada componente normalizado a $[0, 1]$ | Permite comparar e interpretar componentes entre sí sin reescalar. |

**Estructura física del módulo**

```
fitness/
├── components.py    ← las 8 funciones puras + helpers
├── config.py        ← PesosFitness, UmbralesFitness, FitnessConfig
├── penalizacion.py  ← PesosPenalizacion, calcular_penalizacion, desglose_penalizacion
└── objective.py     ← FitnessResult, evaluar_fitness (orquestador)
```

## 2. Vista general de los componentes

| Símbolo | Componente | Grupo | Peso del grupo (ROC) |
|---|---|---|---:|
| $f_{cob}$ | Cobertura insatisfecha | Cobertura | 137/300 ≈ 0.457 |
| $f_{pos}$ | Tiempo óptimo en posición | Laboral (1/3) | 77/300 ≈ 0.257 |
| $f_{trab}$ | Tiempo óptimo entre descansos | Laboral (1/3) | |
| $f_{eje}$ | Porcentaje ejecutivo en [0.4, 0.6] | Laboral (1/3) | |
| $f_{frag}$ | Fragmentación | Estructura (1/2) | 47/300 ≈ 0.157 |
| $f_{desc}$ | Intervalos de descanso | Estructura (1/2) | |
| $f_{acred}$ | Acreditación (sectores elementales) | Acreditación | 27/300 = 0.09 |
| $f_{bal}$ | Balance de carga (σ) | Balance | 12/300 = 0.04 |

## 3. Componentes individuales

### 3.1 Cobertura insatisfecha — $f_{cob}$

**Descripción.** Mide qué fracción de las **posiciones operacionalmente demandadas** está cubierta por algún controlador. Por cada slot $t$, la demanda es $2 \cdot |S_t|$ (un ejecutivo y un planificador por cada sector abierto). El componente penaliza cada posición sin cubrir con valor 1.

**Ecuación.**

$$
v_{cob} = \sum_{t=0}^{T-1} \Big[ |\{s \in S_t : \text{EJ}(s) \notin H_{:,t}\}| + |\{s \in S_t : \text{PL}(s) \notin H_{:,t}\}| \Big]
$$

$$
v_{cob}^{\max} = \sum_{t=0}^{T-1} 2 \cdot |S_t|, \qquad
f_{cob} = \frac{v_{cob}^{\max} - v_{cob}}{v_{cob}^{\max}}
$$

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{cobertura\_insatisfecha($H$, $E$)}
$v \gets 0$; $\text{demanda} \gets 0$\;
\For{$t \gets 0$ \KwTo $T-1$}{
    $S_t \gets E.\text{sectoresAbiertos}(t)$\;
    $\text{demanda} \gets \text{demanda} + 2 \cdot |S_t|$\;
    $\text{tokens}_t \gets \{H[c][t] : c \in [0, N), H[c][t] \text{ es trabajo}\}$\;
    \ForEach{$s \in S_t$}{
        \lIf{$s.\text{id.upper()} \notin \text{tokens}_t$}{$v \gets v + 1$}
        \lIf{$s.\text{id.lower()} \notin \text{tokens}_t$}{$v \gets v + 1$}
    }
}
\Return $(v, \text{demanda})$\;
\end{algorithm}
```

---

### 3.2 Tiempo óptimo en posición — $f_{pos}$ (vn_1)

**Descripción.** Cada controlador debería trabajar bloques continuos en la misma posición (mismo sector + mismo rol EJ/PL) de aproximadamente **45 minutos**. Cualquier desviación de ese óptimo (bloques más cortos o más largos) penaliza. La función promedia las desviaciones sobre todos los controladores.

**Ecuación.**

$$
v_{pos} = \frac{1}{N}\sum_{k=1}^{N} \sum_{i \in I_k} \big|\text{pos}_{opt} - l_i\big|
$$

donde $I_k$ son los intervalos maximales de misma posición de la fila $k$ y $l_i$ es la duración del intervalo $i$ en minutos. La cota máxima teórica de Tello:

$$
v_{pos}^{\max} = |\text{pos}_{opt} - \text{pos}_{\min}| \cdot 8 \cdot \frac{T}{30}, \qquad
f_{pos} = \frac{v_{pos}^{\max} - v_{pos}}{v_{pos}^{\max}}
$$

con $\text{pos}_{opt} = 45$ min, $\text{pos}_{\min} = 15$ min.

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{tiempo\_optimo\_posicion($H$, $P$)}
$\text{suma} \gets 0$\;
\For{$k \gets 0$ \KwTo $N-1$}{
    \ForEach{$(\text{inicio}, \text{fin}, \tau) \in \text{intervalosMismaPosicion}(H[k])$}{
        $l \gets (\text{fin} - \text{inicio}) \cdot P.\text{tamanoSlots}$\;
        $\text{suma} \gets \text{suma} + |\text{pos}_{opt} - l|$\;
    }
}
$v \gets \text{suma} / N$\;
$\text{cota} \gets |\text{pos}_{opt} - \text{pos}_{\min}| \cdot 8 \cdot (T / 30)$\;
\Return $(v, \text{cota})$\;
\end{algorithm}
```

---

### 3.3 Tiempo óptimo entre descansos — $f_{trab}$ (vn_2)

**Descripción.** Cada bloque continuo de **trabajo** (cualquier sector/posición, hasta el siguiente descanso) debería durar aproximadamente **90 minutos**. A diferencia de vn_1, cambiar de sector dentro del bloque no lo corta — sólo el descanso o el fuera-de-turno lo hace.

**Ecuación.**

$$
v_{trab} = \frac{1}{N}\sum_{k=1}^{N} \sum_{i \in J_k} \big|\text{trab}_{opt} - l_i\big|
$$

donde $J_k$ son los bloques de trabajo continuo de la fila $k$.

$$
v_{trab}^{\max} = |\text{trab}_{opt} - \text{trab}_{\min}| \cdot \frac{T}{6}, \qquad
f_{trab} = \frac{v_{trab}^{\max} - v_{trab}}{v_{trab}^{\max}}
$$

con $\text{trab}_{opt} = 90$ min, $\text{trab}_{\min} = 15$ min.

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{tiempo\_optimo\_trabajo($H$, $P$)}
$\text{suma} \gets 0$\;
\For{$k \gets 0$ \KwTo $N-1$}{
    \ForEach{$(\text{inicio}, \text{fin}) \in \text{intervalosTrabajo}(H[k])$}{
        $l \gets (\text{fin} - \text{inicio}) \cdot P.\text{tamanoSlots}$\;
        $\text{suma} \gets \text{suma} + |\text{trab}_{opt} - l|$\;
    }
}
$v \gets \text{suma} / N$\;
$\text{cota} \gets |\text{trab}_{opt} - \text{trab}_{\min}| \cdot (T / 6)$\;
\Return $(v, \text{cota})$\;
\end{algorithm}
```

---

### 3.4 Porcentaje ejecutivo — $f_{eje}$ (vn_3)

**Descripción.** La fracción del tiempo que un controlador trabaja en posición **ejecutiva** debe estar entre el 40 % y el 60 % del total de su trabajo (excluyendo descansos). Si está fuera de la banda, se penaliza con la distancia al borde más cercano. Controladores que no trabajaron se excluyen (no inflan ni la suma ni el denominador).

**Ecuación.** Sea $\text{pEje}_k = \dfrac{\text{slots EJ}_k}{\text{slots trabajo}_k}$ y

$$
\delta_k = \begin{cases}
0 & \text{si } \text{pEje}_k \in [0.4, 0.6] \\
0.4 - \text{pEje}_k & \text{si } \text{pEje}_k < 0.4 \\
\text{pEje}_k - 0.6 & \text{si } \text{pEje}_k > 0.6
\end{cases}
$$

$$
v_{eje} = \sum_{k=1}^{N_{\text{act}}} \delta_k, \qquad
v_{eje}^{\max} = \max(\text{pct}_{\min}, 1 - \text{pct}_{\max}) \cdot N_{\text{act}}
$$

$$
f_{eje} = \frac{v_{eje}^{\max} - v_{eje}}{v_{eje}^{\max}}
$$

donde $N_{\text{act}}$ es el número de controladores con al menos un slot de trabajo.

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{porcentaje\_ejecutivo($H$)}
$v \gets 0$; $N_{\text{act}} \gets 0$\;
\For{$k \gets 0$ \KwTo $N-1$}{
    $e \gets |\{t : H[k][t] \text{ es ejecutivo}\}|$\;
    $p \gets |\{t : H[k][t] \text{ es planificador}\}|$\;
    \lIf{$e + p = 0$}{\textbf{continue}}
    $N_{\text{act}} \gets N_{\text{act}} + 1$\;
    $\text{pEje} \gets e / (e + p)$\;
    \uIf{$\text{pEje} < 0.4$}{$v \gets v + (0.4 - \text{pEje})$}
    \uElseIf{$\text{pEje} > 0.6$}{$v \gets v + (\text{pEje} - 0.6)$}
}
$\text{cota} \gets \max(0.4, 0.4) \cdot N_{\text{act}}$\;
\Return $(v, \text{cota})$\;
\end{algorithm}
```

---

### 3.5 Fragmentación — $f_{frag}$

**Descripción.** Mide cuántos *bloques* distintos (de trabajo o de descanso) tiene cada controlador dentro de su ventana de turno. Un horario compacto tiene pocos bloques (idealmente uno de trabajo y uno de descanso); un horario fragmentado tiene muchos. Los cambios de sector **no** cuentan como cambio de bloque — sólo los cambios entre estado "trabajo" y estado "descanso".

**Ecuación.** Sea $B_k$ el número de bloques (work-or-rest) en la ventana de la fila $k$:

$$
v_{frag} = \sum_{k=1}^{N} B_k, \qquad v_{frag}^{\min} = N_{\text{act}}, \qquad v_{frag}^{\max} = \sum_{k=1}^{N} (b_k - a_k)
$$

donde $[a_k, b_k)$ es la ventana de turno de la fila $k$.

$$
f_{frag} = \frac{v_{frag}^{\max} - v_{frag}}{v_{frag}^{\max} - v_{frag}^{\min}}
$$

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{fragmentacion($H$)}
$v \gets 0$; $v_{\min} \gets 0$; $v_{\max} \gets 0$\;
\For{$k \gets 0$ \KwTo $N-1$}{
    $(a, b) \gets \text{ventanaDe}(H[k])$\;
    \lIf{$b - a = 0$}{\textbf{continue}}
    $v_{\min} \gets v_{\min} + 1$\;
    $v_{\max} \gets v_{\max} + (b - a)$\;
    $\text{bloques} \gets 1$; $\text{est}_{\text{prev}} \gets \text{esTrabajo}(H[k][a])$\;
    \For{$t \gets a+1$ \KwTo $b-1$}{
        $\text{est} \gets \text{esTrabajo}(H[k][t])$\;
        \If{$\text{est} \neq \text{est}_{\text{prev}}$}{
            $\text{bloques} \gets \text{bloques} + 1$\;
            $\text{est}_{\text{prev}} \gets \text{est}$\;
        }
    }
    $v \gets v + \text{bloques}$\;
}
\Return $(v, v_{\min}, v_{\max})$\;
\end{algorithm}
```

---

### 3.6 Intervalos de descanso — $f_{desc}$

**Descripción.** Cuenta cuántos **bloques de descanso separados** tiene cada controlador. Tener uno o dos descansos largos es mejor que tener muchos descansos cortos repartidos: menos cambios de sala, mayor legibilidad del estadillo, mejor experiencia para el operador.

**Ecuación.** Sea $D_k$ el número de bloques de tokens `"111"` en la fila $k$:

$$
v_{desc} = \sum_{k=1}^{N} D_k
$$

$$
v_{desc}^{\min} = N_{\text{act}}, \qquad v_{desc}^{\max} = \frac{T \cdot N_{\text{act}}}{6}
$$

$$
f_{desc} = \frac{v_{desc}^{\max} - \max(v_{desc}, v_{desc}^{\min})}{v_{desc}^{\max} - v_{desc}^{\min}}
$$

El divisor 6 viene de Tello: trabajo mínimo (3 slots) + descanso mínimo (3 slots) = ciclo mínimo de 6.

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{intervalos\_descanso($H$)}
$v \gets 0$; $N_{\text{act}} \gets 0$\;
\For{$k \gets 0$ \KwTo $N-1$}{
    $(a, b) \gets \text{ventanaDe}(H[k])$\;
    \lIf{$b - a = 0$}{\textbf{continue}}
    $N_{\text{act}} \gets N_{\text{act}} + 1$\;
    $\text{enDescanso} \gets \text{False}$\;
    \For{$t \gets a$ \KwTo $b-1$}{
        \uIf{$H[k][t] = \text{"111"}$ \textbf{y} $\neg\text{enDescanso}$}{
            $v \gets v + 1$; $\text{enDescanso} \gets \text{True}$\;
        }
        \uElseIf{$H[k][t] \neq \text{"111"}$}{$\text{enDescanso} \gets \text{False}$}
    }
}
\Return $(v, N_{\text{act}}, \lfloor T \cdot N_{\text{act}} / 6 \rfloor)$\;
\end{algorithm}
```

---

### 3.7 Acreditación — $f_{acred}$

**Descripción.** Cuenta cuántos sectores elementales distintos cubre cada controlador a lo largo del turno. La intuición operacional es **mantener acreditación**: un controlador que sólo trabaja un sector durante todo el turno pierde rodaje en el resto. Maximizar este componente fomenta que los controladores roten por más elementales del espacio aéreo.

**Ecuación.** Sea $\mathcal{E}$ el conjunto de sectores elementales pertenecientes a sectores que se abren en algún slot del turno, y $E_k$ el conjunto de elementales que el controlador $k$ ha cubierto al menos una vez:

$$
v_{acred} = \sum_{k=1}^{N} |E_k|
$$

$$
v_{acred}^{\min} = N, \qquad v_{acred}^{\max} = N \cdot |\mathcal{E}|
$$

$$
f_{acred} = \frac{\max(v_{acred}, v_{acred}^{\min}) - v_{acred}^{\min}}{v_{acred}^{\max} - v_{acred}^{\min}}
$$

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{acreditacion($H$, $E$)}
$\mathcal{S}_{\text{abiertos}} \gets \bigcup_t \{s.\text{id} : s \in E.\text{sectoresAbiertosEn}(t)\}$\;
$\mathcal{E} \gets \bigcup_{s \in \mathcal{S}_{\text{abiertos}}} s.\text{elementales}$\;
$v \gets 0$\;
\For{$k \gets 0$ \KwTo $N-1$}{
    $E_k \gets \emptyset$\;
    \For{$t \gets 0$ \KwTo $T-1$}{
        $\tau \gets H[k][t]$\;
        \If{$\tau \text{ es trabajo} \wedge \tau.\text{lower()} \in \mathcal{S}_{\text{abiertos}}$}{
            $E_k \gets E_k \cup \text{elementalesDe}(\tau)$\;
        }
    }
    $v \gets v + |E_k|$\;
}
\Return $(v, N, N \cdot |\mathcal{E}|)$\;
\end{algorithm}
```

---

### 3.8 Balance de carga — $f_{bal}$

**Descripción.** Mide la equidad de la distribución de trabajo entre controladores usando la **desviación estándar** de los slots trabajados. A diferencia del rango (máx - mín), la σ refleja la dispersión global: un único atípico apenas la mueve, pero un desbalance sistemático sí.

**Ecuación.** Sea $w_k$ los slots trabajados por el controlador $k$ y $\mu = \frac{1}{N}\sum_k w_k$:

$$
\sigma = \sqrt{\frac{1}{N}\sum_{k=1}^{N}(w_k - \mu)^2}, \qquad \sigma_{\max} = \mu
$$

$$
f_{bal} = \frac{\sigma_{\max} - \sigma}{\sigma_{\max}}
$$

La cota $\sigma_{\max} = \mu$ es Tello sec 6.3.3.4: el peor caso bajo el cap operacional (cada controlador trabaja como máximo $2\mu$) se alcanza cuando la mitad trabaja $2\mu$ y la otra mitad 0. **Aplicamos un clamp $f_{bal} \in [0, 1]$** para absorber el caso patológico de distribuciones extremas (un único controlador acapara todo) sin que el componente se vuelva negativo.

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{balance\_carga($H$)}
\If{$N = 0$}{\Return $(0, 0)$}
$w \gets [\text{slotsTrabajados}_k : k \in [0, N)]$\;
$\mu \gets (\sum_k w_k) / N$\;
\lIf{$\mu = 0$}{\Return $(0, 0)$}
$\sigma \gets \sqrt{(\sum_k (w_k - \mu)^2) / N}$\;
\Return $(\sigma, \mu)$\;
\end{algorithm}
```

---

## 4. Penalización por restricciones

**Descripción.** Las 14 restricciones operativas (acreditación, descansos mínimos, ventana 2h30, etc.) **no entran** como componente positivo del fitness. En su lugar, se cuentan y se convierten en un penalty aditivo configurable. Esto permite que el BRKGA explore regiones infactibles libremente y deja al usuario decidir cuán dura quiere ser esa penalización.

**Ecuación.** Sea $v_r$ el conteo de la restricción $r$ devuelto por `_checks` (entero o flotante con micro-penalty) y $\omega_r$ su peso individual:

$$
\text{penalty} = \lambda \cdot \sum_{r=1}^{14} \omega_r \cdot v_r
$$

Con $\lambda = 0.01$ por defecto (calibrado para que 100 violaciones unitarias reduzcan el fitness en 1.0) y $\omega_r = 1$ (uniforme). Tanto $\lambda$ como los $\omega_r$ son configurables vía `PesosPenalizacion`.

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{calcular\_penalizacion(violaciones, pesos)}
$\text{suma} \gets 0$\;
\ForEach{$r \in \text{NOMBRES\_RESTRICCIONES}$}{
    $\text{suma} \gets \text{suma} + \text{violaciones}[r] \cdot \text{pesos}.\omega_r$\;
}
\Return $\text{pesos}.\lambda \cdot \text{suma}$\;
\end{algorithm}
```

---

## 5. Combinación final — el orquestador

Los 8 componentes se agrupan en **5 grupos**; cada grupo se pondera con su peso $w_g$ (ROC); el penalty se resta al final.

**Ecuación.**

$$
\text{grupo}_{\text{laboral}} = \mu_{pos} f_{pos} + \mu_{trab} f_{trab} + \mu_{eje} f_{eje}
$$

$$
\text{grupo}_{\text{estructura}} = \mu_{frag} f_{frag} + \mu_{desc} f_{desc}
$$

$$
\text{valor}_{\text{componentes}} = w_{cob} f_{cob} + w_{lab} \cdot \text{grupo}_{\text{laboral}} + w_{est} \cdot \text{grupo}_{\text{estructura}} + w_{acr} f_{acred} + w_{bal} f_{bal}
$$

$$
\boxed{\;\text{valor} = \text{valor}_{\text{componentes}} - \text{penalty}\;}
$$

**Pseudo-código.**

```latex
\begin{algorithm}[H]
\caption{evaluar\_fitness($H$, $E$, $P$, $C$)}
\tcp{Componentes individuales}
$(v_{cob}, d) \gets \text{coberturaInsatisfecha}(H, E)$\;
$f_{cob} \gets (d - v_{cob}) / d$\;
$(v_{pos}, c_1) \gets \text{tiempoOptimoPosicion}(H, P)$; $f_{pos} \gets (c_1 - v_{pos}) / c_1$\;
$(v_{trab}, c_2) \gets \text{tiempoOptimoTrabajo}(H, P)$; $f_{trab} \gets (c_2 - v_{trab}) / c_2$\;
$(v_{eje}, c_3) \gets \text{porcentajeEjecutivo}(H)$; $f_{eje} \gets (c_3 - v_{eje}) / c_3$\;
$(v_{frag}, m_1, M_1) \gets \text{fragmentacion}(H)$; $f_{frag} \gets (M_1 - v_{frag}) / (M_1 - m_1)$\;
$(v_{desc}, m_2, M_2) \gets \text{intervalosDescanso}(H)$; $f_{desc} \gets (M_2 - v_{desc}) / (M_2 - m_2)$\;
$(v_{acr}, m_3, M_3) \gets \text{acreditacion}(H, E)$; $f_{acred} \gets (v_{acr} - m_3) / (M_3 - m_3)$\;
$(\sigma, \sigma_M) \gets \text{balanceCarga}(H)$; $f_{bal} \gets (\sigma_M - \sigma) / \sigma_M$\;

\tcp{Grupos}
$g_{\text{lab}} \gets \mu_{pos} f_{pos} + \mu_{trab} f_{trab} + \mu_{eje} f_{eje}$\;
$g_{\text{est}} \gets \mu_{frag} f_{frag} + \mu_{desc} f_{desc}$\;

\tcp{Calidad ponderada}
$V_{\text{comp}} \gets w_{cob} f_{cob} + w_{lab} g_{\text{lab}} + w_{est} g_{\text{est}} + w_{acr} f_{acred} + w_{bal} f_{bal}$\;

\tcp{Penalización}
$\text{viol} \gets \text{contarViolaciones}(H, E, P)$\;
$\text{penalty} \gets \text{calcularPenalizacion}(\text{viol}, C.\text{pesosPenalizacion})$\;

\Return $V_{\text{comp}} - \text{penalty}$\;
\end{algorithm}
```

---

## 6. Pesos ROC — Resumen

Los pesos del Rank-Order Centroid (Stillwell, Seaver & Edwards 1981) se calculan por la fórmula

$$
\mu_i = \frac{1}{n}\sum_{j=i}^{n}\frac{1}{j}, \qquad i = 1, \ldots, n
$$

Para $n = 5$ grupos en orden decreciente de importancia:

| Grupo | i | $\mu_i$ exacto | Decimal |
|---|---:|---|---:|
| Cobertura | 1 | $137/300$ | 0.4567 |
| Laboral | 2 | $77/300$ | 0.2567 |
| Estructura | 3 | $47/300$ | 0.1567 |
| Acreditación | 4 | $27/300$ | 0.09 |
| Balance | 5 | $12/300$ | 0.04 |
| **Σ** | | **$300/300$** | **1.0** |

El usuario puede reordenar prioridades vía `PesosFitness.con_orden([...])` sin tocar los pesos a mano.

---

## 7. Interpretación del `FitnessResult`

```python
@dataclass(frozen=True)
class FitnessResult:
    valor: float                       # = valor_componentes - penalty (MAXIMIZAR)
    valor_componentes: float           # ∑ w_g · f_g, sin penalty
    penalty: float                     # ≥ 0
    factible: bool                     # n_violaciones_total == 0
    grupos: dict[str, float]           # 5 grupos en [0, 1]
    componentes: dict[str, float]      # 8 componentes en [0, 1]
    crudos: dict[str, float]           # valores pre-normalización
    violaciones: dict[str, float]      # 14 restricciones
    n_violaciones_total: float
    penalty_por_restriccion: dict[str, float]
```

Una solución **perfecta y factible** da `valor = 1.0`. Una **infactible peor caso** puede dar valores negativos.