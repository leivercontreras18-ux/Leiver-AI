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

# --- CSS AVANZADO (DISEÑO ETHEREAL / FIJO) ---
st.markdown("""
<style>
    /* 1. BLOQUEAR EL SCROLL DE LA PÁGINA */
    html, body, .stApp {
        height: 100vh !important;
        overflow: hidden !important; 
        background-color: #0b0b12;
        background-image: radial-gradient(circle at 50% 50%, #1a1a2e 0%, #0b0b12 100%);
        color: #e0e0e0;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }
    
    /* Ajustar layout principal */
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 0rem !important;
        max-width: 95% !important; 
        height: 90vh !important;
    }

    /* 2. EL ORBE PERFECTO (Flotante y Suave) */
    .orb-container {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100%;
    }
    
    .fluid-orb {
        width: 300px;
        height: 300px;
        border-radius: 50%; /* Redondo perfecto */
        background: linear-gradient(135deg, #fbcfe8 0%, #d8b4fe 50%, #bfdbfe 100%);
        filter: blur(8px); /* Efecto difuminado */
        animation: float 6s ease-in-out infinite;
        box-shadow: 0 0 80px rgba(216, 180, 254, 0.4), inset 0 0 40px rgba(255,255,255,0.5);
    }

    @keyframes float {
        0% { transform: translateY(0px) scale(1); }
        50% { transform: translateY(-15px) scale(1.03); }
        100% { transform: translateY(0px) scale(1); }
    }

    .title-container {
        text-align: center;
        margin-top: 30px;
    }
    .title-container h1 {
        color: #ffffff;
        font-weight: 300;
        letter-spacing: 3px;
        margin-bottom: 0px;
    }
    .title-container p {
        color: #7dd3fc;
        font-size: 14px;
        margin-top: 5px;
    }

    /* 3. EL PANEL DE CHAT (Fijo con su propio scroll) */
    .chat-wrapper {
        height: 80vh; /* Ocupa el 80% de la pantalla */
        display: flex;
        flex-direction: column;
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    
    /* Contenedor interno para que solo el texto haga scroll */
    .chat-messages {
        flex-grow: 1;
        overflow-y: auto;
        padding-right: 10px;
    }

    /* Burbujas del Chat */
    div[data-testid="stChatMessageAvatarUser"], div[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
    div[data-testid="stChatMessage"] { background: transparent !important; padding: 0 !important; }

    /* Usuario (Morado) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background-color: #e9d5ff !important; 
        border-radius: 20px 20px 0 20px !important;
        margin-left: auto !important;
        width: fit-content !important;
        max-width: 85% !important;
        padding: 12px 18px !important;
        margin-bottom: 15px !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) p { color: #1a1a1a !important; margin: 0; }

    /* Nova (Rosa) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        background-color: #fbcfe8 !important;
        border-radius: 20px 20px 20px 0 !important;
        margin-right: auto !important;
        width: fit-content !important;
        max-width: 85% !important;
        padding: 12px 18px !important;
        margin-bottom: 15px !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) p { color: #1a1a1a !important; margin: 0; }

    /* 4. BARRA DE TEXTO ANCLADA AL FONDO */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        padding: 0 !important;
        position: fixed;
        bottom: 20px;
        right: 2.5%;
        width: 45%;
    }
    .stChatInput {
        background: rgba(20, 20, 30, 0.9) !important;
        border: 2px solid #a855f7 !important;
        border-radius: 30px !important;
        box-shadow: 0 0 20px rgba(168, 85, 247, 0.3) !important;
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
    col_izq, col_der = st.columns([1, 1])

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
        st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
        
        # Contenedor de mensajes con scroll propio
        st.markdown('<div class="chat-messages">', unsafe_allow_html=True)
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Espacio extra para que el último mensaje no quede tapado por la barra de texto
        st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

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
