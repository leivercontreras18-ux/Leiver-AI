import streamlit as st
import google.generativeai as genai
import time
import re
import io
import asyncio
import edge_tts
import base64

# --- ¡AQUÍ PONES EL NOMBRE DE TU IA! ---
NOMBRE_IA = "Nova"

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title=NOMBRE_IA, page_icon="🤖", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header { background: transparent !important; }

    /* Fondo oscuro sólido */
    .stApp {
        background-color: #1a1a1a !important;
        color: #ececec !important;
    }

    /* Barra lateral */
    [data-testid="stSidebar"] {
        background-color: #121212 !important;
        border-right: 1px solid #333 !important;
    }

    /* Centrar el chat */
    .block-container {
        max-width: 800px !important;
        padding-top: 2rem !important;
        padding-bottom: 100px !important;
    }

    /* =========================================
       ESTILO DE LOS MENSAJES (CHAT)
       ========================================= */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        display: flex !important;
        margin-bottom: 15px !important;
    }

    /* Para TUS mensajes (Usuario) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse !important; 
        justify-content: flex-start !important; 
        margin-left: auto !important;
        width: fit-content !important;
        max-width: 80% !important;
    }
    
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] {
        background-color: #2f2f2f !important;
        border-radius: 15px 15px 0 15px !important; 
        padding: 10px 15px !important;
        text-align: right !important;
        color: white !important;
    }

    /* Para los mensajes de NOVA (IA) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        flex-direction: row !important; 
        justify-content: flex-start !important;
        margin-right: auto !important;
        width: fit-content !important;
        max-width: 80% !important;
    }

    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] {
        background-color: transparent !important;
        padding: 10px 15px !important;
        text-align: left !important;
    }

    /* Fijar la caja de texto abajo */
    [data-testid="stBottomBlockContainer"] {
        background-color: #1a1a1a !important;
        padding-bottom: 1.5rem !important;
    }
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

# --- FUNCIÓN PARA REPRODUCIR AUDIO ---
def autoplay_audio(audio_buffer, format="audio/mp3"):
    audio_bytes = audio_buffer.read()
    b64 = base64.b64encode(audio_bytes).decode()
    md = f"""
        <audio autoplay="true" hidden="true">
        <source src="data:{format};base64,{b64}" type="{format}">
        </audio>
        """
    st.markdown(md, unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title(f"🤖 {NOMBRE_IA}")
    st.caption("Tu asistente personal")
    st.divider()
    
    st.subheader("⚙️ Configuración")
    activar_voz = st.checkbox("🔊 Hablar respuestas en voz alta", value=True)
    
    voz_seleccionada = st.selectbox(
        "🎙️ Selecciona la voz",
        options=["es-MX-DaliaNeural", "es-ES-ElviraNeural", "en-GB-SoniaNeural"],
        index=0
    )
    
    st.divider()
    st.subheader("🎤 Hablar con Nova")
    audio_grabado = st.audio_input("Graba tu mensaje", label_visibility="collapsed")
    
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

# --- CONFIGURACIÓN DEL CEREBRO ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    instrucciones = f"Eres {NOMBRE_IA}, un asistente experto, elegante, amable y directo. Siempre respondes en español de forma clara."
    modelo = genai.GenerativeModel('gemini-3.5-flash', system_instruction=instrucciones)

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
    prompt = st.chat_input(f"Habla con {NOMBRE_IA}...")

    # --- LÓGICA DE PROCESAMIENTO ---
    if audio_grabado or prompt:
        if prompt:
            texto_usuario = prompt
            contexto_ia = prompt
            tipo_entrada = "texto"
        else:
            texto_usuario = "🎤 (Mensaje de voz)"
            audio_bytes = audio_grabado.read()
            contexto_ia = [
                "Responde a este mensaje de voz:",
                {"mime_type": "audio/wav", "data": audio_bytes}
            ]
            tipo_entrada = "voz"

        with st.chat_message("user", avatar="👤"):
            st.markdown(texto_usuario)
        
        st.session_state.messages.append({"role": "user", "content": texto_usuario})

        if codigo_actual and tipo_entrada == "texto":
            contexto_ia = f"Te adjunto el código actual del archivo:\n\n```python\n{codigo_actual}\n```\n\nMi petición es: {prompt}\n\nPor favor, devuélveme el código completo modificado dentro de un bloque de código."

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Pensando..."):
                max_reintentos = 3
                for intento in range(max_reintentos):
                    try:
                        respuesta = modelo.generate_content(contexto_ia)
                        texto_respuesta = respuesta.text
                        st.markdown(texto_respuesta)
                        st.session_state.messages.append({"role": "assistant", "content": texto_respuesta})
                        
                        if activar_voz and len(texto_respuesta) < 600: 
                            try:
                                audio_buffer = asyncio.run(generar_audio_edge(texto_respuesta, voz_seleccionada))
                                autoplay_audio(audio_buffer, format="audio/mp3")
                            except Exception as e:
                                st.warning(f"No se pudo generar la voz: {e}")
                        
                        break 
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            # Extraemos el tiempo de espera en segundos
                            match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', error_str)
                            espera = int(match.group(1)) if match else 30
                            
                            # Si el tiempo es mayor a 2 minutos, es porque se agotó la cuota diaria
                            if espera > 120:
                                # Convertimos los segundos a un formato bonito (Horas, Minutos, Segundos)
                                horas = espera // 3600
                                minutos = (espera % 3600) // 60
                                segundos = espera % 60
                                
                                tiempo_texto = ""
                                if horas > 0:
                                    tiempo_texto += f"{horas} horas, "
                                if minutos > 0:
                                    tiempo_texto += f"{minutos} minutos y "
                                tiempo_texto += f"{segundos} segundos"
                                
                                st.error(f"❌ Se ha agotado la cuota diaria de tu API Key. Podrás volver a usar a Nova en aproximadamente **{tiempo_texto}**.\n\n*(También puedes crear una nueva clave en un NUEVO proyecto en Google AI Studio para seguir hoy).*")
                                break
                            
                            if intento < max_reintentos - 1:
                                st.warning(f"⏳ Límite por minuto alcanzado. Esperando {espera} segundos...")
                                time.sleep(espera)
                            else:
                                st.error("❌ Límite de la API superado. Intenta de nuevo en un minuto.")
                        else:
                            st.error(f"Error: {e}")
                            break
        
        if prompt:
            st.rerun()

except KeyError:
    st.warning("⚠️ Falta la API Key.")
