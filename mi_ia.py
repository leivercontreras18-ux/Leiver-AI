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
from PIL import Image

# --- ARREGLO 3: PREVENIR QUE LA APP SE CAIGA AL HABLAR ---
import nest_asyncio
nest_asyncio.apply()

# --- CONFIGURACIÓN DE LA PÁGINA ---
NOMBRE_IA = "Lili"
VOZ_FIJA = "es-VE-PaolaNeural" 
VERSION = "v40.0 - Bugfixes & Stable"
ARCHIVO_CHATS = "chats_lili.json"

st.set_page_config(page_title=NOMBRE_IA, page_icon="✨", layout="wide")

# --- SISTEMA DE NOTIFICACIONES FLOTANTES ---
if "toast_msg" not in st.session_state:
    st.session_state.toast_msg = None
if st.session_state.toast_msg:
    st.toast(st.session_state.toast_msg[0], icon=st.session_state.toast_msg[1])
    st.session_state.toast_msg = None

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
def obtener_repositorios(token):
    headers = {"Authorization": f"token {token}"}
    res = requests.get("https://api.github.com/user/repos?per_page=100&sort=updated", headers=headers)
    if res.status_code == 200:
        return [r['name'] for r in res.json()]
    return []

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

# --- CSS PREMIUM HUD ---
st.markdown("""
<style>
    /* Variables de Sistema */
    :root {
        --bg-deep-space: #121620;
        --bg-sidebar: #181d28;
        --bg-active-tab: rgba(0, 229, 255, 0.08);
        --cyan-neon: #00e5ff;
        --text-pure-white: #ffffff;
        --text-muted: #8a99ad;
        --glass-bubble: rgba(24, 29, 40, 0.65);
        --glass-border: rgba(0, 229, 255, 0.15);
    }

    /* Fondo Principal */
    .stApp {
        background: radial-gradient(circle at 60% 50%, #1a2233 0%, var(--bg-deep-space) 100%) !important;
        color: var(--text-pure-white) !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    header { background: transparent !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 6rem !important; max-width: 900px !important; }

    /* =========================================
       BARRA LATERAL
       ========================================= */
    [data-testid="stSidebar"] {
        background-color: #131822 !important;
        min-width: 280px !important;
        border-right: 1px solid rgba(0, 229, 255, 0.05) !important;
    }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }

    [data-testid="stSidebar"] button[key^="menu_"] {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: var(--text-muted) !important;
        text-align: left !important;
        width: 100% !important;
        padding: 14px 20px !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
        border-radius: 0px !important;
        display: flex !important;
        justify-content: flex-start !important;
        transition: all 0.3s ease !important;
        margin-bottom: 0px !important;
    }
    [data-testid="stSidebar"] button[key^="menu_"]:hover {
        color: var(--text-pure-white) !important;
        background-color: rgba(255, 255, 255, 0.02) !important;
    }

    div[data-testid="stSidebar"] div[class*="st-key-menu_"] button {
        color: var(--cyan-neon) !important;
        background-color: rgba(0, 229, 255, 0.08) !important;
        border-left: 3px solid var(--cyan-neon) !important;
        box-shadow: inset 10px 0 15px rgba(0, 229, 255, 0.02) !important;
        font-weight: 700 !important;
    }

    /* =========================================
       HISTORIAL DE CHATS LIMPIO
       ========================================= */
    div[data-testid="stSidebar"] button[key^="btn_"] {
        background-color: transparent !important; border: none !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 0 !important; color: var(--text-muted) !important;
        font-size: 0.8rem !important; font-family: monospace !important;
        text-align: left !important; padding: 8px 10px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stSidebar"] button[key^="btn_"]:hover {
        color: var(--cyan-neon) !important; background-color: rgba(0, 229, 255, 0.05) !important;
    }
    div[data-testid="stSidebar"] button[key^="del_"] {
        background-color: transparent !important; border: none !important;
        color: #56667a !important; font-size: 0.9rem !important; padding: 0 !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stSidebar"] button[key^="del_"]:hover {
        color: #ff4d4d !important; background-color: transparent !important;
        text-shadow: 0 0 8px rgba(255, 77, 77, 0.5) !important;
    }

    /* =========================================
       PANEL DE GITHUB
       ========================================= */
    [data-testid="stExpander"] summary {
        font-size: 0.8rem !important; font-weight: 600 !important;
        letter-spacing: 1.5px !important; text-transform: uppercase !important;
        color: #8a99ad !important; padding: 10px !important;
    }
    [data-testid="stExpander"] summary:hover { color: #ffffff !important; }
    [data-testid="stExpander"] summary svg { display: none !important; }
    [data-testid="stExpander"] button {
        background: rgba(0, 229, 255, 0.03) !important;
        border: 1px solid rgba(0, 229, 255, 0.2) !important;
        border-radius: 6px !important; color: #00e5ff !important;
        font-size: 0.75rem !important; font-weight: 600 !important;
        letter-spacing: 1px !important; text-transform: uppercase !important;
        height: auto !important;
    }
    [data-testid="stExpander"] button:hover {
        border-color: #00e5ff !important; background: rgba(0, 229, 255, 0.08) !important; color: #ffffff !important;
    }
    [data-testid="stExpander"] button img, [data-testid="stExpander"] button span[role="img"] { display: none !important; }
    [data-testid="stExpander"] div[data-baseweb="select"] > div {
        background-color: rgba(10, 14, 22, 0.6) !important;
        border: 1px solid rgba(0, 229, 255, 0.1) !important;
        color: #ffffff !important; border-radius: 6px !important;
    }
    [data-testid="stExpander"] div[data-baseweb="select"] > div:focus-within {
        border-color: #00e5ff !important; box-shadow: 0 0 8px rgba(0, 229, 255, 0.2) !important;
    }
    [data-testid="stExpander"] div[data-baseweb="select"] svg { fill: #00e5ff !important; color: #00e5ff !important; }
    ul[data-baseweb="menu"] { background-color: #131822 !important; border: 1px solid rgba(0, 229, 255, 0.2) !important; border-radius: 6px !important; }
    ul[data-baseweb="menu"] li { color: #ffffff !important; font-size: 0.8rem !important; }
    ul[data-baseweb="menu"] li:hover { background-color: rgba(0, 229, 255, 0.1) !important; color: #00e5ff !important; }
    [data-testid="stExpander"] [data-testid="stHorizontalBlock"] { gap: 8px !important; }
    [data-testid="stExpander"] [data-testid="stHorizontalBlock"] button {
        width: 100% !important; padding: 10px 4px !important;
        font-size: 0.7rem !important; white-space: nowrap !important;
        display: flex !important; justify-content: center !important; align-items: center !important;
    }

    /* =========================================
       SUBIDA DE IMAGEN EN EL CHAT
       ========================================= */
    [data-testid="stFileUploader"] {
        background-color: transparent !important;
        border: 1px dashed rgba(0, 229, 255, 0.2) !important;
        border-radius: 12px !important;
        padding: 10px !important;
        margin-bottom: 10px !important;
        width: 100% !important;
    }
    [data-testid="stFileUploader"] label {
        color: #8a99ad !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stFileUploader"] section {
        background-color: transparent !important;
    }
    [data-testid="stFileUploader"] button {
        background: transparent !important;
        border: 1px solid rgba(0, 229, 255, 0.3) !important;
        color: #00e5ff !important;
        border-radius: 8px !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        padding: 5px 15px !important;
    }
    [data-testid="stFileUploader"] button:hover {
        background: rgba(0, 229, 255, 0.1) !important;
    }

    /* =========================================
       CHAT (GLASSMORPHISM)
       ========================================= */
    [data-testid="stChatMessage"] {
        background: var(--glass-bubble) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        margin-bottom: 20px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        background: rgba(255, 255, 255, 0.04) !important;
        margin-left: auto !important; width: fit-content !important; max-width: 80% !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        border: 1px solid var(--glass-border) !important;
        box-shadow: inset 0 0 15px rgba(0, 229, 255, 0.03) !important;
        margin-right: auto !important; width: fit-content !important; max-width: 80% !important;
    }
    [data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
    [data-testid="stChatMessage"] > div { background-color: transparent !important; }

    /* =========================================
       CAJA DE TEXTO
       ========================================= */
    [data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { 
        background-color: transparent !important; background: transparent !important; 
    }
    [data-testid="stBottomBlockContainer"] { padding-bottom: 2rem !important; max-width: 800px !important; margin: 0 auto !important; }
    .stChatInput { 
        background: rgba(24, 29, 40, 0.7) !important; backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(0, 229, 255, 0.2) !important; border-radius: 30px !important; 
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important; transition: all 0.3s ease !important;
    }
    .stChatInput > div, .stChatInput div, .stChatInput textarea, .stChatInput input { 
        background-color: transparent !important; border: none !important; outline: none !important; 
        box-shadow: none !important; color: var(--text-pure-white) !important; 
    }
    .stChatInput textarea::placeholder { color: rgba(255, 255, 255, 0.5) !important; }
    .stChatInput:focus-within { border-color: var(--cyan-neon) !important; box-shadow: 0 4px 25px rgba(0, 0, 0, 0.4), 0 0 8px rgba(0, 229, 255, 0.3) !important; }
    [data-testid="stChatInput"] button { 
        background: transparent !important; border-radius: 50% !important; border: none !important; 
        margin: 5px !important; width: 35px !important; height: 35px !important; box-shadow: none !important;
    }
    [data-testid="stChatInput"] button:hover { background: rgba(0, 229, 255, 0.1) !important; }
    [data-testid="stChatInput"] button svg { fill: var(--cyan-neon) !important; }
    audio, div[data-testid="stAudio"] { display: none !important; }

    /* =========================================
       REACTOR (ORBE)
       ========================================= */
    .center-display { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 10vh; margin-bottom: 30px; position: relative; padding: 40px 0; }
    .reactor { position: relative; width: 220px; height: 220px; display: flex; align-items: center; justify-content: center; }
    .reactor-ring-outer { position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(0, 229, 255, 0.1); border-top: 2px solid var(--cyan-neon); border-bottom: 2px solid var(--cyan-neon); animation: spin 3s linear infinite; opacity: 0.3; }
    .reactor-ring-mid { position: absolute; inset: 20px; border-radius: 50%; border: 1px dashed rgba(0, 229, 255, 0.2); animation: spin-reverse 8s linear infinite; opacity: 0.3; }
    .reactor-core { width: 80px; height: 80px; border-radius: 50%; background: radial-gradient(circle at 50% 50%, #ffffff 0%, var(--cyan-neon) 40%, #0077ff 100%); box-shadow: 0 0 50px var(--cyan-neon), inset 0 0 20px #ffffff; animation: pulse 2s ease-in-out infinite; z-index: 10; }
    .display-text { margin-top: 30px; font-size: 12px; letter-spacing: 4px; color: var(--cyan-neon); text-transform: uppercase; font-weight: 600; font-family: monospace; background: rgba(24, 29, 40, 0.8); padding: 6px 16px; border-radius: 20px; border: 1px solid rgba(0, 229, 255, 0.3); box-shadow: 0 0 10px rgba(0, 229, 255, 0.1); z-index: 10; }
    @keyframes spin { 100% { transform: rotate(360deg); } }
    @keyframes spin-reverse { 100% { transform: rotate(-360deg); } }
    @keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 30px var(--cyan-neon), inset 0 0 15px #ffffff; } 50% { transform: scale(1.05); box-shadow: 0 0 60px var(--cyan-neon), inset 0 0 30px #ffffff; } 100% { transform: scale(0.95); box-shadow: 0 0 30px var(--cyan-neon), inset 0 0 15px #ffffff; } }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADO ---
if "todos_los_chats" not in st.session_state: 
    st.session_state.todos_los_chats = cargar_todos_los_chats()
    for key in list(st.session_state.todos_los_chats.keys()):
        if "|" not in key:
            new_key = f"Programación|{key}"
            st.session_state.todos_los_chats[new_key] = st.session_state.todos_los_chats.pop(key)
    guardar_todos_los_chats(st.session_state.todos_los_chats)

if "modo_actual" not in st.session_state: 
    st.session_state.modo_actual = "Programación"
    
if "chat_actual_id" not in st.session_state: 
    st.session_state.chat_actual_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"

if "audio_pendiente" not in st.session_state: st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state: st.session_state.mic_key = 0
if "codigo_github" not in st.session_state: st.session_state.codigo_github = ""
if "archivo_cargado_nombre" not in st.session_state: st.session_state.archivo_cargado_nombre = ""

# --- ARREGLO 2: LLAVE PARA LIMPIAR LA IMAGEN ---
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h3 style='padding-left: 20px; font-weight: 700; letter-spacing: 1.5px;'>LILI AI</h3>", unsafe_allow_html=True)
    st.caption(f"<p style='padding-left: 20px; color: #8a99ad; font-size: 0.75rem; margin-top: -10px;'>{VERSION}</p>", unsafe_allow_html=True)
    
    # Botones del Menú Principal
    modos = ["Programación", "Chat General", "Creativo", "Análisis"]
    for m in modos:
        key_name = f"menu_{m.lower().replace(' ', '_')}"
        if st.button(m, key=key_name, use_container_width=True):
            st.session_state.modo_actual = m
            chats_del_modo = [k for k in st.session_state.todos_los_chats.keys() if k.startswith(f"{st.session_state.modo_actual}|")]
            if chats_del_modo:
                st.session_state.chat_actual_id = sorted(chats_del_modo)[-1]
            else:
                st.session_state.chat_actual_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
                st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []
            st.rerun()

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    
    if st.button("+ Nuevo Chat", use_container_width=True):
        nuevo_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
        st.session_state.chat_actual_id = nuevo_id
        st.session_state.todos_los_chats[nuevo_id] = []
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        st.rerun()

    st.markdown("<p style='color: #8a99ad; font-size: 0.8rem; margin-top: 20px; margin-bottom: 10px; padding-left: 20px;'>HISTORIAL</p>", unsafe_allow_html=True)
    
    for chat_id in sorted(list(st.session_state.todos_los_chats.keys()), reverse=True):
        if chat_id.startswith(f"{st.session_state.modo_actual}|") and len(st.session_state.todos_los_chats[chat_id]) > 0:
            col1, col2 = st.columns([0.8, 0.2], vertical_alignment="center")
            with col1:
                icono = "▸" if chat_id == st.session_state.chat_actual_id else "▫"
                hora_chat = chat_id.split("|")[1]
                if st.button(f"{icono} {hora_chat}", key=f"btn_{chat_id}", use_container_width=True):
                    st.session_state.chat_actual_id = chat_id
                    st.rerun()
            with col2:
                if st.button("✕", key=f"del_{chat_id}", use_container_width=True):
                    del st.session_state.todos_los_chats[chat_id]
                    guardar_todos_los_chats(st.session_state.todos_los_chats)
                    if chat_id == st.session_state.chat_actual_id:
                        nuevo_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
                        st.session_state.chat_actual_id = nuevo_id
                        st.session_state.todos_los_chats[nuevo_id] = []
                        guardar_todos_los_chats(st.session_state.todos_los_chats)
                    st.rerun()

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    
    # PANEL DE GITHUB
    if st.session_state.modo_actual == "Programación":
        with st.expander("GITHUB", expanded=True):
            token = st.secrets.get("GITHUB_TOKEN")
            usuario_github = "leivercontreras18-ux"
            
            if token:
                repos = obtener_repositorios(token)
                repo_sel = None
                arch_sel = None
                
                if repos:
                    idx_repo = 0
                    for i, r in enumerate(repos):
                        if r.lower() == "leiver-ai":
                            idx_repo = i
                            break
                            
                    repo_sel = st.selectbox("Repositorio", repos, index=idx_repo)
                    
                    if repo_sel.lower() == "leiver-ai":
                        st.markdown("<p style='color: #00e5ff; font-size: 0.7rem; text-align: right; margin-top: -10px;'>🧠 Repositorio de la IA detectado</p>", unsafe_allow_html=True)
                    
                    archivos = obtener_archivos(usuario_github, repo_sel, token)
                    if archivos:
                        idx_archivo = archivos.index("mi_ia.py") if "mi_ia.py" in archivos else 0
                        arch_sel = st.selectbox("Archivo", archivos, index=idx_archivo)
                    else:
                        st.info("No hay archivos válidos.")
                else:
                    st.warning("No se encontraron repositorios.")
                
                st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("SINCRONIZAR", use_container_width=True):
                        st.session_state.toast_msg = ("Repositorios sincronizados", "🔄")
                        st.rerun()
                        
                with col2:
                    if st.button("CARGAR", use_container_width=True):
                        if repo_sel and arch_sel:
                            exito, resultado = descargar_archivo_github(usuario_github, repo_sel, arch_sel, token)
                            if exito:
                                st.session_state.codigo_github = resultado
                                st.session_state.archivo_cargado_nombre = arch_sel
                                st.session_state.toast_msg = (f"Archivo {arch_sel} cargado", "✅")
                                st.rerun()
                        else:
                            st.error("Selecciona un repo y archivo primero.")
                            
                if st.session_state.archivo_cargado_nombre:
                    st.markdown(f"""
                        <div style="background: rgba(0, 229, 255, 0.1); border: 1px solid #00e5ff; padding: 6px; border-radius: 6px; margin-top: 10px; text-align: center;">
                            <span style="color: #00e5ff; font-size: 0.75rem; font-weight: 600;">✅ IA CARGADA: {st.session_state.archivo_cargado_nombre}</span>
                        </div>
                    """, unsafe_allow_html=True)

    with st.expander("Configuración", expanded=False):
        voz_activa = st.checkbox("Voz activa", value=True)
        audio_grabado = st.audio_input("Graba", key=f"mic_{st.session_state.mic_key}", label_visibility="collapsed")

# --- CONEXIÓN CON GROQ ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("Falta la API Key.")
    st.stop()
cliente = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- LAYOUT PRINCIPAL ---
if st.session_state.chat_actual_id not in st.session_state.todos_los_chats:
    st.session_state.chat_actual_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
    st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []
    guardar_todos_los_chats(st.session_state.todos_los_chats)

mensajes_actuales = st.session_state.todos_los_chats[st.session_state.chat_actual_id]

for message in mensajes_actuales:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Si no hay mensajes, mostramos el Reactor
if len(mensajes_actuales) == 0:
    texto_reactor = "DEV ENVIRONMENT" if st.session_state.modo_actual == "Programación" else "SYSTEM ONLINE"
    mensaje_bienvenida = "Entorno de Desarrollo listo. Carga un archivo de GitHub para comenzar." if st.session_state.modo_actual == "Programación" else "Hola Leiver. ¿Qué hacemos hoy?"
    
    st.markdown(f"""
        <div class="center-display">
            <div class="reactor">
                <div class="reactor-ring-outer"></div>
                <div class="reactor-ring-mid"></div>
                <div class="reactor-core"></div>
            </div>
            <div class="display-text">{texto_reactor}</div>
        </div>
        <div style="text-align: center; margin-top: 20px;">
            <p style="font-size: 16px; color: #8a99ad;">{mensaje_bienvenida}</p>
        </div>
    """, unsafe_allow_html=True)

# --- CAJA DE SUBIDA DE IMAGEN (CON LLAVE PARA QUE SE LIMPIE) ---
imagen_subida = st.file_uploader(
    "Adjuntar imagen para análisis visual", 
    type=["png", "jpg", "jpeg"], 
    label_visibility="visible",
    key=f"uploader_{st.session_state.uploader_key}"
)

if imagen_subida:
    st.image(imagen_subida, caption="Imagen adjunta lista", use_container_width=True)

# --- PROCESAMIENTO DE ENTRADA ---
placeholder_texto = "Pídeme un cambio de código..." if st.session_state.modo_actual == "Programación" else "Escribe tu mensaje..."
prompt = st.chat_input(placeholder_texto)

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
        modelo_a_usar = "openai/gpt-oss-20b"
        mensaje_para_groq_content = texto_usuario
        
        if imagen_subida:
            bytes_imagen = imagen_subida.getvalue()
            imagen_b64 = base64.b64encode(bytes_imagen).decode('utf-8')
            
            mensaje_para_groq_content = [
                {"type": "text", "text": texto_usuario},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}}
            ]
            modelo_a_usar = "llama-3.2-11b-vision-preview" 
            
            st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "user", "content": f"{texto_usuario} [Imagen Adjunta]"})
        else:
            st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "user", "content": texto_usuario})
            
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        
        codigo_actual = st.session_state.codigo_github
        
        if st.session_state.modo_actual == "Programación":
            instrucciones = """Eres Lili Dev, una IA experta en programación y arquitectura de software.
            REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL.
            CONTEXTO: Te habla Leiver, de Venezuela. Estás en MODO PROGRAMACIÓN.
            IMPORTANTE: El usuario TIENE UN ARCHIVO CARGADO en tu memoria. 
            Si el usuario te pregunta "¿de qué trata?", "resume" o "analiza" el código, DEBES leer el código que se te proporcionó abajo y darle un resumen detallado.
            Si te pide cambios, NUNCA devuelvas el archivo completo. Dile: "Borra desde la línea X hasta la Y" y dale el bloque de código exacto. Sé precisa y técnica."""
            
            if codigo_actual:
                instrucciones += f"\n\nAquí está el código actual del proyecto:\n```\n{codigo_actual[:10000]}\n```"
            else:
                instrucciones += "\n\nNOTA: Aún no tienes ningún archivo cargado. Pídele al usuario que cargue uno desde la barra lateral."
                
        elif st.session_state.modo_actual == "Creativo":
            instrucciones = """Eres Lili Creative, una IA imaginativa, poética y apasionada por el arte.
            REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL. CONTEXTO: Estás en MODO CREATIVO."""
            
        elif st.session_state.modo_actual == "Análisis":
            instrucciones = """Eres Lili Analyst, una IA lógica y estructurada.
            REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL. CONTEXTO: Estás en MODO ANÁLISIS."""
            
        else:
            instrucciones = """Eres Lili, una IA avanzada y carismática. REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL."""

        # --- ARREGLO 1: EVITAR DUPLICADOS EN EL HISTORIAL ---
        mensajes_para_groq = [{"role": "system", "content": instrucciones}]
        
        # Enviamos TODO el historial anterior (menos el último mensaje que acabamos de guardar)
        for msg in mensajes_actuales[:-1]:
            contenido_historial = msg["content"].replace(" [Imagen Adjunta]", "")
            mensajes_para_groq.append({"role": msg["role"], "content": contenido_historial})
            
        # Ahora enviamos el último mensaje UNA SOLA VEZ con su formato correcto (texto o imagen+texto)
        mensajes_para_groq.append({"role": "user", "content": mensaje_para_groq_content})

        try:
            with st.spinner("Procesando..."):
                respuesta = cliente.chat.completions.create(
                    model=modelo_a_usar, 
                    messages=mensajes_para_groq, 
                    temperature=0.7, 
                    max_tokens=1024
                )
                texto_respuesta = respuesta.choices[0].message.content
                st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "assistant", "content": texto_respuesta})
                guardar_todos_los_chats(st.session_state.todos_los_chats)
                
                if voz_activa: 
                    try:
                        texto_para_hablar = limpiar_texto_para_voz(texto_respuesta)
                        comunicar = edge_tts.Communicate(texto_para_hablar, VOZ_FIJA, rate="+8%")
                        audio_buffer = io.BytesIO()
                        async def gen_audio():
                            async for chunk in comunicar.stream():
                                if chunk["type"] == "audio": audio_buffer.write(chunk["data"])
                        asyncio.run(gen_audio())
                        audio_buffer.seek(0)
                        st.session_state.audio_pendiente = audio_buffer
                    except Exception: pass
                
                st.session_state.mic_key += 1
                st.session_state.uploader_key += 1 # <--- ARREGLO 2: Esto limpia la imagen
                st.rerun()
        except Exception as e:
            st.error(f"Error de Groq: {e}")

if st.session_state.audio_pendiente:
    audio_bytes = st.session_state.audio_pendiente.read()
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(f'<audio autoplay="true" src="data:audio/mp3;base64,{b64}"></audio>', unsafe_allow_html=True)
    st.session_state.audio_pendiente = None
