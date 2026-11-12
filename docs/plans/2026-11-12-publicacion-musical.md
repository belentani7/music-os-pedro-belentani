# Publicación verificable de MUSIC OS

## PRD y SRS
La portada debe describir la aplicación local existente, conducir a instalación y código, y explicar MIDI, privacidad y demo. Vercel no puede compilar un package.json inexistente.

## Diseño y ADR
Publicar site/ como contenido estático sin build de Node; mantener la misma portada en la raíz para Pages. Conservar el HTML anterior como texto. Reutilizar CSS local sin dependencias ni enlaces vacíos. La aplicación Streamlit y Ollama siguen siendo locales.

## Plan y aceptación
Comprobar rutas de recursos y configuración de publicación. Añadir pruebas del ciclo simulado, MIDI, persistencia en directorio temporal y ausencia de fallback simulado al fallar Ollama. Ejecutarlas en CI con la dependencia MIDI, sin requerir un modelo ni comunicar con proveedores. Las pruebas no acreditan calidad artística.

## Resultado local
Ocho pruebas aprobadas con Python 3.12 y MIDIUtil 1.2.1; compilación de fuentes y revisión del diff sin errores. No se llamó a un modelo real ni se evaluó calidad artística. Se declara Python >=3.9 por las anotaciones nativas del código existente.
