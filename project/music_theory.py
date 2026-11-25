"""Teoría musical mínima y verificable: acordes, tonalidades y armaduras.

Una sola fuente de verdad para interpretar símbolos de acorde ("Am9", "E7#9",
"G7sus4", "C/E") y traducirlos a alturas MIDI. Antes existían dos mapas de
acordes distintos y divergentes (``music_os_core`` y
``agente_compositor_universal``); este módulo los sustituye.

Las cifras de armadura siguen el círculo de quintas estándar (positivo =
sostenidos, negativo = bemoles), que es lo que espera el byte de armadura de
un archivo MIDI estándar (SMF 1.0, sección «Key Signature»).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NOTE_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTAL = {"": 0, "#": 1, "b": -1, "\u266f": 1, "\u266d": -1}

# Semitonos desde la fundamental para cada calidad reconocida.
QUALITY_INTERVALS: dict[str, tuple[int, ...]] = {
    "": (0, 4, 7),
    "maj": (0, 4, 7),
    "m": (0, 3, 7),
    "min": (0, 3, 7),
    "5": (0, 7),
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "mmaj7": (0, 3, 7, 11),
    "dim": (0, 3, 6),
    "dim7": (0, 3, 6, 9),
    "m7b5": (0, 3, 6, 10),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "7sus4": (0, 5, 7, 10),
    "add9": (0, 4, 7, 14),
    "9": (0, 4, 7, 10, 14),
    "maj9": (0, 4, 7, 11, 14),
    "m9": (0, 3, 7, 10, 14),
    "m11": (0, 3, 7, 10, 14, 17),
    "11": (0, 4, 7, 10, 14, 17),
    "13": (0, 4, 7, 10, 14, 21),
    "maj13": (0, 4, 7, 11, 14, 21),
    "m13": (0, 3, 7, 10, 14, 21),
    "7b9": (0, 4, 7, 10, 13),
    "7#9": (0, 4, 7, 10, 15),
    "7#11": (0, 4, 7, 10, 18),
    "9b5": (0, 4, 6, 10, 14),
    "alt": (0, 4, 10, 13, 15),
}

# Armadura por fundamental escrita: sostenidos positivos, bemoles negativos.
MAJOR_KEY_SIGNATURE = {
    "C": 0,
    "G": 1,
    "D": 2,
    "A": 3,
    "E": 4,
    "B": 5,
    "F#": 6,
    "C#": 7,
    "F": -1,
    "Bb": -2,
    "Eb": -3,
    "Ab": -4,
    "Db": -5,
    "Gb": -6,
    "Cb": -7,
}

# Grafía preferida de cada clase de altura al nombrar una tonalidad mayor.
_PITCH_CLASS_TO_MAJOR_SPELLING = {
    0: "C",
    1: "Db",
    2: "D",
    3: "Eb",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "Ab",
    9: "A",
    10: "Bb",
    11: "B",
}

_CHORD_RE = re.compile(
    r"^\s*([A-Ga-g])\s*([#b\u266f\u266d]?)\s*([^/]*?)\s*(?:/\s*([A-Ga-g])\s*([#b\u266f\u266d]?)\s*)?$"
)

# Sufijos con significado armónico propio que no se obtienen recortando.
QUALITY_ALIASES = {
    "7alt": "alt",
    "7+": "7#5",
    "7#5": "alt",
    "9sus4": "7sus4",
    "sus": "sus4",
    "maj": "maj",
    "-": "m",
    "maj7#11": "maj7",
}


class MusicTheoryError(ValueError):
    """Símbolo musical imposible de interpretar con garantías."""


@dataclass(frozen=True)
class Chord:
    """Acorde interpretado: fundamental, calidad, intervalos y bajo opcional."""

    symbol: str
    root_pitch_class: int
    quality: str
    intervals: tuple[int, ...]
    bass_pitch_class: int | None = None
    approximate: bool = False

    def pitches(self, octave: int = 4) -> list[int]:
        """Alturas MIDI ascendentes en el rango ``octave`` (octave 4 = Do central)."""
        base = 12 * (octave + 1) + self.root_pitch_class
        notes = sorted({base + interval for interval in self.intervals})
        if self.bass_pitch_class is not None and self.bass_pitch_class != self.root_pitch_class:
            bass = 12 * octave + self.bass_pitch_class
            notes = [bass] + [n for n in notes if n > bass]
        return notes


def _normalize_quality(raw: str) -> str:
    text = (raw or "").strip().replace("\u266f", "#").replace("\u266d", "b")
    text = text.replace("\u0394", "maj").replace("\u00b0", "dim").replace("\u00f8", "m7b5")
    text = text.replace("\u2212", "-").replace(" ", "")
    if text.startswith("M") and not text.startswith("maj"):
        text = "maj" + text[1:]
    if text.startswith("min"):
        text = "m" + text[3:]
    if text.startswith("ma") and not text.startswith("maj"):
        text = "maj" + text[2:]
    # "M7" ya se normaliza arriba; "M" suelto significa mayor.
    if text == "M":
        text = ""
    return text


def _strip_alterations(quality: str) -> str:
    """Reduce un sufijo desconocido de más a menos específico.

    "m7b5/9" -> "m7b5"; "madd9" -> "m"; "7alt" ya se resuelve por alias.
    """
    candidate = quality
    while candidate:
        if candidate in QUALITY_INTERVALS:
            return candidate
        candidate = candidate[:-1]
    return ""


def parse_chord(symbol: str) -> Chord:
    """Interpreta un símbolo de acorde. Nunca lanza por un sufijo raro.

    Los sufijos no reconocidos se degradan al prefijo conocido más largo y se
    marcan con ``approximate=True`` para que quien exporte pueda advertirlo.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise MusicTheoryError(f"Símbolo de acorde vacío o no textual: {symbol!r}")

    match = _CHORD_RE.match(symbol)
    if not match:
        raise MusicTheoryError(f"Símbolo de acorde ilegible: {symbol!r}")

    letter, accidental, raw_quality, bass_letter, bass_accidental = match.groups()
    root_pc = (NOTE_PITCH_CLASS[letter.upper()] + ACCIDENTAL.get(accidental.lower(), 0)) % 12
    quality = _normalize_quality(raw_quality)
    quality = QUALITY_ALIASES.get(quality, quality)
    exact = quality in QUALITY_INTERVALS
    if not exact:
        quality = _strip_alterations(quality)

    bass_pc = None
    if bass_letter:
        bass_pc = (NOTE_PITCH_CLASS[bass_letter.upper()] + ACCIDENTAL.get((bass_accidental or "").lower(), 0)) % 12

    return Chord(
        symbol=symbol.strip(),
        root_pitch_class=root_pc,
        quality=quality,
        intervals=QUALITY_INTERVALS[quality],
        bass_pitch_class=bass_pc,
        approximate=not exact,
    )


def is_chord(symbol: str) -> bool:
    """True si el símbolo se puede interpretar (aunque sea de forma aproximada)."""
    try:
        parse_chord(symbol)
    except MusicTheoryError:
        return False
    return True


def parse_key(key: str) -> tuple[int, int, str]:
    """Devuelve ``(pitch_class, mode, tonic_spelling)`` para una tonalidad.

    ``mode`` es 0 para mayor y 1 para menor, tal como lo codifica el evento de
    armadura MIDI. Acepta sufijos de calidad ("Fmaj7") porque el histórico de
    la UI los ofrecía como tonalidad.
    """
    chord = parse_chord(key)
    quality = chord.quality
    # Ojo: "maj7"/"maj9" empiezan por "m" pero son mayores.
    is_minor = quality.startswith("m") and not quality.startswith("maj")
    mode = 1 if is_minor else 0

    tonic = ""
    for letter in "ABCDEFG":
        if NOTE_PITCH_CLASS[letter] == chord.root_pitch_class:
            tonic = letter
            break
    # Preferimos la grafía que el usuario escribió si es coherente.
    written = re.match(r"^\s*([A-Ga-g])([#b\u266f\u266d]?)", key)
    if written:
        candidate = written.group(1).upper() + written.group(2).replace("\u266f", "#").replace("\u266d", "b")
        candidate_pc = (NOTE_PITCH_CLASS[candidate[0]] + ACCIDENTAL.get(candidate[1:].lower(), 0)) % 12
        if candidate_pc == chord.root_pitch_class:
            tonic = candidate
    return chord.root_pitch_class, mode, tonic


def key_signature(key: str) -> tuple[int, int]:
    """Armadura ``(alteraciones, modo)`` lista para el evento MIDI."""
    pitch_class, mode, tonic = parse_key(key)
    if not tonic:
        tonic = "C"
    if mode == 0:
        signature = MAJOR_KEY_SIGNATURE.get(tonic, 0)
    else:
        # Relativa mayor: a una tercera menor (3 semitonos) sobre la tónica menor.
        relative_pc = (pitch_class + 3) % 12
        relative = _PITCH_CLASS_TO_MAJOR_SPELLING.get(relative_pc, "C")
        signature = MAJOR_KEY_SIGNATURE.get(relative, 0)
    return signature, mode


def chord_pitches(symbol: str, octave: int = 4) -> list[int]:
    """Atajos usados por los exportadores y por la UI."""
    return parse_chord(symbol).pitches(octave)


def chord_notes(symbol: str, octave: int = 4) -> list[int]:
    """Compatibilidad con el mapa anterior: notas MIDI del acorde."""
    return chord_pitches(symbol, octave)
