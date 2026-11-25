import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from project.music_os_core import GenerationError, ModelUnavailableError, MusicIR, MusicOS, MusicOSAgent

ROOT = Path(__file__).resolve().parents[1]


class MusicLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = MusicOS(model_name="demo-mode")
        self.engine.history_file = str(Path(self.temp.name) / "history.json")

    def generate(self):
        return self.engine.generate_project("un tema de prueba", ["electrónica"], "Portugués", 95, "Dm", 60)

    def test_demo_project_preserves_requested_parameters_and_round_trips(self):
        project = self.generate()
        self.assertEqual(project.musical["bpm"], 95)
        self.assertEqual(project.musical["key"], "Dm")
        self.assertEqual(project.lyrics["language"], "Portugués")
        self.assertEqual(MusicIR.from_json(project.to_json()), project)

    def test_export_is_a_midi_file_with_music_tracks(self):
        self.generate()
        midi = self.engine.export_midi()
        self.assertEqual(midi[:4], b"MThd")
        self.assertIn(b"MTrk", midi)
        self.assertGreater(len(midi), 100)

    def test_exported_duration_matches_tempo_and_meter(self):
        self.generate()
        from project.midi_export import parse_midi

        parsed = parse_midi(self.engine.export_midi("auto"))
        self.assertEqual(parsed.tempos[0][1], 95)
        self.assertEqual(parsed.time_signatures[0][1:], (4, 4))
        self.assertAlmostEqual(parsed.beats / 4, 24, delta=0.2)

    def test_history_is_local_and_feeds_the_next_project(self):
        first = self.generate()
        second = self.generate()
        saved = json.loads(Path(self.engine.history_file).read_text())
        self.assertEqual(len(saved), 2)
        self.assertIn(first.metadata["title"], second.memory["past_references"])

    def test_real_provider_failure_never_returns_the_canned_demo(self):
        def fail(**kwargs):
            raise ConnectionError("offline in test")

        with (
            patch.dict("sys.modules", {"ollama": SimpleNamespace(chat=fail)}),
            self.assertRaisesRegex(ModelUnavailableError, "Ollama no disponible"),
        ):
            MusicOSAgent("Compositor", "real-model").call_llm("test")

    def test_invalid_composition_does_not_persist_a_successful_project(self):
        with (
            patch.object(self.engine.composer, "call_llm", return_value="invalid json"),
            self.assertRaises(GenerationError),
        ):
            self.generate()
        self.assertFalse(Path(self.engine.history_file).exists())


class Publication(unittest.TestCase):
    PAGES = ("index.html", "documentacion.html", "accesibilidad.html", "privacidad.html", "404.html")

    def test_vercel_publishes_an_existing_directory_without_a_node_build(self):
        config = json.loads((ROOT / "vercel.json").read_text())
        self.assertTrue((ROOT / config["outputDirectory"] / "index.html").is_file())
        self.assertIsNone(config["buildCommand"])
        self.assertIsNone(config["installCommand"])
        self.assertNotIn("builds", config)
        self.assertEqual(config.get("outputDirectory"), "site")

    def test_every_published_page_exists_in_site(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                self.assertTrue((ROOT / "site" / page).is_file())

    def test_site_has_one_h1_and_no_missing_local_links(self):
        import re

        for page_name in self.PAGES:
            with self.subTest(page=page_name):
                page = ROOT / "site" / page_name
                text = page.read_text(encoding="utf-8")
                self.assertEqual(text.count("<h1"), 1)
                for href in re.findall(r'href="([^"#][^"]*)"', text):
                    if href.startswith(("http:", "https:", "data:", "mailto:")):
                        continue
                    self.assertTrue((page.parent / href).exists(), f"{page_name} → {href}")

    def test_pages_do_not_claim_online_generation_or_audio_master(self):
        text = (ROOT / "site/index.html").read_text()
        self.assertIn("no ejecuta Ollama ni genera canciones online", text)
        self.assertIn("máster de audio", text)
        self.assertIn("modo demo", text)

    def test_every_page_declares_language_skip_link_and_nav(self):
        for page_name in self.PAGES:
            with self.subTest(page=page_name):
                text = (ROOT / "site" / page_name).read_text(encoding="utf-8")
                self.assertIn('lang="es"', text)
                self.assertIn('class="skip-link"', text)
                self.assertIn('<meta name="viewport"', text)

    def test_published_and_pages_landing_have_real_local_resources_and_actions(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []
                self.ids = set()
                self.h1 = 0

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                self.urls.extend(attrs[k] for k in ("href", "src") if k in attrs)
                if "id" in attrs:
                    self.ids.add(attrs["id"])
                self.h1 += tag == "h1"

        for path in (ROOT / "index.html", ROOT / "site/index.html"):
            with self.subTest(path=path.name):
                page = Links()
                page.feed(path.read_text())
                self.assertEqual(page.h1, 1)
                for url in page.urls:
                    self.assertNotEqual(url, "#")
                    if url.startswith("#"):
                        self.assertIn(url[1:], page.ids)
                    elif not url.startswith(("https:", "data:")):
                        self.assertTrue((path.parent / url).exists(), url)

    def test_landing_does_not_present_a_local_model_as_an_online_service(self):
        text = (ROOT / "site/index.html").read_text()
        self.assertIn("no ejecuta Ollama ni genera canciones online", text)
        self.assertIn("demo es simulada", text)


if __name__ == "__main__":
    unittest.main()
