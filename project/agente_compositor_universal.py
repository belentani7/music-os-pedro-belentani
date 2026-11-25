"""Agente Compositor Universal: una sola pasada de LLM → canción + MIDI.

Vive como módulo independiente de ``project.music_os_core`` porque su flujo
(una única llamada con un prompt «mega») es distinto del ciclo multi-agente.
Lo que se corrige respecto a la versión anterior:

* ``ollama`` ya no se usa sin importar: un fallo del proveedor produce un
  mensaje claro y nunca un ``NameError``.
* El mapa de acordes duplicado desaparece: se usa ``project.music_theory``,
  la misma fuente que el motor principal.
* El JSON del LLM se valida (secciones, acordes legibles) antes de exportar.
* La exportación MIDI usa el mismo renderizador que el resto (mismo formato,
  mismos grooves), en vez de un segundo exportador divergente.

Uso como biblioteca:
    >>> from project.agente_compositor_universal import AgenteCompositorUniversal
    >>> agente = AgenteCompositorUniversal(model_name="demo-mode")
    >>> song = agente.compose("soledad espacial", "Español", ["The Smiths"], 100, "Am", 70)

Uso como app:
    streamlit run project/agente_compositor_universal.py
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .midi_export import GROOVE_MODES, render_project
from .music_ir import MusicIR, dedupe_section_names
from .music_theory import is_chord

PHONETIC_DIRECTIVES = {
    "Español": (
        "REGLA DE ORO: piensa nativamente en español. Usa fricativas y vibrantes (rr, ll, y) "
        "para actitud y tensión; juega con el ritmo de las sílabas."
    ),
    "Portugués": (
        "REGRA DE OURO: pense em português brasileiro nativo. Use vogais nasais (ão, em, am) "
        "para sustentar notas longas e oclusivas para percussão vocal."
    ),
    "Inglés": (
        "GOLDEN RULE: think natively in English. Use stress-timed rhythm and consonant "
        "clusters (tr, bl, str) for percussive flow."
    ),
    "Catalán": (
        "REGLA D'OR: pensa nativament en català. Explota les vocals neutres i tancades per a la "
        "intimitat i obre les vocals a la tornada."
    ),
    "Francés": (
        "RÈGLE D'OR: pense nativement en français. Utilise les liaisons pour lier les mots et "
        "les voyelles nasales pour la mélancolie."
    ),
}

STYLE_MATRICES = {
    "Lady Gaga": "Teatralidad pop, drama, cambios de tempo y vulnerabilidad como espectáculo.",
    "The Smiths": "Melancolía indie, letras de alienación, intercambio modal y guitarras jangly.",
    "Anitta": "Groove percusivo, actitud, síncopa y flow sensual/urbano.",
    "Nathy Peluso": "Tensión armónica, visceralidad, fusión jazz/tango y entrega vocal cruda.",
}

DEMO_SONG: dict[str, Any] = {
    "title": "Soledad de Neón",
    "bpm": 100,
    "key": "Am",
    "structure": ["Verso 1", "Pre-Coro", "Coro", "Puente", "Coro", "Outro"],
    "lyrics": {
        "Verso 1": "Camino por la avenida sin mirar atrás, / cada faro es un recuerdo que no va a volver.",
        "Pre-Coro": "Y el ruido de la ciudad me enseña a respirar, / a sostener la duda sin caer.",
        "Coro": "Somos soledad de neón, / dos sombras que aprendieron a brillar.",
        "Puente": "Si el silencio nos pregunta dónde estamos, / responderemos con la voz.",
        "Outro": "Soledad de neón… / soledad de neón.",
    },
    "chords": {
        "Verso 1": ["Am9", "Fmaj7", "Cmaj7", "G7sus4"],
        "Pre-Coro": ["Dm7", "Em7", "Fmaj7", "G7"],
        "Coro": ["Fmaj7", "Cmaj7", "Am7", "G"],
        "Puente": ["Dm9", "G7sus4", "Cmaj7", "E7#9"],
        "Outro": ["Am9", "Fmaj7"],
    },
    "vocal_direction": (
        "Verso en susurro contenido con síncopa; coro abierto y teatral; puente hablado, casi confesional."
    ),
    "originality_score": 70,
}


class CompositorError(RuntimeError):
    """Error de composición con mensaje apto para la persona usuaria."""


class AgenteCompositorUniversal:
    """Genera una canción completa en una sola llamada y la exporta a MIDI."""

    def __init__(self, model_name: str = "qwen2.5:7b", provider=None):
        self.model = model_name
        self._provider = provider

    # ------------------------------------------------------------------ LLM
    def _call(self, system_prompt: str, prompt: str) -> str:
        if self._provider is not None:
            return self._provider(self.model, system_prompt, prompt)
        if self.model == "demo-mode":
            return json.dumps(DEMO_SONG, ensure_ascii=False)
        try:
            import ollama

            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                format="json",
            )
        except Exception as exc:
            raise CompositorError(
                f"Ollama no disponible para el modelo {self.model!r}; inicia Ollama o usa demo-mode explícitamente."
            ) from exc
        content = response.get("message", {}).get("content", "")
        if not str(content).strip():
            raise CompositorError("El modelo devolvió una respuesta vacía.")
        return content

    @staticmethod
    def clean_json_from_llm(raw_text: str) -> str:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        return raw_text[start : end + 1] if start != -1 and end != -1 else raw_text

    # -------------------------------------------------------------- prompts
    @staticmethod
    def build_mega_prompt(
        language: str,
        styles: list[str],
        theme: str,
        bpm: int,
        key: str,
        creativity: int = 70,
    ) -> str:
        phonetic = PHONETIC_DIRECTIVES.get(language, PHONETIC_DIRECTIVES["Español"])
        style_text = " + ".join(STYLE_MATRICES.get(style, "") for style in styles) or "(libre)"
        return f"""
        Eres el ALGORITMO DE COMPOSICIÓN UNIVERSAL de MUSIC OS.
        {phonetic}

        CONTEXTO ARTÍSTICO (FUSIÓN):
        {style_text}

        PARÁMETROS:
        - Idioma: {language.upper()}
        - Tema: {theme}
        - BPM: {bpm}
        - Tonalidad: {key}
        - Creatividad: {creativity}%

        INSTRUCCIONES TÉCNICAS:
        1. Acordes con extensiones (7, 9, maj7, m7b5, alt, sus).
        2. Estructura con dinámicas contrastadas.
        3. Marca con MAYÚSCULAS la sílaba fuerte de cada verso.
        4. NO TRADUZCAS: escribe directamente en {language}.

        DEVUELVE ÚNICAMENTE UN JSON VÁLIDO CON ESTA ESTRUCTURA:
        {{
            "title": "Título",
            "bpm": {bpm},
            "key": "{key}",
            "structure": ["Verso 1", "Pre-Coro", "Coro", "Puente", "Coro", "Outro"],
            "lyrics": {{ "Verso 1": "...", "Coro": "..." }},
            "chords": {{ "Verso 1": ["Am9", "Fmaj7"], "Coro": ["Fmaj7", "G"] }},
            "vocal_direction": "Instrucciones de tono y actitud.",
            "originality_score": 0
        }}
        """

    # ------------------------------------------------------------ composición
    def compose(
        self,
        theme: str,
        language: str,
        styles: list[str],
        bpm: int,
        key: str,
        creativity: int = 70,
    ) -> dict[str, Any]:
        """Devuelve un ``song_data`` validado y listo para ``generate_midi``."""
        prompt = self.build_mega_prompt(language, styles, theme, bpm, key, creativity)
        raw = self._call("Eres un motor de composición. Devuelve solo JSON válido.", prompt)
        try:
            data = json.loads(self.clean_json_from_llm(raw))
        except (json.JSONDecodeError, TypeError) as exc:
            raise CompositorError("La respuesta del modelo no es JSON válido.") from exc
        if not isinstance(data, dict):
            raise CompositorError("La respuesta del modelo no es un objeto JSON.")
        return self._validate_song(data, bpm=bpm, key=key)

    @staticmethod
    def _validate_song(data: dict[str, Any], *, bpm: int, key: str) -> dict[str, Any]:
        structure = data.get("structure")
        if not isinstance(structure, list) or not structure:
            raise CompositorError("La canción no trae una estructura por secciones.")
        chords_raw = dict(data.get("chords")) if isinstance(data.get("chords"), dict) else {}
        lyrics_raw = dict(data.get("lyrics")) if isinstance(data.get("lyrics"), dict) else {}
        original = [str(section).strip() for section in structure if str(section).strip()]
        structure = dedupe_section_names(original)
        if structure != original:
            # «Coro» repetido → «Coro 2»: hereda la letra y los acordes de la
            # primera aparición en lugar de quedarse sin contenido.
            for index, name in enumerate(structure):
                base = original[index]
                if name == base:
                    continue
                chords_raw.setdefault(name, chords_raw.get(base, []))
                lyrics_raw.setdefault(name, lyrics_raw.get(base, ""))
        chords: dict[str, list[str]] = {}
        for section in structure:
            symbols = [str(symbol).strip() for symbol in chords_raw.get(section, []) if str(symbol).strip()]
            readable = [symbol for symbol in symbols if is_chord(symbol)]
            if not readable:
                raise CompositorError(f"La sección {section!r} no tiene acordes legibles.")
            chords[section] = readable

        try:
            song_bpm = int(data.get("bpm") or bpm)
        except (TypeError, ValueError):
            song_bpm = bpm
        try:
            score = float(data.get("originality_score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0

        return {
            "title": str(data.get("title") or "Sin Título").strip() or "Sin Título",
            "bpm": max(20, min(300, song_bpm)),
            "key": str(data.get("key") or key),
            "structure": structure,
            "lyrics": {section: str(lyrics_raw.get(section, "")).strip() for section in structure},
            "chords": chords,
            "vocal_direction": str(data.get("vocal_direction") or ""),
            "originality_score": max(0.0, min(100.0, score)),
        }

    # ------------------------------------------------------------------ MIDI
    def to_music_ir(self, song_data: dict[str, Any], language: str = "Español", theme: str = "") -> MusicIR:
        ir = MusicIR()
        ir.metadata["title"] = song_data.get("title", "Sin Título")
        ir.metadata["originality_score"] = song_data.get("originality_score", 0.0)
        ir.metadata["provider"] = "demo" if self.model == "demo-mode" else ("callable" if self._provider else "ollama")
        ir.metadata["model"] = self.model
        ir.concept["core_idea"] = theme
        ir.musical["bpm"] = song_data.get("bpm", 105)
        ir.musical["key"] = song_data.get("key", "Am")
        ir.musical["sections"] = list(song_data.get("structure", []))
        ir.lyrics["language"] = language
        ir.lyrics["content"] = dict(song_data.get("lyrics", {}))
        ir.harmony["chords"] = dict(song_data.get("chords", {}))
        ir.production["interpretation"] = song_data.get("vocal_direction", "")
        return ir

    def generate_midi(self, song_data: dict[str, Any], groove: str = "auto", *, language: str = "Español"):
        """Objeto ``MIDIFile`` equivalente, para quien ya usara esta API."""
        if groove not in GROOVE_MODES:
            raise ValueError(f"Groove desconocido {groove!r}.")
        ir = self.to_music_ir(song_data, language=language)
        result = render_project(ir, groove)
        from midiutil import MIDIFile

        midi = MIDIFile(1)
        midi.addTempo(0, 0, int(ir.musical["bpm"]))
        # Reutiliza el archivo ya renderizado: esta API solo devuelve el objeto
        # que Streamlit necesita para ``writeFile``; los bytes canónicos salen
        # de ``render_project`` (export_midi_bytes).
        midi_bytes = result.data
        self.last_midi_bytes = midi_bytes
        from project.midi_export import parse_midi

        parsed = parse_midi(midi_bytes)
        for note in parsed.notes:
            midi.addNote(0, note.channel, note.pitch, note.start, note.duration, note.velocity)
        return midi

    def export_midi_bytes(self, song_data: dict[str, Any], groove: str = "auto", *, language: str = "Español") -> bytes:
        """Bytes MIDI canónicos (formato 1, varias pistas) del song_data."""
        ir = self.to_music_ir(song_data, language=language)
        return render_project(ir, groove).data


def _render_streamlit() -> None:  # pragma: no cover - requiere navegador
    import streamlit as st

    from .piano_roll import RollNote, render_piano_roll_svg
    from .session_report import render_session_sheet

    st.set_page_config(page_title="Agente Compositor Universal", page_icon="🎛️", layout="wide")
    st.title("Agente Compositor Universal")
    st.caption("Una sola pasada de modelo → canción + maqueta MIDI. Mismo núcleo que MUSIC OS.")

    with st.sidebar:
        st.header("Configuración")
        demo = st.toggle("Modo demo (sin modelo)", value=True)
        model = "demo-mode" if demo else st.text_input("Modelo Ollama", value="qwen2.5:7b")
        language = st.selectbox("Idioma", list(PHONETIC_DIRECTIVES))
        styles = st.multiselect("Fusión de estilos", list(STYLE_MATRICES), default=["Lady Gaga", "The Smiths"])
        bpm = st.slider("BPM", 60, 180, 100)
        key = st.selectbox("Tonalidad", ["Am", "C", "Dm", "G", "Em", "Fmaj7", "Bm", "F", "Bb"])
        creativity = st.slider("Creatividad", 0, 100, 70)

    theme = st.text_area(
        "Concepto o tema de la canción", placeholder="Ej.: la soledad de un astronauta en una discoteca abandonada…"
    )

    if st.button("Componer", type="primary"):
        if not theme.strip():
            st.error("Escribe un tema.")
            return
        agent = AgenteCompositorUniversal(model_name=model)
        try:
            with st.status("Componiendo…", expanded=False) as status:
                song = agent.compose(theme, language, styles, bpm, key, creativity)
                status.update(label="Canción lista.", state="complete")
        except CompositorError as exc:
            st.error(f"{exc}\n\nArranca Ollama o usa el modo demo.")
            return

        st.subheader(f"«{song['title']}»")
        st.caption(f"{song['key']} · {song['bpm']} BPM · proveedor {'demo' if demo else model}")
        if song.get("vocal_direction"):
            st.info(f"**Dirección vocal:** {song['vocal_direction']}")
        for section in song["structure"]:
            with st.expander(f"{section} — {' | '.join(song['chords'][section])}"):
                st.write(song["lyrics"].get(section) or "_(instrumental)_")

        midi_bytes = agent.export_midi_bytes(song, "auto", language=language)
        ir = agent.to_music_ir(song, language=language, theme=theme)
        svg = render_piano_roll_svg(
            [
                RollNote(pitch=n.pitch, start=n.start, duration=n.duration, velocity=n.velocity, channel=n.channel)
                for n in __import__("project.midi_export", fromlist=["parse_midi"]).parse_midi(midi_bytes).notes
            ]
        )
        st.markdown(f'<div class="roll-frame">{svg}</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        cols[0].download_button("Descargar MIDI", midi_bytes, f"{song['title']}.mid", mime="audio/midi")
        cols[1].download_button("Hoja de sesión", render_session_sheet(ir), f"{song['title']}_sesion.txt")
        cols[2].download_button("MusicIR", ir.to_json(), f"{song['title']}_musicir.json")


if __name__ == "__main__":
    if "streamlit" in sys.modules or any("streamlit" in arg for arg in sys.argv):
        _render_streamlit()
    else:
        print(__doc__)
