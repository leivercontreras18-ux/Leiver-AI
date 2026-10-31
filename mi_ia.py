import streamlit as st
import time
import io
import asyncio
import edge_tts
import base64
import streamlit.components.v1 as components
from groq import Groq

# --- ¡AQUÍ PONES EL NOMBRE DE TU IA! ---
NOMBRE_IA = "Nova"
VOZ_FIJA = "es-MX-DaliaNeural" # Voz única en español latino

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title=NOMBRE_IA, page_icon="🤖", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }
    .stApp { background-color: #1a1a1a !important; color: #ececec !important; }
    [data-testid="stSidebar"] { background-color: #121212 !important; border-right: 1px solid #333 !important; }
    .block-container { max-width: 800px !important; padding-top: 2rem !important; padding-bottom: 100px !important; }
    
    /* ESTILO DE LOS MENSAJES (CHAT) */
    div[data-testid="stChatMessage"] { background-color: transparent !important; border: none !important; padding: 0 !important; display: flex !important; margin-bottom: 15px !important; }
    
    /* Mensajes del Usuario (Derecha) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse !important; justify-content: flex-start !important; margin-left: auto !important; width: fit-content !important; max-width: 80% !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] { background-color: #2f2f2f !important; border-radius: 15px 15px 0 15px !important; padding: 10px 15px !important; text-align: right !important; color: white !important; }
    
    /* Mensajes de Nova (Izquierda) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) { flex-direction: row !important; justify-content: flex-start !important; margin-right: auto !important; width: fit-content !important; max-width: 80% !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] { background-color: transparent !important; padding: 10px 15px !important; text-align: left !important; }
    
    /* Ocultar cualquier reproductor de audio nativo */
    div[data-testid="stAudio"] { display: none !important; }
    
    [data-testid="stBottomBlockContainer"] { background-color: #1a1a1a !important; padding-bottom: 1.5rem !important; }
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

# --- FUNCIÓN PARA REPRODUCIR AUDIO (FORZADO) ---
def autoplay_audio(audio_buffer, format="audio/mp3"):
    audio_bytes = audio_buffer.read()
    b64 = base64.b64encode(audio_bytes).decode()
    # Usamos un iframe invisible con JavaScript para forzar al navegador a reproducir
    audio_html = f"""
        <audio id="nova-voice" autoplay>
            <source src="data:{format};base64,{b64}" type="{format}">
        </audio>
        <script>
            var audio = document.getElementById("nova-voice");
            var playPromise = audio.play();
            if (playPromise !== undefined) {{
                playPromise.catch(error => {{
                    // Si se bloquea, intentamos de nuevo tras un mini retraso
                    setTimeout(() => {{ audio.play(); }}, 500);
                }});
            }}
        </script>
    """
    components.html(audio_html, height=0, width=0)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title(f"🤖 {NOMBRE_IA}")
    st.caption("Powered by Groq ⚡")
    st.divider()
    
    st.subheader("⚙️ Configuración")
    activar_voz = st.checkbox("🔊 Hablar respuestas en voz alta", value=True)
    
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

# --- CONFIGURACIÓN DEL CEREBRO (GROQ) ---
try:
    api_key = st.secrets["GROQ_API_KEY"]
    cliente = Groq(api_key=api_key)
    
    instrucciones = f"Eres {NOMBRE_IA}, un asistente experto, elegante, amable y directo. Siempre respondes en español de forma clara."

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- ÁREA PRINCIPAL DEL CHAT ---
    if not st.session_state.messages:
        st.markdown(f"<h2 style='text-align: center; margin-top: 20vh; color: #ececec;'>¿En qué puedo ayudarte hoy?</h2>", unsafe_allow_html=True)
    
    for message in st.session_state.messages:
        avatar = "👤" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # --- ZONA DE ENTRADA ---
    prompt = st.chat_input(f"Escribe tu mensaje para {NOMBRE_IA}...")

    # --- LÓGICA DE PROCESAMIENTO ---
    if prompt:
        texto_usuario = prompt
        
        with st.chat_message("user", avatar="👤"):
            st.markdown(texto_usuario)
        
        st.session_state.messages.append({"role": "user", "content": texto_usuario})

        contexto_ia = texto_usuario
        if codigo_actual:
            contexto_ia = f"Te adjunto el código actual del archivo:\n\n```python\n{codigo_actual}\n```\n\nMi petición es: {texto_usuario}\n\nPor favor, devuélveme el código completo modificado dentro de un bloque de código."

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Pensando..."):
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
                    st.markdown(texto_respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": texto_respuesta})
                    
                    # Reproducir voz de Nova
                    if activar_voz: 
                        try:
                            audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, VOZ_FIJA))
                            autoplay_audio(audio_buffer, format="audio/mp3")
                        except Exception as e:
                            st.warning(f"No se pudo generar la voz: {e}")
                    
                except Exception as e:
                    st.error(f"Error de Groq: {e}")
        
        if prompt:
            st.rerun()

except KeyError:
    st.warning("⚠️ Falta la API Key de Groq. Configúrala en los Secrets de Streamlit.")
