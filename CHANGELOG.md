# Changelog — music-os-pedro-belentani

## [2.0.0] — 2026-11-25

### Añadido
- **Modo demo explícito** en la interfaz: todo el flujo se puede probar sin
  Ollama, siempre etiquetado como simulación (`project/music_os_ui.py`).
- **CLI** `music-os` con `generate`, `inspect`, `verify`, `history` y
  `clear-history` (`tools/music_os_cli.py`), con `--help` y códigos de salida.
- **Teoría musical verificable** (`project/music_theory.py`): acordes, bajos
  alternos, armaduras del círculo de quintas.
- **MusicIR esquema 2.0** (`project/music_ir.py`): `validate()` real y
  migración de documentos antiguos en `from_json`/`from_dict`.
- **Exportador MIDI SMF 1** (`project/midi_export.py`): pista de tempo/compás/
  armadura, armonía, bajo y tres grooves que cambian el archivo de verdad.
  Lector MIDI propio para auditar lo exportado.
- **Historial atómico** (`project/history_store.py`): aparta archivos corruptos,
  escritura con `os.replace` y límite de entradas.
- **Piano-roll SVG** y **hoja de sesión** (`project/piano_roll.py`,
  `project/session_report.py`), generados desde el MIDI real.
- **Sitio unificado** (`site/`): portada, documentación, accesibilidad,
  privacidad y 404 reales; cabeceras de seguridad en `vercel.json`.
- **Suite de 65 pruebas** (`tests/test_engine.py`, `tests/test_interface.py`,
  contrato de publicación ampliado) y CI con dos jobs: núcleo sin UI en Python
  3.10 y 3.12, y suite completa + ruff en 3.12.
- `pyproject.toml` con ruff, `requirements-dev.txt`, tema oscuro
  (`.streamlit/config.toml`) y `.gitignore` de artefactos.

### Corregido
- `from music_os_core import MusicOS` rompía `python -m project.music_os_ui` y
  las pruebas: ahora el paquete es importable desde la raíz y como script.
- `agente_compositor_universal.py` usaba `ollama` sin importar (`NameError`);
  ahora el fallo es un `CompositorError` con instrucciones. Su mapa de acordes
  duplicado desaparece a favor de `music_theory`.
- Historial JSON corrupto tumbaba la aplicación (`JSONDecodeError`).
- Títulos con «—», emoji o griego rompían el MIDI (`UnicodeEncodeError` en
  midiutil); se sanean los meta-eventos.
- El parámetro `style_groove` de `export_midi` no hacía nada; ahora es real.
- Secciones repetidas («Coro», «Coro») perdían acordes y letra; ahora se
  numeran y heredan contenido.
- `stress_test_music_os` escribía `music_os_history.json` y su informe en el
  repositorio; ahora usa un directorio temporal.
- Contraste insuficiente en la interfaz (texto claro sobre botón rosa): tema
  oscuro declarado y texto `#0a0d12` sobre `#ff9aac`.
- Enlaces que apuntaban a `docs.html` chocaban con el directorio `docs/`;
  la página pasa a `documentacion.html`.

### Eliminado
- Pruebas placeholder `test_basic.py` y `test_smoke.py` (`assert True`).
- Páginas `404/accesibilidad/privacidad/docs` de la raíz con `<canvas>` inerte,
  sustituidas por las de `site/`.
