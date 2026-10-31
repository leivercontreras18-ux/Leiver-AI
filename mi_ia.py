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
VERSION = "v24.0 - Slate Futurist"
ARCHIVO_CHATS = "chats_lili.json"

st.set_page_config(page_title=NOMBRE_IA, page_icon="🌐", layout="wide")

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

# --- CSS FUTURISTA (PALETA SLATE - MÁS CLARA) ---
st.markdown("""
<style>
    /* 1. FONDO GRIS PIZARRA (Más claro y elegante) */
    .stApp {
        background-color: #1e293b !important; /* Slate 800 */
        color: #f8fafc !important;
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header { background: transparent !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 6rem !important; max-width: 900px !important; }

    /* =========================================
       BARRA LATERAL (Slate 900)
       ========================================= */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important; /* Slate 900 */
        border-right: 1px solid #334155 !important; /* Borde sutil */
    }
    [data-testid="stSidebar"] h3 {
        color: #38bdf8 !important; /* Azul cielo */
        text-align: center;
    }
    [data-testid="stSidebar"] button {
        background: transparent !important; color: #cbd5e1 !important; border: 1px solid transparent !important;
        text-align: left !important; padding: 8px 12px !important; border-radius: 8px !important; transition: all 0.2s ease !important;
    }
    [data-testid="stSidebar"] button:hover {
        background: #1e293b !important; color: #f8fafc !important;
    }
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:first-child button {
        background: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important;
        text-align: center !important; font-weight: bold !important;
    }

    /* =========================================
       CHAT (BURBUJAS HUD)
       ========================================= */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important; border: none !important; padding: 0 !important;
        margin-bottom: 20px !important; display: flex !important;
    }
    div[data-testid="stChatMessageAvatarUser"], div[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }

    /* TUS MENSAJES (Derecha - Azul Cielo Suave) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse !important; justify-content: flex-start !important;
        margin-left: auto !important; width: fit-content !important; max-width: 80% !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] {
        background: #0ea5e9 !important; /* Azul cielo sólido */
        color: #ffffff !important; 
        border-radius: 15px 15px 0 15px !important; padding: 12px 18px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
    }

    /* MENSAJES DE LILI (Izquierda - Gris Slate Claro) */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {
        flex-direction: row !important; justify-content: flex-start !important;
        margin-right: auto !important; width: fit-content !important; max-width: 80% !important;
    }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] {
        background: #334155 !important; /* Slate 700 */
        color: #f8fafc !important; 
        border-radius: 15px 15px 15px 0 !important; padding: 12px 18px !important;
        border: 1px solid #475569 !important;
    }

    /* =========================================
       CAJA DE TEXTO (FONDO MÁS CLARO)
       ========================================= */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important; padding-bottom: 2rem !important; max-width: 800px !important; margin: 0 auto !important;
    }
    
    .stChatInput {
        background: #334155 !important; /* Slate 700 (más claro que el fondo) */
        border: 1px solid #475569 !important; 
        border-radius: 30px !important; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
    }
    
    /* El truco de transparencia para que no se vea el fondo feo */
    .stChatInput > div,
    .stChatInput div,
    .stChatInput div[data-baseweb="base-input"],
    .stChatInput div[data-baseweb="textarea"],
    .stChatInput textarea,
    .stChatInput input {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        color: #f8fafc !important;
    }
    
    /* Al hacer clic, el borde se ilumina en azul */
    .stChatInput:focus-within { 
        border: 1px solid #38bdf8 !important; 
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.2) !important;
    }

    /* Botón de enviar */
    [data-testid="stChatInput"] button {
        background: #38bdf8 !important; /* Fondo azul para el botón */
        color: #0f172a !important; 
        border-radius: 50% !important;
        border: none !important;
        margin: 5px !important;
        width: 35px !important;
        height: 35px !important;
    }
    [data-testid="stChatInput"] button svg { fill: #0f172a !important; }

    audio, div[data-testid="stAudio"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADO ---
if "todos_los_chats" not in st.session_state: st.session_state.todos_los_chats = cargar_todos_los_chats()
if "chat_actual_id" not in st.session_state: st.session_state.chat_actual_id = datetime.datetime.now().strftime("%H:%M:%S")
if st.session_state.chat_actual_id not in st.session_state.todos_los_chats: st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []
if "audio_pendiente" not in st.session_state: st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state: st.session_state.mic_key = 0
if "codigo_github" not in st.session_state: st.session_state.codigo_github = ""
if "archivo_cargado_nombre" not in st.session_state: st.session_state.archivo_cargado_nombre = ""

# --- SIDEBAR (HISTORIAL Y BORRAR) ---
with st.sidebar:
    st.markdown("<h3>🌐 Lili AI</h3>", unsafe_allow_html=True)
    
    if st.button("➕ Nuevo Chat", use_container_width=True):
        nuevo_id = datetime.datetime.now().strftime("%H:%M:%S")
        st.session_state.chat_actual_id = nuevo_id
        st.session_state.todos_los_chats[nuevo_id] = []
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        st.rerun()

    st.markdown("---")
    st.markdown("**Historial**")
    
    for chat_id in sorted(list(st.session_state.todos_los_chats.keys()), reverse=True):
        if len(st.session_state.todos_los_chats[chat_id]) > 0:
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                icono = "🟢" if chat_id == st.session_state.chat_actual_id else "⚪"
                if st.button(f"{icono} {chat_id}", key=f"btn_{chat_id}", use_container_width=True):
                    st.session_state.chat_actual_id = chat_id
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{chat_id}", use_container_width=True):
                    del st.session_state.todos_los_chats[chat_id]
                    guardar_todos_los_chats(st.session_state.todos_los_chats)
                    if chat_id == st.session_state.chat_actual_id:
                        nuevo_id = datetime.datetime.now().strftime("%H:%M:%S")
                        st.session_state.chat_actual_id = nuevo_id
                        st.session_state.todos_los_chats[nuevo_id] = []
                        guardar_todos_los_chats(st.session_state.todos_los_chats)
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
        <div style="text-align: center; margin-top: 25vh;">
            <h1 style="font-size: 32px; font-weight: 300; color: #38bdf8;">Sistemas en Línea</h1>
            <p style="font-size: 16px; color: #94a3b8;">Bienvenido de nuevo, Leiver. ¿Cuál es la misión de hoy?</p>
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