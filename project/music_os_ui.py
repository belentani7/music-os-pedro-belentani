import streamlit as st
import json
import io
import os
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from music_os_core import MusicOS

# Configuración de la página
st.set_page_config(
    page_title="MUSIC OS v1.0 | Creative Engine",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1DB954; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.1rem; color: #888; margin-bottom: 2rem; }
    .section-title { font-size: 1.3rem; font-weight: bold; color: #1DB954; margin-top: 1.5rem; margin-bottom: 1rem; }
    .metric-card { background-color: #1e1e1e; padding: 1rem; border-radius: 0.5rem; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# Título principal
st.title("🧠 MUSIC OS v1.0")
st.caption("Taller local de composición, arreglos y exportación MIDI")

# --- BARRA LATERAL: CONFIGURACIÓN AVANZADA ---
with st.sidebar:
    st.header("⚙️ Configuración del Sistema")
    
    st.markdown("### 🎨 Parámetros de Creatividad")
    creativity = st.slider("Nivel de Creatividad / Originalidad", 0, 100, 75, help="Controla qué tan arriesgado y original será el algoritmo.")
    
    st.markdown("### 🎯 Objetivo Artístico")
    language = st.selectbox("Idioma Nativo", ["Español", "Portugués", "Inglés", "Catalán", "Francés"])
    styles = st.multiselect("Fusión de Estilos", ["Lady Gaga", "The Smiths", "Anitta", "Nathy Peluso"], default=["Lady Gaga", "The Smiths"])
    
    st.markdown("### 🎼 Parámetros Musicales")
    bpm = st.slider("BPM (Tempo)", 60, 160, 105)
    key = st.selectbox("Tonalidad", ["Am", "C", "Dm", "G", "Em", "Fmaj7", "Bm", "F", "Bb"])
    
    st.markdown("### 🤖 Cerebro Local")
    model = st.text_input("Modelo Ollama", value="qwen2.5:7b")
    if model.strip() == "demo-mode":
        st.warning("Modo DEMO: genera siempre la misma canción de ejemplo, no una obra nueva.")
    
    def clear_local_history():
        if not st.session_state.get("music_os_confirm_clear", False):
            return
        try:
            if os.path.exists("music_os_history.json"):
                os.remove("music_os_history.json")
                st.session_state["music_os_history_clear_status"] = "deleted"
            else:
                st.session_state["music_os_history_clear_status"] = "missing"
        except OSError:
            st.session_state["music_os_history_clear_status"] = "error"
        finally:
            # Callback runs before widgets are rebuilt, so consent never persists.
            st.session_state["music_os_confirm_clear"] = False

    confirm_clear = st.checkbox(
        "Confirmo que deseo borrar permanentemente el historial local de canciones",
        key="music_os_confirm_clear",
    )
    st.button("🗑️ Borrar historial local", disabled=not confirm_clear, on_click=clear_local_history)
    clear_status = st.session_state.pop("music_os_history_clear_status", None)
    if clear_status == "deleted":
        st.success("Historial local borrado.")
    elif clear_status == "missing":
        st.info("No existe historial local que borrar.")
    elif clear_status == "error":
        st.error("No se pudo borrar el historial. Revisa los permisos del archivo.")

# --- ÁREA CENTRAL ---
tab1, tab2, tab3 = st.tabs(["🎵 Composición", "🧠 Aprendizaje", "🗄️ Historial"])

with tab1:
    st.subheader("📝 Concepto creativo")
    theme = st.text_area("¿Sobre qué quieres que aprenda y cree el sistema hoy?", placeholder="Ej: La alienación en la era digital con un toque de cabaret oscuro...")
    
    if st.button("🚀 GENERAR Y EVOLUCIONAR", type="primary", use_container_width=True):
        if not theme.strip():
            st.error("Introduce un tema.")
        else:
            with st.spinner("🧠 Agentes negociando y aprendiendo de la historia..."):
                try:
                    mos = MusicOS(model_name=model)
                    music_ir = mos.generate_project(theme, styles, language, bpm, key, creativity)
                    
                    st.session_state["music_os_last_result"] = {
                        "ir": music_ir,
                        "midi": mos.export_midi(),
                        "demo": model.strip() == "demo-mode",
                    }

                except Exception as e:
                    st.error(f"Error: {e}")

    last_result = st.session_state.get("music_os_last_result")
    if last_result is not None:
        # Keep results and download buttons available across Streamlit reruns.
        music_ir = last_result["ir"]
        st.caption("Última composición generada en esta sesión")
        for warning in music_ir.evaluation.get("feedback", []):
            st.warning(str(warning))
        if last_result["demo"]:
            st.info("Demostración completada: composición de ejemplo, sin generación original.")
        else:
            st.success("Composición recibida de Ollama local. Revisa los resultados antes de utilizarlos.")
        
        # Dashboard de la Canción
        col_t, col_o, col_c = st.columns(3)
        with col_t: st.metric("🎶 Título", music_ir.metadata["title"])
        with col_o: st.metric("✨ Originalidad", "No evaluada")
        with col_c: st.metric("🌍 Idioma", music_ir.lyrics["language"])
        
        # Analítica Visual de la Canción
        st.subheader("📊 Análisis de dinámica y energía")
        dyn_data = music_ir.arrangement.get("dynamics", {})
        if dyn_data:
            df_dyn = pd.DataFrame(list(dyn_data.items()), columns=['Sección', 'Energía'])
            fig_dyn = px.line(df_dyn, x='Sección', y='Energía', markers=True, 
                             title="Curva de Dinámica Belentani",
                             color_discrete_sequence=['#1DB954'])
            fig_dyn.update_layout(template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_dyn, use_container_width=True)
            with st.expander("Ver datos de dinámica en tabla"):
                st.dataframe(df_dyn, hide_index=True, use_container_width=True)
        
        # Letra y Producción
        st.markdown("---")
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("**📖 Letra y Estructura:**")
            for sec in music_ir.musical["sections"]:
                with st.expander(f"🎼 {sec.upper()} | {', '.join(music_ir.harmony['chords'].get(sec, []))}"):
                    st.write(music_ir.lyrics["content"].get(sec, ""))
        with c2:
            st.markdown("**🎛️ Producción y Arreglos:**")
            st.info(f"🗣️ **Voz:** {music_ir.production['interpretation']}")
            st.json(music_ir.arrangement["instrumentation"])
        
        # Descargas
        st.markdown("---")
        d1, d2, d3 = st.columns(3)
        title_slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(music_ir.metadata.get("title") or "cancion")).strip("._-")[:80] or "cancion"
        lyrics_text = "\n\n".join(
            f"[{section}]\n{music_ir.lyrics['content'].get(section, '')}"
            for section in music_ir.musical["sections"]
        )
        d1.download_button("🎹 Descargar MIDI", last_result["midi"], f"music-os-{title_slug}.mid", mime="audio/midi")
        d2.download_button("📄 Descargar letra (TXT)", lyrics_text, f"music-os-{title_slug}-letra.txt", mime="text/plain")
        d3.download_button("📋 Music IR (JSON)", music_ir.to_json(), f"music-os-{title_slug}-ir.json", mime="application/json")


try:
    saved_history = MusicOS()._load_history()
except (OSError, ValueError):
    saved_history = []
    st.error("El historial local no se puede leer. Se ha conservado intacto: restaura una copia antes de modificarlo.")

with tab2:
    st.caption("Los patrones y métricas son propuestas del modelo, no entrenamiento ni medidas independientes de originalidad.")
    if saved_history:
        st.subheader("Parámetros creativos utilizados")
        history_rows = [
            {
                "Canción": str(entry.get("metadata", {}).get("title", "Sin título")),
                "Creatividad configurada": entry.get("metadata", {}).get("creativity_level", "—"),
            }
            for entry in saved_history if isinstance(entry.get("metadata"), dict)
        ]
        if history_rows:
            st.dataframe(pd.DataFrame(history_rows), hide_index=True, use_container_width=True)
        last = saved_history[-1]
        patterns = last.get("memory", {}).get("learned_patterns", [])
        if isinstance(patterns, list) and patterns:
            st.subheader("Patrones sugeridos por el modelo")
            for pattern in patterns:
                st.write(str(pattern))
        else:
            st.info("La última composición no contiene patrones sugeridos.")
        metrics = last.get("evaluation", {}).get("evolution_metrics", {})
        if isinstance(metrics, dict) and metrics:
            with st.expander("Estimaciones internas no verificadas"):
                st.json(metrics)
    else:
        st.info("Todavía no hay composiciones guardadas.")

with tab3:
    st.subheader("🗄️ Historial local")
    if saved_history:
        for entry in reversed(saved_history):
            metadata = entry.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            title = str(metadata.get("title", "Sin título"))
            styles = metadata.get("styles", [])
            style_text = ", ".join(str(style) for style in styles) if isinstance(styles, list) else ""
            st.write(f"🎵 **{title}** · Estilos: {style_text or 'Sin especificar'}")
    else:
        st.info("Historial vacío.")

st.markdown("---")
st.markdown("**MUSIC OS v1.0** | Motor de Evolución Artística para Pedro Belentani")
