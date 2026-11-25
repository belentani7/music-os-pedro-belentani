# music-os-pedro-belentani — AGENTS.md

> Repositorio del ecosistema belentani7. Adaptado automáticamente con superpowers + impeccable.

## Contexto del proyecto

Repositorio clonado de GitHub (belentani7/music-os-pedro-belentani). Tecnología detectada: python.

## Reglas de desarrollo

### Protocolo spec-first

Toda modificación sigue: PRD → SRS → Design Doc → ADR → Plan → Tests GWT.

### Impeccable (diseño frontend)

Registro brand y product. Pre-ship checklist obligatoria:
- Body text contrast >= 4.5:1
- No muted gray on tinted backgrounds
- Line length capped at 65-75ch
- Display letter-spacing >= -0.04em
- No gradient text
- No side-stripe borders
- No eyebrow on every section
- No identical card grids
- No nested cards
- z-index semántico, nunca 999/9999
- Animaciones con prefers-reduced-motion
- No bounce ni elastic easing
- Touch targets >= 44px
- Estados vacío, error y carga diseñados

### Tokens de diseño (CANON)

- Negro vacío: #05030a
- Rojo neón: #ff073a
- Dorado Zion: #d4af37
- Cyan señal: #4de8e0

## Seguridad

- No commitear secretos, API keys, tokens ni credenciales.
- Ejecutar gitleaks antes de cada push.
- CODEOWNERS: @belentani7 revisión requerida.

## Comandos

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p "test_*.py" -v
ruff check . && ruff format --check .
streamlit run project/music_os_ui.py
python -m tools.music_os_cli --help
```

- Despliegue web: `site/` estático (cero build de Node), publicado por
  `vercel.json`; la misma portada en la raíz sirve para Pages.
- Artefactos locales (`music_os_history.json`, `salida/`) están en `.gitignore`:
  nunca se versionan.
- El modo demo debe seguir siendo **explícito** y etiquetado como simulación.
  Un fallo del modelo real nunca se sustituye por la demo.

## Convenciones de commit

`type(scope): summary` (feat, fix, docs, chore, refactor, test, perf, style).
