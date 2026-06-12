STRING_DESCANSO = "111"
STRING_NO_TURNO = "000"
LONGITUD_CADENAS = 3

# =============================================================================
# CORRESPONDENCIA CON CÓDIGO JAVA
# =============================================================================
# Archivo Java:
#   - src/main/herramientas/CridaUtils.java
#       → STRING_DESCANSO   = "111"
#       → STRING_NO_TURNO   = "000"
#       → LONGITUD_CADENAS  = 3
#
# Solo se migran las constantes usadas en el flujo SA.
# CridaUtils.java contiene además métodos auxiliares (esTrabajo, esDescanso,
# split3In3, obtenerNucleosAlQuePerteneceUnSector) que están en metaheuristic.py
# o no son necesarios en SA.
# =============================================================================