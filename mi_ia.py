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
VERSION = "v19.1 - One Piece Theme"
ARCHIVO_CHATS = "chats_lili.json"

st.set_page_config(page_title=NOMBRE_IA, page_icon="🏴‍☠️", layout="wide")

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

# --- CSS ESTILO ONE PIECE (DARK GRAND LINE) ---
st.markdown("""
<style>
    /* 1. FONDO SÓLIDO OSCURO (Azul Mar Profundo) */
    .stApp {
        background-color: #0b1320 !important; /* Azul marino casi negro */
        background-image: radial-gradient(circle at 50% 0%, #1a2a40 0%, #0b1320 80%) !important;
        color: #ffffff !important;
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header { background: transparent !important; }
    
    .block-container { padding-top: 2rem !important; max-width: 1000px !important; }

    /* =========================================
       BARRA LATERAL (MENÚ FLOTANTE PIRATA)
       ========================================= */
    [data-testid="stSidebar"] {
        background-color: #0d1826 !important;
        border-right: 2px solid #d4af37 !important; /* Borde Dorado */
    }
    
    /* El Orbe (Ahora simula una Fruta del Diablo o el Sol de Luffy) */
    .side-orb {
        width: 120px; height: 120px; border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #ffeb3b, #ff9800, #d32f2f);
        box-shadow: 0 0 50px rgba(255, 152, 0, 0.8), inset 0 0 20px rgba(255, 255, 255, 0.8);
        animation: float 4s ease-in-out infinite;
        margin: 20px auto 40px auto;
        position: relative;
    }
    /* Anillo exterior */
    .side-orb::after {
        content: "🏴‍☠️"; font-size: 40px; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
        animation: pulse 3s infinite alternate;
    }

    @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }
    @keyframes pulse { 0% { opacity: 0.7; transform: scale(0.95); } 100% { opacity: 1; transform: scale(1.05); } }

    /* Botones del menú */
    [data-testid="stSidebar"] button {
        background: transparent !important; color: #d4af37 !important; /* Texto Dorado */
        border: none !important; text-align: left !important; padding: 15px 10px !important;
        font-size: 16px !important; font-weight: bold !important; letter-spacing: 2px !important;
        transition: all 0.3s ease !important;
    }
    [data-testid="stSidebar"] button:hover {
        color: #ffeb3b !important; padding-left: 20px !important; text-shadow: 0 0 10px #ffeb3b;
    }
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:first-child button {
        color: #ffffff !important; border-left: 3px solid #d32f2f !important; /* Borde Rojo */
    }

    /* =========================================
       CHAT (TEXTO FLOTANTE CON ALTO CONTRASTE)
       ========================================= */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 0 !important;
        margin-bottom: 20px !important;
    }
    div[data-testid="stChatMessageAvatarUser"], div[data-testid="stChatMessageAvatarAssistant"] { 
        display: none !important; 
    }
    
    /* Forzar que el texto sea blanco puro y legible */
    div[data-testid="stChatMessage"] p {
        font-size: 16px !important;
        line-height: 1.7 !important;
        color: #ffffff !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.8); /* Sombra para mejor lectura */
    }

    /* =========================================
       CAJA DE TEXTO (ESTILO TESORO)
       ========================================= */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important; 
        padding-bottom: 2rem !important; 
        max-width: 800px !important; 
        margin: 0 auto !important;
    }
    
    .stChatInput {
        background: rgba(13, 24, 38, 0.9) !important;
        border: 2px solid #d4af37 !important; /* Borde Dorado */
        border-radius: 15px !important;
        box-shadow: 0 0 20px rgba(212, 175, 55, 0.2) !important;
    }
    .stChatInput:focus-within { 
        border: 2px solid #ffeb3b !important; 
        box-shadow: 0 0 30px rgba(255, 235, 59, 0.4) !important;
    }
    [data-testid="stChatInput"] textarea { 
        color: #ffffff !important; font-size: 16px !important; padding: 12px 20px !important; 
    }
    
    /* Botón de enviar */
    [data-testid="stChatInput"] button {
        background: transparent !important; color: #d4af37 !important; border: none !important; 
    }
    [data-testid="stChatInput"] button svg { fill: #d4af37 !important; }
    [data-testid="stChatInput"] button:hover { color: #ffeb3b !important; }

    /* Ajustes de textos internos de Streamlit para que se lean */
    .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #ffffff !important;
    }
    
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

# --- SIDEBAR ---
with st.sidebar:
    st.markdown('<div class="side-orb"></div>', unsafe_allow_html=True)
    
    if st.button("⚓ H O M E", use_container_width=True):
        nuevo_id = datetime.datetime.now().strftime("%d/%m %H:%M")
        st.session_state.chat_actual_id = nuevo_id
        st.session_state.todos_los_chats[nuevo_id] = []
        st.rerun()

    st.button("🗺️ H I S T O R Y", use_container_width=True)
    st.button("👤 P R O F I L E", use_container_width=True)
    
    with st.expander("⚙️ S E T T I N G S"):
        voz_activa = st.checkbox("🔊 Voz activa", value=True)
        token = st.secrets.get("GITHUB_TOKEN")
        usuario_github = "leivercontreras18-ux"
        if token:
            repos = obtener_repositorios(token, usuario_github)
            if repos:
                repo_sel = st.selectbox("Repo", repos)
                archivos = obtener_archivos(usuario_github, repo_sel, token)
                if archivos:
                    arch_sel = st.selectbox("File", archivos)
                    if st.button("Cargar GitHub", use_container_width=True):
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
        <div style="text-align: left; margin-top: 10vh; color: #ffffff; max-width: 600px; text-shadow: 1px 1px 3px black;">
            <h1 style="font-size: 32px; font-weight: 400; line-height: 1.4; font-family: serif; color: #d4af37;">"El Rey de los Piratas"</h1>
            <p style="font-size: 18px; color: #e5e5e5;">Bienvenido al Grand Line, Leiver. Soy Lili, tu nakama. Estoy lista para ayudarte a navegar por el código, buscar tesoros de información o simplemente charlar. ¿Cuál es nuestro próximo destino?</p>
        </div>
    """, unsafe_allow_html=True)

# --- PROCESAMIENTO DE ENTRADA ---
prompt = st.chat_input("Escribe tu mensaje al mar...")

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
        
        instrucciones = f"""Eres {NOMBRE_IA}, una IA avanzada, cercana y carismática. Actúas como un nakama (compañero) de Leiver.
        REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL.
        CONTEXTO: Te habla Leiver, de Venezuela. Tienes una vibra pirata, leal y emocionada por la aventura.
        REGLA DE PROGRAMACIÓN: NUNCA devuelvas archivos completos. Dile: "Borra desde la línea X hasta la Y" y dale el bloque de código exacto."""
        
        if codigo_actual:
            instrucciones += f"\n\nCódigo actual:\n```\n{codigo_actual[:10000]}\n```"

        mensajes_para_groq = [{"role": "system", "content": instrucciones}]
        for msg in mensajes_actuales:
            mensajes_para_groq.append({"role": msg["role"], "content": msg["content"]})
        mensajes_para_groq.append({"role": "user", "content": texto_usuario})

        try:
            with st.spinner("Navegando..."):
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