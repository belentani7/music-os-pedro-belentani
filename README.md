# MUSIC OS — Pedro Belentani

Taller **local** de preproducción musical: de un concepto a un proyecto editable
(`MusicIR`), una maqueta **MIDI real** a tres pistas y una hoja de sesión para tu
DAW. Corre en tu equipo con [Ollama](https://ollama.com/) o en **modo demo**,
sin modelo y sin nube.

> **Qué no es:** el MIDI no es un máster de audio, ni una mezcla, ni una canción
> cantada. La puntuación de originalidad es una estimación del modelo, no una
> medición independiente. La web pública solo presenta el proyecto: no ejecuta
> Ollama ni genera canciones online.

## Instalar

```bash
git clone https://github.com/belentani7/music-os-pedro-belentani.git
cd music-os-pedro-belentani
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

Python 3.10 o superior. El núcleo y la CLI necesitan solo `midiutil` (y `ollama`
si vas a usar un modelo real); Streamlit, pandas y plotly son para la interfaz.

## Usar

### Interfaz

```bash
streamlit run project/music_os_ui.py
```

- **Sin modelo:** activa **«Usar modo demo»** en la barra lateral. Recorres todo
  el flujo con un proyecto de ejemplo que la interfaz marca como *simulación*.
- **Con modelo:** arranca Ollama (`ollama serve`) y descarga el modelo
  (`ollama pull qwen2.5:7b`). Si el modelo falla, la app lo dice y **no**
  sustituye el resultado por la demo.

Obtienes: estructura por secciones, acordes con extensiones, letra, dirección
vocal, instrumentación, curva de dinámica, **piano-roll del MIDI real** y tres
descargas (MIDI, hoja de sesión, MusicIR).

### CLI

```bash
python -m tools.music_os_cli --help
python -m tools.music_os_cli generate --theme "alienación digital" --demo --out salida/
python -m tools.music_os_cli verify salida/*.mid
python -m tools.music_os_cli inspect salida/*.musicir.json
python -m tools.music_os_cli history --limit 5
python -m tools.music_os_cli clear-history --yes
```

`generate` escribe cuatro artefactos: `.musicir.json` (proyecto), `.mid`
(maqueta), `.txt` (hoja de sesión) y `.svg` (piano-roll generado del MIDI).

## Probar

```bash
python -m unittest discover -s tests -p "test_*.py" -v   # 65 pruebas
python -m project.stress_test_music_os                   # 4 casos demo
ruff check . && ruff format --check .                     # lint
```

La suite no toca tu historial ni escribe en el repositorio: usa directorios
temporales. La interfaz se prueba con `streamlit.testing.v1.AppTest`.

## Cómo funciona

```
tools/music_os_cli.py ─┐
project/music_os_ui.py ─┴─▶ project/music_os_core.py ─▶ agents (Director → Compositor → Productor → Aprendizaje)
                                   │                        │
                                   ▼                        ▼
                          project/music_ir.py        project/midi_export.py
                          (validación/migración)     (SMF 1: tempo+compás+armadura,
                                   │                   armonía GM5, bajo GM39)
                                   ├─▶ project/music_theory.py (una sola fuente de acordes)
                                   ├─▶ project/history_store.py (escritura atómica, tolera corrupción)
                                   └─▶ project/session_report.py + project/piano_roll.py
```

| Módulo | Responsabilidad |
|---|---|
| `project/music_theory.py` | Interpreta acordes («Am9», «E7#9», «C/E») y armaduras. |
| `project/music_ir.py` | Esquema 2.0 del proyecto, migración y `validate()`. |
| `project/midi_export.py` | Exportación y lectura de MIDI (grooves `auto`, `arpeggio`, `pad`, `stab`). |
| `project/history_store.py` | Historial local atómico y acotado; aparta archivos corruptos. |
| `project/music_os_core.py` | Agentes y ciclo de generación; proveedor LLM inyectable. |
| `project/music_os_ui.py` | Interfaz Streamlit con estados vacío/carga/error. |
| `project/agente_compositor_universal.py` | Variante de una sola llamada al modelo. |
| `tools/music_os_cli.py` | `generate`, `inspect`, `verify`, `history`, `clear-history`. |

## Datos

La app escribe `music_os_history.json` en el directorio desde el que la lanzas
(50 entradas como máximo, solo resúmenes). Está en `.gitignore`. Bórralo desde la
interfaz o con la CLI. Si el archivo se corrompe, se aparta como
`music_os_history.json.corrupt-<fecha>` y la app continúa.

## Publicación web

`vercel.json` publica `site/` como HTML estático, sin build de Node. La portada
raíz (`index.html`) sirve para GitHub Pages con los mismos contenidos. Cinco
páginas: portada, documentación, accesibilidad, privacidad y 404.

## Histórico

`versions/`, `docs/` y `plataforma/` conservan el material original del
proyecto. Las versiones antiguas del motor están en `versions/` tal cual, sin
modificar.

## Licencia

Consulta [LICENSE](LICENSE).
