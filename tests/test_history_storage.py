"""Regression tests for local unpublished music history; no network or Ollama needed."""
import json
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("midiutil", types.SimpleNamespace(MIDIFile=object))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project"))
from music_os_core import MusicIR, MusicOS


class TestPrivateHistory(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.engine = MusicOS(model_name="demo-mode")
        self.engine.history_file = str(Path(self.directory.name) / "music_os_history.json")

    def test_unicode_history_is_saved_and_appended(self):
        first = MusicIR()
        first.metadata["title"] = "Canción inédita — coração"
        self.engine._save_to_history(first)
        second = MusicIR()
        second.metadata["title"] = "Segunda canción"
        self.engine._save_to_history(second)
        history = self.engine._load_history()
        self.assertEqual([item["metadata"]["title"] for item in history],
                         ["Canción inédita — coração", "Segunda canción"])
        self.assertIn("coração", Path(self.engine.history_file).read_text(encoding="utf-8"))
        if os.name == "posix":
            permissions = stat.S_IMODE(os.stat(self.engine.history_file).st_mode)
            self.assertEqual(permissions & 0o077, 0)

    def test_invalid_json_is_not_overwritten(self):
        original = "{private unfinished draft"
        Path(self.engine.history_file).write_text(original, encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            self.engine._save_to_history(MusicIR())
        self.assertEqual(Path(self.engine.history_file).read_text(encoding="utf-8"), original)

    def test_invalid_history_shape_is_not_overwritten(self):
        original = '{"metadata": {"title": "Not a history list"}}'
        Path(self.engine.history_file).write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "formato inválido"):
            self.engine._save_to_history(MusicIR())
        self.assertEqual(Path(self.engine.history_file).read_text(encoding="utf-8"), original)

    def test_failed_replace_keeps_original_and_removes_temp_file(self):
        self.engine._save_to_history(MusicIR())
        original = Path(self.engine.history_file).read_bytes()
        with patch("music_os_core.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                self.engine._save_to_history(MusicIR())
        self.assertEqual(Path(self.engine.history_file).read_bytes(), original)
        self.assertEqual(sorted(path.name for path in Path(self.directory.name).iterdir()),
                         ["music_os_history.json"])


if __name__ == "__main__":
    unittest.main()
