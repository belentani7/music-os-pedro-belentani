"""Persistencia local del historial de MUSIC OS.

Requisitos que cubre (todos estaban rotos o ausentes antes):

* Un JSON corrupto **no** tumba la aplicación: se aparta a ``*.corrupt-<ts>``
  y se continúa con historial vacío, informándolo.
* Las escrituras son atómicas (temporal + ``os.replace``): un corte de luz a
  mitad de guardado no deja un archivo a medias.
* El tamaño se acota con ``max_entries`` y se puede ``clear()`` desde la UI/CLI.
* Solo se guarda un **resumen** del proyecto (título, tonalidad, acordes,
  letra…), no el IR completo con toda la instrumentación.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

DEFAULT_MAX_ENTRIES = 50


class HistoryStore:
    """Historial en disco con recuperación ante corrupción."""

    def __init__(self, path: str | os.PathLike[str], max_entries: int = DEFAULT_MAX_ENTRIES):
        self.path = Path(path)
        self.max_entries = max(1, int(max_entries))
        self.last_warning: str | None = None

    # --------------------------------------------------------------- lectura
    def load(self) -> list[dict[str, Any]]:
        self.last_warning = None
        if not self.path.exists():
            return []
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.last_warning = self._quarantine(exc)
            return []
        if not isinstance(data, list):
            self.last_warning = self._quarantine(ValueError("la raíz no es una lista"))
            return []
        return [entry for entry in data if isinstance(entry, dict)]

    def _quarantine(self, exc: Exception) -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_suffix(self.path.suffix + f".corrupt-{stamp}")
        try:
            os.replace(self.path, backup)
        except OSError:
            backup = None
        where = f"; copia en {backup.name}" if backup else ""
        return f"Historial ilegible ({type(exc).__name__}); se empieza de cero{where}."

    # -------------------------------------------------------------- escritura
    def append(self, entry: dict[str, Any]) -> Path:
        entries = self.load()
        entries.append(entry)
        if len(entries) > self.max_entries:
            entries = entries[-self.max_entries :]
        return self._write(entries)

    def save(self, entries: list[dict[str, Any]]) -> Path:
        return self._write(entries[-self.max_entries :])

    def clear(self) -> bool:
        """Borra el historial. Devuelve True si existía algo que borrar."""
        existed = self.path.exists()
        try:
            self.path.unlink()
        except FileNotFoundError:
            existed = False
        return existed

    def _write(self, entries: list[dict[str, Any]]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(entries, indent=2, ensure_ascii=False)
        fd, tmp_name = tempfile.mkstemp(prefix=".history-", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)
            raise
        return self.path
