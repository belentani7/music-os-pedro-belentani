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


## Producto
Véase `plataforma/OFERTA.md`, `plataforma/precios.json`, `plataforma/ONEPAGER.md`.

## Publicación de la web

Vercel publica `site/` como HTML estático sin compilación de Node. La misma portada en la raíz permite la publicación de Pages; ninguna de estas portadas ejecuta el motor local. El entorno requiere Python 3.9 o posterior (CI verificado con 3.12).

Pruebas sin modelo local: `python -m unittest discover -s tests -p test_release.py -v`, con `midiutil==1.2.1` instalado. Incluyen MIDI real, historial temporal, errores del proveedor y contrato de publicación. Las generaciones de prueba usan demo explícita.
