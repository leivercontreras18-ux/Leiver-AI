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

# --- CSS AVANZADO (DISEÑO ETHEREAL / CORTANA) ---
st.markdown("""
<style>
    /* Fondo Espacial Profundo */
    .stApp {
        background-color: #0b0b12;
        background-image: radial-gradient(circle at 50% 50%, #1a1a2e 0%, #0b0b12 100%);
        color: #e0e0e0;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }
    
    /* Ajustar layout para que todo quepa */
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 2rem !important;
        max-width: 95% !important; 
    }

    /* -----------------------------------------
       EL ORBE FLUIDO (Morphing Blob CSS)
       ----------------------------------------- */
    .orb-container {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100%;
        margin-top: 5vh;
    }
    
    .fluid-orb {
        width: 320px;
        height: 320px;
        /* Colores pastel: Rosa, Morado, Azul */
        background: linear-gradient(135deg, #fbcfe8 0%, #d8b4fe 50%, #bfdbfe 100%);
        border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%;
        animation: morph 8s ease-in-out infinite, glow 3s infinite alternate;
        box-shadow: 0 0 80px rgba(216, 180, 254, 0.4), inset 0 0 40px rgba(255,255,255,0.5);
        position: relative;
    }

    /* Animación del Orbe (Cambio de forma) */
    @keyframes morph {
        0%, 100% { border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%; transform: rotate(0deg) scale(1); }
        34% { border-radius: 70% 30% 50% 50% / 30% 30% 70% 70%; transform: rotate(120deg) scale(1.05); }
        67% { border-radius: 100% 60% 60% 100% / 100% 100% 60% 60%; transform: rotate(240deg) scale(0.95); }
    }

    @keyframes glow {
        0% { box-shadow: 0 0 60px rgba(216, 180, 254, 0.3), inset 0 0 30px rgba(255,255,255,0.3); }
        100% { box-shadow: 0 0 120px rgba(251, 207, 232, 0.6), inset 0 0 50px rgba(255,255,255,0.6); }
    }

    .title-container {
        text-align: center;
        margin-top: 40px;
    }
    .title-container h1 {
        color: #ffffff;
        font-weight: 400;
        letter-spacing: 2px;
        margin-bottom: 5px;
    }
    .title-container p {
        color: #7dd3fc; /* Azul clarito */
        font-size: 14px;
    }

    /* -----------------------------------------
       EL PANEL DE CHAT (GLASSMORPHISM)
       ----------------------------------------- */
    /* Contenedor del chat con efecto cristal */
    div[data-testid="stVerticalBlock"]:has(> div > div > div > div[data-testid="stChatMessage"]) {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 20px !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
    }

    /* Ocultar avatares por defecto */
    div[data-testid="stChatMessageAvatarUser"],
    div[data-testid="stChatMessageAvatarAssistant"] {
        display: none !important;
    }

    /* Burbuja del Usuario (Morado Pastel) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background-color: #e9d5ff !important; 
        border-radius: 20px 20px 0 20px !important;
        margin-left: auto !important;
        width: fit-content !important;
        max-width: 85% !important;
        padding: 12px 18px !important;
    }
    /* Texto oscuro dentro de la burbuja del usuario */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) p {
        color: #1a1a1a !important; 
        font-size: 14px;
    }

    /* Burbuja de Nova (Rosa Pastel) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background-color: #fbcfe8 !important;
        border-radius: 20px 20px 20px 0 !important;
        margin-right: auto !important;
        width: fit-content !important;
        max-width: 85% !important;
        padding: 12px 18px !important;
    }
    /* Texto oscuro dentro de la burbuja de Nova */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) p {
        color: #1a1a1a !important;
        font-size: 14px;
    }

    /* -----------------------------------------
       BARRA DE TEXTO (Estilo Píldora Brillante)
       ----------------------------------------- */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        padding-bottom: 2rem !important;
    }
    .stChatInput {
        background: rgba(20, 20, 30, 0.8) !important;
        border: 2px solid #a855f7 !important; /* Borde Morado Brillante */
        border-radius: 30px !important;
        box-shadow: 0 0 20px rgba(168, 85, 247, 0.3) !important;
    }
    .stChatInput input {
        color: white !important;
    }

    /* Ocultar reproductor de audio */
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

# --- CONFIGURACIÓN DEL CEREBRO ---
try:
    api_key = st.secrets["GROQ_API_KEY"]
    cliente = Groq(api_key=api_key)
    instrucciones = f"Eres {NOMBRE_IA}, una IA avanzada, elegante y servicial. Responde de forma concisa y directa."

    # --- LAYOUT PRINCIPAL (2 Columnas: Orbe a la Izquierda, Chat a la Derecha) ---
    col_izq, col_der = st.columns([1.2, 1])

    with col_izq:
        st.markdown("""
            <div class="orb-container">
                <div class="fluid-orb"></div>
                <div class="title-container">
                    <h1>Nova</h1>
                    <p>How can I help you today?</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_der:
        # Contenedor con scroll para el chat
        chat_container = st.container(height=550)
        with chat_container:
            # Mostrar mensajes (sin avatares, el CSS los oculta)
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # --- LÓGICA DE ENTRADA ---
    prompt = st.chat_input(f"Ask {NOMBRE_IA}...")

    # El micrófono ahora va oculto en la barra lateral para mantener el diseño limpio
    with st.sidebar:
        st.markdown("### ⚙️ System")
        activar_voz = st.checkbox("🔊 Voz activa", value=True)
        audio_grabado = st.audio_input("🎤 Hablar", key=f"mic_{st.session_state.mic_key}")
        archivo_subido = st.file_uploader("📂 Código")
        codigo_actual = archivo_subido.read().decode("utf-8") if archivo_subido else ""
        if st.button("🗑️ Limpiar Chat"):
            st.session_state.messages = []
            st.session_state.mic_key += 1
            st.rerun()

    # --- PROCESAMIENTO ---
    if audio_grabado or prompt:
        texto_usuario = ""
        
        if audio_grabado and not prompt:
            with st.spinner("Escuchando..."):
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

    # --- AUDIO PENDIENTE ---
    if st.session_state.audio_pendiente:
        autoplay_audio(st.session_state.audio_pendiente)
        st.session_state.audio_pendiente = None

except KeyError:
    st.warning("⚠️ Falta la API Key de Groq.")
