"""Prueba de estrés del motor en modo demo y sin escribir en el repositorio.

Uso:
    python -m project.stress_test_music_os            # desde la raíz
    python stress_test_music_os.py                    # desde project/

El informe y el historial van a un directorio temporal: ejecutar la prueba
no ensucia el árbol de trabajo ni el historial real de la persona usuaria.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project.music_os_core import MusicOS


def run_stress_test(report_path: str | Path | None = None) -> list[dict]:
    """Ejecuta los cuatro casos demo y devuelve el informe.

    Cada caso se registra como PASSED/FAILED/CRASHED; el proceso solo devuelve
    código de error si algún caso no pasa (ver ``__main__``).
    """
    print("Prueba de estrés de MUSIC OS (modo demo explícito)")
    workspace = Path(tempfile.mkdtemp(prefix="music-os-stress-"))
    mos = MusicOS(model_name="demo-mode", history_file=workspace / "history.json")

    test_cases = [
        {
            "theme": "Soledad espacial",
            "styles": ["Lady Gaga", "The Smiths"],
            "lang": "Español",
            "bpm": 120,
            "key": "Am",
            "creativity": 80,
        },
        {
            "theme": "Carnaval distópico",
            "styles": ["Anitta", "Nathy Peluso"],
            "lang": "Portugués",
            "bpm": 95,
            "key": "Dm",
            "creativity": 60,
        },
        {
            "theme": "Ruptura en París",
            "styles": ["Lady Gaga", "Nathy Peluso"],
            "lang": "Francés",
            "bpm": 80,
            "key": "Em",
            "creativity": 90,
        },
        {
            "theme": "Nostalgia urbana",
            "styles": ["The Smiths"],
            "lang": "Catalán",
            "bpm": 105,
            "key": "G",
            "creativity": 70,
        },
    ]

    results = []

    for i, case in enumerate(test_cases):
        print(f"\nCaso {i + 1}: {case['theme']} ({case['lang']})")
        try:
            music_ir = mos.generate_project(
                theme=case["theme"],
                styles=case["styles"],
                language=case["lang"],
                bpm=case["bpm"],
                key=case["key"],
                creativity=case["creativity"],
            )

            # Verificaciones de Coherencia
            checks = {
                "title_exists": bool(music_ir.metadata["title"]),
                "sections_count": len(music_ir.musical["sections"]),
                "lyrics_complete": len(music_ir.lyrics["content"]) == len(music_ir.musical["sections"]),
                "chords_complete": len(music_ir.harmony["chords"]) == len(music_ir.musical["sections"]),
                "midi_generated": len(mos.export_midi()) > 0,
                "learning_updated": len(music_ir.memory["learned_patterns"]) > 0,
            }

            status = "✅ PASSED" if all(checks.values()) else "❌ FAILED"
            results.append({"case": case["theme"], "status": status, "checks": checks})
            print(f"Resultado: {status}")

        except Exception as e:
            print(f"ERROR CRÍTICO en el caso {i + 1}: {e}")
            results.append({"case": case["theme"], "status": "❌ CRASHED", "error": str(e)})

    print("\n" + "=" * 50)
    print("RESUMEN DE LA PRUEBA DE ESTRÉS")
    print("=" * 50)
    for res in results:
        print(f"- {res['case']}: {res['status']}")

    destination = Path(report_path) if report_path else workspace / "stress_test_report.json"
    destination.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReporte guardado en {destination}")
    return results


if __name__ == "__main__":
    report = run_stress_test(sys.argv[1] if len(sys.argv) > 1 else None)
    raise SystemExit(0 if all(str(item["status"]).startswith("✅") for item in report) else 1)
