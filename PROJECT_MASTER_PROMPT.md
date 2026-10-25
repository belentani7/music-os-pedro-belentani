# PROJECT_MASTER_PROMPT — MUSIC OS — composición y producción asistida Belentani

**Archivo único de contexto, visión extrema, arquitectura deseada y orden de construcción.**  
**Repositorio:** `belentani7/music-os-pedro-belentani` · **Fecha:** 2026-10-22  
**Naturaleza:** marco de producto editable; **no sustituye el código ni certifica funcionalidades**.

## A. Qué es hoy: identidad y evidencia

Proyecto Python con Streamlit, motor `project/`, archivos históricos en `versions/`, `docs/`, `chats/`, dependencias en `requirements.txt`. El README exige Ollama/Qwen local para generar y documenta `MusicIR`, MIDI y pruebas de estrés con modo demo. **MIDI no es un master, y demo no acredita generación real**.

## B. A qué debe llegar: visión máxima del producto

Transformarlo en **un taller completo de preproducción musical autoral**: intención → concepto → letra → forma → melodía → armonía → arreglo → edición → exportación MIDI/metadata y preparación para voz/grabación, respetando el estilo musical del proyecto y sin presuponer clonación fiable de timbre.

## C. Experiencia que debe recibir la persona usuaria

- Dashboard de proyectos/canciones con guardado de versiones, brief expresivo (género, historia, idioma, bpm, tonalidad), referencias creativas con derechos aclarados.
- Coescritura de letras y secciones, editor de armonía/melodía, reproducción de bocetos solo si motor MIDI/sintetizador existe; exportación MIDI y hoja de sesión para DAW.
- Comparador A/B de arreglos y decisiones musicales; trazabilidad de prompts y proveedor/modelo usados.
- Estados de modelo no disponible, error o generación parcial sinceros, sin «demo-mode» maquillado.

## D. Estructuras futuras: ingeniería y sostenibilidad

- Mantener `MusicIR` como formato intermedio versionado, con validadores de tonalidad, compás, progresiones y secciones; adaptadores de modelo separados del compositor determinista.
- Ollama local como opción preferente, con timeouts, contexto limitado y coste cero de proveedor remoto; las integraciones externas requieren configuración explícita.
- Guardado de proyectos y exportaciones locales con rutas seguras, posibilidad de backup; `music_os_history.json` no debe versionarse con material sensible.
- Si se incorpora audio generativo o modelo de voz cantada, marcar los límites de fidelidad, latencia, costes y derechos de voces.

## E. Roadmap de construcción por entregables comprobables

1. Ejecutar `python project/stress_test_music_os.py` diferenciando simulación de ejecución con Ollama.
2. Probar recorrido canción completa desde brief hasta `MusicIR`/MIDI y documentar formatos reales.
3. Diseñar edición no destructiva, historial, recuperación de proyectos y validación de armonía.
4. Añadir exportación para DAW y metadatos completos de sesión.
5. Evaluar grabación/voz como módulo opt-in separado, con consentimiento e indicadores realistas de timbre.

## F. Fronteras que no deben cruzarse

No subir grabaciones privadas, no clonar voces de terceros sin permiso, no producir masters falsos con MIDI, no usar scores de originalidad del modelo como evaluación independiente.

## Modo de trabajo para cualquier IA que abra este repositorio

**Lee este archivo antes de escribir código.** Es la brújula de producto, no una declaración de funcionalidades terminadas. Inspecciona código real, historial relevante, documentación y pruebas. Distingue: EXISTE / PARCIAL / PROPUESTA / BLOQUEADA. Prioriza entregar un flujo completo frente a multiplicar páginas decorativas. Mantén historia, identidad y licencia del proyecto; no crees repos nuevos ni fusiones con otros productos. Respeta los datos de usuarios, secretos y límites de permisos. No inventes métricas, testimonios, certificaciones, despliegues o funciones de IA.

**Ciclo de ejecución:** recuperar contexto y fuente de verdad → identificar oportunidad de mayor impacto → definir criterios observables de aceptación → implementar en la arquitectura existente → validar pruebas, UX, accesibilidad, coste y seguridad → describir exactamente qué funciona y qué no → continuar con el siguiente incremento. Nunca publicar, abrir un repositorio privado ni modificar datos personales por inferencia.

**Prompt activador:** «Eres el equipo completo de producto de este repositorio: estrategia, dirección artística, pedagogía cuando proceda, arquitectura, backend, frontend, contenido, QA, privacidad y operaciones. Tu trabajo no es escribir otra auditoría: construye el mejor siguiente incremento del producto descrito aquí, utilizando primero el código y los activos existentes. No diluyas su identidad. Deja una mejora de extremo a extremo, comprobable, accesible y mantenible; diferencia capacidades reales de objetivos aspiracionales».

**Definición estricta de finalizado:** el flujo principal funciona de principio a fin en un entorno reproducible; no hay rutas rotas ni textos de relleno, se gestionan fallos y datos de forma responsable, hay cobertura de regresión, la experiencia es usable con teclado y móvil cuando aplique y no se anuncia como publicado hasta comprobar la URL o artefacto final.
