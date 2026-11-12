import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from project.music_os_core import MusicIR, MusicOS, MusicOSAgent

ROOT = Path(__file__).resolve().parents[1]


class MusicLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = MusicOS(model_name='demo-mode')
        self.engine.history_file = str(Path(self.temp.name) / 'history.json')

    def generate(self):
        return self.engine.generate_project('un tema de prueba', ['electrónica'], 'Portugués', 95, 'Dm', 60)

    def test_demo_project_preserves_requested_parameters_and_round_trips(self):
        project = self.generate()
        self.assertEqual(project.musical['bpm'], 95)
        self.assertEqual(project.musical['key'], 'Dm')
        self.assertEqual(project.lyrics['language'], 'Portugués')
        self.assertEqual(MusicIR.from_json(project.to_json()), project)

    def test_export_is_a_midi_file_with_music_tracks(self):
        self.generate()
        midi = self.engine.export_midi()
        self.assertEqual(midi[:4], b'MThd')
        self.assertIn(b'MTrk', midi)
        self.assertGreater(len(midi), 100)

    def test_history_is_local_and_feeds_the_next_project(self):
        first = self.generate()
        second = self.generate()
        saved = json.loads(Path(self.engine.history_file).read_text())
        self.assertEqual(len(saved), 2)
        self.assertIn(first.metadata['title'], second.memory['past_references'])

    def test_real_provider_failure_never_returns_the_canned_demo(self):
        def fail(**kwargs):
            raise ConnectionError('offline in test')
        with patch.dict('sys.modules', {'ollama': SimpleNamespace(chat=fail)}):
            with self.assertRaisesRegex(RuntimeError, 'Ollama no disponible'):
                MusicOSAgent('Compositor', 'real-model').call_llm('test')

    def test_invalid_composition_does_not_persist_a_successful_project(self):
        with patch.object(self.engine.composer, 'call_llm', return_value='invalid json'):
            with self.assertRaises(ValueError):
                self.generate()
        self.assertFalse(Path(self.engine.history_file).exists())


class Publication(unittest.TestCase):
    def test_vercel_publishes_an_existing_directory_without_a_node_build(self):
        config = json.loads((ROOT / 'vercel.json').read_text())
        self.assertTrue((ROOT / config['outputDirectory'] / 'index.html').is_file())
        self.assertIsNone(config['buildCommand'])
        self.assertIsNone(config['installCommand'])
        self.assertNotIn('builds', config)

    def test_published_and_pages_landing_have_real_local_resources_and_actions(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []
                self.ids = set()
                self.h1 = 0
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                self.urls.extend(attrs[k] for k in ('href', 'src') if k in attrs)
                if 'id' in attrs:
                    self.ids.add(attrs['id'])
                self.h1 += tag == 'h1'
        for path in (ROOT / 'index.html', ROOT / 'site/index.html'):
            with self.subTest(path=path.name):
                page = Links()
                page.feed(path.read_text())
                self.assertEqual(page.h1, 1)
                for url in page.urls:
                    self.assertNotEqual(url, '#')
                    if url.startswith('#'):
                        self.assertIn(url[1:], page.ids)
                    elif not url.startswith(('https:', 'data:')):
                        self.assertTrue((path.parent / url).exists(), url)

    def test_landing_does_not_present_a_local_model_as_an_online_service(self):
        text = (ROOT / 'site/index.html').read_text()
        self.assertIn('no ejecuta Ollama ni genera canciones online', text)
        self.assertIn('demo es simulada', text)


if __name__ == '__main__':
    unittest.main()
