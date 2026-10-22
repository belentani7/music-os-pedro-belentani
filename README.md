# MUSIC OS — compositor y estudio musical local

Sistema de composición **Python + Ollama + Streamlit**, con estructura musical intermedia `MusicIR`, letras, acordes, dirección vocal, propuestas de producción y exportación MIDI. Conserva los borradores y conversaciones musicales del archivo original sin mezclarlos con otros productos.

## Cómo ejecutarlo

Se necesitan Python 3.11 o superior, un modelo compatible con el formato JSON y Ollama funcionando en el equipo. No requiere una API de terceros ni está publicado como servicio de generación de audio en la nube.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
ollama pull qwen2.5:7b
streamlit run project/music_os_ui.py
```

En la barra lateral de la aplicación introduce el nombre de un modelo **que exista localmente**. La composición y los arreglos llaman al servicio real de Ollama; si no está disponible, el programa muestra un error y **no se guarda una canción falsa** como si hubiera sido generada.

El valor especial `demo-mode` es únicamente una demostración explícita: reutiliza una composición de ejemplo para probar la interfaz y el exportador MIDI sin red. **No genera letras nuevas** para el tema introducido. No uses ese modo para entregar una canción original.

## Qué entrega el motor

- Un objeto estructurado `MusicIR` con secciones, letras en el idioma solicitado, acordes y parámetros de producción.
- Exportación de un archivo MIDI de acompañamiento desde la progresión de acordes; es un boceto instrumental y **no un MP3, una grabación de voz ni una clonación vocal**.
- Historial local en `music_os_history.json` generado por la aplicación. Haz copias de seguridad porque contiene obras musicales inéditas.
- Vista de composición, evolución del historial y gráficos de dinámica en Streamlit.
- Validaciones: se rechazan respuestas sin JSON, secciones, letras o acordes completos. Las puntuaciones de originalidad devueltas por un LLM no son mediciones verificadas y no se presentan como evidencia.

## Comprobaciones

```bash
python -m compileall -q project tests
python -m unittest discover -s tests -p 'test_*.py'
python project/stress_test_music_os.py
```

La prueba de estrés utiliza `demo-mode` y puede crear un historial local: úsala en una carpeta de pruebas separada. Los test unitarios no requieren que Ollama esté conectado. Antes de publicar una versión es necesario comprobar de extremo a extremo el modelo, el MIDI y los permisos del historial.

Este repositorio conserva las versiones históricas en `versions/` y los textos en `chats/`. No se crea ni se fusiona ninguna marca musical adicional.

Licencia: consulta `LICENSE`.
