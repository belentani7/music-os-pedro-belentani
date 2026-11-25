"""Contrato de la interfaz Streamlit y de las herramientas internas.

La UI se prueba con ``streamlit.testing.v1.AppTest`` (API oficial de Streamlit),
sin navegador y sin modelo: modo demo explícito.

Se omiten si Streamlit no está instalado, porque el núcleo debe funcionar
sin la capa de interfaz.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest

    STREAMLIT_AVAILABLE = True
except ImportError:  # pragma: no cover - entorno mínimo sin UI
    STREAMLIT_AVAILABLE = False

from tools import music_os_cli

UI_PATH = str(Path(__file__).resolve().parents[1] / "project" / "music_os_ui.py")


@unittest.skipUnless(STREAMLIT_AVAILABLE, "Streamlit no instalado")
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path.cwd()
        import os

        os.chdir(self.temp.name)  # el historial de la UI se escribe en cwd
        self.addCleanup(os.chdir, self.cwd)

    def run_app(self) -> AppTest:
        app = AppTest.from_file(UI_PATH, default_timeout=240)
        app.run()
        return app

    def test_empty_state_is_designed_and_has_no_exceptions(self):
        app = self.run_app()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any("Todavía no hay proyecto" in str(i.value) for i in app.info))

    def test_demo_flow_generates_project_midi_and_downloads(self):
        app = self.run_app()
        app.toggle[0].set_value(True).run()
        app.text_area[0].input("La alienación en la era digital")
        app.button[0].click().run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(list(app.error), [])
        self.assertTrue(any("simulación demo" in str(w.value) for w in app.warning))
        self.assertTrue(any("Proyecto generado" in str(s.value) for s in app.success))

        metrics = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(metrics.get("Tonalidad"), "Am")
        self.assertEqual(metrics.get("BPM"), "105")

        downloads = [widget.label for widget in app.get("download_button")]
        self.assertIn("Descargar MIDI", downloads)
        self.assertIn("Hoja de sesión (.txt)", downloads)
        self.assertIn("MusicIR (.json)", downloads)

        history = Path("music_os_history.json")
        self.assertTrue(history.exists())
        entries = json.loads(history.read_text(encoding="utf-8"))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["metadata"]["provider"], "demo")

    def test_real_model_without_ollama_shows_actionable_error_and_saves_nothing(self):
        app = self.run_app()
        app.text_area[0].input("prueba sin modelo")
        app.button[0].click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any("Ollama no disponible" in str(e.value) for e in app.error))
        self.assertTrue(any("modo demo" in str(e.value) for e in app.error))
        self.assertFalse(Path("music_os_history.json").exists())

    def test_empty_theme_is_rejected_without_touching_the_model(self):
        app = self.run_app()
        app.button[0].click().run()
        self.assertTrue(any("Escribe un concepto" in str(e.value) for e in app.error))

    def test_all_three_tabs_render(self):
        app = self.run_app()
        labels = [tab.label for tab in app.tabs]
        self.assertEqual(labels, ["Composición", "Aprendizaje", "Historial"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.history = self.root / "history.json"
        self.out = self.root / "salida"

    def run_cli(self, *args: str) -> int:
        argv = ["--history-file", str(self.history), *args]
        return music_os_cli.main(argv)

    def test_help_is_available(self):
        with self.assertRaises(SystemExit) as ctx:
            music_os_cli.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_generate_writes_the_four_artifacts(self):
        code = self.run_cli("generate", "--theme", "alienación", "--demo", "--out", str(self.out), "--json")
        self.assertEqual(code, 0)
        files = {path.suffix for path in self.out.iterdir()}
        self.assertEqual(files, {".json", ".mid", ".txt", ".svg"})
        payload = json.loads(next(self.out.glob("*.musicir.json")).read_text(encoding="utf-8"))
        self.assertEqual(payload["metadata"]["provider"], "demo")
        self.assertTrue(next(self.out.glob("*.mid")).read_bytes().startswith(b"MThd"))

    def test_verify_and_inspect_validate_the_outputs(self):
        self.assertEqual(
            self.run_cli("generate", "--theme", "x", "--demo", "--out", str(self.out)),
            0,
        )
        midi = next(self.out.glob("*.mid"))
        project = next(self.out.glob("*.musicir.json"))
        self.assertEqual(self.run_cli("verify", str(midi)), 0)
        self.assertEqual(self.run_cli("inspect", str(project)), 0)

    def test_real_model_failure_returns_exit_code_2(self):
        code = self.run_cli("generate", "--theme", "x", "--out", str(self.out))
        self.assertEqual(code, 2)

    def test_history_and_clear(self):
        self.run_cli("generate", "--theme", "x", "--demo", "--no-files")
        self.assertTrue(self.history.exists())
        self.assertEqual(self.run_cli("history", "--limit", "1"), 0)
        self.assertEqual(self.run_cli("clear-history", "--yes"), 0)
        self.assertFalse(self.history.exists())

    def test_inspect_rejects_a_broken_file(self):
        broken = self.root / "broken.json"
        broken.write_text("{no es json", encoding="utf-8")
        self.assertEqual(self.run_cli("inspect", str(broken)), 3)


if __name__ == "__main__":
    unittest.main()
