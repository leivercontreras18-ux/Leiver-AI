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

# --- CSS AVANZADO (LAYOUT PERFECTO Y FIJO) ---
st.markdown("""
<style>
    /* 1. RESET Y BLOQUEO DEL SCROLL GLOBAL */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        height: 100vh !important;
        overflow: hidden !important;
        background-color: #121214 !important;
    }
    
    /* Ocultar menús y footers */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 2. CONTENEDOR PRINCIPAL CENTRADO */
    .block-container { 
        padding-top: 0 !important; 
        padding-bottom: 0 !important;
        max-width: 1200px !important; 
        margin: 0 auto !important;
        height: 100vh !important;
        display: flex !important;
        align-items: center !important; /* Centra verticalmente */
        justify-content: center !important;
    }

    /* Fondo con Glows */
    .stApp::before {
        content: "";
        position: fixed; inset: 0;
        background: 
            radial-gradient(circle at 30% 30%, rgba(88, 28, 135, 0.15), transparent 40%),
            radial-gradient(circle at 70% 70%, rgba(131, 24, 67, 0.1), transparent 40%),
            radial-gradient(circle at 50% 50%, rgba(49, 46, 129, 0.15), transparent 50%);
        pointer-events: none;
        z-index: 0;
    }

    /* 3. EL ORBE (Perfectamente centrado) */
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
        width: 100%;
        height: 100%;
    }

    .orb-wrapper {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 300px;
        height: 300px;
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
        width: 260px; height: 260px;
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
        letter-spacing: 0.05em;
        text-align: center;
        margin-top: 5px;
    }

    /* 4. EL PANEL DE CHAT (Altura calculada) */
    .chat-panel {
        height: 75vh; /* Ocupa el 75% de la pantalla */
        max-height: 800px;
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(24px) !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
        border-radius: 24px !important;
        padding: 20px !important;
        display: flex;
        flex-direction: column;
    }
    
    /* Área con scroll interno */
    .chat-scroll {
        flex: 1;
        overflow-y: auto !important;
        padding-right: 10px;
    }
    
    /* Scrollbar personalizada */
    .chat-scroll::-webkit-scrollbar { width: 6px; }
    .chat-scroll::-webkit-scrollbar-thumb { background: rgba(168, 85, 247, 0.3); border-radius: 10px; }
    .chat-scroll::-webkit-scrollbar-track { background: transparent; }

    /* Ocultar avatares y botones de Streamlit */
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

    /* 5. BARRA DE ENTRADA FLOATING */
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
    }
    
    .stChatInput:focus-within {
        border: 1px solid rgba(168, 85, 247, 0.6) !important;
        box-shadow: 0 0 25px rgba(168, 85, 247, 0.25) !important;
    }

    /* Ocultar reproductores de audio */
    audio, div[data-testid="stAudio"] { display: none !important; }

    /* Personalizar Sidebar */
    [data-testid="stSidebar"] { background-color: #1a1a1e !important; }
</style>
""", unsafe_allow_html=True)

# --- PROCESADORES DE AUDIO ---
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

# --- ESTADO DE SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "audio_pendiente" not in st.session_state:
    st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state:
    st.session_state.mic_key = 0

# --- SIDEBAR ---
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
    if st.button("🗑️ Limpiar Chat"):
        st.session_state.messages = []
        st.session_state.mic_key += 1
        st.rerun()

# --- CONEXIÓN CON GROQ ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("Error: Falta la API Key de Groq en los Secrets.")
    st.stop()

cliente = Groq(api_key=st.secrets["GROQ_API_KEY"])
instrucciones = f"Eres {NOMBRE_IA}, una IA avanzada, elegante y servicial. Responde de forma concisa."

# --- GRID PRINCIPAL (2 Columnas Centradas) ---
col_izq, col_der = st.columns([1.2, 1], gap="large")

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

with col_der:
    # Contenedor del panel de chat
    st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
    st.markdown('<div class="chat-scroll">', unsafe_allow_html=True)
    
    # Mensajes
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- ENTRADA DE TEXTO ---
prompt = st.chat_input(f"Ask {NOMBRE_IA}...")

# --- LÓGICA DE PROCESAMIENTO ---
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
            
            if voz_activa: 
                try:
                    audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, VOZ_FIJA))
                    st.session_state.audio_pendiente = audio_buffer
                except Exception:
                    pass
            
            st.session_state.mic_key += 1
            st.rerun()
            
        except Exception as e:
            st.error(f"Error de Groq: {e}")

# --- REPRODUCIR AUDIO PENDIENTE ---
if st.session_state.audio_pendiente:
    autoplay_audio(st.session_state.audio_pendiente)
    st.session_state.audio_pendiente = None
