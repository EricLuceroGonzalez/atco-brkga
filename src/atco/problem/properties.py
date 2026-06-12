from __future__ import annotations

from pathlib import Path

# =============================================================================
# CORRESPONDENCIA CON CÓDIGO JAVA
# =============================================================================
# Sin equivalente Java directo.
# Java usa java.util.Properties (parte del JDK) para leer ficheros .properties.
# Este módulo reimplementa ese comportamiento para Python.
# Usado por: parameters.py (Parametros, ParametrosAlgoritmo, PesosObjetivos)
# =============================================================================


def load_properties(path: str | Path) -> dict[str, str]:
    """Load a Java .properties file using the subset used by ABACO."""

    result: dict[str, str] = {}
    current_key: str | None = None
    current_value = ""

    for raw_line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue

        continued = line.endswith("\\")
        if continued:
            line = line[:-1].rstrip()

        if current_key is not None:
            current_value += line
        else:
            key, value = _split_property(line)
            current_key = key
            current_value = value

        if not continued:
            result[current_key] = _unescape_property(current_value.strip())
            current_key = None
            current_value = ""

    if current_key is not None:
        result[current_key] = _unescape_property(current_value.strip())

    return result


def _split_property(line: str) -> tuple[str, str]:
    for index, char in enumerate(line):
        if char in "=:":
            return line[:index].strip(), line[index + 1 :].strip()
    parts = line.split(None, 1)
    if len(parts) == 1:
        return parts[0].strip(), ""
    return parts[0].strip(), parts[1].strip()


def _unescape_property(value: str) -> str:
    replacements = {
        r"\:": ":",
        r"\=": "=",
        r"\ ": " ",
        r"\\": "\\",
        r"\t": "\t",
        r"\n": "\n",
        r"\r": "\r",
    }
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    return value
