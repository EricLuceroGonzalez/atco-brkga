# Notas sobre el BRKGA

## Ideas de decodificador

### "Decodificador Estocástico"

Si quieres mantener la idea de la "probabilidad" pero hacerla eficiente, no uses las probabilidades como una asignación directa, úsalas como Pesos de Selección (Stochastic Greedy).
En lugar de que el cromosoma diga "probabilidad de trabajar en el Slot X", haz que el cromosoma diga:

- Peso de preferencia del controlador i: w_i
- Peso de importancia del sector j: s_j

El decodificador entonces realiza un proceso constructivo:
Para cada Slot t: Calcula el score de cada controlador: Score(ATCO_i)=w_i x Disponibilidad(t) x Afinidad(Sector_j).

Asigna el trabajo al ATCO con el mejor score.

#### ¿Por qué esto explora mejor?

Porque no estás forzando a la BRKGA a encontrar la "matriz perfecta" (lo cual es casi imposible), sino que le pides que encuentre la "jerarquía de preferencias perfecta". La BRKGA es excepcionalmente buena encontrando jerarquías (ordenamientos), pero es muy ineficiente llenando matrices binarias completas.