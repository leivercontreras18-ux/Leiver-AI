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

# --- CSS AVANZADO (RÉPLICA EXACTA DEL DISEÑO REACT/TAILWIND) ---
st.markdown("""
<style>
    /* 1. FONDO OSCURO Y GLOWS DE NEBULOSA (React: bg-[#121214]) */
    .stApp {
        background-color: #121214 !important;
        color: #e2e8f0;
        overflow: hidden !important; 
    }
    
    /* Los resplandores de fondo (Glows) */
    .glow-1 { position: fixed; top: 25%; left: 25%; width: 384px; height: 384px; border-radius: 50%; background: rgba(88, 28, 135, 0.2); filter: blur(120px); pointer-events: none; z-index: -1; }
    .glow-2 { position: fixed; bottom: 33%; right: 25%; width: 400px; height: 400px; border-radius: 50%; background: rgba(131, 24, 67, 0.1); filter: blur(150px); pointer-events: none; z-index: -1; }
    .glow-3 { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 320px; height: 320px; border-radius: 50%; background: rgba(49, 46, 129, 0.2); filter: blur(100px); pointer-events: none; z-index: -1; }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }
    
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 0 !important;
        max-width: 95% !important; 
        height: 100vh !important;
    }

    /* 2. EL ORBE (Animación exacta) */
    @keyframes blob {
        0%, 100% { border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%; transform: scale(1); }
        33% { border-radius: 70% 30% 52% 48% / 60% 40% 60% 40%; transform: scale(1.03) rotate(4deg); }
        66% { border-radius: 28% 72% 35% 65% / 40% 60% 30% 70%; transform: scale(0.97) rotate(-4deg); }
    }

    .orb-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 70vh;
    }

    .orb-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 300px;
        height: 300px;
    }

    /* Brillo exterior del orbe */
    .orb-glow {
        position: absolute;
        width: 300px; height: 300px;
        border-radius: 50%;
        background: linear-gradient(to top right, rgba(168, 85, 247, 0.3), rgba(99, 102, 241, 0.2), rgba(236, 72, 153, 0.3));
        filter: blur(60px);
        animation: pulse 3s infinite alternate;
    }

    /* Cuerpo del orbe con gradientes */
    .orb-body {
        width: 256px; height: 256px;
        background: linear-gradient(to right, rgba(192, 132, 252, 0.4), rgba(249, 168, 212, 0.5), rgba(129, 140, 248, 0.4));
        backdrop-filter: blur(12px);
        box-shadow: inset 0 0 40px rgba(255, 255, 255, 0.2);
        animation: blob 8s infinite ease-in-out;
        border: 1px solid rgba(255, 255, 255, 0.2);
        position: relative;
        overflow: hidden;
    }

    /* Capa interior giratoria */
    .orb-inner {
        position: absolute; inset: 0;
        background: linear-gradient(to bottom left, rgba(236, 72, 153, 0.2), transparent, rgba(147, 51, 234, 0.3));
        mix-blend-mode: overlay;
        animation: spin 12s infinite linear;
    }

    @keyframes pulse { 0% { opacity: 0.6; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1.1); } }
    @keyframes spin { 100% { transform: rotate(360deg); } }

    /* Textos NOVA */
    .nova-title {
        font-size: 36px;
        font-weight: 200;
        letter-spacing: 0.2em;
        background: linear-gradient(to right, #e9d5ff, #f1f5f9, #fbcfe8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 30px;
        margin-bottom: 0;
        text-align: center;
    }
    .nova-subtitle {
        font-size: 14px;
        color: rgba(233, 213, 255, 0.6);
        letter-spacing: 0.05em;
        text-align: center;
        margin-top: 5px;
    }

    /* 3. EL PANEL DE CHAT (Glassmorphism) */
    .chat-panel {
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(24px) !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
        border-radius: 24px;
        height: 75vh;
        padding: 20px;
        overflow-y: auto !important;
        display: flex;
        flex-direction: column;
    }

    .chat-header {
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        font-size: 14px;
        color: #cbd5e1;
        font-weight: 500;
        letter-spacing: 0.05em;
        margin-bottom: 15px;
    }

    /* Ocultar avatares de Streamlit */
    div[data-testid="stChatMessageAvatarUser"],
    div[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }

    /* Burbuja del Usuario */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: rgba(147, 51, 234, 0.1) !important;
        border: 1px solid rgba(168, 85, 247, 0.2) !important;
        color: #f3e8ff !important;
        border-radius: 16px 16px 0 16px !important;
        margin-left: auto !important;
        width: fit-content !important;
        max-width: 85% !important;
        padding: 12px 16px !important;
        margin-bottom: 15px !important;
    }

    /* Burbuja de Nova */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        color: rgba(252, 231, 243, 0.9) !important;
        border-radius: 16px 16px 16px 0 !important;
        margin-right: auto !important;
        width: fit-content !important;
        max-width: 85% !important;
        padding: 12px 16px !important;
        margin-bottom: 15px !important;
    }

    /* 4. BARRA DE TEXTO (Píldora Flotante) */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        position: fixed !important;
        bottom: 25px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 100% !important;
        max-width: 600px !important;
        padding: 0 !important;
        z-index: 1000;
    }
    
    .stChatInput {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(168, 85, 247, 0.3) !important;
        border-radius: 30px !important;
        backdrop-filter: blur(24px) !important;
        box-shadow: 0 0 20px rgba(168, 85, 247, 0.1) !important;
        transition: all 0.3s ease !important;
        overflow: hidden !important;
    }
    
    .stChatInput:focus-within {
        border: 1px solid rgba(168, 85, 247, 0.6) !important;
        box-shadow: 0 0 25px rgba(168, 85, 247, 0.25) !important;
    }

    /* Ocultar audio nativo */
    audio { display: none !important; }
    div[data-testid="stAudio"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- INYECTAR GLOWS DE FONDO ---
st.markdown("""
    <div class="glow-1"></div>
    <div class="glow-2"></div>
    <div class="glow-3"></div>
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
if "audio_pendiente" not in st.session_state:
    st.session_state.audio_pendiente = None

# --- CONTROL DE LLAVE DE SEGURIDAD (Groq) ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("Error: Falta la credencial `GROQ_API_KEY` en los secretos de tu entorno de Streamlit.")
    st.stop()

# --- INSTANCIAR CLIENTE ---
api_key = st.secrets["GROQ_API_KEY"]
cliente = Groq(api_key=api_key)
instrucciones = f"Eres {NOMBRE_IA}, una inteligencia artificial avanzada, con una personalidad sumamente elegante, sofisticada y servicial. Responde siempre de forma clara y muy concisa."

# --- LAYOUT PRINCIPAL EN COLUMNAS ---
col_izq, col_der = st.columns([1, 1], gap="large")

# COLUMNA IZQUIERDA: Orbe Holográfico Animado
with col_izq:
    st.markdown(f"""
    <div class="orb-container">
        <div class="orb-wrapper">
            <div class="orb-glow"></div>
            <div class="orb-body">
                <div class="orb-inner"></div>
            </div>
        </div>
        <div class="nova-title">{NOMBRE_IA.upper()}</div>
        <div class="nova-subtitle">How can I help you today?</div>
    </div>
    """, unsafe_allow_html=True)

# COLUMNA DERECHA: Registro de Chat Estilo Cristal
with col_der:
    st.markdown('<div class="chat-header">Conversación Activa</div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        st.markdown('</div>', unsafe_allow_html=True)

# --- BARRA DE ENTRADA DE TEXTO ---
prompt = st.chat_input("Ask Nova...")

if prompt:
    # 1. Registrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Preparar el contexto histórico para Groq
    mensajes_api = [{"role": "system", "content": instrucciones}]
