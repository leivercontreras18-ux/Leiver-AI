import streamlit as st
import google.generativeai as genai
import time
import re
import io
from gtts import gTTS

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Leiver AI 2.0", page_icon="🤖", layout="wide")

# --- CSS PERSONALIZADO PARA DISEÑO PREMIUM ---
st.markdown("""
<style>
    /* Ocultar menús */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Fondo general más limpio */
    .stApp {
        background-color: #0e1117;
    }

    /* Estilo de las burbujas de chat */
    .stChatMessage {
        background-color: #1e2530;
        border-radius: 15px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #2e3a4e;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }

    /* Barra lateral más elegante */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #2e3a4e;
    }
</style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("🤖 Leiver AI 2.0")
    st.caption("Tu asistente personal de élite")
    st.divider()
    
    st.subheader("⚙️ Configuración")
    activar_voz = st.checkbox("🔊 Hablar respuestas en voz alta", value=True)
    
    st.divider()
    st.subheader("📂 Sube tu código")
    archivo_subido = st.file_uploader("Archivo (ej. app.py)", type=["py", "txt", "html", "css", "js"])
    codigo_actual = ""
    if archivo_subido is not None:
        codigo_actual = archivo_subido.read().decode("utf-8")
        st.success(f"✅ {archivo_subido.name} ({len(codigo_actual.splitlines())} líneas)")
    
    st.divider()
    if st.button("🗑️ Limpiar Conversación", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- CONFIGURACIÓN DEL CEREBRO ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    instrucciones = "Eres Leiver AI, un asistente experto, elegante, amable y directo (estilo Jarvis). Siempre respondes en español de forma clara y breve si es una charla."
    modelo = genai.GenerativeModel('gemini-1.5-flash', system_instruction=instrucciones)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- ÁREA PRINCIPAL DEL CHAT ---
    st.subheader("💬 Centro de Mando")
    
    # Mostrar historial
    for message in st.session_state.messages:
        avatar = "👤" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # --- ZONA DE ENTRADA (Voz y Texto) ---
    col1, col2 = st.columns([1, 4])
    with col1:
        st.write("🎤 **Voz:**")
        audio_grabado = st.audio_input("Habla aquí", label_visibility="collapsed")
    with col2:
        st.write("⌨️ **Texto:**")
        prompt = st.chat_input("Escribe tu mensaje...")

    # --- LÓGICA DE PROCESAMIENTO ---
    if audio_grabado or prompt:
        if prompt:
            texto_usuario = prompt
            contexto_ia = prompt
            tipo_entrada = "texto"
        else:
            texto_usuario = "🎤 (Mensaje de voz)"
            audio_bytes = audio_grabado.read()
            contexto_ia = [
                "Responde a este mensaje de voz:",
                {"mime_type": "audio/wav", "data": audio_bytes}
            ]
            tipo_entrada = "voz"

        with st.chat_message("user", avatar="👤"):
            if tipo_entrada == "voz":
                st.audio(audio_grabado)
                st.markdown(texto_usuario)
            else:
                st.markdown(texto_usuario)
        
        st.session_state.messages.append({"role": "user", "content": texto_usuario})

        if codigo_actual and tipo_entrada == "texto":
            contexto_ia = f"Te adjunto el código actual del archivo:\n\n```python\n{codigo_actual}\n```\n\nMi petición es: {prompt}\n\nPor favor, devuélveme el código completo modificado dentro de un bloque de código."

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Procesando..."):
                max_reintentos = 3
                for intento in range(max_reintentos):
                    try:
                        respuesta = modelo.generate_content(contexto_ia)
                        texto_respuesta = respuesta.text
                        st.markdown(texto_respuesta)
                        st.session_state.messages.append({"role": "assistant", "content": texto_respuesta})
                        
                        if activar_voz and len(texto_respuesta) < 600: 
                            tts = gTTS(text=texto_respuesta, lang='es', slow=False)
                            audio_salida = io.BytesIO()
                            tts.write_to_fp(audio_salida)
                            st.audio(audio_salida, format="audio/mp3", autoplay=True)
                        elif activar_voz:
                            st.info("🔇 Respuesta larga (código). No se lee en voz alta.")
                        
                        break 
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            if intento < max_reintentos - 1:
                                match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', error_str)
                                espera = int(match.group(1)) + 2 if match else 30
                                st.warning(f"⏳ Límite alcanzado. Esperando {espera} segundos...")
                                time.sleep(espera)
                            else:
                                st.error("❌ Límite de la API superado.")
                        else:
                            st.error(f"Error: {e}")
                            break

except KeyError:
    st.warning("⚠️ Falta la API Key.")
