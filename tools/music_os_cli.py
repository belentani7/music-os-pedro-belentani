#!/usr/bin/env python3
"""music-os — CLI del taller MUSIC OS.

Uso:
    python -m tools.music_os_cli --help
    python -m tools.music_os_cli generate --theme "alienación digital" --demo --out salida/
    python -m tools.music_os_cli inspect salida/proyecto.musicir.json
    python -m tools.music_os_cli verify salida/maqueta.mid
    python -m tools.music_os_cli history --limit 5
    python -m tools.music_os_cli clear-history --yes

Todo ocurre en local. Con ``--demo`` no se llama a ningún modelo y el
resultado se marca como simulación en el JSON, el MIDI y la hoja de sesión.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project.history_store import HistoryStore  # noqa: E402
from project.midi_export import GROOVE_MODES, parse_midi, section_grooves  # noqa: E402
from project.music_ir import MusicIR  # noqa: E402
from project.music_os_core import (  # noqa: E402
    DEFAULT_MODEL,
    DEMO_MODEL,
    GenerationError,
    ModelUnavailableError,
    MusicOS,
)
from project.piano_roll import RollNote, render_piano_roll_svg  # noqa: E402
from project.session_report import render_session_sheet  # noqa: E402

DEFAULT_HISTORY = ROOT / "music_os_history.json"


def _slug(text: str) -> str:
    keep = [ch if (ch.isalnum() or ch in " -_") else "" for ch in text]
    slug = "".join(keep).strip().replace(" ", "_")
    return slug or "proyecto"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="music-os",
        description="Taller local de preproducción musical: MusicIR, maqueta MIDI y hoja de sesión.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            '  music-os generate --theme "alienación digital" --demo\n'
            '  music-os generate --theme "cabaret oscuro" --model qwen2.5:7b --bpm 90 --key Dm\n'
            "  music-os verify maqueta.mid\n"
            "  music-os inspect proyecto.musicir.json\n"
            "  music-os history --limit 5\n"
        ),
    )
    parser.add_argument("--version", action="version", version="music-os 2.0")
    parser.add_argument(
        "--history-file",
        default=str(DEFAULT_HISTORY),
        help=f"Ruta del historial local (por defecto: {DEFAULT_HISTORY.name}).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Genera un proyecto y lo exporta a un directorio.")
    gen.add_argument("--theme", required=True, help="Concepto creativo de la canción.")
    gen.add_argument("--styles", default="", help="Estilos fusionados separados por comas.")
    gen.add_argument("--language", default="Español", help="Idioma de la letra.")
    gen.add_argument("--bpm", type=int, default=105)
    gen.add_argument("--key", default="Am", help="Tonalidad (Am, C, Dm, Fmaj7…).")
    gen.add_argument("--creativity", type=int, default=70, help="0–100.")
    gen.add_argument("--model", default=DEFAULT_MODEL, help=f"Modelo Ollama o «{DEMO_MODEL}».")
    gen.add_argument("--demo", action="store_true", help="Fuerza el modo demo (sin modelo).")
    gen.add_argument("--groove", default="auto", choices=list(GROOVE_MODES))
    gen.add_argument("--no-bass", action="store_true", help="Omite la pista de bajo.")
    gen.add_argument("--out", default="salida", help="Directorio de salida.")
    gen.add_argument("--no-files", action="store_true", help="Solo imprime el resumen; no escribe archivos.")
    gen.add_argument("--json", action="store_true", help="Resumen en JSON por stdout.")

    ins = sub.add_parser("inspect", help="Valida y resume un MusicIR (.json).")
    ins.add_argument("path", help="Ruta del archivo MusicIR.")

    ver = sub.add_parser("verify", help="Audita un archivo MIDI: notas, tempo, compás, compases.")
    ver.add_argument("path", help="Ruta del archivo .mid")

    hist = sub.add_parser("history", help="Muestra el historial local.")
    hist.add_argument("--limit", type=int, default=10)

    clear = sub.add_parser("clear-history", help="Borra el historial local.")
    clear.add_argument("--yes", action="store_true", help="Confirma el borrado sin preguntar.")

    return parser


def cmd_generate(args: argparse.Namespace) -> int:
    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    model = DEMO_MODEL if args.demo else args.model
    engine = MusicOS(model_name=model, history_file=args.history_file)
    try:
        ir = engine.generate_project(args.theme, styles, args.language, args.bpm, args.key, args.creativity)
    except ModelUnavailableError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        print("[PISTA] Usa --demo para probar el flujo sin modelo.", file=sys.stderr)
        return 2
    except (GenerationError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 3

    midi = engine.export_midi_result(args.groove, include_bass=not args.no_bass)
    slug = _slug(str(ir.metadata.get("title", "proyecto")))
    summary = {
        "title": ir.metadata.get("title"),
        "provider": ir.metadata.get("provider"),
        "model": ir.metadata.get("model"),
        "key": ir.musical.get("key"),
        "bpm": ir.musical.get("bpm"),
        "sections": ir.sections,
        "grooves": section_grooves(ir, args.groove),
        "midi": {"notes": midi.notes, "bars": midi.bars, "tracks": midi.tracks, "bytes": len(midi.data)},
    }

    if not args.no_files:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{slug}.musicir.json").write_text(ir.to_json(), encoding="utf-8")
        (out / f"{slug}.mid").write_bytes(midi.data)
        (out / f"{slug}_sesion.txt").write_text(render_session_sheet(ir, midi, groove=args.groove), encoding="utf-8")
        parsed = parse_midi(midi.data)
        notes = [
            RollNote(pitch=n.pitch, start=n.start, duration=n.duration, velocity=n.velocity, channel=n.channel)
            for n in parsed.notes
        ]
        (out / f"{slug}_pianoroll.svg").write_text(
            render_piano_roll_svg(notes, beats_per_bar=int(str(ir.musical.get("meter", "4/4")).split("/")[0])),
            encoding="utf-8",
        )
        summary["files"] = sorted(p.name for p in out.iterdir() if p.is_file())

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"«{summary['title']}» · {summary['key']} · {summary['bpm']} BPM · proveedor: {summary['provider']}")
        print(f"Secciones: {', '.join(summary['sections'])}")
        print(f"MIDI: {midi.notes} notas · {midi.bars} compases · {midi.tracks} pistas · {len(midi.data)} bytes")
        if not args.no_files:
            print(f"Archivos en {Path(args.out).resolve()}: {', '.join(summary['files'])}")
        if ir.metadata.get("provider") == "demo":
            print("[AVISO] Modo demo: la letra y los acordes son un ejemplo fijo, no una generación real.")
    for warning in midi.warnings:
        print(f"[AVISO] {warning}", file=sys.stderr)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"[ERROR] No existe {path}", file=sys.stderr)
        return 2
    try:
        ir = MusicIR.from_json(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 3
    problems = ir.validate()
    print(f"Título: {ir.metadata.get('title')}  ·  proveedor: {ir.metadata.get('provider')}")
    print(f"Tonalidad {ir.musical.get('key')} · {ir.musical.get('bpm')} BPM · {ir.musical.get('meter')}")
    print(f"Secciones ({len(ir.sections)}): {', '.join(ir.sections)}")
    for section in ir.sections:
        print(f"  {section}: {' | '.join(ir.harmony.get('chords', {}).get(section, []))}")
    if problems:
        print("[INVÁLIDO]")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("[VÁLIDO] El proyecto se puede exportar a MIDI.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"[ERROR] No existe {path}", file=sys.stderr)
        return 2
    try:
        parsed = parse_midi(path.read_bytes())
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 3
    tempos = ", ".join(f"{bpm} BPM en pulso {beat:g}" for beat, bpm in parsed.tempos) or "sin tempo"
    signatures = ", ".join(f"{num}/{den}" for _, num, den in parsed.time_signatures) or "sin compás"
    print(f"Pistas: {parsed.track_count} · notas: {len(parsed.notes)} · duración: {parsed.beats:g} pulsos")
    print(f"Tempo: {tempos} · Compás: {signatures}")
    if not parsed.notes:
        print("[INVÁLIDO] El archivo no contiene notas.")
        return 1
    pitches = [note.pitch for note in parsed.notes]
    print(f"Rango de altura: {min(pitches)}–{max(pitches)} · canales: {sorted({n.channel for n in parsed.notes})}")
    print("[OK] MIDI legible con cabecera y eventos de nota.")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    store = HistoryStore(args.history_file)
    entries = store.load()
    if store.last_warning:
        print(f"[AVISO] {store.last_warning}", file=sys.stderr)
    if not entries:
        print("Historial vacío.")
        return 0
    for entry in entries[-args.limit :]:
        meta = entry.get("metadata") or {}
        print(
            f"- {entry.get('title', 'Sin Título')} · {entry.get('key')} · {entry.get('bpm')} BPM"
            f" · {meta.get('provider', '—')} · originalidad {meta.get('originality_score', '—')}"
        )
    print(f"Total: {len(entries)} proyectos en {args.history_file}")
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    store = HistoryStore(args.history_file)
    if not args.yes:
        answer = input(f"¿Borrar {args.history_file}? [s/N] ").strip().lower()
        if answer not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado.")
            return 0
    removed = store.clear()
    print("Historial borrado." if removed else "No había historial.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "generate": cmd_generate,
        "inspect": cmd_inspect,
        "verify": cmd_verify,
        "history": cmd_history,
        "clear-history": cmd_clear,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
