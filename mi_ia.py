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

# --- CSS AVANZADO (EL ALMA DE LA INTERFAZ SCI-FI) ---
st.markdown("""
<style>
    /* Fondo espacial profundo */
    .stApp {
        background: radial-gradient(circle at 50% 50%, #0d1117 0%, #000000 100%);
        color: #e0e0e0;
    }
    
    /* Ocultar barras por defecto */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }

    /* -----------------------------------------
       EL NÚCLEO (ORBE CENTRAL)
       ----------------------------------------- */
    .orb-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 60vh;
        position: relative;
    }
    
    .orb {
        width: 250px;
        height: 250px;
        border-radius: 50%;
        background: radial-gradient(circle, #00f2fe 0%, #4facfe 30%, #ff0844 80%, transparent 100%);
        box-shadow: 0 0 60px #00f2fe, 0 0 120px #ff0844, inset 0 0 50px #ffffff;
        animation: pulse 2s infinite alternate, rotate 10s linear infinite;
        filter: blur(4px);
    }

    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.8; }
        100% { transform: scale(1.05); opacity: 1; }
    }
    
    @keyframes rotate {
        0% { filter: hue-rotate(0deg); }
        100% { filter: hue-rotate(360deg); }
    }

    /* Anillos orbitales */
    .orb-ring {
        position: absolute;
        width: 350px;
        height: 350px;
        border-radius: 50%;
        border: 2px solid rgba(0, 242, 254, 0.3);
        animation: spin 15s linear infinite;
    }
    .orb-ring-2 {
        position: absolute;
        width: 400px;
        height: 400px;
        border-radius: 50%;
        border: 1px dashed rgba(255, 8, 68, 0.3);
        animation: spin 25s linear infinite reverse;
    }

    @keyframes spin {
        100% { transform: rotate(360deg); }
    }

    /* -----------------------------------------
       EL CHAT (PANELES FLOTANTES A LA DERECHA)
       ----------------------------------------- */
    div[data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.03) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 15px !important;
        padding: 15px !important;
        margin-bottom: 15px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
    }

    /* -----------------------------------------
       LA BARRA DE TEXTO DE CRISTAL
       ----------------------------------------- */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        padding-bottom: 2rem !important;
    }
    .stChatInput {
        background: rgba(20, 25, 35, 0.7) !important;
        backdrop-filter: blur(15px) !important;
        border: 1px solid #00f2fe !important;
        border-radius: 30px !important;
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.2) !important;
    }

    /* Ocultar reproductor de audio nativo */
    audio { display: none !important; }
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

# --- BARRA LATERAL (MINIMALISTA) ---
with st.sidebar:
    st.markdown(f"### 🌌 {NOMBRE_IA} System")
    st.divider()
    activar_voz = st.checkbox("🔊 Voz activa", value=True)
    audio_grabado = st.audio_input("🎤 Hablar")
    archivo_subido = st.file_uploader("📂 Código")
    codigo_actual = archivo_subido.read().decode("utf-8") if archivo_subido else ""
    if st.button("🗑️ Reiniciar Sistema"):
        st.session_state.messages = []
        st.rerun()

# --- CONFIGURACIÓN DEL CEREBRO ---
try:
    api_key = st.secrets["GROQ_API_KEY"]
    cliente = Groq(api_key=api_key)
    instrucciones = f"Eres {NOMBRE_IA}, un asistente experto, elegante, amable y directo. Siempre respondes en español de forma clara."

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- LAYOUT PRINCIPAL: ORBE A LA IZQUIERDA, CHAT A LA DERECHA ---
    col_izq, col_der = st.columns([1.5, 1])

    with col_izq:
        # Aquí dibujamos el Orbe con HTML puro
        st.markdown("""
            <div class="orb-container">
                <div class="orb-ring"></div>
                <div class="orb-ring-2"></div>
                <div class="orb"></div>
            </div>
            <div style="text-align: center; margin-top: -50px;">
                <h2 style="color: #00f2fe; letter-spacing: 5px;">NOVA</h2>
                <p style="color: gray;">SISTEMAS OPERATIVOS</p>
            </div>
        """, unsafe_allow_html=True)

    with col_der:
        # Aquí va el historial de chat
        st.markdown("<h3 style='color: #00f2fe; margin-bottom: 20px;'>Registro de Misión</h3>", unsafe_allow_html=True)
        
        chat_container = st.container(height=500) # Altura fija para que no empuje el orbe
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

            # Generar respuesta
            try:
                respuesta = cliente.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": instrucciones},
                        {"role": "user", "content": contexto_ia}
                    ],
                    temperature=0.7,
                    max_tokens=4096
                )
                
                texto_respuesta = respuesta.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": texto_respuesta})
                
                if activar_voz: 
                    try:
                        audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, VOZ_FIJA))
                        autoplay_audio(audio_buffer)
                    except Exception as e:
                        pass # Silencioso para no romper la ilusión visual
                
                # Recargamos para mostrar el nuevo mensaje en el chat
                st.rerun()
                
            except Exception as e:
                st.error(f"Error de Groq: {e}")

except KeyError:
    st.warning("⚠️ Falta la API Key de Groq.")
