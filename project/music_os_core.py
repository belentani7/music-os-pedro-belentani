import json
import re
import sys
import io
import os
import tempfile
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from midiutil import MIDIFile

# --- MUSIC IR (Representación Intermedia) ---
@dataclass
class MusicIR:
    """Gemelo Digital de la Canción: Una única fuente de verdad para la obra musical."""
    metadata: Dict[str, Any] = field(default_factory=lambda: {
        "title": "Sin Título", 
        "artist": "Pedro Belentani", 
        "version": "1.0",
        "styles": [],
        "originality_score": 0.0,
        "creativity_level": 50
    })
    concept: Dict[str, str] = field(default_factory=lambda: {"emotion": "", "objective": "", "core_idea": ""})
    musical: Dict[str, Any] = field(default_factory=lambda: {"key": "Am", "bpm": 105, "meter": "4/4", "sections": []})
    lyrics: Dict[str, Any] = field(default_factory=lambda: {"language": "Español", "content": {}, "phonetics": {}, "prosody": {}})
    harmony: Dict[str, Any] = field(default_factory=lambda: {"chords": {}, "tension": []})
    melody: Dict[str, Any] = field(default_factory=lambda: {"notes": {}, "phrasing": {}})
    arrangement: Dict[str, Any] = field(default_factory=lambda: {"instrumentation": {}, "dynamics": {}, "spatial": {}, "automations": []})
    production: Dict[str, Any] = field(default_factory=lambda: {"mix": {}, "interpretation": {}, "sound_design": []})
    evaluation: Dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "feedback": [], "evolution_metrics": {}})
    memory: Dict[str, Any] = field(default_factory=lambda: {"past_references": [], "learned_patterns": []})

    def to_json(self):
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        return cls(**data)

# --- AGENTES ESPECIALIZADOS ---
class MusicOSAgent:
    """Clase base para los agentes de MUSIC OS."""
    def __init__(self, name: str, model_name: str = "qwen2.5:7b"):
        self.name = name
        self.model = model_name

    def call_llm(self, prompt: str, system_prompt: str = "") -> str:
        """Use the configured local Ollama model; demo requires explicit opt-in."""
        if self.model != "demo-mode":
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
                    raise ValueError("Ollama devolvió una respuesta vacía")
                return content
            except Exception as exc:
                # Never silently substitute a fixed demo song and claim success.
                raise RuntimeError(
                    "No se pudo generar con Ollama. Comprueba el servicio local "
                    "y el modelo seleccionado o elige explícitamente demo-mode."
                ) from exc

        # --- DEMOSTRACIÓN EXPLÍCITA, NUNCA GENERACIÓN REAL ---
        if "Compositor" in self.name:
            return json.dumps({
                "title": "Eclipse en la Ciudad",
                "structure": ["Intro", "Verso 1", "Coro", "Outro"],
                "lyrics": {
                    "Intro": "(Instrumental dramático con piano oscuro)",
                    "Verso 1": "Las lUces se apAgan en el cAfé, / el frÍo me abRAza, no sÉ por quÉ. / Busco tu sOmbra en el cristAl, / un rastro dULce, un rastro mAL.",
                    "Coro": "Es un eclIpse en el corazÓn, / bAilando sOlo, sin rAzón. / Teatral y crUdo, como un adiÓs, / sOmos el rEco de una sOla vOz.",
                    "Outro": "Solo el rEco... / solo la vOz."
                },
                "chords": {
                    "Intro": ["Am9", "Fmaj7"],
                    "Verso 1": ["Am9", "Fmaj7", "Cmaj7", "E7#9"],
                    "Coro": ["Fmaj7", "Cmaj7", "Am7", "G7sus4"],
                    "Outro": ["Am9", "Fmaj7"]
                },
                "vocal_direction": "Empieza con un susurro íntimo estilo Morrissey, subiendo a una entrega teatral y dramática en el coro como Gaga. Mantén la síncopa en el verso.",
                "originality_score": 85
            })
        elif "Productor" in self.name:
            return json.dumps({
                "instrumentation": {
                    "Intro": "Piano de cola con reverb larga, sintetizador pad oscuro.",
                    "Verso 1": "Piano, bajo sintetizado profundo, chasquidos de dedos rítmicos.",
                    "Coro": "Batería potente, cuerdas épicas, guitarras eléctricas con chorus.",
                    "Outro": "Solo piano con filtro de paso bajo cerrándose."
                },
                "dynamics": {"Intro": 20, "Verso 1": 40, "Coro": 90, "Outro": 10},
                "spatial": {
                    "Intro": "Espacio inmenso, catedral.",
                    "Verso 1": "Espacio íntimo, seco.",
                    "Coro": "Ancho estéreo máximo, mucha profundidad.",
                    "Outro": "Voz muy cerca del oído."
                }
            })
        elif "Aprendizaje" in self.name:
            return json.dumps({
                "learned_patterns": ["Uso recurrente de Am9 para melancolía", "Preferencia por estribillos explosivos a 90% dinámica"],
                "evolution_metrics": {"creativity_growth": 15, "style_coherence": 92}
            })
        
        raise RuntimeError("El modo demo no implementa este agente")

    def _clean_json(self, raw_text):
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        return raw_text[start:end+1] if start != -1 and end != -1 else raw_text

class DirectorAgent(MusicOSAgent):
    def set_goal(self, music_ir: MusicIR, theme: str, styles: List[str], creativity_level: int):
        music_ir.concept["core_idea"] = theme
        music_ir.metadata["styles"] = styles
        music_ir.metadata["creativity_level"] = creativity_level

class CompositionAgent(MusicOSAgent):
    def compose(self, music_ir: MusicIR):
        styles = music_ir.metadata.get("styles", [])
        theme = music_ir.concept["core_idea"]
        language = music_ir.lyrics["language"]
        bpm = music_ir.musical["bpm"]
        key = music_ir.musical["key"]
        creativity = music_ir.metadata["creativity_level"]
        learned_context = "\n".join([f"- {p}" for p in music_ir.memory.get("learned_patterns", [])])

        system_prompt = f"""
        Eres el AGENTE DE COMPOSICIÓN de MUSIC OS v1.0. 
        Creatividad: {creativity}%. 
        Pensamiento Nativo: {language}.
        
        CONTEXTO EVOLUTIVO (PATRONES APRENDIDOS):
        {learned_context if learned_context else "Ninguno todavía. Establece las bases."}
        
        REGLAS ARTÍSTICAS:
        - Fusión: {styles}.
        - No traduzcas, usa la sonoridad propia del idioma.
        - Estructura dinámica y acordes American/Jazz/Pop complejos.
        """
        
        prompt = f"Genera composición completa en {language} sobre '{theme}'. BPM: {bpm}, Key: {key}. Devuelve JSON con title, structure, lyrics, chords, vocal_direction, originality_score."
        
        response_json = self.call_llm(prompt, system_prompt)
        try:
            data = json.loads(self._clean_json(response_json))
        except (TypeError, ValueError) as exc:
            raise ValueError("El compositor no devolvió JSON válido") from exc
        if (not isinstance(data, dict) or
                not isinstance(data.get("structure"), list) or
                not data["structure"] or
                not all(isinstance(section, str) and section for section in data["structure"]) or
                not isinstance(data.get("lyrics"), dict) or
                not isinstance(data.get("chords"), dict) or
                any(not isinstance(data["lyrics"].get(section), str) or
                    not data["lyrics"].get(section) or
                    not isinstance(data["chords"].get(section), list) or
                    not data["chords"].get(section)
                    for section in data["structure"])):
            raise ValueError("La composición carece de secciones, letras o acordes completos")
        music_ir.metadata["title"] = str(data.get("title") or music_ir.metadata["title"])
        # A model-provided originality number is not an independent evaluation.
        music_ir.metadata["originality_score"] = 0.0
        music_ir.musical["sections"] = data["structure"]
        music_ir.lyrics["content"] = data["lyrics"]
        music_ir.harmony["chords"] = data["chords"]
        music_ir.production["interpretation"] = str(data.get("vocal_direction") or "")

class ProductionAgent(MusicOSAgent):
    def produce(self, music_ir: MusicIR):
        system_prompt = "Eres el AGENTE DE PRODUCCIÓN de MUSIC OS. Diseña instrumentación, dinámica y espacio."
        prompt = f"Analiza composición: {music_ir.to_json()}. Diseña instrumentación, dinámicas y espacio. Devuelve JSON con instrumentation, dynamics, spatial."
        
        response_json = self.call_llm(prompt, system_prompt)
        try:
            data = json.loads(self._clean_json(response_json))
            music_ir.arrangement["instrumentation"] = data.get("instrumentation", {})
            music_ir.arrangement["dynamics"] = data.get("dynamics", {})
            music_ir.arrangement["spatial"] = data.get("spatial", {})
        except: pass

class LearningAgent(MusicOSAgent):
    """Agente que analiza el historial y evoluciona el sistema."""
    def evolve(self, music_ir: MusicIR, history: List[Dict]):
        system_prompt = "Eres el AGENTE DE APRENDIZAJE de MUSIC OS. Analiza el historial y evoluciona patrones."
        # Do not send all previous unpublished lyrics or titles to the model.
        # Only recent musical parameters are relevant to identifying patterns.
        history_summary = []
        for entry in history[-5:]:
            metadata = entry.get("metadata", {})
            musical = entry.get("musical", {})
            if not isinstance(metadata, dict) or not isinstance(musical, dict):
                continue
            history_summary.append({
                "styles": metadata.get("styles", []),
                "bpm": musical.get("bpm"),
                "key": musical.get("key"),
            })
        prompt = (
            f"Historial musical resumido (sin letras ni títulos): {json.dumps(history_summary, ensure_ascii=False)}. "
            f"Canción actual: {music_ir.to_json()}. "
            "Identifica patrones sugeridos y métricas estimadas; devuelve JSON con learned_patterns, evolution_metrics."
        )
        
        response_json = self.call_llm(prompt, system_prompt)
        try:
            data = json.loads(self._clean_json(response_json))
            music_ir.memory["learned_patterns"] = data.get("learned_patterns", [])
            music_ir.evaluation["evolution_metrics"] = data.get("evolution_metrics", {})
        except: pass

# --- MUSIC OS ENGINE ---
class MusicOS:
    def __init__(self, model_name: str = "qwen2.5:7b"):
        self.music_ir = MusicIR()
        self.director = DirectorAgent("Director", model_name)
        self.composer = CompositionAgent("Compositor", model_name)
        self.producer = ProductionAgent("Productor", model_name)
        self.learner = LearningAgent("Aprendizaje", model_name)
        self.history_file = "music_os_history.json"

    def _load_history(self) -> List[Dict]:
        if not os.path.exists(self.history_file):
            return []
        with open(self.history_file, "r", encoding="utf-8") as history_file:
            history = json.load(history_file)
        if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
            raise ValueError("El historial tiene un formato inválido; no se sobrescribirá.")
        return history

    def _save_to_history(self, music_ir: MusicIR):
        # Never truncate a user's unpublished songs before the replacement is ready.
        history = self._load_history()
        history.append(asdict(music_ir))
        destination = os.path.abspath(self.history_file)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=os.path.dirname(destination),
                prefix=".music-os-history-", suffix=".tmp", delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(history, temporary_file, indent=2, ensure_ascii=False)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            if os.name == "posix":
                os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def generate_project(self, theme: str, styles: List[str], language: str, bpm: int, key: str, creativity: int):
        self.music_ir = MusicIR() # Reset para nueva canción
        self.music_ir.lyrics["language"] = language
        self.music_ir.musical["bpm"] = bpm
        self.music_ir.musical["key"] = key
        
        history = self._load_history()
        
        # Inyectar memoria de sesiones pasadas ANTES de componer
        if history:
            last_entry = history[-1]
            self.music_ir.memory["learned_patterns"] = last_entry.get("memory", {}).get("learned_patterns", [])
            self.music_ir.memory["past_references"] = [h["metadata"]["title"] for h in history[-5:]]
        
        self.director.set_goal(self.music_ir, theme, styles, creativity)
        self.composer.compose(self.music_ir)
        self.producer.produce(self.music_ir)
        
        # Evolucionar patrones basados en la nueva composición
        self.learner.evolve(self.music_ir, history)
        
        self._save_to_history(self.music_ir)
        return self.music_ir

    def export_midi(self, style_groove: str = "Pop/Indie"):
        """
        Exportador MIDI Pro: Traduce acordes y estructuras a patrones rítmicos 
        y arpegios avanzados según el groove seleccionado.
        """
        midi = MIDIFile(1)
        track = 0
        time = 0
        bpm = self.music_ir.musical["bpm"]
        midi.addTempo(track, time, bpm)
        
        # Diccionario avanzado de acordes (American/Jazz/Modal extensions)
        chord_map = {
            'C': [60, 64, 67], 'Cm': [60, 63, 67], 'Cmaj7': [60, 64, 67, 71], 'Cmaj9': [60, 64, 67, 71, 74],
            'Cm7': [60, 63, 67, 70], 'Cm9': [60, 63, 67, 70, 74], 'C7': [60, 64, 67, 70],
            'Dm': [62, 65, 69], 'Dm7': [62, 65, 69, 72], 'Dm9': [62, 65, 69, 72, 76],
            'Em': [64, 67, 71], 'Em7': [64, 67, 71, 74], 'E7#9': [64, 68, 71, 74, 77],
            'F': [65, 69, 72], 'Fmaj7': [65, 69, 72, 76], 'Fm': [65, 68, 72], 'Fmaj9': [65, 69, 72, 76, 79],
            'G': [67, 71, 74], 'G7': [67, 71, 74, 77], 'Gmaj7': [67, 71, 74, 78], 'G7sus4': [67, 70, 74, 77],
            'Am': [69, 72, 76], 'Am7': [69, 72, 76, 79], 'Am9': [69, 72, 76, 79, 83], 'A7alt': [69, 73, 76, 79, 82],
            'Bb': [70, 74, 77], 'Bbmaj7': [70, 74, 77, 81], 'Dbmaj7': [61, 65, 68, 72], 'Ebmaj7': [63, 67, 70, 74]
        }

        for section in self.music_ir.musical["sections"]:
            section_chords = self.music_ir.harmony["chords"].get(section, [])
            if not section_chords:
                section_chords = ["Am9", "Fmaj7"] # Fallback seguro
                
            for chord_str in section_chords:
                clean_chord = chord_str.split('/')[0].strip()
                notes = chord_map.get(clean_chord, [60, 64, 67, 71]) # Default a maj7
                
                # Generación de Groove Arpegiado / Rítmico Avanzado
                if "Intro" in section or "Verso" in section:
                    # Estilo Arpegio / Jangly (The Smiths / Intros íntimas)
                    duration = 1.0
                    for i in range(4): # 4 tiempos por compás
                        for note_idx, note in enumerate(notes):
                            # Retardo sutil para toque humano
                            note_time = time + (i * 1.0) + (note_idx * 0.1)
                            velocity = 85 if note_idx % 2 == 0 else 70
                            midi.addNote(track, 0, note, note_time, 0.9, velocity)
                    time += 4
                else:
                    # Estilo Bloques / Pads con fuerza (Estribillo / Clímax tipo Gaga)
                    for note in notes:
                        midi.addNote(track, 0, note, time, 3.8, 105) # Acorde completo con pegada
                    time += 4
        
        buffer = io.BytesIO()
        midi.writeFile(buffer)
        return buffer.getvalue()
