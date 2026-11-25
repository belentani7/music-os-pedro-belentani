"""Hoja de sesión y exportador TXT: lo que se lleva a un DAW.

La exportación de texto anterior era una concatenación sin metadatos. Esta
incluye tempo, tonalidad, compás, estructura, acordes, letra, producción y
las advertencias de la exportación MIDI (acordes aproximados, etc.).
"""

from __future__ import annotations

from .midi_export import MidiExportResult, section_grooves
from .music_ir import MusicIR


def render_session_sheet(ir: MusicIR, midi: MidiExportResult | None = None, *, groove: str = "auto") -> str:
    """Hoja de sesión en texto plano, lista para pegar en un DAW o un chat."""
    meta = ir.metadata
    lines: list[str] = [
        f"TÍTULO: {meta.get('title', 'Sin Título')}",
        f"ARTISTA: {meta.get('artist', 'Pedro Belentani')}",
        f"TONALIDAD: {ir.musical.get('key')}   BPM: {ir.musical.get('bpm')}   COMPÁS: {ir.musical.get('meter')}",
        f"IDIOMA: {ir.lyrics.get('language')}   ESTILOS: {', '.join(meta.get('styles') or []) or '—'}",
        f"PROVEEDOR: {meta.get('provider', 'desconocido')}   MODELO: {meta.get('model') or '—'}",
        f"CREATIVIDAD: {meta.get('creativity_level')}%   ORIGINALIDAD (estimación del modelo): {meta.get('originality_score')}%",
        "",
        f"CONCEPTO: {ir.concept.get('core_idea', '')}",
        "",
    ]

    if ir.production.get("interpretation"):
        lines += ["DIRECCIÓN VOCAL:", str(ir.production["interpretation"]), ""]

    grooves = section_grooves(ir, groove)
    chords_map = ir.harmony.get("chords", {})
    lyrics_map = ir.lyrics.get("content", {})
    dynamics = ir.arrangement.get("dynamics", {})
    instrumentation = ir.arrangement.get("instrumentation", {})
    spatial = ir.arrangement.get("spatial", {})

    for index, section in enumerate(ir.sections, start=1):
        lines.append(f"[{index:02d} · {section.upper()}]")
        chords = chords_map.get(section, [])
        lines.append(f"ACORDES: {' | '.join(chords) if chords else '—'}")
        lines.append(f"GROOVE: {grooves.get(section, groove)}")
        if section in dynamics:
            lines.append(f"DINÁMICA: {dynamics[section]}")
        if section in instrumentation:
            lines.append(f"INSTRUMENTACIÓN: {instrumentation[section]}")
        if section in spatial:
            lines.append(f"ESPACIO: {spatial[section]}")
        lines.append("LETRA:")
        lines.append(str(lyrics_map.get(section, "")).strip() or "(instrumental)")
        lines.append("")

    if midi is not None:
        lines += [
            "SESIÓN MIDI:",
            f"- Formato 1, {midi.tracks} pistas, {midi.bars} compases, {midi.notes} notas.",
            "- Canales: 0 armónica (GM 5 piano eléctrico), 1 bajo (GM 39 synth bass).",
            "- El MIDI es una maqueta de arreglo: no es un máster de audio ni una voz cantada.",
        ]
        if midi.warnings:
            lines.append("- Advertencias:")
            lines += [f"  · {warning}" for warning in midi.warnings]
        lines.append("")

    if ir.memory.get("learned_patterns"):
        lines.append("PATRONES APRENDIDOS USADOS:")
        lines += [f"- {pattern}" for pattern in ir.memory["learned_patterns"]]
        lines.append("")

    lines.append("Generado por MUSIC OS · la puntuación de originalidad es una estimación del modelo.")
    return "\n".join(lines)
