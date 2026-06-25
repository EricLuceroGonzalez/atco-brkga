"""Generadores heurísticos de soluciones-semilla para BRKGA.

Este paquete contiene heurísticos que producen `Solucion`s operativamente
factibles (o casi) que se usan para sembrar la población inicial del solver.
La codificación a cromosoma se hace fuera de aquí (la realiza el decoder
correspondiente vía su método `solucion_to_chromosome`).

Convenio: cada generador es una función pura ``construir_solucion_*`` que
recibe ``(entrada, parametros, rng)`` y devuelve una ``Solucion``.

Garantías esperadas de cada generador (ver
``docs/thesis/notes-design.md`` §2.2 para el contrato detallado):

* Licencia respetada (CON -> sólo sectores ruta, núcleo del ATCo).
* Ventana de turno respetada (TC vs TL).
* Biyección controlador ↔ fila del horario.

Las restricciones que NO se garantizan (balance, trabajo continuo mínimo,
etc.) se delegan al fitness para que el BRKGA tenga margen de mejora.
"""

from atco.seeds.greedy import construir_solucion_heuristica

__all__ = ["construir_solucion_heuristica"]
