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
    /* Fondo Espacial */
    .stApp {
        background-color: #0b0b12;
        background-image: radial-gradient(circle at 50% 50%, #1a1a2e 0%, #0b0b12 100%);
        color: #e0e0e0;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }
    
    .block-container { 
        padding-top: 3rem !important; 
        padding-bottom: 2rem !important;
        max-width: 90% !important; 
    }

    /* -----------------------------------------
       1. EL ORBE DEFORMABLE (Morpling Blob)
       ----------------------------------------- */
    .orb-wrapper {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 70vh;
    }
    
    .fluid-orb {
        width: 280px;
        height: 280px;
        /* Gradiente pastel: Rosa, Morado, Azul */
        background: linear-gradient(135deg, #fbcfe8 0%, #d8b4fe 50%, #bfdbfe 100%);
        /* Animación combinada: deformación + flotación */
        animation: morph 8s ease-in-out infinite, float 6s ease-in-out infinite;
        box-shadow: 0 0 60px rgba(216, 180, 254, 0.5), inset 0 0 40px rgba(255,255,255,0.6);
        filter: blur(6px);
    }

    /* La animación de deformación que te gustó */
    @keyframes morph {
        0%, 100% { border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%; }
        34% { border-radius: 70% 30% 50% 50% / 30% 30% 70% 70%; }
        67% { border-radius: 100% 60% 60% 100% / 100% 100% 60% 60%; }
    }

    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-15px); }
        100% { transform: translateY(0px); }
    }

    .title-container {
        text-align: center;
        margin-top: 30px;
    }
    .title-container h1 {
        color: #ffffff;
        font-weight: 300;
        letter-spacing: 2px;
        margin-bottom: 0px;
    }
    .title-container p {
        color: #7dd3fc;
        font-size: 14px;
    }

    /* -----------------------------------------
       2. EL PANEL DE CHAT (Cristal Templado)
       ----------------------------------------- */
    /* Caja contenedora del chat */
    div[data-testid="stVerticalBlock"]:has(div[data-testid="stChatMessage"]) {
        background: rgba(255, 255, 255, 0.04) !important;
        backdrop-filter: blur(15px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 20px !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4) !important;
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
        padding: 10px 15px !important;
        margin-bottom: 15px !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) p {
        color: #1a1a1a !important; 
        margin: 0;
    }

    /* Burbuja de Nova (Rosa Pastel) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background-color: #fbcfe8 !important;
        border-radius: 20px 20px 20px 0 !important;
        margin-right: auto !important;
        width: fit-content !important;
        max-width: 85% !important;
        padding: 10px 15px !important;
        margin-bottom: 15px !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) p {
        color: #1a1a1a !important;
        margin: 0;
    }

    /* -----------------------------------------
       3. BARRA DE TEXTO (Píldora Brillante)
       ----------------------------------------- */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        padding-bottom: 1rem !important;
    }
    .stChatInput {
        background: rgba(20, 20, 30, 0.9) !important;
        border: 2px solid #a855f7 !important; 
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
    instrucciones = f"Eres {NOMBRE_IA}, una IA avanzada, elegante y servicial. Responde de forma concisa."

    # --- LAYOUT PRINCIPAL ---
    col_izq, col_der = st.columns([1.2, 1])

    with col_izq:
        st.markdown("""
            <div class="orb-wrapper">
                <div class="fluid-orb"></div>
                <div class="title-container">
                    <h1>Nova</h1>
                    <p>How can I help you today?</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_der:
        # Contenedor con altura fija para el chat
        chat_container = st.container(height=550)
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # --- LÓGICA DE ENTRADA ---
    prompt = st.chat_input(f"Ask {NOMBRE_IA}...")

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

    if st.session_state.audio_pendiente:
        autoplay_audio(st.session_state.audio_pendiente)
        st.session_state.audio_pendiente = None

except KeyError:
    st.warning("⚠️ Falta la API Key de Groq.")
