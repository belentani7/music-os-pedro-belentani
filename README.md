# MUSIC OS — Pedro Belentani

Sistema de composición musical asistida con interfaz Streamlit, agentes de
composición, producción y aprendizaje, exportación MIDI y un modelo intermedio
de proyecto (`MusicIR`). Las versiones y archivos históricos se conservan
en `versions/`, `chats/` y `docs/`.

## Instalar

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
streamlit run project/music_os_ui.py
```

Debes tener Ollama ejecutándose localmente para generar composiciones reales.
Si Ollama no está disponible, se informa del error en vez de presentar letras
de ejemplo como si fueran una generación auténtica.

## Probar el motor sin un modelo local

```bash
cd project
python stress_test_music_os.py
```

La prueba utiliza intencionadamente `demo-mode` y **contenido simulado**.
Sus composiciones no acreditan calidad artística ni originalidad. El valor
`originality_score` es una estimación devuelta por el modelo, no una medida
externa verificada.

## Datos

La aplicación crea `music_os_history.json` localmente para guardar proyectos
anteriores. Revísalo antes de compartir un directorio o publicarlo. La
exportación MIDI representa progresiones y arreglos; no equivale a producir un
master de audio o una canción cantada. Las funciones históricas están
conservadas, pero no todas forman parte de la experiencia actual.

## Licencia

Consulta el archivo `LICENSE` para conocer los términos aplicables.
