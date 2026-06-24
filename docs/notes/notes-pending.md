# Pendientes

<!-- - 🅿️ -->
- 🅿️ Verificar si es conveniente: - Si $|\text{cand}| = 1$: solo EJ, PL queda descubierto (penalizado por fitness).
- 🅿️ Verificar qué es `solucion.turnos` (deberia ser `cadenas`)
- 🅿️ Verificar en checks
   
    ```python
    p += 1
    p += (cnt - t_max) * 0.025
    t = 1
    ```

    - Eliminar eso de imaginario
    - Incluir el tiempo o slots de trabajo/descanso
- 🅿️ Verificar la import de `from .fitness import Fitness` en _instance.py_
- 🅿️ Verificar lo del `..._fast_cache` en algunas funciones
  - `entrada._fast_volumes_by_id`, `entrada._fast_sector_by_id`, `entrada._fast_num_max_sectores_cache`
- 🅿️ Eliminar variable `sectorizacion_modificada` y todo lo de táctico
- 🅿️ `Docstrings` de todas las funciones

## Hecho

<!-- - ✅  -->
- ✅ Verificar `sectorización_modificada`. Esto no se usará. Corresponde al problema táctico.
- ✅ Verificar las clases de los models.py. 
- ✅ `estudio_estadillos` es para comparar con los horarios reales hechos por los planificadores.
- ✅ Implementer el `logging`
- ✅ Importación de la función `listar()` en `instance.py`