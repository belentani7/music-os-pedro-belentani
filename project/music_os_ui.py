"""MUSIC OS · interfaz Streamlit.

Principios de esta pantalla:

* Se puede **probar sin Ollama**: el modo demo es una opción explícita y la UI
  lo etiqueta como simulación en todos los sitios donde importa.
* Estados vacío, de carga y de error diseñados (no un ``st.error`` genérico).
* Lo que se descarga se puede **ver antes**: piano-roll del MIDI real y hoja
  de sesión.
* Nada se anuncia como publicado ni como máster de audio: MIDI es un boceto
  de arreglo y la originalidad es una estimación del modelo.

Se ejecuta con:
    streamlit run project/music_os_ui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

if __package__ in (None, ""):
    # Ejecutado como script: ``streamlit run project/music_os_ui.py``.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project.history_store import HistoryStore
from project.midi_export import GROOVE_MODES, parse_midi
from project.music_ir import MusicIR
from project.music_os_core import (
    DEFAULT_MODEL,
    DEMO_MODEL,
    GenerationError,
    ModelUnavailableError,
    MusicOS,
)
from project.piano_roll import RollNote, render_piano_roll_svg
from project.session_report import render_session_sheet

APP_VERSION = "2.0"
HISTORY_PATH = Path.cwd() / "music_os_history.json"
PALETTE = {"ink": "#f5f7fa", "muted": "#a4acb7", "accent": "#ff9aac", "bass": "#7fd1e8"}

GROOVE_HELP = {
    "auto": "Elige por sección: arpegio en intro/verso, stabs en coro, pad en puente/outro.",
    "arpeggio": "Corcheas arpegiadas con acentos, estilo intro íntima.",
    "pad": "Acordes sostenidos de compás entero, estilo ambient.",
    "stab": "Bloques rítmicos con aire entre golpes, estilo coro.",
}

STYLE_OPTIONS = ["Lady Gaga", "The Smiths", "Anitta", "Nathy Peluso", "Björk", "Radiohead"]
LANGUAGES = ["Español", "Portugués", "Inglés", "Catalán", "Francés"]
KEYS = ["Am", "C", "Dm", "G", "Em", "Fmaj7", "Bm", "F", "Bb", "C#m", "Eb"]
MODEL_HELP = (
    "`demo-mode` es una simulación local, sin modelo: sirve para probar el flujo. "
    "Con un modelo real hace falta Ollama en tu equipo (`ollama pull qwen2.5:7b`)."
)


# --------------------------------------------------------------------- sesión
def _state() -> dict:
    defaults = {
        "model_input": DEFAULT_MODEL,
        "project": None,
        "last_midi": None,
        "last_groove": "auto",
        "include_bass": True,
        "history_warning": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    return st.session_state


def _history() -> HistoryStore:
    return HistoryStore(HISTORY_PATH, max_entries=50)


def _is_demo(model: str) -> bool:
    return model.strip().lower() == DEMO_MODEL


def _provider_badge(model: str) -> tuple[str, str]:
    if _is_demo(model):
        return ":violet-badge[DEMO · SIMULACIÓN LOCAL]", "warning"
    return f":blue-badge[OLLAMA · {model or DEFAULT_MODEL}]", "info"


def _piano_roll_svg(midi_bytes: bytes, beats_per_bar: int = 4) -> str:
    parsed = parse_midi(midi_bytes)
    notes = [
        RollNote(pitch=n.pitch, start=n.start, duration=n.duration, velocity=n.velocity, channel=n.channel)
        for n in parsed.notes
    ]
    return render_piano_roll_svg(notes, beats_per_bar=beats_per_bar)


def _render_downloads(engine: MusicOS, ir: MusicIR) -> None:
    groove = st.segmented_control(
        "Groove de la maqueta MIDI",
        options=list(GROOVE_MODES),
        default=st.session_state["last_groove"],
        format_func=lambda option: option.capitalize(),
        help="Afecta a la maqueta MIDI que descargas, no a la letra ni a los acordes.",
        key="groove_selector",
    )
    groove = groove or "auto"
    include_bass = st.toggle("Incluir pista de bajo", value=st.session_state["include_bass"], key="bass_toggle")
    st.session_state["last_groove"] = groove
    st.session_state["include_bass"] = include_bass

    try:
        midi_result = engine.export_midi_result(groove, include_bass=include_bass)
    except ValueError as exc:
        st.error(f"No se pudo generar el MIDI: {exc}")
        return

    st.session_state["last_midi"] = midi_result.data

    meters = ir.musical.get("meter", "4/4")
    try:
        beats_per_bar = int(str(meters).split("/")[0])
    except (ValueError, IndexError):
        beats_per_bar = 4
    st.markdown(
        f'<div class="roll-frame">{_piano_roll_svg(midi_result.data, beats_per_bar)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Maqueta MIDI real · {midi_result.tracks} pistas · {midi_result.bars} compases · "
        f"{midi_result.notes} notas · groove **{groove}**. "
        "El MIDI es un boceto de arreglo, no un máster de audio ni una voz cantada."
    )
    for warning in midi_result.warnings:
        st.warning(warning)

    sheet = render_session_sheet(ir, midi_result, groove=groove)
    slug = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in str(ir.metadata.get("title", "proyecto")))
    slug = slug.strip().replace(" ", "_") or "proyecto"

    columns = st.columns(3)
    columns[0].download_button(
        "Descargar MIDI",
        midi_result.data,
        f"{slug}.mid",
        mime="audio/midi",
        width="stretch",
    )
    columns[1].download_button(
        "Hoja de sesión (.txt)",
        sheet,
        f"{slug}_sesion.txt",
        mime="text/plain",
        width="stretch",
    )
    columns[2].download_button(
        "MusicIR (.json)",
        ir.to_json(),
        f"{slug}_musicir.json",
        mime="application/json",
        width="stretch",
    )


def _render_project(engine: MusicOS, ir: MusicIR) -> None:
    meta = ir.metadata
    st.subheader(f"«{meta.get('title', 'Sin Título')}»")
    badge, _ = _provider_badge(str(meta.get("model") or ""))
    st.markdown(badge, help="Proveedor que generó este proyecto.")
    if str(meta.get("provider")) == "demo":
        st.warning(
            "Este proyecto es una **simulación demo**: la letra y los acordes son un ejemplo "
            "fijo del código, no una composición generada. Descarga y edita con libertad, pero "
            "no lo presentes como resultado de un modelo.",
            icon="⚠️",
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tonalidad", str(ir.musical.get("key")))
    m2.metric("BPM", str(ir.musical.get("bpm")))
    m3.metric("Compás", str(ir.musical.get("meter")))
    m4.metric("Originalidad (estimación)", f"{float(meta.get('originality_score', 0)):.0f}%")

    dynamics = ir.arrangement.get("dynamics") or {}
    if dynamics:
        figure = go.Figure(
            go.Scatter(
                x=list(dynamics.keys()),
                y=list(dynamics.values()),
                mode="lines+markers",
                line={"color": PALETTE["accent"], "width": 3},
                marker={"size": 8},
                fill="tozeroy",
                fillcolor="rgba(255,154,172,.12)",
            )
        )
        figure.update_layout(
            title="Curva de dinámica por sección",
            yaxis={"range": [0, 100], "title": "Energía declarada"},
            xaxis={"title": None},
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=280,
            margin={"l": 10, "r": 10, "t": 50, "b": 10},
        )
        st.plotly_chart(figure, width="stretch")

    left, right = st.columns([3, 2])
    chords_map = ir.harmony.get("chords", {})
    lyrics_map = ir.lyrics.get("content", {})
    with left:
        st.markdown("#### Letra y armonía")
        for index, section in enumerate(ir.sections, start=1):
            header = f"{index:02d} · {section} — {' | '.join(chords_map.get(section, []))}"
            with st.expander(header):
                st.write(lyrics_map.get(section) or "_(instrumental)_")
    with right:
        st.markdown("#### Producción")
        if ir.production.get("interpretation"):
            st.info(f"**Voz:** {ir.production['interpretation']}")
        for section in ir.sections:
            instrumentation = (ir.arrangement.get("instrumentation") or {}).get(section)
            spatial = (ir.arrangement.get("spatial") or {}).get(section)
            if instrumentation or spatial:
                st.markdown(f"**{section}**")
                if instrumentation:
                    st.write(instrumentation)
                if spatial:
                    st.caption(f"Espacio: {spatial}")

    st.markdown("---")
    st.markdown("#### Maqueta y descargas")
    _render_downloads(engine, ir)


def _generate(
    model: str, demo: bool, theme: str, styles: list[str], language: str, bpm: int, key: str, creativity: int
):
    actual_model = DEMO_MODEL if demo else (model.strip() or DEFAULT_MODEL)
    engine = MusicOS(model_name=actual_model, history_file=HISTORY_PATH)
    try:
        if demo:
            with st.status("Generando con el **modo demo** (simulación local)…", expanded=False) as status:
                status.write("Director: fijando objetivo artístico.")
                status.write("Compositor: aplicando el ejemplo demo.")
                status.write("Productor: arreglando instrumentación demo.")
                status.write("Aprendizaje: actualizando patrones.")
                ir = engine.generate_project(theme, styles, language, bpm, key, creativity)
                status.update(label="Proyecto demo listo.", state="complete", expanded=False)
        else:
            with st.status(f"Consultando Ollama (`{actual_model}`)…", expanded=True) as status:
                status.write("Esto puede tardar: el modelo corre en tu equipo.")
                ir = engine.generate_project(theme, styles, language, bpm, key, creativity)
                status.update(label="Proyecto generado.", state="complete", expanded=False)
    except ModelUnavailableError as exc:
        st.error(
            f"{exc}\n\n**Qué hacer:** arranca Ollama (`ollama serve`), descarga el modelo "
            f"(`ollama pull {actual_model}`) o marca «Usar modo demo» para probar el flujo sin modelo.",
            icon="🔌",
        )
        return
    except GenerationError as exc:
        st.error(f"El modelo respondió algo inservible: {exc}. No se ha guardado nada.", icon="🧩")
        return
    except ValueError as exc:
        st.error(str(exc), icon="⚠️")
        return

    st.session_state["project"] = ir.to_dict()
    st.session_state["history_warning"] = engine.history_warning
    st.success("Proyecto generado y guardado en el historial local.")


# ---------------------------------------------------------------------- vista
def main() -> None:
    state = _state()
    st.set_page_config(
        page_title="MUSIC OS · taller de composición local",
        page_icon="🎛️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
          :root { --os-ink:#f5f7fa; --os-muted:#a4acb7; --os-accent:#ff9aac; --os-line:rgba(255,255,255,.14); }
          .stApp { background: radial-gradient(circle at 85% 0%, rgba(255,154,172,.10), transparent 32rem), #090b10; }
          h1, h2, h3 { letter-spacing: -.02em; }
          .os-lede { color: var(--os-muted); max-width: 72ch; font-size: 1.02rem; }
          .roll-frame { border: 1px solid var(--os-line); border-radius: 12px; padding: .75rem;
                        background: #11151d; margin-top: .5rem; }
          [data-testid="stMetricValue"] { color: var(--os-accent); }
          /* Botón primario: texto casi negro sobre rosa => 9.6:1 (AA/AAA). */
          [data-testid="stBaseButton-primary"] { color: #0a0d12 !important; font-weight: 700; }
          [data-testid="stBaseButton-primary"]:hover { border-color: #fff !important; }
          [data-testid="stDownloadButton"] button { font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("MUSIC OS")
    st.markdown(
        '<p class="os-lede">Taller local de preproducción musical: de un concepto a un proyecto '
        "MusicIR editable, una maqueta MIDI y una hoja de sesión para tu DAW. Sin nube, sin "
        "suscripción y sin prometer másters que un MIDI no puede entregar.</p>",
        unsafe_allow_html=True,
    )
    st.markdown(f":gray-badge[v{APP_VERSION}] :gray-badge[MusicIR v2] :gray-badge[Historial local]")

    # ---------------------------------------------------------------- sidebar
    with st.sidebar:
        st.header("Configuración")
        demo = st.toggle(
            "Usar modo demo (sin modelo)",
            value=_is_demo(state["model_input"]),
            help="Simulación local con un proyecto de ejemplo fijo. Sirve para probar la interfaz.",
        )
        if demo:
            st.caption("Modo demo activo: **no** se llama a ningún modelo.")
            model = DEMO_MODEL
        else:
            model = st.text_input(
                "Modelo Ollama",
                value=state["model_input"] if not _is_demo(state["model_input"]) else DEFAULT_MODEL,
                help=MODEL_HELP,
            )
            state["model_input"] = model or DEFAULT_MODEL

        st.divider()
        creativity = st.slider("Creatividad", 0, 100, 75, help="Se envía al compositor; el modelo decide cómo usarla.")
        language = st.selectbox("Idioma", LANGUAGES)
        styles = st.multiselect("Fusión de estilos", STYLE_OPTIONS, default=["Lady Gaga", "The Smiths"])
        bpm = st.slider("BPM", 60, 180, 105)
        key = st.selectbox("Tonalidad", KEYS, index=0)

        st.divider()
        if st.button("Limpiar historial", width="stretch"):
            removed = _history().clear()
            st.session_state["project"] = None
            st.toast("Historial borrado." if removed else "No había historial.")

    # ---------------------------------------------------------------- pestañas
    tab_compose, tab_learn, tab_history = st.tabs(["Composición", "Aprendizaje", "Historial"])

    with tab_compose:
        with st.form("compose_form", border=False):
            theme = st.text_area(
                "Concepto creativo",
                placeholder="Ej.: la alienación en la era digital con un toque de cabaret oscuro…",
                height=110,
            )
            submitted = st.form_submit_button("Generar proyecto", type="primary", width="stretch")
        if submitted:
            if not theme.strip():
                st.error("Escribe un concepto: sin tema no hay canción.", icon="✏️")
            else:
                _generate(model, demo, theme, styles, language, bpm, key, creativity)
                state["project"] = st.session_state.get("project")

        project_payload = st.session_state.get("project")
        if st.session_state.get("history_warning"):
            st.warning(st.session_state["history_warning"])
        if project_payload:
            engine = MusicOS(
                model_name=str(project_payload.get("metadata", {}).get("model") or DEMO_MODEL),
                history_file=HISTORY_PATH,
            )
            engine.music_ir = MusicIR.from_dict(project_payload)
            _render_project(engine, engine.music_ir)
        else:
            st.markdown("---")
            st.markdown("#### Estado vacío")
            st.info(
                "Todavía no hay proyecto. Escribe un concepto y pulsa **Generar proyecto**.\n\n"
                "Si no tienes Ollama instalado, activa **Usar modo demo** en la barra lateral: "
                "verás el flujo completo con un proyecto de ejemplo, claramente etiquetado como simulación.",
                icon="🎼",
            )
            st.markdown(
                "**Qué obtendrás:** estructura por secciones, acordes con extensiones, letra, "
                "instrumentación, curva de dinámica, maqueta MIDI con tres grooves y hoja de sesión."
            )

    with tab_learn:
        st.markdown("#### Evolución del criterio artístico")
        entries = _history().load()
        if not entries:
            st.info("Aún no hay historial. Genera un proyecto y el sistema empezará a acumular patrones.", icon="🌱")
        else:
            frame = pd.DataFrame(
                [
                    {
                        "Proyecto": entry.get("title", "Sin Título"),
                        "Originalidad (estimación)": float(
                            (entry.get("metadata") or {}).get("originality_score", 0) or 0
                        ),
                        "Creatividad": int((entry.get("metadata") or {}).get("creativity_level", 0) or 0),
                        "Proveedor": (entry.get("metadata") or {}).get("provider", "—"),
                    }
                    for entry in entries
                ]
            )
            figure = go.Figure()
            figure.add_trace(
                go.Scatter(
                    x=frame["Proyecto"],
                    y=frame["Originalidad (estimación)"],
                    mode="lines+markers",
                    name="Originalidad (estimación)",
                    line={"color": PALETTE["accent"], "width": 3},
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=frame["Proyecto"],
                    y=frame["Creatividad"],
                    mode="lines",
                    name="Creatividad pedida",
                    line={"color": PALETTE["muted"], "width": 2, "dash": "dot"},
                )
            )
            figure.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=320,
                margin={"l": 10, "r": 10, "t": 20, "b": 10},
                yaxis={"range": [0, 100]},
            )
            st.plotly_chart(figure, width="stretch")
            st.caption(
                "La originalidad es una estimación que devolvió el modelo, no una medida "
                "independiente ni una garantía de originalidad artística."
            )

            last = entries[-1]
            patterns = (last.get("memory") or {}).get("learned_patterns") or []
            metrics = (last.get("evaluation") or {}).get("evolution_metrics") or {}
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Patrones usados en la última sesión**")
                if patterns:
                    for pattern in patterns:
                        st.markdown(f"- {pattern}")
                else:
                    st.caption("Sin patrones registrados.")
            with c2:
                st.markdown("**Métricas declaradas por el modelo**")
                if metrics:
                    for name, value in metrics.items():
                        st.markdown(f"- {str(name).replace('_', ' ').capitalize()}: {value}")
                else:
                    st.caption("Sin métricas registradas.")

    with tab_history:
        st.markdown("#### Memoria local")
        st.caption(f"Archivo: `{HISTORY_PATH.name}` — vive en tu equipo y no se sube a ningún sitio.")
        entries = _history().load()
        if not entries:
            st.info("Historial vacío.", icon="🗂️")
        else:
            rows = [
                {
                    "Título": entry.get("title", "Sin Título"),
                    "Tonalidad": entry.get("key"),
                    "BPM": entry.get("bpm"),
                    "Secciones": len(entry.get("sections") or []),
                    "Proveedor": (entry.get("metadata") or {}).get("provider", "—"),
                }
                for entry in reversed(entries)
            ]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            selected = st.selectbox("Cargar un proyecto del historial", [row["Título"] for row in rows], index=None)
            if selected:
                entry = next(e for e in reversed(entries) if e.get("title") == selected)
                st.session_state["project"] = MusicIR.from_dict(entry).to_dict()
                st.success(f"«{selected}» cargado en Composición.")

    st.markdown("---")
    st.caption(
        "MUSIC OS · el motor corre en local con Ollama o en modo demo. "
        "La web pública solo muestra esta herramienta; no ejecuta modelos ni genera canciones online."
    )


if __name__ == "__main__":
    main()
