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
import threading
import chromadb

# --- CONFIGURACIÓN DE LA PÁGINA ---
NOMBRE_IA = "Lili"
VOZ_FIJA = "es-VE-PaolaNeural" 
VERSION = "v42.0 - RAG & Clean UI"
ARCHIVO_CHATS = "chats_lili.json"

# --- DATOS DE GITHUB ---
USUARIO_GITHUB = "leivercontreras18-ux"
REPO_DEFECTO = "leiver-ai"

st.set_page_config(page_title=NOMBRE_IA, page_icon="✨", layout="wide")

# --- FUNCIONES GITHUB ---
def obtener_repositorios(token):
    headers = {"Authorization": f"token {token}"}
    res = requests.get("https://api.github.com/user/repos?per_page=100&sort=updated", headers=headers)
    if res.status_code == 200:
        return [r['name'] for r in res.json()]
    return []

def obtener_archivos_codigo(usuario, repo, token):
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
        return True, base64.b64decode(res.json()['content']).decode('utf-8', errors='ignore')
    return False, ""

def guardar_archivo_github(usuario, repo, archivo, contenido_str, token):
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/repos/{usuario}/{repo}/contents/{archivo}"
    sha = None
    res_get = requests.get(url, headers=headers)
    if res_get.status_code == 200:
        sha = res_get.json().get("sha")
    contenido_b64 = base64.b64encode(contenido_str.encode('utf-8')).decode('utf-8')
    data = {"message": "Actualización automática de memoria", "content": contenido_b64}
    if sha: data["sha"] = sha
    response = requests.put(url, headers=headers, json=data)
    return response.status_code in (200, 201)

# --- FUNCIONES DE MEMORIA DE CHATS ---
def cargar_todos_los_chats():
    token = st.secrets.get("GITHUB_TOKEN")
    if token:
        exito, contenido = descargar_archivo_github(USUARIO_GITHUB, REPO_DEFECTO, ARCHIVO_CHATS, token)
        if exito:
            try: return json.loads(contenido)
            except: pass
    if os.path.exists(ARCHIVO_CHATS):
        with open(ARCHIVO_CHATS, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def guardar_todos_los_chats(chats):
    with open(ARCHIVO_CHATS, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False, indent=4)
    token = st.secrets.get("GITHUB_TOKEN")
    if token:
        contenido_str = json.dumps(chats, ensure_ascii=False, indent=4)
        guardar_archivo_github(USUARIO_GITHUB, REPO_DEFECTO, ARCHIVO_CHATS, contenido_str, token)

# --- MOTOR RAG (CHROMADB) ---
@st.cache_resource
def obtener_cliente_chroma():
    return chromadb.Client()

def chunk_texto(texto, tamaño=1500, solapamiento=200):
    """Divide el texto en pedazos para que la IA pueda leerlos."""
    chunks = []
    for i in range(0, len(texto), tamaño - solapamiento):
        chunks.append(texto[i:i + tamaño])
    return chunks

def indexar_repositorio(usuario, repo, token):
    """Descarga el repo, lo trocea y lo guarda en la base de datos."""
    cliente = obtener_cliente_chroma()
    try:
        cliente.delete_collection("codigo_repo")
    except:
        pass
    coleccion = cliente.create_collection("codigo_repo")
    
    archivos = obtener_archivos_codigo(usuario, repo, token)
    if not archivos:
        return False
        
    documentos = []
    metadatos = []
    ids = []
    contador = 0
    
    for archivo in archivos:
        exito, contenido = descargar_archivo_github(usuario, repo, archivo, token)
        if exito and contenido:
            pedazos = chunk_texto(contenido)
            for pedazo in pedazos:
                documentos.append(pedazo)
                metadatos.append({"archivo": archivo})
                ids.append(f"id_{contador}")
                contador += 1
                
    if documentos:
        coleccion.add(documents=documentos, metadatas=metadatos, ids=ids)
        return True
    return False

def buscar_contexto_codigo(pregunta):
    """Busca en la base de datos los fragmentos más relevantes para la pregunta."""
    try:
        cliente = obtener_cliente_chroma()
        coleccion = cliente.get_collection("codigo_repo")
        resultados = coleccion.query(query_texts=[pregunta], n_results=4)
        
        contexto = ""
        for i in range(len(resultados['documents'][0])):
            archivo = resultados['metadatas'][0][i]['archivo']
            texto = resultados['documents'][0][i]
            contexto += f"\n\n--- Archivo: {archivo} ---\n{texto}"
        return contexto
    except:
        return "No se encontró contexto de código."

# --- AUDIO Y VOZ ---
def generar_audio_seguro(texto, voz):
    audio_buffer = io.BytesIO()
    def tarea_audio():
        try:
            async def generar():
                comunicar = edge_tts.Communicate(texto, voz, rate="+8%")
                async for chunk in comunicar.stream():
                    if chunk["type"] == "audio": audio_buffer.write(chunk["data"])
            asyncio.run(generar())
        except: pass
    hilo = threading.Thread(target=tarea_audio)
    hilo.start()
    hilo.join()
    audio_buffer.seek(0)
    return audio_buffer

def limpiar_texto_para_voz(texto):
    texto_limpio = re.sub(r'[*#_`]', '', texto)
    texto_limpio = re.sub(r'^\s*-\s*', '', texto_limpio, flags=re.MULTILINE)
    emoji_pattern = re.compile("[" u"\U0001F600-\U0001F64F" u"\U0001F300-\U0001F5FF" u"\U0001F680-\U0001F6FF" u"\U00002702-\U000027B0" "]+", flags=re.UNICODE)
    texto_limpio = emoji_pattern.sub(r'', texto_limpio)
    texto_limpio = re.sub(r'(?<=\d),(?=\d)', '', texto_limpio) 
    return re.sub(r'\s+', ' ', texto_limpio).strip()

# --- CSS (El mismo de siempre, pero limpio) ---
st.markdown("""
<style>
    :root { --bg-deep-space: #121620; --bg-sidebar: #181d28; --cyan-neon: #00e5ff; --text-pure-white: #ffffff; --text-muted: #8a99ad; --glass-bubble: rgba(24, 29, 40, 0.65); --glass-border: rgba(0, 229, 255, 0.15); }
    .stApp { background: radial-gradient(circle at 60% 50%, #1a2233 0%, var(--bg-deep-space) 100%) !important; color: var(--text-pure-white) !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header { background: transparent !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 6rem !important; max-width: 900px !important; }
    [data-testid="stSidebar"] { background-color: #131822 !important; min-width: 280px !important; border-right: 1px solid rgba(0, 229, 255, 0.05) !important; }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    [data-testid="stSidebar"] button[key^="menu_"] { background-color: transparent !important; border: none !important; box-shadow: none !important; color: var(--text-muted) !important; text-align: left !important; width: 100% !important; padding: 14px 20px !important; font-size: 0.85rem !important; font-weight: 500 !important; letter-spacing: 1px !important; text-transform: uppercase !important; border-radius: 0px !important; display: flex !important; justify-content: flex-start !important; transition: all 0.3s ease !important; margin-bottom: 0px !important; }
    [data-testid="stSidebar"] button[key^="menu_"]:hover { color: var(--text-pure-white) !important; background-color: rgba(255, 255, 255, 0.02) !important; }
    div[data-testid="stSidebar"] div[class*="st-key-menu_"] button { color: var(--cyan-neon) !important; background-color: rgba(0, 229, 255, 0.08) !important; border-left: 3px solid var(--cyan-neon) !important; box-shadow: inset 10px 0 15px rgba(0, 229, 255, 0.02) !important; font-weight: 700 !important; }
    div[data-testid="stSidebar"] button[key^="btn_"] { background-color: transparent !important; border: none !important; border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important; border-radius: 0 !important; color: var(--text-muted) !important; font-size: 0.8rem !important; font-family: monospace !important; text-align: left !important; padding: 8px 10px !important; transition: all 0.2s ease !important; }
    div[data-testid="stSidebar"] button[key^="btn_"]:hover { color: var(--cyan-neon) !important; background-color: rgba(0, 229, 255, 0.05) !important; }
    div[data-testid="stSidebar"] button[key^="del_"] { background-color: transparent !important; border: none !important; color: #56667a !important; font-size: 0.9rem !important; padding: 0 !important; transition: all 0.2s ease !important; }
    div[data-testid="stSidebar"] button[key^="del_"]:hover { color: #ff4d4d !important; background-color: transparent !important; text-shadow: 0 0 8px rgba(255, 77, 77, 0.5) !important; }
    [data-testid="stFileUploader"] { background-color: transparent !important; border: 1px dashed rgba(0, 229, 255, 0.2) !important; border-radius: 12px !important; padding: 10px !important; margin-bottom: 10px !important; width: 100% !important; }
    [data-testid="stFileUploader"] label { color: #8a99ad !important; font-size: 0.8rem !important; }
    [data-testid="stFileUploader"] button { background: transparent !important; border: 1px solid rgba(0, 229, 255, 0.3) !important; color: #00e5ff !important; border-radius: 8px !important; font-size: 0.75rem !important; font-weight: 600 !important; padding: 5px 15px !important; }
    [data-testid="stChatMessage"] { background: var(--glass-bubble) !important; backdrop-filter: blur(12px) !important; border-radius: 12px !important; padding: 16px 20px !important; margin-bottom: 20px !important; border: 1px solid rgba(255, 255, 255, 0.05) !important; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { border: 1px solid rgba(255, 255, 255, 0.08) !important; background: rgba(255, 255, 255, 0.04) !important; margin-left: auto !important; width: fit-content !important; max-width: 80% !important; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) { border: 1px solid var(--glass-border) !important; box-shadow: inset 0 0 15px rgba(0, 229, 255, 0.03) !important; margin-right: auto !important; width: fit-content !important; max-width: 80% !important; }
    [data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
    [data-testid="stChatMessage"] > div { background-color: transparent !important; }
    [data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background-color: transparent !important; background: transparent !important; }
    [data-testid="stBottomBlockContainer"] { padding-bottom: 2rem !important; max-width: 800px !important; margin: 0 auto !important; }
    .stChatInput { background: rgba(24, 29, 40, 0.7) !important; backdrop-filter: blur(10px) !important; border: 1px solid rgba(0, 229, 255, 0.2) !important; border-radius: 30px !important; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important; transition: all 0.3s ease !important; }
    .stChatInput > div, .stChatInput div, .stChatInput textarea, .stChatInput input { background-color: transparent !important; border: none !important; outline: none !important; box-shadow: none !important; color: var(--text-pure-white) !important; }
    .stChatInput textarea::placeholder { color: rgba(255, 255, 255, 0.5) !important; }
    .stChatInput:focus-within { border-color: var(--cyan-neon) !important; box-shadow: 0 4px 25px rgba(0, 0, 0, 0.4), 0 0 8px rgba(0, 229, 255, 0.3) !important; }
    [data-testid="stChatInput"] button { background: transparent !important; border-radius: 50% !important; border: none !important; margin: 5px !important; width: 35px !important; height: 35px !important; box-shadow: none !important; }
    [data-testid="stChatInput"] button:hover { background: rgba(0, 229, 255, 0.1) !important; }
    [data-testid="stChatInput"] button svg { fill: var(--cyan-neon) !important; }
    audio, div[data-testid="stAudio"] { display: none !important; }
    .center-display { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 10vh; margin-bottom: 30px; position: relative; padding: 40px 0; }
    .reactor { position: relative; width: 220px; height: 220px; display: flex; align-items: center; justify-content: center; }
    .reactor-ring-outer { position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(0, 229, 255, 0.1); border-top: 2px solid var(--cyan-neon); border-bottom: 2px solid var(--cyan-neon); animation: spin 3s linear infinite; opacity: 0.3; }
    .reactor-ring-mid { position: absolute; inset: 20px; border-radius: 50%; border: 1px dashed rgba(0, 229, 255, 0.2); animation: spin-reverse 8s linear infinite; opacity: 0.3; }
    .reactor-core { width: 80px; height: 80px; border-radius: 50%; background: radial-gradient(circle at 50% 50%, #ffffff 0%, var(--cyan-neon) 40%, #0077ff 100%); box-shadow: 0 0 50px var(--cyan-neon), inset 0 0 20px #ffffff; animation: pulse 2s ease-in-out infinite; z-index: 10; }
    .display-text { margin-top: 30px; font-size: 12px; letter-spacing: 4px; color: var(--cyan-neon); text-transform: uppercase; font-weight: 600; font-family: monospace; background: rgba(24, 29, 40, 0.8); padding: 6px 16px; border-radius: 20px; border: 1px solid rgba(0, 229, 255, 0.3); box-shadow: 0 0 10px rgba(0, 229, 255, 0.1); z-index: 10; }
    @keyframes spin { 100% { transform: rotate(360deg); } }
    @keyframes spin-reverse { 100% { transform: rotate(-360deg); } }
    @keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 30px var(--cyan-neon), inset 0 0 15px #ffffff; } 50% { transform: scale(1.05); box-shadow: 0 0 60px var(--cyan-neon), inset 0 0 30px #ffffff; } 100% { transform: scale(0.95); box-shadow: 0 0 30px var(--cyan-neon), inset 0 0 15px #ffffff; } }
    /* Estilo limpio para el selector de repo */
    .repo-selector { background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.2); padding: 15px; border-radius: 8px; margin-bottom: 20px; }
    .repo-selector p { margin: 0; color: #8a99ad; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# --- ESTADO INICIAL ---
if "todos_los_chats" not in st.session_state: 
    st.session_state.todos_los_chats = cargar_todos_los_chats()
if "modo_actual" not in st.session_state: st.session_state.modo_actual = "Programación"
if "chat_actual_id" not in st.session_state: st.session_state.chat_actual_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
if "audio_pendiente" not in st.session_state: st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state: st.session_state.mic_key = 0
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "repo_seleccionado" not in st.session_state: st.session_state.repo_seleccionado = REPO_DEFECTO
if "repo_indexado" not in st.session_state: st.session_state.repo_indexado = None

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h3 style='padding-left: 20px; font-weight: 700; letter-spacing: 1.5px;'>LILI AI</h3>", unsafe_allow_html=True)
    st.caption(f"<p style='padding-left: 20px; color: #8a99ad; font-size: 0.75rem; margin-top: -10px;'>{VERSION}</p>", unsafe_allow_html=True)
    
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

    # --- NUEVO SELECTOR LIMPIO DE REPOSITORIO ---
    if st.session_state.modo_actual == "Programación":
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        st.markdown("<div class='repo-selector'>", unsafe_allow_html=True)
        st.markdown("<p>🧠 Repositorio a analizar:</p>", unsafe_allow_html=True)
        token = st.secrets.get("GITHUB_TOKEN")
        
        if token:
            # Usamos caché para no saturar la API de GitHub cada vez que recarga
            @st.cache_data(ttl=300)
            def repos_cache(tk): return obtener_repositorios(tk)
            
            repos = repos_cache(token)
            if repos:
                idx = repos.index(st.session_state.repo_seleccionado) if st.session_state.repo_seleccionado in repos else 0
                repo_sel = st.selectbox("Repositorio", repos, index=idx, label_visibility="collapsed")
                
                if repo_sel != st.session_state.repo_seleccionado:
                    st.session_state.repo_seleccionado = repo_sel
                    st.session_state.repo_indexado = None # Forzar re-indexación
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

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

if len(mensajes_actuales) == 0:
    texto_reactor = "DEV ENVIRONMENT" if st.session_state.modo_actual == "Programación" else "SYSTEM ONLINE"
    mensaje_bienvenida = "Entorno de Desarrollo listo. Hazme cualquier pregunta sobre tu código." if st.session_state.modo_actual == "Programación" else "Hola Leiver. ¿Qué hacemos hoy?"
    st.markdown(f"""
        <div class="center-display">
            <div class="reactor">
                <div class="reactor-ring-outer"></div>
                <div class="reactor-ring-mid"></div>
                <div class="reactor-core"></div>
            </div>
            <div class="display-text">{texto_reactor}</div>
        </div>
        <div style="text-align: center; margin-top: 20px;"><p style="font-size: 16px; color: #8a99ad;">{mensaje_bienvenida}</p></div>
    """, unsafe_allow_html=True)

imagen_subida = st.file_uploader("Adjuntar imagen para análisis visual", type=["png", "jpg", "jpeg"], label_visibility="visible", key=f"uploader_{st.session_state.uploader_key}")
if imagen_subida:
    st.image(imagen_subida, caption="Imagen adjunta lista", use_container_width=True)

placeholder_texto = "Pregúntame sobre el código..." if st.session_state.modo_actual == "Programación" else "Escribe tu mensaje..."
prompt = st.chat_input(placeholder_texto)

if audio_grabado or prompt:
    texto_usuario = prompt if prompt else ""
    
    if audio_grabado and not prompt:
        with st.spinner("Escuchando..."):
            try:
                transcripcion = cliente.audio.transcriptions.create(file=("audio.wav", audio_grabado.read()), model="whisper-large-v3", language="es")
                texto_usuario = transcripcion.text
            except Exception as e: st.error(f"Error de audio: {e}")
                
    if texto_usuario:
        modelo_a_usar = "openai/gpt-oss-120b"
        mensaje_para_groq_content = texto_usuario
        
        if imagen_subida:
            imagen_b64 = base64.b64encode(imagen_subida.getvalue()).decode('utf-8')
            mensaje_para_groq_content = [{"type": "text", "text": texto_usuario}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}}]
            modelo_a_usar = "llama-3.2-11b-vision-preview" 
            st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "user", "content": f"{texto_usuario} [Imagen Adjunta]"})
        else:
            st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "user", "content": texto_usuario})
            
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        
        # --- MAGIA RAG ---
        if st.session_state.modo_actual == "Programación":
            token = st.secrets.get("GITHUB_TOKEN")
            repo = st.session_state.repo_seleccionado
            
            # Si el repo cambió o no está indexado, lo indexamos ahora
            if st.session_state.repo_indexado != repo:
                with st.spinner(f"🧠 Estudiando el repositorio {repo}... (esto toma unos segundos)"):
                    exito = indexar_repositorio(USUARIO_GITHUB, repo, token)
                    if exito:
                        st.session_state.repo_indexado = repo
                    else:
                        st.error("No se pudieron leer los archivos del repositorio.")
            
            with st.spinner("Buscando en el código..."):
                contexto_codigo = buscar_contexto_codigo(texto_usuario)
            
            instrucciones = f"""Eres Lili Dev, una IA experta en programación.
            REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL.
            CONTEXTO: Te habla Leiver, de Venezuela. Estás en MODO PROGRAMACIÓN.
            IMPORTANTE: Estás analizando el repositorio '{repo}'. 
            Aquí tienes los fragmentos de código más relevantes para la pregunta del usuario:
            {contexto_codigo}
            
            Responde basándote en estos fragmentos. Si no encuentras la respuesta, dilo claramente."""
                
        elif st.session_state.modo_actual == "Creativo":
            instrucciones = "Eres Lili Creative, una IA imaginativa, poética y apasionada por el arte. REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL."
        elif st.session_state.modo_actual == "Análisis":
            instrucciones = "Eres Lili Analyst, una IA lógica y estructurada. REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL."
        else:
            instrucciones = "Eres Lili, una IA avanzada y carismática. REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL."

        mensajes_para_groq = [{"role": "system", "content": instrucciones}]
        for msg in mensajes_actuales[:-1]:
            mensajes_para_groq.append({"role": msg["role"], "content": msg["content"].replace(" [Imagen Adjunta]", "")})
        mensajes_para_groq.append({"role": "user", "content": mensaje_para_groq_content})

        try:
            with st.spinner("Redactando respuesta..."):
                respuesta = cliente.chat.completions.create(model=modelo_a_usar, messages=mensajes_para_groq, temperature=0.7, max_tokens=1024)
                texto_respuesta = respuesta.choices[0].message.content
                st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "assistant", "content": texto_respuesta})
                guardar_todos_los_chats(st.session_state.todos_los_chats)
                
                if voz_activa: 
                    try:
                        texto_para_hablar = limpiar_texto_para_voz(texto_respuesta)
                        st.session_state.audio_pendiente = generar_audio_seguro(texto_para_hablar, VOZ_FIJA)
                    except Exception as e: print(f"Error audio: {e}")
                
                st.session_state.mic_key += 1
                st.session_state.uploader_key += 1
                st.rerun()
        except Exception as e:
            st.error(f"Error de Groq: {e}")

if st.session_state.audio_pendiente:
    audio_bytes = st.session_state.audio_pendiente.read()
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(f'<audio autoplay="true" src="data:audio/mp3;base64,{b64}"></audio>', unsafe_allow_html=True)
    st.session_state.audio_pendiente = None
