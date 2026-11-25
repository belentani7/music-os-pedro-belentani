"""Exportación MIDI real del MusicIR: varias pistas, compás, armadura y grooves.

El exportador anterior generaba una sola pista con acordes en bloque y el
parámetro ``style_groove`` no tenía ningún efecto. Ahora:

* pista de tempo/mapa (compás + armadura + tempo),
* pista de armonía con tres grooves verificables (arpeggio, pad, stab),
* pista de bajo que sigue la fundamental de cada acorde,
* metadatos de sesión (nombre de pista, aviso de groove, notas aproximadas).

API pública:
    ``render_project(ir, groove="arpeggio", ...) -> bytes``
    ``MidiExportResult`` con ``data``, ``bars``, ``notes``, ``warnings``.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from midiutil import MIDIFile

from .music_ir import MusicIR
from .music_theory import MusicTheoryError, key_signature, parse_chord

# Canales General MIDI (0-indexados): 0 = armónica, 1 = bajo.
HARMONY_CHANNEL = 0
BASS_CHANNEL = 1
PROGRAM_ELECTRIC_PIANO = 4  # GM 5 «Electric Piano 1»
PROGRAM_SYNTH_BASS = 38  # GM 39 «Synth Bass 1»

GROOVES = ("arpeggio", "pad", "stab")
GROOVE_MODES = (*GROOVES, "auto")
GROOVE_LABELS = {
    "arpeggio": "Arpegio de corcheas con acentos — intro/verso",
    "pad": "Acordes sostenidos de compás entero — ambient/puente",
    "stab": "Bloques rítmicos con silencio en el 2 y el 4 — coro/clímax",
}

DEFAULT_SECTION_GROOVE = {
    "intro": "arpeggio",
    "verso": "arpeggio",
    "verse": "arpeggio",
    "pre": "pad",
    "puente": "pad",
    "bridge": "pad",
    "coro": "stab",
    "chorus": "stab",
    "outro": "pad",
}

_BEATS_PER_CHORD = 4
_MAX_PITCH = 127
_MIN_PITCH = 0


@dataclass
class MidiExportResult:
    """Resultado auditable de una exportación MIDI."""

    data: bytes
    bars: int
    notes: int
    tracks: int
    groove: str
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # un archivo vacío no es una exportación
        return bool(self.data)


def _groove_for_section(section: str, selected: str) -> str:
    """Un groove explícito se respeta en todas las secciones; "auto" decide por nombre."""
    if selected != "auto":
        return selected
    lowered = section.lower()
    for hint, groove in DEFAULT_SECTION_GROOVE.items():
        if hint in lowered:
            return groove
    return "arpeggio"


def section_grooves(ir: MusicIR, selected: str = "auto") -> dict[str, str]:
    """Mapa sección → groove, para mostrarlo en la UI sin duplicar la regla."""
    return {section: _groove_for_section(section, selected) for section in ir.sections}


def _midi_text(text: object) -> str:
    """midiutil codifica los meta-eventos en ISO-8859-1: saneamos antes de escribir.

    Sin esto, un título con «—», emoji o griego rompe la exportación con
    ``UnicodeEncodeError`` (comprobado con midiutil 1.2.1).
    """
    return (
        str(text)
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def _clamp(pitch: int) -> int:
    return max(_MIN_PITCH, min(_MAX_PITCH, int(pitch)))


def _add_harmony(
    midi: MIDIFile,
    track: int,
    chords: list[str],
    start: float,
    groove: str,
    warnings: list[str],
) -> tuple[int, float]:
    """Escribe un acorde por compás; devuelve ``(notas, siguiente_beats)``."""
    notes = 0
    time = start
    for symbol in chords:
        try:
            parsed = parse_chord(symbol)
        except MusicTheoryError as exc:
            warnings.append(f"Acorde omitido {symbol!r}: {exc}")
            time += _BEATS_PER_CHORD
            continue
        if parsed.approximate:
            warnings.append(f"Acorde aproximado {symbol!r} → calidad {parsed.quality!r}.")

        pitches = [_clamp(p) for p in parsed.pitches(octave=4)]

        if groove == "pad":
            for pitch in pitches:
                midi.addNote(track, HARMONY_CHANNEL, pitch, time, 3.9, 92)
                notes += 1
        elif groove == "stab":
            for offset, velocity in ((0.0, 112), (1.5, 96), (3.0, 104)):
                for pitch in pitches:
                    midi.addNote(track, HARMONY_CHANNEL, pitch, time + offset, 0.4, velocity)
                    notes += 1
        else:  # arpeggio: corcheas ascendentes con acento en tiempo fuerte
            sequence = pitches + pitches[-2:0:-1]
            for step, pitch in enumerate(sequence * 2):
                velocity = 92 if step % 4 == 0 else 70
                midi.addNote(track, HARMONY_CHANNEL, pitch, time + step * 0.5, 0.45, velocity)
                notes += 1
        time += _BEATS_PER_CHORD
    return notes, time


def _add_bass(
    midi: MIDIFile,
    track: int,
    chords: list[str],
    start: float,
    groove: str,
    warnings: list[str],
) -> tuple[int, float]:
    """Bajo: fundamental en negras (pad, stab) o figura de octava en corcheas (arpeggio)."""
    notes = 0
    time = start
    for symbol in chords:
        try:
            parsed = parse_chord(symbol)
        except MusicTheoryError:
            time += _BEATS_PER_CHORD
            continue
        root = _clamp(
            36 + parsed.bass_pitch_class if parsed.bass_pitch_class is not None else 36 + parsed.root_pitch_class
        )
        if groove == "arpeggio":
            pattern = [
                (root, 0.0, 0.9, 104),
                (root + 12, 1.5, 0.45, 78),
                (root, 2.0, 0.9, 96),
                (root + 7, 3.0, 0.7, 84),
            ]
        elif groove == "stab":
            pattern = [(root, 0.0, 1.4, 110), (root, 2.0, 1.4, 100)]
        else:  # pad
            pattern = [(root, 0.0, 3.9, 88)]
        for pitch, offset, duration, velocity in pattern:
            midi.addNote(track, BASS_CHANNEL, _clamp(pitch), time + offset, duration, velocity)
            notes += 1
        time += _BEATS_PER_CHORD
    return notes, time


def render_project(
    ir: MusicIR,
    groove: str = "auto",
    *,
    include_bass: bool = True,
    adjust_origin: bool = False,
) -> MidiExportResult:
    """Convierte un MusicIR en bytes MIDI formato 1, listos para descargar."""
    if groove not in GROOVE_MODES:
        raise ValueError(f"Groove desconocido {groove!r}; usa uno de {', '.join(GROOVE_MODES)}.")

    problems = ir.validate()
    if problems:
        raise ValueError("El proyecto no es exportable: " + " · ".join(problems))

    chords_map = ir.harmony.get("chords", {})
    sections = ir.sections
    warnings: list[str] = []

    num_tracks = 3 if include_bass else 2
    midi = MIDIFile(num_tracks, adjust_origin=adjust_origin)

    bpm = int(ir.musical.get("bpm", 105))
    numerator, _, denominator = str(ir.musical.get("meter", "4/4")).partition("/")
    meter_num, meter_den = int(numerator), int(denominator)

    tempo_track = 0
    harmony_track = 1
    bass_track = 2

    midi.addTrackName(tempo_track, 0, _midi_text(f"{ir.metadata.get('title', 'Sin Título')} - sesión"))
    midi.addTempo(tempo_track, 0, bpm)
    midi.addTimeSignature(tempo_track, 0, meter_num, meter_den.bit_length() - 1, 24)
    try:
        accidentals, mode = key_signature(str(ir.musical.get("key", "Am")))
        midi.addKeySignature(tempo_track, 0, accidentals, 0, mode)
    except MusicTheoryError as exc:  # validado antes; red de seguridad
        warnings.append(f"Armadura omitida: {exc}")

    midi.addTrackName(harmony_track, 0, _midi_text("Armonía"))
    midi.addProgramChange(harmony_track, HARMONY_CHANNEL, 0, PROGRAM_ELECTRIC_PIANO)
    if include_bass:
        midi.addTrackName(bass_track, 0, _midi_text("Bajo"))
        midi.addProgramChange(bass_track, BASS_CHANNEL, 0, PROGRAM_SYNTH_BASS)

    total_notes = 0
    time = 0.0
    for section in sections:
        section_chords = [str(c) for c in chords_map.get(section, []) if str(c).strip()]
        if not section_chords:
            warnings.append(f"Sección {section!r} sin acordes; se omite.")
            continue
        section_groove = _groove_for_section(section, groove)
        if not include_bass and section_groove == "stab":
            section_groove = "pad"  # sin bajo, los stabs quedan cojos
        written, time = _add_harmony(midi, harmony_track, section_chords, time, section_groove, warnings)
        total_notes += written
        if include_bass:
            written, time = _add_bass(midi, bass_track, section_chords, time, section_groove, warnings)
            total_notes += written

    if total_notes == 0:
        raise ValueError("El proyecto no produce ninguna nota MIDI; revisa acordes y secciones.")

    buffer = io.BytesIO()
    midi.writeFile(buffer)
    data = buffer.getvalue()
    if not data.startswith(b"MThd"):
        raise RuntimeError("La exportación MIDI no generó una cabecera MThd válida.")

    beats = time
    beats_per_bar = meter_num
    bars = round(beats / beats_per_bar) if beats_per_bar else 0
    return MidiExportResult(
        data=data,
        bars=bars,
        notes=total_notes,
        tracks=num_tracks,
        groove=groove,
        warnings=warnings,
    )


# ---------------------------------------------------------------- lectura MIDI
def _read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos


@dataclass(frozen=True)
class ParsedNote:
    """Nota leída de un archivo MIDI estándar (tiempos en pulsos)."""

    pitch: int
    start: float
    duration: float
    velocity: int
    channel: int


@dataclass(frozen=True)
class ParsedMidi:
    notes: tuple[ParsedNote, ...]
    tempos: tuple[tuple[float, int], ...]  # (pulso, bpm)
    time_signatures: tuple[tuple[float, int, int], ...]  # (pulso, num, den)
    track_count: int

    @property
    def beats(self) -> float:
        return max((n.start + n.duration for n in self.notes), default=0.0)


def parse_midi(data: bytes, ticks_per_quarter: int | None = None) -> ParsedMidi:
    """Parser SMF mínimo (formato 1/2) suficiente para auditar nuestras exportaciones."""
    import struct

    if data[:4] != b"MThd":
        raise ValueError("No es un archivo MIDI estándar (falta MThd).")
    header_len = struct.unpack(">I", data[4:8])[0]
    division = struct.unpack(">H", data[12:14])[0]
    tpq = ticks_per_quarter or (division & 0x7FFF) or 480

    pos = 8 + header_len
    notes: list[ParsedNote] = []
    tempos: list[tuple[float, int]] = []
    signatures: list[tuple[float, int, int]] = []
    track_count = 0

    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        chunk_len = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        body = data[pos + 8 : pos + 8 + chunk_len]
        pos += 8 + chunk_len
        if chunk_id != b"MTrk":
            continue
        track_count += 1
        abs_ticks = 0
        cursor = 0
        running_status = None
        open_notes: dict[tuple[int, int], tuple[float, int]] = {}
        while cursor < len(body):
            delta, cursor = _read_vlq(body, cursor)
            abs_ticks += delta
            status = body[cursor]
            if status < 0x80:
                if running_status is None:
                    raise ValueError("Evento MIDI sin estado previo (running status ilegal).")
                status = running_status
            else:
                cursor += 1
                if status < 0xF0:
                    running_status = status
            beat = abs_ticks / tpq

            if status == 0xFF:
                meta_type = body[cursor]
                cursor += 1
                length, cursor = _read_vlq(body, cursor)
                payload = body[cursor : cursor + length]
                cursor += length
                if meta_type == 0x51 and length == 3:
                    micros = int.from_bytes(payload, "big")
                    if micros:
                        tempos.append((beat, round(60_000_000 / micros)))
                elif meta_type == 0x58 and length >= 2:
                    signatures.append((beat, payload[0], 2 ** payload[1]))
                continue
            if status in (0xF0, 0xF7):
                length, cursor = _read_vlq(body, cursor)
                cursor += length
                continue

            event_type = status & 0xF0
            channel = status & 0x0F
            data_len = 1 if event_type in (0xC0, 0xD0) else 2
            payload = body[cursor : cursor + data_len]
            cursor += data_len
            if len(payload) < data_len:
                break
            first, second = payload[0], (payload[1] if data_len > 1 else 0)

            if event_type == 0x90 and second > 0:
                open_notes[(channel, first)] = (beat, second)
            elif event_type in (0x80, 0x90):
                started = open_notes.pop((channel, first), None)
                if started:
                    start_beat, velocity = started
                    notes.append(
                        ParsedNote(
                            pitch=first,
                            start=round(start_beat, 4),
                            duration=round(max(0.0, beat - start_beat), 4),
                            velocity=velocity,
                            channel=channel,
                        )
                    )

    notes.sort(key=lambda n: (n.start, n.pitch))
    return ParsedMidi(
        notes=tuple(notes),
        tempos=tuple(tempos),
        time_signatures=tuple(signatures),
        track_count=track_count,
    )
