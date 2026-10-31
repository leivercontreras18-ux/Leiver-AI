import streamlit as st
import time
import io
import asyncio
import edge_tts
import base64
from groq import Groq

# --- CONFIGURACIÓN DE LA PÁGINA ---
NOMBRE_IA = "Nova"
VOZ_FIJA = "es-MX-DaliaNeural"

st.set_page_config(page_title=NOMBRE_IA, page_icon="🌌", layout="wide")

# --- CSS AVANZADO (RESPONSIVE Y ADAPTABLE) ---
st.markdown("""
<style>
    /* 1. FONDO Y GLOWS */
    .stApp {
        background-color: #121214 !important;
    }
    
    .glow-1 { position: fixed; top: 25%; left: 25%; width: 384px; height: 384px; border-radius: 50%; background: rgba(88, 28, 135, 0.2); filter: blur(120px); pointer-events: none; z-index: 0; }
    .glow-2 { position: fixed; bottom: 33%; right: 25%; width: 400px; height: 400px; border-radius: 50%; background: rgba(131, 24, 67, 0.1); filter: blur(150px); pointer-events: none; z-index: 0; }
    .glow-3 { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 320px; height: 320px; border-radius: 50%; background: rgba(49, 46, 129, 0.2); filter: blur(100px); pointer-events: none; z-index: 0; }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }

    /* 2. BLOQUEO DEL SCROLL GLOBAL Y ESTRUCTURA PRINCIPAL */
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 0 !important;
        max-width: 95% !important; 
        height: 100vh !important; 
        overflow: hidden !important; /* Evita que toda la página haga scroll */
    }

    /* 3. EL ORBE (Animación fluida) */
    @keyframes blob {
        0%, 100% { border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%; transform: scale(1); }
        33% { border-radius: 70% 30% 52% 48% / 60% 40% 60% 40%; transform: scale(1.03) rotate(4deg); }
        66% { border-radius: 28% 72% 35% 65% / 40% 60% 30% 70%; transform: scale(0.97) rotate(-4deg); }
    }

    .orb-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 300px;
        height: 300px;
        margin: 0 auto;
    }

    .orb-glow {
        position: absolute;
        width: 300px; height: 300px;
        border-radius: 50%;
        background: linear-gradient(to top right, rgba(168, 85, 247, 0.4), rgba(99, 102, 241, 0.2), rgba(236, 72, 153, 0.4));
        filter: blur(60px);
        animation: pulse 3s infinite alternate;
    }

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

    .orb-inner {
        position: absolute; inset: 0;
        background: linear-gradient(to bottom left, rgba(236, 72, 153, 0.2), transparent, rgba(147, 51, 234, 0.3));
        mix-blend-mode: overlay;
        animation: spin 12s infinite linear;
    }

    @keyframes pulse { 0% { opacity: 0.6; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1.1); } }
    @keyframes spin { 100% { transform: rotate(360deg); } }

    .nova-title {
        font-size: 36px;
        font-weight: 200;
        letter-spacing: 0.2em;
        background: linear-gradient(to right, #e9d5ff, #f1f5f9, #fbcfe8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 20px;
        margin-bottom: 0;
        text-align: center;
    }
    .nova-subtitle {
        font-size: 14px;
        color: rgba(233, 213, 255, 0.6);
        text-align: center;
        margin-top: 5px;
    }

    /* 4. EL CHAT (Caja de cristal con altura adaptable) */
    /* Usamos calc() para que el chat ocupe el alto de la pantalla menos 180px (espacio para la barra) */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(div[data-testid="stChatMessage"]) {
        height: calc(100vh - 180px) !important; 
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(24px) !important;
        border-radius: 24px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
        padding: 20px !important;
    }

    /* Ocultar bordes y fondos feos de Streamlit dentro del contenedor */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        border: none !important;
        background: transparent !important;
    }

    /* Ocultar avatares por defecto */
    div[data-testid="stChatMessageAvatarUser"],
    div[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
    div[data-testid="stChatMessage"] button { display: none !important; }

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

    /* 5. BARRA DE TEXTO (Flotante y centrada) */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        padding-bottom: 1.5rem !important;
        max-width: 800px !important; 
        margin: 0 auto !important; 
    }
    
    .stChatInput {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(168, 85, 247, 0.3) !important;
        border-radius: 30px !important;
        backdrop-filter: blur(24px) !important;
        box-shadow: 0 0 20px rgba(168, 85, 247, 0.1) !important;
        transition: all 0.3s ease !important;
    }
    
    .stChatInput:focus-within {
        border: 1px solid rgba(168, 85, 247, 0.6) !important;
        box-shadow: 0 0 25px rgba(168, 85, 247, 0.25) !important;
    }

    /* Ocultar audio nativo */
    audio, div[data-testid="stAudio"] { display: none !important; }

    /* Personalizar Sidebar */
    [data-testid="stSidebar"] { background-color: #1a1a1e !important; }
</style>
""", unsafe_allow_html=True)

# --- INYECTAR GLOWS DE FONDO ---
st.markdown('<div class="glow-1"></div><div class="glow-2"></div><div class="glow-3"></div>', unsafe_allow_html=True)

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

# --- ESTADO DE LA SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "audio_pendiente" not in st.session_state:
    st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state:
    st.session_state.mic_key = 0

# --- SIDEBAR (Panel Izquierdo) ---
with st.sidebar:
    st.title("⚙️ System")
    voz_activa = st.checkbox("🔊 Voz activa", value=True)
    
    st.subheader("🎤 Hablar")
    audio_grabado = st.audio_input("Graba tu mensaje", key=f"mic_{st.session_state.mic_key}", label_visibility="collapsed")
    
    st.subheader("📁 Código")
    uploaded_file = st.file_uploader("Upload", type=["py", "txt", "json", "js"], label_visibility="collapsed")
    codigo_actual = uploaded_file.read().decode("utf-8") if uploaded_file else ""
    if uploaded_file:
        st.success(f"Cargado: {uploaded_file.name}")
        
    st.markdown("---")
    if st.button("🗑️ Limpiar Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.mic_key += 1
        st.rerun()

# --- CONEXIÓN CON GROQ ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("Error: Falta la API Key de Groq en los Secrets de Streamlit.")
    st.stop()

cliente = Groq(api_key=st.secrets["GROQ_API_KEY"])
instrucciones = f"Eres {NOMBRE_IA}, una IA avanzada, elegante y servicial. Responde de forma concisa y clara."

# --- LAYOUT PRINCIPAL (Dos Columnas) ---
col_izq, col_der = st.columns([1, 1], gap="large")

# Columna Izquierda: El Orbe
with col_izq:
    st.markdown(f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%;">
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

# Columna Derecha: El Chat
with col_der:
    # st.container genera un contenedor con scroll interno automático
    with st.container(border=True, height=int(100)): # El CSS se encarga de la altura real
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

# --- PROCESAMIENTO DE ENTRADA ---
prompt = st.chat_input(f"Ask {NOMBRE_IA}...")

if audio_grabado or prompt:
    texto_usuario = prompt if prompt else ""
    
    # 1. Procesar audio (si se envió voz)
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
                
    # 2. Procesar texto y generar respuesta
    if texto_usuario:
        st.session_state.messages.append({"role": "user", "content": texto_usuario})
        
        contexto_ia = f"Código:\n```python\n{codigo_actual}\n```\nPetición: {texto_usuario}" if codigo_actual else texto_usuario

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
            
            # Generar voz de salida
            if voz_activa: 
                try:
                    audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, VOZ_FIJA))
                    st.session_state.audio_pendiente = audio_buffer
                except Exception:
                    pass
            
            # Recargar para mostrar mensaje y reproducir audio
            st.session_state.mic_key += 1
            st.rerun()
            
        except Exception as e:
            st.error(f"Error de Groq: {e}")

# --- REPRODUCIR AUDIO PENDIENTE (Al final para evitar bloqueos) ---
if st.session_state.audio_pendiente:
    autoplay_audio(st.session_state.audio_pendiente)
    st.session_state.audio_pendiente = None
