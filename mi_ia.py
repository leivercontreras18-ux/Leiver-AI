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

# --- CSS AVANZADO ---
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at 50% 50%, #0d1117 0%, #000000 100%);
        color: #e0e0e0;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }

    /* CONTENEDOR DEL ORBE */
    .orb-container {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 70vh;
        position: relative;
    }
    
    .orb {
        width: 260px;
        height: 260px;
        border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #00f2fe 0%, #4facfe 40%, #ff0844 80%, transparent 100%);
        box-shadow: 0 0 60px #00f2fe, 0 0 120px #ff0844, inset 0 0 40px #ffffff;
        animation: pulse 2s infinite alternate ease-in-out, rotate 8s linear infinite;
        filter: blur(3px);
    }

    @keyframes pulse {
        0% { transform: scale(0.92); opacity: 0.8; }
        100% { transform: scale(1.08); opacity: 1; }
    }
    
    @keyframes rotate {
        0% { filter: hue-rotate(0deg) blur(3px); }
        100% { filter: hue-rotate(360deg) blur(3px); }
    }

    .orb-ring {
        position: absolute;
        width: 360px;
        height: 360px;
        border-radius: 50%;
        border: 2px solid rgba(0, 242, 254, 0.2);
        animation: spin 15s linear infinite;
    }
    .orb-ring-2 {
        position: absolute;
        width: 420px;
        height: 420px;
        border-radius: 50%;
        border: 1px dashed rgba(255, 8, 68, 0.2);
        animation: spin 25s linear infinite reverse;
    }

    @keyframes spin { 100% { transform: rotate(360deg); } }

    /* CHAT ESTILO CRISTAL */
    div[data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 15px !important;
        padding: 15px !important;
        margin-bottom: 15px !important;
    }

    /* BARRA DE TEXTO */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        padding-bottom: 2rem !important;
    }
    .stChatInput {
        background: rgba(20, 25, 35, 0.7) !important;
        backdrop-filter: blur(15px) !important;
        border: 1px solid #00f2fe !important;
        border-radius: 30px !important;
    }

    /* Ocultar cualquier reproductor nativo de audio */
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
    instrucciones = f"Eres {NOMBRE_IA}, un asistente experto. Responde de forma directa y concisa. No des listas infinitas a menos que sea estrictamente necesario."

    # --- LAYOUT PRINCIPAL ---
    col_izq, col_der = st.columns([1.2, 1])

    with col_izq:
        st.markdown("""
            <div class="orb-container">
                <div class="orb-ring"></div>
                <div class="orb-ring-2"></div>
                <div class="orb"></div>
                <div style="text-align: center; margin-top: 30px; z-index: 10;">
                    <h2 style="color: #00f2fe; letter-spacing: 5px; text-shadow: 0 0 10px #00f2fe;">NOVA</h2>
                    <p style="color: gray;">SISTEMAS OPERATIVOS</p>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col_der:
        st.markdown("<h3 style='color: #00f2fe; margin-bottom: 20px;'>Registro de Misión</h3>", unsafe_allow_html=True)
        
        # CONTENEDOR CON SCROLL PARA EL CHAT
        chat_container = st.container(height=550)
        with chat_container:
            for message in st.session_state.messages:
                avatar = "👤" if message["role"] == "user" else "🤖"
                with st.chat_message(message["role"], avatar=avatar):
                    st.markdown(message["content"])

    # --- LÓGICA DE ENTRADA ---
    prompt = st.chat_input(f"Habla con {NOMBRE_IA}...")

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
                        # Guardamos el audio en el estado de la sesión
                        audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, VOZ_FIJA))
                        st.session_state.audio_pendiente = audio_buffer
                    except Exception:
                        pass
                
                # Recargamos para que se dibuje el chat. El audio se reproducirá al final.
                st.session_state.mic_key += 1
                st.rerun()
                
            except Exception as e:
                st.error(f"Error de Groq: {e}")

    # --- REPRODUCCIÓN DEL AUDIO PENDIENTE (SE EJECUTA AL FINAL DE LA CARGA) ---
    if st.session_state.audio_pendiente:
        autoplay_audio(st.session_state.audio_pendiente)
        st.session_state.audio_pendiente = None # Limpiamos para que no se repita

except KeyError:
    st.warning("⚠️ Falta la API Key de Groq.")
