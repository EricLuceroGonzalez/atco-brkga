import logging
import sys
import os


def setup_logging(log_name="abaco.log", level="INFO"):
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    # Configuración básica del logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_name, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Clase para redirigir print() y salidas de Java al logger
    class LoggerWriter:
        def __init__(self, level):
            self.level = level

        def write(self, message):
            if message.strip():
                self.level(message.strip())

        def flush(self):
            pass

    # Redirección de la salida estándar y de errores
    sys.stdout = LoggerWriter(logging.info)
    sys.stderr = LoggerWriter(logging.error)

    return logging.getLogger()
