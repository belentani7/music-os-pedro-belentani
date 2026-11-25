"""Instrumentos de escritura: un piano-roll SVG generado en Python.

Se usa en la vista previa de la sesión MIDI para que lo que se descarga se
pueda **ver** sin abrir un DAW. Sin dependencias nuevas: SVG puro a partir de
las notas reales del archivo exportado (no de una ilustración decorativa).
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class RollNote:
    pitch: int
    start: float  # en pulsos (beats)
    duration: float
    velocity: int
    channel: int


def _pitch_name(pitch: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[pitch % 12]}{pitch // 12 - 1}"


def render_piano_roll_svg(
    notes: list[RollNote],
    *,
    width: int = 960,
    height: int = 260,
    max_pitch: int | None = None,
    min_pitch: int | None = None,
    beats_per_bar: int = 4,
    title: str = "Piano roll",
) -> str:
    """Devuelve un SVG accesible (role=img, <title>) con las notas indicadas."""
    if not notes:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" '
            'aria-label="Sin notas"><title>Sin notas</title></svg>'
        )

    lo = min_pitch if min_pitch is not None else min(n.pitch for n in notes)
    hi = max_pitch if max_pitch is not None else max(n.pitch for n in notes)
    lo = max(0, lo)
    hi = min(127, max(hi, lo + 6))
    span = hi - lo

    total_beats = max(n.start + n.duration for n in notes)
    total_beats = max(total_beats, beats_per_bar)

    left, right, top, bottom = 44, 12, 18, 20
    plot_w = max(1, width - left - right)
    plot_h = max(1, height - top - bottom)
    row_h = plot_h / (span + 1)

    def x_of(beat: float) -> float:
        return left + (beat / total_beats) * plot_w

    def y_of(pitch: int) -> float:
        return top + (hi - pitch) * row_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-labelledby="pr-title" style="width:100%;height:auto;display:block">',
        f'<title id="pr-title">{escape(title)}: {len(notes)} notas, {total_beats:g} pulsos</title>',
        '<rect width="100%" height="100%" fill="transparent"/>',
    ]

    # Rejilla de compases y líneas de pulso.
    bar = 0
    while bar * beats_per_bar <= total_beats + 0.001:
        beat = bar * beats_per_bar
        parts.append(
            f'<line x1="{x_of(beat):.2f}" y1="{top}" x2="{x_of(beat):.2f}" '
            f'y2="{top + plot_h}" stroke="rgba(245,247,250,.20)" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x_of(beat) + 4:.2f}" y="{top - 5}" fill="#a4acb7" '
            f'font-size="10" font-family="ui-monospace,monospace">{bar + 1}</text>'
        )
        bar += 1
    for octave_pitch in range(lo, hi + 1):
        if octave_pitch % 12 == 0:
            parts.append(
                f'<line x1="{left}" y1="{y_of(octave_pitch) + row_h:.2f}" x2="{left + plot_w}" '
                f'y2="{y_of(octave_pitch) + row_h:.2f}" stroke="rgba(245,247,250,.08)"/>'
            )
            parts.append(
                f'<text x="6" y="{y_of(octave_pitch) + row_h - 2:.2f}" fill="#a4acb7" '
                f'font-size="10" font-family="ui-monospace,monospace">{_pitch_name(octave_pitch)}</text>'
            )

    for note in notes:
        # Canal 1 = bajo: color distinto para distinguir las dos pistas.
        fill = "#ff9aac" if note.channel == 0 else "#7fd1e8"
        opacity = 0.45 + 0.55 * (max(1, min(127, note.velocity)) / 127)
        x = x_of(note.start)
        w = max(2.0, x_of(note.start + note.duration) - x)
        y = y_of(note.pitch) + row_h * 0.18
        h = max(2.0, row_h * 0.64)
        parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{h / 2:.2f}" '
            f'fill="{fill}" fill-opacity="{opacity:.2f}"/>'
        )
    parts.append("</svg>")
    return "".join(parts)
