"""Real-vs-demo routing tests; do not require a running Ollama instance."""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# The routing logic is importable without external MIDI hardware or software.
sys.modules.setdefault("midiutil", types.SimpleNamespace(MIDIFile=object))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project"))
from music_os_core import MusicOSAgent


class TestLLMRouting(unittest.TestCase):
    def test_configured_model_is_called_instead_of_fixed_demo_song(self):
        calls = []
        def chat(**kwargs):
            calls.append(kwargs)
            return {"message": {"content": '{"title":"Tema original comprobado"}'}}
        with patch.dict(sys.modules, {"ollama": types.SimpleNamespace(chat=chat)}):
            agent = MusicOSAgent("Compositor", model_name="qwen2.5:7b")
            answer = agent.call_llm("La deuda: bachata oscura", "Compositor ético")
        self.assertEqual(json.loads(answer)["title"], "Tema original comprobado")
        self.assertEqual(calls[0]["model"], "qwen2.5:7b")
        self.assertEqual(calls[0]["messages"][1]["content"], "La deuda: bachata oscura")
        self.assertEqual(calls[0]["format"], "json")

    def test_unavailable_model_fails_instead_of_saving_fake_track(self):
        def offline(**_kwargs):
            raise ConnectionError("server unreachable")
        with patch.dict(sys.modules, {"ollama": types.SimpleNamespace(chat=offline)}):
            with self.assertRaisesRegex(RuntimeError, "Ollama"):
                MusicOSAgent("Compositor", "not-installed").call_llm("My song")

    def test_demo_is_explicit_and_does_not_call_external_provider(self):
        def forbidden(**kwargs):
            raise AssertionError("No real request expected")
        with patch.dict(sys.modules, {"ollama": types.SimpleNamespace(chat=forbidden)}):
            text = MusicOSAgent("Compositor", "demo-mode").call_llm("test")
        self.assertEqual(json.loads(text)["title"], "Eclipse en la Ciudad")


if __name__ == "__main__":
    unittest.main()
