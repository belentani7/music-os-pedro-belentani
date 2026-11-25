"""MusicIR: gemelo digital de la canción, con validación y migración de esquema.

El contrato público se mantiene: ``MusicIR(...)``, ``to_json()`` y
``from_json()`` siguen existiendo y ``from_json(to_json(x)) == x``.

Lo nuevo es que el IR **valida** lo que describe (secciones, acordes, BPM,
tonalidad, compás) y que ``from_json`` **migra** documentos antiguos en lugar
de estallar con ``TypeError`` cuando falta o sobra un campo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .music_theory import MusicTheoryError, is_chord, parse_key

SCHEMA_VERSION = "2.0"


def dedupe_section_names(sections: list[str]) -> list[str]:
    """Hace únicas las etiquetas de sección conservando el orden.

    ``harmony.chords`` es un diccionario por nombre de sección, así que dos
    «Coro» en la estructura se pisarían y se perdería información. La segunda
    aparición pasa a «Coro 2», «Coro 3»…
    """
    counts: dict[str, int] = {}
    result: list[str] = []
    for raw in sections:
        name = str(raw).strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
        if counts[name] == 1:
            result.append(name)
        else:
            # Sufijo 2, 3… evitando chocar con una etiqueta que ya exista.
            suffix = counts[name]
            candidate = f"{name} {suffix}"
            while candidate in counts and counts[candidate] > 0:
                suffix += 1
                candidate = f"{name} {suffix}"
            counts[candidate] = 1
            result.append(candidate)
    return result


def _default_metadata() -> dict[str, Any]:
    return {
        "title": "Sin Título",
        "artist": "Pedro Belentani",
        "version": "1.0",
        "styles": [],
        "originality_score": 0.0,
        "creativity_level": 50,
        "schema_version": SCHEMA_VERSION,
        "provider": "desconocido",
        "model": "",
    }


@dataclass
class MusicIR:
    """Gemelo Digital de la Canción: una única fuente de verdad para la obra."""

    metadata: dict[str, Any] = field(default_factory=_default_metadata)
    concept: dict[str, str] = field(default_factory=lambda: {"emotion": "", "objective": "", "core_idea": ""})
    musical: dict[str, Any] = field(default_factory=lambda: {"key": "Am", "bpm": 105, "meter": "4/4", "sections": []})
    lyrics: dict[str, Any] = field(
        default_factory=lambda: {"language": "Español", "content": {}, "phonetics": {}, "prosody": {}}
    )
    harmony: dict[str, Any] = field(default_factory=lambda: {"chords": {}, "tension": []})
    melody: dict[str, Any] = field(default_factory=lambda: {"notes": {}, "phrasing": {}})
    arrangement: dict[str, Any] = field(
        default_factory=lambda: {"instrumentation": {}, "dynamics": {}, "spatial": {}, "automations": []}
    )
    production: dict[str, Any] = field(default_factory=lambda: {"mix": {}, "interpretation": {}, "sound_design": []})
    evaluation: dict[str, Any] = field(default_factory=lambda: {"score": 0.0, "feedback": [], "evolution_metrics": {}})
    memory: dict[str, Any] = field(default_factory=lambda: {"past_references": [], "learned_patterns": []})

    # ------------------------------------------------------------------ JSON
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> MusicIR:
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"MusicIR: el documento no es JSON válido ({exc.msg}).") from exc
        if not isinstance(data, dict):
            raise ValueError("MusicIR: se esperaba un objeto JSON en la raíz.")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MusicIR:
        """Construye un IR tolerante: campos desconocidos fuera, campos faltantes con defecto.

        Acepta también el **resumen plano** que guarda el historial
        (``summary()``): título, tonalidad, estructura, acordes y letra en la
        raíz del objeto.
        """
        if not isinstance(data, dict):
            raise ValueError("MusicIR: se esperaba un diccionario.")
        ir = cls()
        for name, current in ir.to_dict().items():
            incoming = data.get(name, current)
            if not isinstance(incoming, dict):
                continue  # se conserva el bloque por defecto; nunca se rompe el tipo
            merged = dict(current)
            merged.update(incoming)
            setattr(ir, name, merged)
        if not (ir.musical.get("sections") or []) and isinstance(data.get("structure"), list):
            ir.musical["sections"] = [str(section) for section in data["structure"]]
        if (not isinstance(ir.harmony.get("chords"), dict) or not ir.harmony["chords"]) and isinstance(
            data.get("chords"), dict
        ):
            ir.harmony["chords"] = data["chords"]
        if (not isinstance(ir.lyrics.get("content"), dict) or not ir.lyrics["content"]) and isinstance(
            data.get("lyrics"), dict
        ):
            ir.lyrics["content"] = data["lyrics"]
        ir.migrate()
        return ir

    # ------------------------------------------------------------- validación
    @property
    def sections(self) -> list[str]:
        raw = self.musical.get("sections") or []
        return [str(s) for s in raw if str(s).strip()]

    def migrate(self) -> MusicIR:
        """Normaliza documentos antiguos al esquema actual (idempotente)."""
        meta = self.metadata
        meta.setdefault("schema_version", "1.0")
        meta.setdefault("provider", "desconocido")
        meta.setdefault("model", "")
        if not isinstance(meta.get("styles"), list):
            meta["styles"] = [str(meta["styles"])] if meta.get("styles") else []
        musical = self.musical
        musical.setdefault("meter", "4/4")
        if isinstance(musical.get("sections"), str):
            musical["sections"] = [s.strip() for s in musical["sections"].split(",") if s.strip()]
        if not isinstance(self.harmony.get("chords"), dict):
            self.harmony["chords"] = {}
        if not isinstance(self.lyrics.get("content"), dict):
            self.lyrics["content"] = {}
        meta["schema_version"] = SCHEMA_VERSION
        return self

    def validate(self) -> list[str]:
        """Devuelve la lista de problemas bloqueantes. Lista vacía = IR exportable."""
        problems: list[str] = []
        musical = self.musical
        bpm = musical.get("bpm")
        try:
            bpm_value = int(bpm)
        except (TypeError, ValueError):
            problems.append(f"BPM no numérico: {bpm!r}")
        else:
            if not 20 <= bpm_value <= 300:
                problems.append(f"BPM fuera del rango permitido (20–300): {bpm_value}")

        meter = str(musical.get("meter", "4/4"))
        numerator, _, denominator = meter.partition("/")
        if not (numerator.isdigit() and denominator.isdigit() and int(numerator) > 0 and int(denominator) > 0):
            problems.append(f"Compás no reconocido: {meter!r} (se espera N/D, p. ej. 4/4)")

        try:
            parse_key(str(musical.get("key", "")))
        except MusicTheoryError as exc:
            problems.append(f"Tonalidad no reconocida: {musical.get('key')!r} ({exc})")

        sections = self.sections
        if not sections:
            problems.append("La canción no declara ninguna sección.")
        elif len(set(sections)) != len(sections):
            problems.append("Hay secciones con el mismo nombre; se perderían sus acordes.")

        chords = self.harmony.get("chords") or {}
        if not isinstance(chords, dict):
            problems.append("harmony.chords debe ser un objeto por sección.")
        else:
            missing = [s for s in sections if not chords.get(s)]
            if sections and missing:
                problems.append("Secciones sin acordes: " + ", ".join(missing))
            unknown = sorted({c for values in chords.values() for c in (values or []) if not is_chord(c)})
            if unknown:
                problems.append("Acordes ilegibles: " + ", ".join(map(str, unknown)))

        lyrics = self.lyrics.get("content") or {}
        missing_lyrics = [s for s in sections if not str(lyrics.get(s, "")).strip()]
        if sections and missing_lyrics:
            problems.append("Secciones sin letra: " + ", ".join(missing_lyrics))
        return problems

    def is_valid(self) -> bool:
        return not self.validate()

    def summary(self) -> dict[str, Any]:
        """Resumen serializable para historial, CLI y UI."""
        return {
            "title": self.metadata.get("title", "Sin Título"),
            "key": self.musical.get("key"),
            "bpm": self.musical.get("bpm"),
            "meter": self.musical.get("meter"),
            # "structure" (y no "sections") para que reabrir el resumen
            # reconstruya music_ir.musical.sections sin ambigüedad.
            "structure": list(self.musical.get("sections") or []),
            "sections": self.sections,
            "chords": self.harmony.get("chords", {}),
            "lyrics": self.lyrics.get("content", {}),
            "arrangement": self.arrangement,
            "instrumentation": self.arrangement.get("instrumentation", {}),
            "dynamics": self.arrangement.get("dynamics", {}),
            "spatial": self.arrangement.get("spatial", {}),
            "interpretation": self.production.get("interpretation", ""),
            "originality": self.metadata.get("originality_score", 0.0),
            "styles": self.metadata.get("styles", []),
            "language": self.lyrics.get("language", "Español"),
            "evaluation": self.evaluation,
            "memory": self.memory,
            "concept": self.concept,
            # Bloque anidado para que el historial se pueda reabrir tal cual
            # (MusicIR.from_dict) sin perder artista, proveedor ni creatividad.
            "metadata": self.metadata,
        }
