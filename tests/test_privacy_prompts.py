"""No prior unpublished lyrics or titles may be forwarded in learning prompts."""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("midiutil", types.SimpleNamespace(MIDIFile=object))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project"))
from music_os_core import LearningAgent, MusicIR, MusicOS, ProductionAgent


class TestPrivacyPrompts(unittest.TestCase):
    def test_learning_prompt_excludes_prior_lyrics_and_titles(self):
        prior = [{
            "metadata": {"title": "TITULO_SECRETO_742", "styles": ["dark pop"]},
            "musical": {"bpm": 112, "key": "Am"},
            "lyrics": {"content": {"Coro": "LETRA_PRIVADA_913"}},
        }]
        agent = LearningAgent("Aprendizaje", "demo-mode")
        with patch.object(agent, "call_llm", return_value='{"learned_patterns":[],"evolution_metrics":{}}') as mock:
            agent.evolve(MusicIR(), prior)
        prompt = mock.call_args.args[0]
        self.assertNotIn("TITULO_SECRETO_742", prompt)
        self.assertNotIn("LETRA_PRIVADA_913", prompt)
        self.assertIn("dark pop", prompt)
        self.assertIn("112", prompt)

    def test_previous_titles_are_not_copied_into_current_music_ir(self):
        engine = MusicOS("demo-mode")
        old = [{"metadata": {"title": "TITULO_SECRETO_742", "styles": []},
                "memory": {"learned_patterns": ["Am9"]},
                "musical": {"bpm": 112, "key": "Am"}}]
        with patch.object(engine, "_load_history", return_value=old), patch.object(engine, "_save_to_history"):
            ir = engine.generate_project("Nueva canción", ["pop"], "Español", 105, "Am", 70)
        self.assertNotIn("TITULO_SECRETO_742", ir.to_json())
        self.assertEqual(ir.memory["learned_patterns"], ["Uso recurrente de Am9 para melancolía", "Preferencia por estribillos explosivos a 90% dinámica"])


    def test_malformed_production_marks_result_incomplete(self):
        ir = MusicIR()
        agent = ProductionAgent("Productor", "demo-mode")
        with patch.object(agent, "call_llm", return_value="not JSON"):
            agent.produce(ir)
        self.assertTrue(any("arreglos válidos" in msg for msg in ir.evaluation["feedback"]))

    def test_malformed_learning_marks_result_incomplete(self):
        ir = MusicIR()
        agent = LearningAgent("Aprendizaje", "demo-mode")
        with patch.object(agent, "call_llm", return_value='{"learned_patterns": "not a list"}'):
            agent.evolve(ir, [])
        self.assertTrue(any("análisis válido" in msg for msg in ir.evaluation["feedback"]))


if __name__ == "__main__":
    unittest.main()
