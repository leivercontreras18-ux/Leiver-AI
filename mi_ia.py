import streamlit as st
import google.generativeai as genai
import time
import re
import io
from gtts import gTTS

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Leiver AI", page_icon="🤖", layout="wide")

# --- CSS PERSONALIZADO (DISEÑO PREMIUM) ---
st.markdown("""
<style>
    /* Ocultar menús de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Fondo con degradado espacial */
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        color: #e0e0e0;
    }

    /* Barra lateral con efecto cristal */
    [data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.7);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Burbujas de chat estilo cristal */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 1.2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        color: #ffffff;
    }

    /* Botones elegantes */
    .stButton>button {
        background: linear-gradient(90deg, #4b33a8 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 10px;
        transition: transform 0.2s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
    }

    /* Cuadro de texto */
    .stChatInput {
        border-radius: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("🤖 Leiver AI")
    st.caption("v2.5 - Premium Edition")
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
    
    instrucciones = "Eres Leiver AI, un asistente experto, elegante, amable y directo (estilo Jarvis). Siempre respondes en español de forma clara."
    # Usamos 3.5-flash que está activo y es más estable
    modelo = genai.GenerativeModel('gemini-3.5-flash', system_instruction=instrucciones)

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
