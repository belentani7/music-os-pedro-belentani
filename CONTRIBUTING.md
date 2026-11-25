# Contribuir

## Flujo

1. Abre un issue describiendo el problema o la propuesta.
2. Crea una rama corta: `feat/...`, `fix/...` o `docs/...`.
3. Aplica el protocolo spec-first y añade tests.
4. Ejecuta la verificación local.
5. Abre un PR completando la checklist de `.github/pull_request_template.md`.

## Comandos

- `python -m pip install -r requirements-dev.txt`
- `python -m unittest discover -s tests -p "test_*.py" -v`
- `ruff check . && ruff format --check .`
- `streamlit run project/music_os_ui.py` (interfaz, sin necesidad de modelo)
- `python -m tools.music_os_cli --help` (CLI)

## Reglas

- Conventional commits.
- Sin secretos ni credenciales.
- Un cambio reversible por PR.
- Revisión de `@belentani7` y CI verde.
