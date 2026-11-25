"""Pruebas del núcleo: teoría, IR, MIDI, historial, proveedores y sesión.

Todas usan ``tmp_path``/``TemporaryDirectory``: la suite no escribe en el
repositorio ni toca el historial real de nadie.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from project.agente_compositor_universal import AgenteCompositorUniversal, CompositorError
from project.history_store import HistoryStore
from project.midi_export import GROOVE_MODES, parse_midi, render_project, section_grooves
from project.music_ir import SCHEMA_VERSION, MusicIR
from project.music_os_core import (
    DEMO_MODEL,
    GenerationError,
    ModelUnavailableError,
    MusicOS,
    MusicOSError,
)
from project.music_theory import MusicTheoryError, is_chord, key_signature, parse_chord, parse_key
from project.piano_roll import RollNote, render_piano_roll_svg
from project.session_report import render_session_sheet


def demo_ir(**overrides) -> MusicIR:
    ir = MusicIR()
    ir.metadata["title"] = "Prueba"
    ir.musical.update({"key": "Dm", "bpm": 95, "meter": "4/4", "sections": ["Intro", "Coro"]})
    ir.harmony["chords"] = {"Intro": ["Am9", "Fmaj7"], "Coro": ["Fmaj7", "G7sus4"]}
    ir.lyrics["content"] = {"Intro": "(instrumental)", "Coro": "letra"}
    for key, value in overrides.items():
        setattr(ir, key, value)
    return ir


class MusicTheoryTests(unittest.TestCase):
    def test_common_chords_parse_to_expected_pitch_sets(self):
        cases = {
            "Am9": [69, 72, 76, 79, 83],
            "Fmaj7": [65, 69, 72, 76],
            "E7#9": [64, 68, 71, 74, 79],
            "G7sus4": [67, 72, 74, 77],
            "Cmaj7": [60, 64, 67, 71],
        }
        for symbol, expected in cases.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(parse_chord(symbol).pitches(), expected)

    def test_slash_bass_and_enharmonics(self):
        chord = parse_chord("C/E")
        self.assertEqual(chord.bass_pitch_class, 4)
        self.assertEqual(chord.pitches()[0], 52)
        self.assertEqual(parse_chord("A♯m").quality, "m")
        self.assertEqual(parse_chord("Bb").root_pitch_class, 10)

    def test_unknown_suffix_degrades_but_never_raises(self):
        chord = parse_chord("A7alt")
        self.assertEqual(chord.quality, "alt")
        self.assertFalse(chord.approximate)
        approx = parse_chord("Cwhatever9")
        self.assertTrue(approx.approximate)
        self.assertIn(approx.quality, ("", "sus4", "m"))

    def test_garbage_is_rejected(self):
        for bad in ("", "   ", "Hm7", "N.C.", "??", None, 42):
            with self.subTest(bad=bad):
                self.assertFalse(is_chord(bad))
                with self.assertRaises(MusicTheoryError):
                    parse_chord(bad)

    def test_key_signatures_follow_the_circle_of_fifths(self):
        self.assertEqual(key_signature("C"), (0, 0))
        self.assertEqual(key_signature("G"), (1, 0))
        self.assertEqual(key_signature("F"), (-1, 0))
        self.assertEqual(key_signature("Am"), (0, 1))
        self.assertEqual(key_signature("Dm"), (-1, 1))
        self.assertEqual(key_signature("F#"), (6, 0))
        self.assertEqual(key_signature("Ebmaj7"), (-3, 0))

    def test_parse_key_reports_mode_and_tonic(self):
        self.assertEqual(parse_key("C#m"), (1, 1, "C#"))
        self.assertEqual(parse_key("Bb")[0], 10)


class MusicIRTests(unittest.TestCase):
    def test_round_trip_is_lossless(self):
        ir = demo_ir()
        self.assertEqual(MusicIR.from_json(ir.to_json()), ir)

    def test_valid_project_has_no_problems(self):
        self.assertEqual(demo_ir().validate(), [])

    def test_validation_catches_real_defects(self):
        broken = demo_ir()
        broken.musical["bpm"] = 900
        broken.musical["key"] = "H"
        broken.harmony["chords"]["Coro"] = ["??", "C#m7b5"]
        broken.lyrics["content"].pop("Coro")
        problems = " ".join(broken.validate())
        for expected in ("BPM", "Tonalidad", "Acordes ilegibles", "sin letra"):
            self.assertIn(expected, problems)

    def test_from_json_migrates_the_old_schema(self):
        legacy = {
            "metadata": {"title": "Vieja", "styles": "Rock", "originality_score": 10},
            "musical": {"key": "Am", "bpm": "88", "sections": "Intro, Coro"},
            "harmony": {"chords": {"Intro": ["Am"], "Coro": ["F"]}},
            "lyrics": {"content": {"Intro": "a", "Coro": "b"}},
        }
        ir = MusicIR.from_dict(legacy)
        self.assertEqual(ir.metadata["schema_version"], SCHEMA_VERSION)
        self.assertEqual(ir.metadata["styles"], ["Rock"])
        self.assertEqual(ir.sections, ["Intro", "Coro"])
        self.assertEqual(ir.validate(), [])

    def test_from_dict_reopens_a_flat_history_summary(self):
        ir = demo_ir()
        reopened = MusicIR.from_dict(ir.summary())
        self.assertEqual(reopened.sections, ir.sections)
        self.assertEqual(reopened.harmony["chords"], ir.harmony["chords"])
        self.assertEqual(reopened.validate(), [])

    def test_bad_json_raises_value_error_not_type_error(self):
        for payload in ("{no", "[]", "null"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                MusicIR.from_json(payload)


class MidiExportTests(unittest.TestCase):
    def test_file_is_format_one_with_tempo_harmony_and_bass(self):
        result = render_project(demo_ir(), "arpeggio")
        self.assertTrue(result.data.startswith(b"MThd"))
        self.assertEqual(result.tracks, 3)
        parsed = parse_midi(result.data)
        self.assertEqual(parsed.track_count, 4)  # tempo + 3 pistas
        self.assertEqual(len(parsed.tempos), 1)
        self.assertEqual(parsed.tempos[0][1], 95)
        self.assertEqual(parsed.time_signatures[0][1:], (4, 4))
        self.assertEqual({note.channel for note in parsed.notes}, {0, 1})

    def test_written_notes_equal_parsed_notes(self):
        for groove in (*GROOVE_MODES, "auto"):
            with self.subTest(groove=groove):
                result = render_project(demo_ir(), groove)
                self.assertEqual(len(parse_midi(result.data).notes), result.notes)

    def test_grooves_produce_audibly_different_files(self):
        payloads = {groove: render_project(demo_ir(), groove).data for groove in GROOVE_MODES}
        self.assertEqual(len(set(payloads.values())), len(GROOVE_MODES))
        self.assertLess(
            len(render_project(demo_ir(), "pad").data),
            len(render_project(demo_ir(), "arpeggio").data),
        )

    def test_auto_groove_maps_sections(self):
        ir = demo_ir()
        ir.musical["sections"] = ["Intro", "Coro", "Puente"]
        ir.harmony["chords"] = {"Intro": ["Am"], "Coro": ["F"], "Puente": ["C"]}
        ir.lyrics["content"] = {"Intro": "a", "Coro": "b", "Puente": "c"}
        self.assertEqual(
            section_grooves(ir, "auto"),
            {"Intro": "arpeggio", "Coro": "stab", "Puente": "pad"},
        )
        self.assertEqual(set(section_grooves(ir, "pad").values()), {"pad"})

    def test_export_without_a_project_raises_a_clear_error(self):
        with self.assertRaisesRegex(MusicOSError, "Todavía no hay proyecto"):
            MusicOS(model_name=DEMO_MODEL).export_midi()

    def test_invalid_ir_is_not_exported(self):
        with self.assertRaises(ValueError):
            render_project(MusicIR())
        with self.assertRaises(ValueError):
            render_project(demo_ir(), "swing")

    def test_non_latin_title_does_not_break_midi_meta_events(self):
        ir = demo_ir()
        ir.metadata["title"] = "Eclipse — en la ciudad 🎵 «live»"
        self.assertTrue(render_project(ir, "pad").data.startswith(b"MThd"))

    def test_bass_can_be_disabled(self):
        result = render_project(demo_ir(), "pad", include_bass=False)
        self.assertEqual(result.tracks, 2)
        self.assertEqual({n.channel for n in parse_midi(result.data).notes}, {0})

    def test_parser_rejects_non_midi(self):
        with self.assertRaises(ValueError):
            parse_midi(b"RIFF....WAVE")


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.json"

    def test_corrupt_file_is_quarantined_not_fatal(self):
        self.path.write_text("{corrupto", encoding="utf-8")
        store = HistoryStore(self.path)
        self.assertEqual(store.load(), [])
        self.assertIn("Historial ilegible", store.last_warning or "")
        backups = list(self.path.parent.glob("history.json.corrupt-*"))
        self.assertEqual(len(backups), 1)

    def test_writes_are_atomic_and_capped(self):
        store = HistoryStore(self.path, max_entries=3)
        for index in range(5):
            store.append({"n": index})
        self.assertEqual([entry["n"] for entry in store.load()], [2, 3, 4])
        self.assertEqual(list(self.path.parent.glob(".history-*")), [])  # sin temporales

    def test_non_dict_entries_are_filtered(self):
        self.path.write_text('[1, null, {"ok": true}]', encoding="utf-8")
        self.assertEqual(HistoryStore(self.path).load(), [{"ok": True}])

    def test_clear_reports_whether_something_existed(self):
        store = HistoryStore(self.path)
        self.assertFalse(store.clear())
        store.append({"x": 1})
        self.assertTrue(store.clear())
        self.assertFalse(self.path.exists())


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.history = Path(self.temp.name) / "history.json"

    def make_engine(self, **kwargs) -> MusicOS:
        return MusicOS(history_file=self.history, **kwargs)

    def generate(self, engine: MusicOS, **kwargs):
        params = {
            "theme": "prueba",
            "styles": ["The Smiths"],
            "language": "Español",
            "bpm": 95,
            "key": "Dm",
            "creativity": 60,
        }
        params.update(kwargs)
        return engine.generate_project(**params)

    def test_demo_project_is_valid_and_round_trips(self):
        project = self.generate(self.make_engine(model_name=DEMO_MODEL))
        self.assertTrue(project.is_valid())
        self.assertEqual(MusicIR.from_json(project.to_json()), project)
        self.assertEqual(project.metadata["provider"], "demo")

    def test_demo_is_marked_and_never_claims_a_real_model(self):
        project = self.generate(self.make_engine(model_name=DEMO_MODEL))
        self.assertEqual(project.metadata["model"], DEMO_MODEL)

    def test_real_provider_failure_raises_and_never_returns_the_demo(self):
        def fail(**kwargs):
            raise ConnectionError("offline")

        with (
            patch.dict("sys.modules", {"ollama": type("M", (), {"chat": staticmethod(fail)})}),
            self.assertRaises(ModelUnavailableError),
        ):
            self.generate(self.make_engine(model_name="qwen2.5:7b"))
        self.assertFalse(self.history.exists())

    def test_injected_provider_makes_the_flow_testable(self):
        def provider(model, system, prompt):
            if "COMPOSICIÓN" in system:
                return json.dumps(
                    {
                        "title": "Inyectada",
                        "structure": ["Intro", "Coro"],
                        "lyrics": {"Intro": "a", "Coro": "b"},
                        "chords": {"Intro": ["Am7"], "Coro": ["Fmaj7", "G"]},
                        "vocal_direction": "susurro",
                        "originality_score": 42,
                    }
                )
            if "PRODUCCIÓN" in system:
                return json.dumps({"instrumentation": {"Intro": "piano"}, "dynamics": {"Intro": 10}, "spatial": {}})
            return json.dumps({"learned_patterns": ["patrón"], "evolution_metrics": {"c": 1}})

        engine = self.make_engine(provider=provider)
        project = self.generate(engine)
        self.assertEqual(project.metadata["title"], "Inyectada")
        self.assertEqual(project.metadata["provider"], "callable")
        self.assertEqual(project.metadata["originality_score"], 42.0)
        self.assertTrue(engine.export_midi())

    def test_invalid_model_output_persists_nothing(self):
        engine = self.make_engine(provider=lambda *args: "no soy json")
        with self.assertRaises(GenerationError):
            self.generate(engine)
        self.assertFalse(self.history.exists())

    def test_empty_theme_is_rejected(self):
        with self.assertRaises(ValueError):
            self.generate(self.make_engine(model_name=DEMO_MODEL), theme="   ")

    def test_history_feeds_the_next_project_and_survives_reload(self):
        engine = self.make_engine(model_name=DEMO_MODEL)
        first = self.generate(engine, theme="uno")
        second = self.generate(engine, theme="dos")
        self.assertIn(first.metadata["title"], second.memory["past_references"])
        self.assertTrue(second.memory["learned_patterns"])
        stored = HistoryStore(self.history).load()
        self.assertEqual(len(stored), 2)
        reopened = MusicIR.from_dict(stored[-1])
        self.assertEqual(reopened.sections, second.sections)
        self.assertTrue(reopened.is_valid())

    def test_history_file_attribute_remains_mutable(self):
        engine = MusicOS(model_name=DEMO_MODEL)
        engine.history_file = str(self.history)
        self.generate(engine)
        self.assertTrue(self.history.exists())

    def test_export_uses_the_requested_groove(self):
        engine = self.make_engine(model_name=DEMO_MODEL)
        self.generate(engine)
        payloads = {groove: engine.export_midi(groove) for groove in GROOVE_MODES}
        self.assertEqual(len(set(payloads.values())), len(GROOVE_MODES))
        result = engine.export_midi_result("stab", include_bass=False)
        self.assertEqual(result.tracks, 2)
        with self.assertRaises(ValueError):
            engine.export_midi("swing")


class CompositorUniversalTests(unittest.TestCase):
    def test_demo_composition_and_midi_are_consistent(self):
        agent = AgenteCompositorUniversal(model_name=DEMO_MODEL)
        song = agent.compose("soledad", "Español", ["The Smiths"], 100, "Am")
        self.assertEqual(song["structure"], ["Verso 1", "Pre-Coro", "Coro", "Puente", "Coro 2", "Outro"])
        self.assertEqual(set(song["structure"]), set(song["chords"]))
        midi_bytes = agent.export_midi_bytes(song)
        self.assertTrue(midi_bytes.startswith(b"MThd"))
        midi_object = agent.generate_midi(song)
        buffer = io.BytesIO()
        midi_object.writeFile(buffer)
        self.assertGreater(len(buffer.getvalue()), 100)

    def test_real_model_failure_is_a_compositor_error_not_name_error(self):
        with patch.dict("sys.modules", {"ollama": None}), self.assertRaises(CompositorError):
            AgenteCompositorUniversal(model_name="qwen2.5:7b").compose("x", "Español", [], 100, "Am")

    def test_prompt_is_plain_json_instructions(self):
        prompt = AgenteCompositorUniversal.build_mega_prompt("Español", ["Anitta"], "tema", 100, "Am")
        self.assertNotIn("{{", prompt)
        self.assertIn('"title"', prompt)

    def test_invalid_song_is_rejected(self):
        with self.assertRaises(CompositorError):
            AgenteCompositorUniversal._validate_song({"structure": ["Intro"], "chords": {}}, bpm=100, key="Am")


class PresentationTests(unittest.TestCase):
    def test_session_sheet_contains_the_contract(self):
        ir = demo_ir()
        sheet = render_session_sheet(ir, render_project(ir, "auto"))
        for expected in ("TÍTULO", "BPM", "ACORDES", "GROOVE", "SESIÓN MIDI", "no es un máster"):
            self.assertIn(expected, sheet)
        self.assertIn("Am9", sheet)

    def test_piano_roll_is_accessible_svg_with_real_notes(self):
        notes = [RollNote(pitch=60 + i, start=i * 0.5, duration=0.4, velocity=90, channel=0) for i in range(4)]
        svg = render_piano_roll_svg(notes, title="Maqueta")
        self.assertIn('role="img"', svg)
        self.assertIn("<title", svg)
        self.assertIn("Maqueta", svg)
        self.assertEqual(svg.count("<rect"), 4 + 1)  # 4 notas + fondo
        self.assertNotIn('height="auto"', svg)

    def test_empty_piano_roll_is_still_valid(self):
        svg = render_piano_roll_svg([])
        self.assertIn("Sin notas", svg)


if __name__ == "__main__":
    unittest.main()
