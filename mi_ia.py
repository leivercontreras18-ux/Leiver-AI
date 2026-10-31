import streamlit as st
import time
import io
import asyncio
import edge_tts
import base64
from groq import Groq

# --- CONFIGURACIÓN ---
NOMBRE_IA = "Nova"
VOZ_FIJA = "es-MX-DaliaNeural"

st.set_page_config(page_title=NOMBRE_IA, page_icon="🌌", layout="wide")

# --- CSS AVANZADO (ESTILO CYBERPUNK / HOLOGRÁFICO) ---
st.markdown("""
<style>
    /* Fondo espacial profundo */
    .stApp {
        background: radial-gradient(circle at 50% 50%, #050510 0%, #000000 100%);
        color: #e0e0e0;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }
    .block-container { padding-top: 1rem !important; max-width: 95% !important; }

    /* -----------------------------------------
       EL ORBE HOLOGRÁFICO (Usando un GIF animado)
       ----------------------------------------- */
    .orb-container {
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        align-items: center;
        height: 50vh;
        position: relative;
        margin-top: 20px;
    }
    
    .orb-gif {
        width: 320px;
        height: 320px;
        border-radius: 50%;
        /* Aquí usamos una imagen animada de plasma en lugar de un div CSS */
        background-image: url('https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Z5Z3R6cXZ4Z3R6cXZ4Z3R6cXZ4Z3R6cXZ4Z3R6cXZ4Z3R6cXZ4JmVwPXYxX2ludGVybmFsX2dpZl9ieV9pZCZjdD1n/3o7TKr3nzbCg4rO5u8/giphy.gif');
        background-size: cover;
        background-position: center;
        box-shadow: 0 0 50px rgba(0, 242, 254, 0.5), 0 0 100px rgba(255, 0, 128, 0.3);
        animation: pulse 2s infinite alternate ease-in-out;
    }

    @keyframes pulse {
        0% { transform: scale(0.95); filter: brightness(0.8); }
        100% { transform: scale(1.05); filter: brightness(1.2); }
    }

    /* -----------------------------------------
       LOS PANELES DE CHAT (ESTILO HOLOGRAMA)
       ----------------------------------------- */
    /* Estilo general de las burbujas */
    div[data-testid="stChatMessage"] {
        background: rgba(0, 0, 0, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        border-radius: 10px !important;
        padding: 15px !important;
        margin-bottom: 15px !important;
    }

    /* Panel del Usuario (Borde Magenta) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        border: 1px solid #ff00ff !important;
        box-shadow: 0 0 15px rgba(255, 0, 255, 0.4), inset 0 0 10px rgba(255, 0, 255, 0.2) !important;
    }

    /* Panel de Nova (Borde Cian) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        border: 1px solid #00f2fe !important;
        box-shadow: 0 0 15px rgba(0, 242, 254, 0.4), inset 0 0 10px rgba(0, 242, 254, 0.2) !important;
    }

    /* Barra de texto estilo consola futurista */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        padding-bottom: 0rem !important;
    }
    .stChatInput {
        background: rgba(10, 15, 30, 0.8) !important;
        backdrop-filter: blur(15px) !important;
        border: 1px solid #00f2fe !important;
        border-radius: 10px !important;
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.3) !important;
    }

    audio { display: none !important; }
    div[data-testid="stAudio"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE AUDIO ---
async def generar_audio_edge(texto, voz):
    comunicar = edge_tts.Communicate(texto, voz)
    audio_buffer = io.BytesIO()
    async for chunk in comunicar.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    audio_buffer.seek(0)
    return audio_buffer

def autoplay_audio(audio_buffer):
    audio_bytes = audio_buffer.read()
    b64 = base64.b64encode(audio_bytes).decode()
    audio_html = f'<audio autoplay="true" src="data:audio/mp3;base64,{b64}"></audio>'
    st.markdown(audio_html, unsafe_allow_html=True)

# --- INICIALIZAR ESTADO ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "mic_key" not in st.session_state:
    st.session_state.mic_key = 0
if "audio_pendiente" not in st.session_state:
    st.session_state.audio_pendiente = None

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"### 🌌 {NOMBRE_IA} System")
    st.divider()
    activar_voz = st.checkbox("🔊 Voz activa", value=True)
    audio_grabado = st.audio_input("🎤 Hablar", key=f"mic_{st.session_state.mic_key}")
    archivo_subido = st.file_uploader("📂 Código")
    codigo_actual = archivo_subido.read().decode("utf-8") if archivo_subido else ""
    if st.button("🗑️ Reiniciar Sistema"):
        st.session_state.messages = []
        st.session_state.mic_key += 1
        st.rerun()

# --- CONFIGURACIÓN DEL CEREBRO ---
try:
    api_key = st.secrets["GROQ_API_KEY"]
    cliente = Groq(api_key=api_key)
    instrucciones = f"Eres {NOMBRE_IA}, un asistente experto. Responde de forma directa, elegante y concisa."

    # --- LAYOUT PRINCIPAL ---
    col_izq, col_der = st.columns([1.1, 1])

    with col_izq:
        st.markdown("""
            <div class="orb-container">
                <div class="orb-gif"></div>
                <div style="text-align: center; margin-top: 20px; z-index: 10;">
                    <h2 style="color: #00f2fe; letter-spacing: 8px; text-shadow: 0 0 15px #00f2fe; margin-bottom: 0;">NOVA</h2>
                    <p style="color: #888; font-size: 12px; letter-spacing: 2px;">STATUS: ONLINE</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_der:
        st.markdown("<h3 style='color: #00f2fe; margin-bottom: 10px; margin-top: 0; text-shadow: 0 0 5px #00f2fe;'>REGISTRO DE MISIÓN</h3>", unsafe_allow_html=True)
        
        chat_container = st.container(height=450)
        with chat_container:
            for message in st.session_state.messages:
                avatar = "👤" if message["role"] == "user" else "🤖"
                with st.chat_message(message["role"], avatar=avatar):
                    st.markdown(message["content"])

    # --- LÓGICA DE ENTRADA ---
    prompt = st.chat_input(f"Escribe un comando para {NOMBRE_IA}...")

    if audio_grabado or prompt:
        texto_usuario = ""
        
        if audio_grabado and not prompt:
            with st.spinner("Analizando voz..."):
                try:
                    transcripcion = cliente.audio.transcriptions.create(
                        file=("audio.wav", audio_grabado.read()),
                        model="whisper-large-v3",
                        language="es"
                    )
                    texto_usuario = transcripcion.text
                except Exception as e:
                    st.error(f"Error de audio: {e}")
        elif prompt:
            texto_usuario = prompt
            
        if texto_usuario:
            st.session_state.messages.append({"role": "user", "content": texto_usuario})

            contexto_ia = texto_usuario
            if codigo_actual:
                contexto_ia = f"Código:\n```python\n{codigo_actual}\n```\nPetición: {texto_usuario}"

            try:
                respuesta = cliente.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": instrucciones},
                        {"role": "user", "content": contexto_ia}
                    ],
                    temperature=0.7,
                    max_tokens=2048
                )
                
                texto_respuesta = respuesta.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": texto_respuesta})
                
                if activar_voz: 
                    try:
                        audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, VOZ_FIJA))
                        st.session_state.audio_pendiente = audio_buffer
                    except Exception:
                        pass
                
                st.session_state.mic_key += 1
                st.rerun()
                
            except Exception as e:
                st.error(f"Error de Groq: {e}")

    # --- AUDIO PENDIENTE AL FINAL ---
    if st.session_state.audio_pendiente:
        autoplay_audio(st.session_state.audio_pendiente)
        st.session_state.audio_pendiente = None

except KeyError:
    st.warning("⚠️ Falta la API Key de Groq.")
