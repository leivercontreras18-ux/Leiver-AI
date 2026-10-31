import streamlit as st
import time
import io
import asyncio
import edge_tts
import base64
import json
import os
import re
import requests
import datetime
from datetime import timezone, timedelta
from groq import Groq

# --- CONFIGURACIÓN DE LA PÁGINA ---
NOMBRE_IA = "Lili"
VOZ_FIJA = "es-VE-PaolaNeural" 
VERSION = "v21.0 - Red Anime & Bubbles"
ARCHIVO_CHATS = "chats_lili.json"

st.set_page_config(page_title=NOMBRE_IA, page_icon="🌸", layout="wide")

# --- FUNCIONES PARA LA MEMORIA MULTI-CHAT ---
def cargar_todos_los_chats():
    if os.path.exists(ARCHIVO_CHATS):
        with open(ARCHIVO_CHATS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_todos_los_chats(chats):
    with open(ARCHIVO_CHATS, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False, indent=4)

# --- FUNCIÓN PARA LIMPIAR EL TEXTO DE LA VOZ ---
def limpiar_texto_para_voz(texto):
    texto_limpio = re.sub(r'[*#_`]', '', texto)
    texto_limpio = re.sub(r'^\s*-\s*', '', texto_limpio, flags=re.MULTILINE)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F" u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF" u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0" u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    texto_limpio = emoji_pattern.sub(r'', texto_limpio)
    texto_limpio = re.sub(r'(?<=\d),(?=\d)', '', texto_limpio) 
    texto_limpio = texto_limpio.replace('?', ',').replace('¡', '').replace('!', ',')
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio)
    return texto_limpio.strip()

# --- FUNCIONES PARA GITHUB ---
@st.cache_data(ttl=60)
def obtener_repositorios(token, usuario):
    headers = {"Authorization": f"token {token}"}
    res = requests.get(f"https://api.github.com/users/{usuario}/repos?per_page=100", headers=headers)
    if res.status_code == 200:
        return [r['name'] for r in res.json()]
    return []

@st.cache_data(ttl=60)
def obtener_archivos(usuario, repo, token):
    headers = {"Authorization": f"token {token}"}
    repo_info = requests.get(f"https://api.github.com/repos/{usuario}/{repo}", headers=headers)
    if repo_info.status_code != 200:
        return []
    default_branch = repo_info.json().get("default_branch", "main")
    tree_url = f"https://api.github.com/repos/{usuario}/{repo}/git/trees/{default_branch}?recursive=1"
    res = requests.get(tree_url, headers=headers)
    if res.status_code == 200:
        tree = res.json().get("tree", [])
        extensiones_validas = ('.py', '.html', '.css', '.js', '.json', '.txt', '.md')
        return [f['path'] for f in tree if f['type'] == 'blob' and f['path'].endswith(extensiones_validas)]
    return []

def descargar_archivo_github(usuario, repo, archivo, token):
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/repos/{usuario}/{repo}/contents/{archivo}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return True, base64.b64decode(res.json()['content']).decode('utf-8')
    return False, f"Error {res.status_code}"

# --- CSS ESTILO ANIME ROJO (BURBUJAS Y ALINEACIÓN) ---
st.markdown("""
<style>
    /* 1. FONDO ROJO OSCURO CON DEGRADADO */
    .stApp {
        background: radial-gradient(circle at center, #4a0404 0%, #0a0000 100%) !important;
        color: #ffffff !important;
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header { background: transparent !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 6rem !important; max-width: 900px !important; }

    /* =========================================
       BARRA LATERAL
       ========================================= */
    [data-testid="stSidebar"] {
        background-color: rgba(10, 0, 0, 0.8) !important;
        border-right: 1px solid #8b0000 !important;
        backdrop-filter: blur(10px) !important;
    }
    
    [data-testid="stSidebar"] h2 {
        color: #ff4d4d !important;
        text-align: center;
        font-weight: 300;
    }
    
    /* Botones del sidebar */
    [data-testid="stSidebar"] button {
        background: transparent !important; 
        color: #d4d4d4 !important; 
        border: 1px solid transparent !important;
        text-align: left !important; 
        padding: 10px 15px !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stSidebar"] button:hover {
        color: #ffffff !important; 
        border-left: 3px solid #ff4d4d !important;
        background: rgba(255, 77, 77, 0.1) !important;
    }
    
    /* Botón Nuevo Chat */
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:first-child button {
        background: rgba(255, 77, 77, 0.2) !important;
        border: 1px solid #ff4d4d !important;
        text-align: center !important;
        border-radius: 8px !important;
        margin-bottom: 15px !important;
    }

    /* =========================================
       CHAT (BURBUJAS Y ALINEACIÓN)
       ========================================= */
    /* Contenedor general del mensaje */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin-bottom: 15px !important;
        display: flex !important;
    }

    /* Ocultar avatares para que se vea más limpio */
    div[data-testid="stChatMessageAvatarUser"], div[data-testid="stChatMessageAvatarAssistant"] { 
        display: none !important; 
    }

    /* TUS MENSAJES (A LA DERECHA) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse !important;
        justify-content: flex-start !important;
        margin-left: auto !important;
        width: fit-content !important;
        max-width: 80% !important;
    }
    
    /* La burbuja de tus mensajes */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] {
        background: rgba(255, 77, 77, 0.2) !important; /* Rojo translúcido */
        border: 1px solid rgba(255, 77, 77, 0.4) !important;
        color: #ffffff !important;
        border-radius: 20px 20px 0 20px !important; /* Borde inferior derecho recto */
        padding: 12px 18px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important;
    }

    /* MENSAJES DE LILI (A LA IZQUIERDA) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        flex-direction: row !important;
        justify-content: flex-start !important;
        margin-right: auto !important;
        width: fit-content !important;
        max-width: 80% !important;
    }
    
    /* La burbuja de Lili */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] {
        background: rgba(255, 255, 255, 0.08) !important; /* Blanco translúcido */
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        color: #e5e5e5 !important;
        border-radius: 20px 20px 20px 0 !important; /* Borde inferior izquierdo recto */
        padding: 12px 18px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important;
    }
    
    /* Texto dentro de las burbujas */
    div[data-testid="stChatMessage"] p {
        font-size: 15px !important;
        line-height: 1.5 !important;
        margin: 0 !important;
    }

    /* =========================================
       CAJA DE TEXTO (ESTILO FOTO)
       ========================================= */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important; 
        padding-bottom: 2rem !important; 
        max-width: 800px !important; 
        margin: 0 auto !important;
    }
    
    .stChatInput {
        background: rgba(20, 20, 25, 0.9) !important;
        border: 1px solid #ff4d4d !important; /* Borde rojo */
        border-radius: 15px !important;
        box-shadow: 0 0 15px rgba(255, 77, 77, 0.3) !important;
    }
    .stChatInput:focus-within { 
        border: 1px solid #ff8080 !important; 
        box-shadow: 0 0 25px rgba(255, 77, 77, 0.5) !important;
    }
    [data-testid="stChatInput"] textarea { 
        color: #ffffff !important; font-size: 16px !important; padding: 12px 20px !important; 
    }
    
    /* Botón de enviar */
    [data-testid="stChatInput"] button {
        background: #ffffff !important; 
        color: #000000 !important; 
        border-radius: 50% !important;
        border: none !important; 
        width: 35px !important; height: 35px !important;
        margin: 8px !important;
    }
    [data-testid="stChatInput"] button svg { fill: #000000 !important; }

    audio, div[data-testid="stAudio"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADO ---
if "todos_los_chats" not in st.session_state: st.session_state.todos_los_chats = cargar_todos_los_chats()
if "chat_actual_id" not in st.session_state: st.session_state.chat_actual_id = datetime.datetime.now().strftime("%d/%m %H:%M")
if st.session_state.chat_actual_id not in st.session_state.todos_los_chats: st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []
if "audio_pendiente" not in st.session_state: st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state: st.session_state.mic_key = 0
if "codigo_github" not in st.session_state: st.session_state.codigo_github = ""
if "archivo_cargado_nombre" not in st.session_state: st.session_state.archivo_cargado_nombre = ""

# --- SIDEBAR (HISTORIAL CORREGIDO) ---
with st.sidebar:
    st.markdown("<h2>🌸 Lili AI</h2>", unsafe_allow_html=True)
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        nuevo_id = datetime.datetime.now().strftime("%H:%M:%S") # Usamos segundos para que no se repita
        st.session_state.chat_actual_id = nuevo_id
        st.session_state.todos_los_chats[nuevo_id] = []
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        st.rerun()

    st.markdown("---")
    st.markdown("### Historial")
    
    # AQUÍ ESTÁ LA CORRECCIÓN PARA QUE SE VEAN TODOS LOS CHATS
    for chat_id in sorted(st.session_state.todos_los_chats.keys(), reverse=True):
        # Mostramos el chat si tiene mensajes (o si es el actual)
        if len(st.session_state.todos_los_chats[chat_id]) > 0:
            icono = "🟢" if chat_id == st.session_state.chat_actual_id else "⚪"
            if st.button(f"{icono} Chat {chat_id}", key=f"btn_{chat_id}", use_container_width=True):
                st.session_state.chat_actual_id = chat_id
                st.rerun()

    st.markdown("---")
    with st.expander("⚙️ Ajustes"):
        voz_activa = st.checkbox("🔊 Voz activa", value=True)
        token = st.secrets.get("GITHUB_TOKEN")
        usuario_github = "leivercontreras18-ux"
        if token:
            repos = obtener_repositorios(token, usuario_github)
            if repos:
                repo_sel = st.selectbox("Repositorio", repos)
                archivos = obtener_archivos(usuario_github, repo_sel, token)
                if archivos:
                    arch_sel = st.selectbox("Archivo", archivos)
                    if st.button("📥 Cargar", use_container_width=True):
                        exito, resultado = descargar_archivo_github(usuario_github, repo_sel, arch_sel, token)
                        if exito:
                            st.session_state.codigo_github = resultado
                            st.session_state.archivo_cargado_nombre = arch_sel
                            st.rerun()
            if st.session_state.archivo_cargado_nombre:
                st.success(f"✅ {st.session_state.archivo_cargado_nombre}")

# --- CONEXIÓN CON GROQ ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("Falta la API Key.")
    st.stop()
cliente = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- LAYOUT PRINCIPAL ---
mensajes_actuales = st.session_state.todos_los_chats[st.session_state.chat_actual_id]

for message in mensajes_actuales:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if len(mensajes_actuales) == 0:
    st.markdown("""
        <div style="text-align: center; margin-top: 20vh; color: #ffffff;">
            <h1 style="font-size: 30px; font-weight: 300; letter-spacing: 1px;">Hey</h1>
            <p style="font-size: 18px; color: #ff4d4d;">¡Hola Leiver! ¿En qué puedo ayudarte hoy?</p>
        </div>
    """, unsafe_allow_html=True)

# --- PROCESAMIENTO DE ENTRADA ---
prompt = st.chat_input("Escribe tu mensaje...")

with st.sidebar:
    with st.expander("🎤 Micrófono"):
        audio_grabado = st.audio_input("Graba", key=f"mic_{st.session_state.mic_key}", label_visibility="collapsed")

if audio_grabado or prompt:
    texto_usuario = prompt if prompt else ""
    
    if audio_grabado and not prompt:
        with st.spinner("Escuchando..."):
            try:
                transcripcion = cliente.audio.transcriptions.create(
                    file=("audio.wav", audio_grabado.read()), model="whisper-large-v3", language="es"
                )
                texto_usuario = transcripcion.text
            except Exception as e:
                st.error(f"Error de audio: {e}")
                
    if texto_usuario:
        st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "user", "content": texto_usuario})
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        
        codigo_actual = st.session_state.codigo_github
        
        instrucciones = f"""Eres {NOMBRE_IA}, una IA avanzada, cercana y carismática.
        REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL.
        CONTEXTO: Te habla Leiver, de Venezuela. Eres su asistente personal y de programación.
        REGLA DE PROGRAMACIÓN: Si te pide cambios de código, NUNCA devuelvas el archivo completo. Dile: "Borra desde la línea X hasta la Y" y dale el bloque de código exacto."""
        
        if codigo_actual:
            instrucciones += f"\n\nCódigo actual:\n```\n{codigo_actual[:10000]}\n```"

        mensajes_para_groq = [{"role": "system", "content": instrucciones}]
        for msg in mensajes_actuales:
            mensajes_para_groq.append({"role": msg["role"], "content": msg["content"]})
        mensajes_para_groq.append({"role": "user", "content": texto_usuario})

        try:
            with st.spinner("Pensando..."):
                respuesta = cliente.chat.completions.create(
                    model="openai/gpt-oss-20b", messages=mensajes_para_groq, temperature=0.8, max_tokens=1024
                )
                texto_respuesta = respuesta.choices[0].message.content
                st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "assistant", "content": texto_respuesta})
                guardar_todos_los_chats(st.session_state.todos_los_chats)
                
                if voz_activa: 
                    try:
                        texto_para_hablar = limpiar_texto_para_voz(texto_respuesta)
                        comunicar = edge_tts.Communicate(texto_para_hablar, VOZ_FIJA, rate="+8%")
                        audio_buffer = io.BytesIO()
                        import asyncio
                        async def gen_audio():
                            async for chunk in comunicar.stream():
                                if chunk["type"] == "audio": audio_buffer.write(chunk["data"])
                        asyncio.run(gen_audio())
                        audio_buffer.seek(0)
                        st.session_state.audio_pendiente = audio_buffer
                    except Exception: pass
                
                st.session_state.mic_key += 1
                st.rerun()
        except Exception as e:
            st.error(f"Error de Groq: {e}")

if st.session_state.audio_pendiente:
    audio_bytes = st.session_state.audio_pendiente.read()
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(f'<audio autoplay="true" src="data:audio/mp3;base64,{b64}"></audio>', unsafe_allow_html=True)
    st.session_state.audio_pendiente = None