"""Configuración global de logging.

Redirige `sys.stdout` y `sys.stderr` al sistema de logging para que
mensajes de `print()` y de bibliotecas externas (incluyendo la JVM
en versiones antiguas) acaben en el mismo archivo y formato que los
logs estructurados.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any


def setup_logging(
    log_name: str = "abaco.log",
    level: str | int = "INFO",
) -> logging.Logger:
    """Inicializa logging con salida a archivo + stdout.

    Args:
        log_name: Ruta del archivo de log.
        level: Nivel mínimo a registrar. Acepta un string
            (``"DEBUG"``, ``"INFO"``, …) o el entero equivalente
            de ``logging``.

    Returns:
        El root logger ya configurado.
    """
    level_int: int = (
        getattr(logging, level.upper(), logging.INFO)
        if isinstance(level, str)
        else level
    )
    logging.basicConfig(
        level=level_int,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_name, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    class LoggerWriter:
        """Adapta una función de logging al protocolo de stream (write/flush).

        Permite hacer ``sys.stdout = LoggerWriter(logger.info)`` y que
        cualquier ``print()`` posterior acabe pasando por el logger.
        """

        def __init__(self, level: Callable[[str], None]) -> None:
            self.level = level

        def write(self, message: str) -> None:
            stripped = message.strip()
            if stripped:
                self.level(stripped)

        def flush(self) -> None:
            pass

    sys.stdout = LoggerWriter(logging.info)  # type: ignore[assignment]
    sys.stderr = LoggerWriter(logging.error)  # type: ignore[assignment]

    return logging.getLogger()
