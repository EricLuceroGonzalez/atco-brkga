from atco.domain.constants import STRING_DESCANSO, STRING_NO_TURNO

PESO_POR_RESTRICCION = [2, 2, 3, 2, 3, 2, 3, 0.9, 3, 2, 0.85, 0.5, 5, 5]
PENALIZACION = 0.001
REST_SLOTS = {STRING_DESCANSO, STRING_NO_TURNO}
restricciones_no_cumplidas = [0.0] * 14
