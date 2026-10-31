import streamlit as st
import google.generativeai as genai
import time
import re
import io
import asyncio
import edge_tts
import base64

# --- ¡AQUÍ PONES EL NOMBRE DE TU IA! ---
NOMBRE_IA = "Nova"

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title=NOMBRE_IA, page_icon="🤖", layout="wide")

# --- CSS PERSONALIZADO (ESTILO CHATGPT) ---
st.markdown("""
<style>
    /* Ocultar menús de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }

    /* Fondo general estilo ChatGPT */
    .stApp {
        background-color: #212121;
        color: #ececec;
    }

    /* Barra lateral gris muy oscuro */
    [data-testid="stSidebar"] {
        background-color: #171717;
        border-right: none;
    }

    /* Centrar el contenido para que no ocupe toda la pantalla */
    .block-container {
        max-width: 800px;
        padding-top: 2rem;
        padding-bottom: 6rem;
    }

    /* Burbujas de chat limpias */
    .stChatMessage {
        background-color: transparent !important;
        border: none !important;
        padding: 0.5rem 0 !important;
        box-shadow: none !important;
    }

    /* El mensaje del usuario se resalta con un fondo gris */
    /* (Usamos un truco para pintar solo los mensajes del usuario) */
    .stChatMessage[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background-color: #2f2f2f !important;
        border-radius: 15px !important;
        padding: 1rem !important;
        margin-bottom: 1rem !important;
    }

    /* Botones */
    .stButton>button {
        background-color: #2f2f2f;
        color: #ececec;
        border: 1px solid #444;
        border-radius: 8px;
    }
    .stButton>button:hover {
        background-color: #3f3f3f;
        color: #fff;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNCIÓN PARA GENERAR EL AUDIO ---
async def generar_audio_edge(texto, voz):
    comunicar = edge_tts.Communicate(texto, voz)
    audio_buffer = io.BytesIO()
    async for chunk in comunicar.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    audio_buffer.seek(0)
    return audio_buffer

# --- FUNCIÓN PARA REPRODUCIR AUDIO (INVISIBLE) ---
def autoplay_audio(audio_buffer, format="audio/mp3"):
    audio_bytes = audio_buffer.read()
    b64 = base64.b64encode(audio_bytes).decode()
    md = f"""
        <audio autoplay="true" hidden="true">
        <source src="data:{format};base64,{b64}" type="{format}">
        </audio>
        """
    st.markdown(md, unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title(f"🤖 {NOMBRE_IA}")
    st.caption("Tu asistente personal")
    st.divider()
    
    st.subheader("⚙️ Configuración")
    activar_voz = st.checkbox("🔊 Hablar respuestas en voz alta", value=True)
    
    voz_seleccionada = st.selectbox(
        "🎙️ Selecciona la voz",
        options=[
            "es-MX-DaliaNeural",  # Español Latino
            "es-ES-ElviraNeural", # Español de España
            "en-GB-SoniaNeural"   # Inglés Británico
        ],
        index=0
    )
    
    st.divider()
    st.subheader("📂 Sube tu código")
    archivo_subido = st.file_uploader("Archivo (ej. app.py)", type=["py", "txt", "html", "css", "js"])
    codigo_actual = ""
    if archivo_subido is not None:
        codigo_actual = archivo_subido.read().decode("utf-8")
        st.success(f"✅ {archivo_subido.name} ({len(codigo_actual.splitlines())} líneas)")
    
    st.divider()
    if st.button("🗑️ Nuevo Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- CONFIGURACIÓN DEL CEREBRO ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    instrucciones = f"Eres {NOMBRE_IA}, un asistente experto, elegante, amable y directo. Siempre respondes en español de forma clara."
    modelo = genai.GenerativeModel('gemini-3.5-flash', system_instruction=instrucciones)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- ÁREA PRINCIPAL DEL CHAT ---
    st.markdown(f"### ¿En qué puedo ayudarte hoy?")
    
    for message in st.session_state.messages:
        avatar = "👤" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # --- ZONA DE ENTRADA ---
    col1, col2 = st.columns([1, 8])
    with col1:
        audio_grabado = st.audio_input("Habla aquí", label_visibility="collapsed")
    with col2:
        prompt = st.chat_input(f"Habla con {NOMBRE_IA}...")

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
            with st.spinner("Pensando..."):
                max_reintentos = 3
                for intento in range(max_reintentos):
                    try:
                        respuesta = modelo.generate_content(contexto_ia)
                        texto_respuesta = respuesta.text
                        st.markdown(texto_respuesta)
                        st.session_state.messages.append({"role": "assistant", "content": texto_respuesta})
                        
                        if activar_voz and len(texto_respuesta) < 600: 
                            try:
                                audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, voz_seleccionada))
                                autoplay_audio(audio_buffer, format="audio/mp3")
                            except Exception as e:
                                st.warning(f"No se pudo generar la voz: {e}")
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
