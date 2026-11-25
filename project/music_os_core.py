"""Motor de MUSIC OS: agentes, MusicIR y ciclo de generación.

Cambios sobre la versión anterior (verificados con tests):

* Importable como paquete (``from project.music_os_core import MusicOS``) y
  como script desde ``project/`` gracias a las importaciones relativas
  tolerantes del bloque final.
* El modo demo es **explícito**: ``model_name="demo-mode"``. Un modelo real
  caído lanza ``ModelUnavailableError`` y nunca devuelve la composición demo.
* El proveedor LLM es inyectable (``provider=callable``), lo que permite
  probar el flujo completo sin Ollama y sin mocks frágiles de ``sys.modules``.
* El historial es atómico, tolera corrupción y guarda un resumen acotado.
* ``export_midi`` acepta los tres grooves reales y devuelve bytes válidos.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .history_store import HistoryStore
from .midi_export import GROOVE_MODES, MidiExportResult, render_project
from .music_ir import SCHEMA_VERSION, MusicIR, dedupe_section_names
from .music_theory import is_chord

DEMO_MODEL = "demo-mode"
DEFAULT_MODEL = "qwen2.5:7b"
PROVIDER_DEMO = "demo"
PROVIDER_OLLAMA = "ollama"
PROVIDER_CALLABLE = "callable"

DEFAULT_HISTORY_PATH = Path.cwd() / "music_os_history.json"


class MusicOSError(RuntimeError):
    """Error de negocio del motor, con mensaje apto para mostrar a la persona."""


class ModelUnavailableError(MusicOSError):
    """El modelo real no respondió; jamás se sustituye por la demo."""


class GenerationError(MusicOSError):
    """El modelo respondió algo que no se puede convertir en un proyecto válido."""


def _composer_payload() -> dict[str, Any]:
    return {
        "title": "Eclipse en la Ciudad",
        "structure": ["Intro", "Verso 1", "Coro", "Outro"],
        "lyrics": {
            "Intro": "(Instrumental dramático con piano oscuro)",
            "Verso 1": "Las luces se apagan en el café, / el frío me abraza, no sé por qué. / Busco tu sombra en el cristal, / un rastro dulce, un rastro mal.",
            "Coro": "Es un eclipse en el corazón, / bailando solo, sin razón. / Teatral y crudo, como un adiós, / somos el eco de una sola voz.",
            "Outro": "Solo el eco... / solo la voz.",
        },
        "chords": {
            "Intro": ["Am9", "Fmaj7"],
            "Verso 1": ["Am9", "Fmaj7", "Cmaj7", "E7#9"],
            "Coro": ["Fmaj7", "Cmaj7", "Am7", "G7sus4"],
            "Outro": ["Am9", "Fmaj7"],
        },
        "vocal_direction": (
            "Empieza con un susurro íntimo estilo Morrissey y sube a una entrega teatral "
            "en el coro. Mantén la síncopa del verso."
        ),
        "originality_score": 85,
    }


def _producer_payload() -> dict[str, Any]:
    return {
        "instrumentation": {
            "Intro": "Piano de cola con reverb larga y pad oscuro.",
            "Verso 1": "Piano, bajo sintetizado profundo, chasquidos rítmicos.",
            "Coro": "Batería potente, cuerdas épicas, guitarras con chorus.",
            "Outro": "Solo piano con filtro de paso bajo cerrándose.",
        },
        "dynamics": {"Intro": 20, "Verso 1": 40, "Coro": 90, "Outro": 10},
        "spatial": {
            "Intro": "Espacio inmenso, catedral.",
            "Verso 1": "Espacio íntimo, seco.",
            "Coro": "Ancho estéreo máximo, mucha profundidad.",
            "Outro": "Voz muy cerca del oído.",
        },
    }


def _learning_payload() -> dict[str, Any]:
    return {
        "learned_patterns": [
            "Uso recurrente de Am9 para melancolía",
            "Preferencia por estribillos explosivos a 90% de dinámica",
        ],
        "evolution_metrics": {"creativity_growth": 15, "style_coherence": 92},
    }


class MusicOSAgent:
    """Clase base de los agentes de MUSIC OS."""

    demo_payload: Callable[[], dict[str, Any]] | None = None

    def __init__(
        self,
        name: str,
        model_name: str = DEFAULT_MODEL,
        provider: Callable[[str, str, str], str] | None = None,
    ):
        self.name = name
        self.model = model_name
        self._provider = provider

    @property
    def uses_demo(self) -> bool:
        return self.model == DEMO_MODEL or self._provider is not None

    def call_llm(self, prompt: str, system_prompt: str = "") -> str:
        """Llamada al LLM. La demo solo se usa cuando se pide explícitamente."""
        if self._provider is not None:
            return self._provider(self.model, system_prompt, prompt)

        if self.model == DEMO_MODEL:
            if self.demo_payload is None:
                return "{}"
            return json.dumps(self.demo_payload(), ensure_ascii=False)

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
            content = response["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("respuesta vacía del modelo")
            return content
        except Exception as exc:
            raise ModelUnavailableError(
                f"Ollama no disponible para el modelo {self.model!r}; inicia Ollama o utiliza demo-mode explícitamente."
            ) from exc

    @staticmethod
    def clean_json(raw_text: str) -> str:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        return raw_text[start : end + 1] if start != -1 and end != -1 else raw_text

    def _payload(self, raw_text: str, role: str) -> dict[str, Any]:
        try:
            data = json.loads(self.clean_json(raw_text))
        except (json.JSONDecodeError, TypeError) as exc:
            raise GenerationError(f"El agente {role} no devolvió JSON válido; no se guarda nada.") from exc
        if not isinstance(data, dict):
            raise GenerationError(f"El agente {role} devolvió un JSON que no es un objeto.")
        return data


class DirectorAgent(MusicOSAgent):
    def set_goal(self, music_ir: MusicIR, theme: str, styles: list[str], creativity_level: int) -> None:
        music_ir.concept["core_idea"] = theme
        music_ir.concept["emotion"] = music_ir.concept.get("emotion", "")
        music_ir.metadata["styles"] = list(styles)
        music_ir.metadata["creativity_level"] = max(0, min(100, int(creativity_level)))


class CompositionAgent(MusicOSAgent):
    demo_payload = staticmethod(_composer_payload)

    def compose(self, music_ir: MusicIR) -> None:
        styles = music_ir.metadata.get("styles", [])
        theme = music_ir.concept["core_idea"]
        language = music_ir.lyrics["language"]
        bpm = music_ir.musical["bpm"]
        key = music_ir.musical["key"]
        creativity = music_ir.metadata["creativity_level"]
        learned = music_ir.memory.get("learned_patterns", [])
        learned_context = "\n".join(f"- {pattern}" for pattern in learned)

        system_prompt = f"""
        Eres el AGENTE DE COMPOSICIÓN de MUSIC OS.
        Creatividad: {creativity}%.
        Pensamiento nativo: {language}.

        CONTEXTO EVOLUTIVO (PATRONES APRENDIDOS):
        {learned_context if learned_context else "Ninguno todavía. Establece las bases."}

        REGLAS ARTÍSTICAS:
        - Fusión: {styles}.
        - No traduzcas: usa la sonoridad propia del idioma.
        - Estructura dinámica y acordes con extensiones (7, 9, sus, alt).
        """
        prompt = (
            f"Genera una composición completa en {language} sobre '{theme}'. "
            f"BPM: {bpm}, tonalidad: {key}. Devuelve JSON con title, structure, "
            "lyrics, chords, vocal_direction, originality_score."
        )
        data = self._payload(self.call_llm(prompt, system_prompt), self.name)

        sections = data.get("structure") or music_ir.musical.get("sections") or []
        if not isinstance(sections, list) or not sections:
            raise GenerationError("La composición no trae secciones utilizables.")
        sections = dedupe_section_names([str(section) for section in sections if str(section).strip()])
        if not sections:
            raise GenerationError("La composición no trae secciones utilizables.")

        lyrics = data.get("lyrics") if isinstance(data.get("lyrics"), dict) else {}
        chords_raw = data.get("chords") if isinstance(data.get("chords"), dict) else {}

        chords: dict[str, list[str]] = {}
        for section in sections:
            symbols = [str(symbol).strip() for symbol in chords_raw.get(section, []) if str(symbol).strip()]
            readable = [symbol for symbol in symbols if is_chord(symbol)]
            if not readable:
                raise GenerationError(f"La sección {section!r} no tiene acordes legibles.")
            chords[section] = readable

        music_ir.metadata["title"] = str(data.get("title") or music_ir.metadata["title"]).strip() or "Sin Título"
        try:
            score = float(data.get("originality_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        music_ir.metadata["originality_score"] = max(0.0, min(100.0, score))
        music_ir.musical["sections"] = sections
        music_ir.lyrics["content"] = {section: str(lyrics.get(section, "")).strip() for section in sections}
        music_ir.harmony["chords"] = chords
        music_ir.production["interpretation"] = str(data.get("vocal_direction", "") or "")


class ProductionAgent(MusicOSAgent):
    demo_payload = staticmethod(_producer_payload)

    def produce(self, music_ir: MusicIR) -> None:
        system_prompt = (
            "Eres el AGENTE DE PRODUCCIÓN de MUSIC OS. Diseña instrumentación, dinámica y espacio por sección."
        )
        prompt = (
            f"Analiza la composición: {music_ir.to_json()}. Devuelve JSON con "
            "instrumentation, dynamics y spatial, indexados por sección."
        )
        data = self._payload(self.call_llm(prompt, system_prompt), self.name)
        arrangement = music_ir.arrangement
        arrangement["instrumentation"] = data.get("instrumentation", {}) or {}
        arrangement["dynamics"] = data.get("dynamics", {}) or {}
        arrangement["spatial"] = data.get("spatial", {}) or {}


class LearningAgent(MusicOSAgent):
    """Analiza el historial y propone patrones para la siguiente canción."""

    demo_payload = staticmethod(_learning_payload)

    def evolve(self, music_ir: MusicIR, history: list[dict[str, Any]]) -> None:
        system_prompt = (
            "Eres el AGENTE DE APRENDIZAJE de MUSIC OS. Analiza el historial y "
            "extrae patrones; no inventes métricas de calidad musical."
        )
        prompt = (
            f"Historial: {json.dumps(history[-5:], ensure_ascii=False)}. "
            f"Canción actual: {music_ir.to_json()}. Devuelve JSON con "
            "learned_patterns y evolution_metrics."
        )
        data = self._payload(self.call_llm(prompt, system_prompt), self.name)
        patterns = data.get("learned_patterns") or []
        if isinstance(patterns, list):
            music_ir.memory["learned_patterns"] = [str(p) for p in patterns][:20]
        metrics = data.get("evolution_metrics") or {}
        if isinstance(metrics, dict):
            music_ir.evaluation["evolution_metrics"] = metrics


def _entry_title(entry: dict[str, Any]) -> str:
    """Título de una entrada de historial: formato nuevo (raíz) o antiguo (metadata)."""
    meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    return str(entry.get("title") or meta.get("title") or "Sin Título")


class MusicOS:
    """Orquestador: Director → Compositor → Productor → Aprendizaje."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        provider: Callable[[str, str, str], str] | None = None,
        history_file: str | os.PathLike[str] | None = None,
        history: HistoryStore | None = None,
    ):
        self.model_name = model_name
        self.provider_kind = (
            PROVIDER_CALLABLE if provider else PROVIDER_DEMO if model_name == DEMO_MODEL else PROVIDER_OLLAMA
        )
        self.music_ir = MusicIR()
        self.director = DirectorAgent("Director", model_name, provider)
        self.composer = CompositionAgent("Compositor", model_name, provider)
        self.producer = ProductionAgent("Productor", model_name, provider)
        self.learner = LearningAgent("Aprendizaje", model_name, provider)
        self.history = history or HistoryStore(history_file or DEFAULT_HISTORY_PATH)

    # ``history_file`` se conserva como propiedad mutable por compatibilidad.
    @property
    def history_file(self) -> str:
        return str(self.history.path)

    @history_file.setter
    def history_file(self, value: str | os.PathLike[str]) -> None:
        self.history = HistoryStore(value, max_entries=self.history.max_entries)

    @property
    def history_warning(self) -> str | None:
        return self.history.last_warning

    def _load_history(self) -> list[dict[str, Any]]:
        return self.history.load()

    def generate_project(
        self,
        theme: str,
        styles: list[str],
        language: str,
        bpm: int,
        key: str,
        creativity: int,
    ) -> MusicIR:
        theme = (theme or "").strip()
        if not theme:
            raise ValueError("El tema no puede estar vacío.")

        music_ir = MusicIR()
        music_ir.lyrics["language"] = language
        music_ir.musical["bpm"] = bpm
        music_ir.musical["key"] = key
        music_ir.metadata["provider"] = self.provider_kind
        music_ir.metadata["model"] = self.model_name
        music_ir.metadata["schema_version"] = SCHEMA_VERSION

        history = self._load_history()
        if history:
            last = history[-1]
            memory = last.get("memory") if isinstance(last.get("memory"), dict) else {}
            music_ir.memory["learned_patterns"] = list(memory.get("learned_patterns", []))[:20]
            titles = []
            for entry in history[-5:]:
                titles.append(str(_entry_title(entry)))
            music_ir.memory["past_references"] = [title for title in titles if title]

        self.director.set_goal(music_ir, theme, styles, creativity)
        self.composer.compose(music_ir)
        self.producer.produce(music_ir)
        self.learner.evolve(music_ir, history)

        problems = music_ir.validate()
        if problems:
            raise GenerationError("El proyecto generado no es válido: " + " · ".join(problems))

        self.history.append(music_ir.summary())
        self.music_ir = music_ir
        return music_ir

    def export_midi(self, style_groove: str = "auto", *, include_bass: bool = True) -> bytes:
        """MIDI real del proyecto actual. ``style_groove`` ∈ GROOVE_MODES."""
        return self.export_midi_result(style_groove, include_bass=include_bass).data

    def export_midi_result(self, style_groove: str = "auto", *, include_bass: bool = True) -> MidiExportResult:
        if not self.music_ir.sections:
            raise MusicOSError("Todavía no hay proyecto: genera o carga uno antes de exportar MIDI.")
        if style_groove not in GROOVE_MODES:
            raise ValueError(f"Groove desconocido {style_groove!r}; usa {', '.join(GROOVE_MODES)}.")
        return render_project(self.music_ir, style_groove, include_bass=include_bass)


__all__ = [
    "DEMO_MODEL",
    "CompositionAgent",
    "DirectorAgent",
    "GenerationError",
    "LearningAgent",
    "ModelUnavailableError",
    "MusicIR",
    "MusicOS",
    "MusicOSAgent",
    "MusicOSError",
    "ProductionAgent",
]
