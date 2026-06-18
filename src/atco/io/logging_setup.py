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
from pathlib import Path


def setup_logging(
    log_dir: str | Path = "docs/logs/",
    log_filename: str = "logs.log",
    level: str | int = "INFO",
    redirect_print: bool = True,
) -> logging.Logger:
    """Inicializa logging con salida a archivo y stdout.

    Args:
        log_dir: Directorio donde se guarda el archivo. Se crea si no existe.
        log_filename: Nombre del archivo de log (sin la ruta).
        level: Nivel mínimo a registrar. Acepta string (``"DEBUG"``,
            ``"INFO"``, ``"WARNING"``, ``"ERROR"``) o el entero
            equivalente de ``logging``.
        redirect_print: Si True, redirige ``stdout`` y ``stderr`` al
            logger para que ``print()`` y errores no formateados pasen
            por el sistema.

    Returns:
        El root logger ya configurado.
    """

    level_int = _to_level(level)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    full_path = log_path / log_filename

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = logging.FileHandler(full_path, encoding="utf-8")
    file_handler.setLevel(level_int)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level_int)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # evita duplicados si se llama 2 veces
    root_logger.setLevel(level_int)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

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

    if redirect_print:
        sys.stdout = LoggerWriter(logging.info)  # type: ignore[assignment]
        sys.stderr = LoggerWriter(logging.error)  # type: ignore[assignment]

    return root_logger


def _to_level(value: str | int) -> int:
    if isinstance(value, str):
        return getattr(logging, value.upper(), logging.INFO)
    return value
