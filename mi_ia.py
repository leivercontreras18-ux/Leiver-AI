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
VERSION = "v31.3 - Isolated Modes"
ARCHIVO_CHATS = "chats_lili.json"

st.set_page_config(page_title=NOMBRE_IA, page_icon="💻", layout="wide")

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

# --- CSS ESTILOS DINÁMICOS ---
st.markdown("""
<style>
    :root { --accent-color: #00f2fe; --bg-glow: rgba(0, 242, 254, 0.1); }
    .stApp { background: radial-gradient(circle at 50% 50%, #0f172a 0%, #050810 100%) !important; color: #f8fafc !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header { background: transparent !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 6rem !important; max-width: 900px !important; }
    [data-testid="stSidebar"] { background-color: #0b1120 !important; border-right: 1px solid #1e293b !important; }
    [data-testid="stSidebar"] .stRadio > div { gap: 5px; }
    [data-testid="stSidebar"] .stRadio label { background: transparent !important; color: #cbd5e1 !important; border: 1px solid transparent !important; padding: 8px 12px !important; border-radius: 8px !important; transition: all 0.2s ease !important; cursor: pointer; }
    [data-testid="stSidebar"] .stRadio label:hover { background: #1e293b !important; color: #ffffff !important; }
    [data-testid="stSidebar"] button { background: transparent !important; color: #cbd5e1 !important; border: 1px solid #1e293b !important; text-align: left !important; padding: 8px 12px !important; border-radius: 8px !important; transition: all 0.2s ease !important; }
    [data-testid="stSidebar"] button:hover { background: #1e293b !important; color: #ffffff !important; border-color: #334155 !important;}
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:first-child button { background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%) !important; color: #000000 !important; text-align: center !important; font-weight: bold !important; border: none !important; }
    div[data-testid="stChatMessage"] { background-color: transparent !important; border: none !important; padding: 0 !important; margin-bottom: 20px !important; display: flex !important; }
    div[data-testid="stChatMessageAvatarUser"], div[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse !important; justify-content: flex-start !important; margin-left: auto !important; width: fit-content !important; max-width: 80% !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) div[data-testid="stChatMessageContent"] { background: #1e293b !important; color: #ffffff !important; border-radius: 16px 16px 0 16px !important; padding: 12px 18px !important; border: 1px solid #334155 !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) { flex-direction: row !important; justify-content: flex-start !important; margin-right: auto !important; width: fit-content !important; max-width: 80% !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) div[data-testid="stChatMessageContent"] { background: var(--bg-glow) !important; color: #ffffff !important; border-radius: 16px 16px 16px 0 !important; padding: 12px 18px !important; border: 1px solid var(--accent-color) !important; }
    [data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background-color: transparent !important; background: transparent !important; }
    [data-testid="stBottomBlockContainer"] { padding-bottom: 2rem !important; max-width: 800px !important; margin: 0 auto !important; }
    .stChatInput { background: #0f172a !important; border: 1px solid var(--accent-color) !important; border-radius: 30px !important; box-shadow: 0 0 15px var(--bg-glow) !important; }
    .stChatInput > div, .stChatInput div, .stChatInput textarea, .stChatInput input { background-color: transparent !important; border: none !important; outline: none !important; box-shadow: none !important; color: #ffffff !important; }
    .stChatInput textarea::placeholder { color: #64748b !important; }
    .stChatInput:focus-within { box-shadow: 0 0 25px var(--bg-glow) !important; }
    [data-testid="stChatInput"] button { background: var(--accent-color) !important; border-radius: 50% !important; border: none !important; margin: 5px !important; width: 35px !important; height: 35px !important; }
    [data-testid="stChatInput"] button svg { fill: #000000 !important; }
    audio, div[data-testid="stAudio"] { display: none !important; }
    .center-display { display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 10vh; margin-bottom: 30px; position: relative; }
    .reactor { position: relative; width: 220px; height: 220px; display: flex; align-items: center; justify-content: center; }
    .reactor-ring-outer { position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(0, 242, 254, 0.3); border-top: 2px solid var(--accent-color); border-bottom: 2px solid var(--accent-color); animation: spin 3s linear infinite; box-shadow: 0 0 30px var(--bg-glow); }
    .reactor-ring-mid { position: absolute; inset: 20px; border-radius: 50%; border: 1px dashed rgba(157, 78, 221, 0.6); animation: spin-reverse 8s linear infinite; }
    .reactor-core { width: 80px; height: 80px; border-radius: 50%; background: radial-gradient(circle at 50% 50%, #ffffff 0%, var(--accent-color) 40%, #4facfe 100%); box-shadow: 0 0 50px var(--accent-color), inset 0 0 20px #ffffff; animation: pulse 2s ease-in-out infinite; z-index: 10; }
    .display-text { margin-top: 30px; font-size: 14px; letter-spacing: 5px; color: var(--accent-color); text-transform: uppercase; text-shadow: 0 0 15px var(--bg-glow); z-index: 10; font-weight: 600; font-family: monospace; }
    @keyframes spin { 100% { transform: rotate(360deg); } }
    @keyframes spin-reverse { 100% { transform: rotate(-360deg); } }
    @keyframes pulse { 0% { transform: scale(0.95); box-shadow: 0 0 30px var(--accent-color), inset 0 0 15px #ffffff; } 50% { transform: scale(1.05); box-shadow: 0 0 60px var(--accent-color), inset 0 0 30px #ffffff; } 100% { transform: scale(0.95); box-shadow: 0 0 30px var(--accent-color), inset 0 0 15px #ffffff; } }
</style>
""", unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADO Y MIGRACIÓN ---
if "todos_los_chats" not in st.session_state: 
    st.session_state.todos_los_chats = cargar_todos_los_chats()
    
    # Migración: Si los chats antiguos no tienen el prefijo del modo, se los ponemos (ej: "💻 Programación|17:00")
    for key in list(st.session_state.todos_los_chats.keys()):
        if "|" not in key:
            new_key = f"💻 Programación|{key}"
            st.session_state.todos_los_chats[new_key] = st.session_state.todos_los_chats.pop(key)
    guardar_todos_los_chats(st.session_state.todos_los_chats)

if "modo_actual" not in st.session_state: 
    st.session_state.modo_actual = "💻 Programación"
    
if "chat_actual_id" not in st.session_state: 
    st.session_state.chat_actual_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"

if "audio_pendiente" not in st.session_state: st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state: st.session_state.mic_key = 0
if "codigo_github" not in st.session_state: st.session_state.codigo_github = ""
if "archivo_cargado_nombre" not in st.session_state: st.session_state.archivo_cargado_nombre = ""

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h3 style='color: var(--accent-color);'>💻 Lili Dev</h3>", unsafe_allow_html=True)
    st.caption(f"{VERSION}")
    
    st.markdown("### Modo de Trabajo")
    modos = ["💻 Programación", "💬 Chat General", "🎨 Creativo", "📊 Análisis"]
    
    # Manejo del cambio de modo: Autocambia al último chat de ese modo o crea uno nuevo
    seleccion = st.radio("", modos, index=modos.index(st.session_state.modo_actual), label_visibility="collapsed")
    if seleccion != st.session_state.modo_actual:
        st.session_state.modo_actual = seleccion
        # Buscar si hay chats en este modo
        chats_del_modo = [k for k in st.session_state.todos_los_chats.keys() if k.startswith(f"{st.session_state.modo_actual}|")]
        if chats_del_modo:
            st.session_state.chat_actual_id = sorted(chats_del_modo)[-1] # El más reciente
        else:
            st.session_state.chat_actual_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
            st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []
        st.rerun()

    st.markdown("---")
    
    if st.button("+ Nuevo Chat", use_container_width=True):
        nuevo_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
        st.session_state.chat_actual_id = nuevo_id
        st.session_state.todos_los_chats[nuevo_id] = []
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        st.rerun()

    st.markdown("**Historial**")
    # FILTRO: Solo mostramos los chats que empiezan con el nombre del modo actual
    for chat_id in sorted(list(st.session_state.todos_los_chats.keys()), reverse=True):
        if chat_id.startswith(f"{st.session_state.modo_actual}|") and len(st.session_state.todos_los_chats[chat_id]) > 0:
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                icono = "▸" if chat_id == st.session_state.chat_actual_id else "▫"
                # Mostramos solo la hora, no el nombre del modo entero
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

    st.markdown("---")
    
    # GITHUB CON AUTOSELECCIÓN
    if st.session_state.modo_actual == "💻 Programación":
        st.markdown("#### 🐙 Repositorios")
        token = st.secrets.get("GITHUB_TOKEN")
        usuario_github = "leivercontreras18-ux"
        
        if token:
            if st.button("🔄 Sincronizar Repositorios", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
                
            repos = obtener_repositorios(token, usuario_github)
            if repos:
                idx_repo = repos.index("Leiver-AI") if "Leiver-AI" in repos else 0
                repo_sel = st.selectbox("Repositorio", repos, index=idx_repo)
                
                archivos = obtener_archivos(usuario_github, repo_sel, token)
                if archivos:
                    idx_archivo = archivos.index("mi_ia.py") if "mi_ia.py" in archivos else 0
                    arch_sel = st.selectbox("Archivo", archivos, index=idx_archivo)
                    
                    if st.button("📥 Cargar Archivo", use_container_width=True):
                        exito, resultado = descargar_archivo_github(usuario_github, repo_sel, arch_sel, token)
                        if exito:
                            st.session_state.codigo_github = resultado
                            st.session_state.archivo_cargado_nombre = arch_sel
                            st.rerun()
            else:
                st.warning("No se encontraron repositorios. Revisa tu Token.")
                
            if st.session_state.archivo_cargado_nombre:
                st.success(f"✅ Leyendo: {st.session_state.archivo_cargado_nombre}")

    with st.expander("Configuración General"):
        voz_activa = st.checkbox("Voz activa", value=True)
        with st.expander("Micrófono"):
            audio_grabado = st.audio_input("Graba", key=f"mic_{st.session_state.mic_key}", label_visibility="collapsed")

# --- CONEXIÓN CON GROQ ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("Falta la API Key.")
    st.stop()
cliente = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- LAYOUT PRINCIPAL ---
# Aseguramos que el chat actual exista (por si se borró o hubo un error)
if st.session_state.chat_actual_id not in st.session_state.todos_los_chats:
    st.session_state.chat_actual_id = f"{st.session_state.modo_actual}|{datetime.datetime.now().strftime('%H:%M:%S')}"
    st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []
    guardar_todos_los_chats(st.session_state.todos_los_chats)

mensajes_actuales = st.session_state.todos_los_chats[st.session_state.chat_actual_id]

for message in mensajes_actuales:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if len(mensajes_actuales) == 0:
    texto_reactor = "DEV ENVIRONMENT" if st.session_state.modo_actual == "💻 Programación" else "SYSTEM ONLINE"
    mensaje_bienvenida = "Entorno de Desarrollo listo. Carga un archivo de GitHub para comenzar." if st.session_state.modo_actual == "💻 Programación" else "Hola Leiver. ¿Qué hacemos hoy?"
    
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
            <p style="font-size: 16px; color: #94a3b8;">{mensaje_bienvenida}</p>
        </div>
    """, unsafe_allow_html=True)

# --- PROCESAMIENTO DE ENTRADA ---
placeholder_texto = "Pídeme un cambio de código..." if st.session_state.modo_actual == "💻 Programación" else "Escribe tu mensaje..."
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
        st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "user", "content": texto_usuario})
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        
        codigo_actual = st.session_state.codigo_github
        
        if st.session_state.modo_actual == "💻 Programación":
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
                
        elif st.session_state.modo_actual == "🎨 Creativo":
            instrucciones = """Eres Lili Creative, una IA imaginativa, poética y apasionada por el arte.
            REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL.
            CONTEXTO: Te habla Leiver. Estás en MODO CREATIVO.
            Tu objetivo es inspirar, escribir historias, brainstorming y pensar fuera de la caja. Usa un tono entusiasta."""
            
        elif st.session_state.modo_actual == "📊 Análisis":
            instrucciones = """Eres Lili Analyst, una IA lógica y estructurada.
            REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL.
            CONTEXTO: Te habla Leiver. Estás en MODO ANÁLISIS.
            Tu objetivo es resumir, extraer datos clave y dar respuestas lógicas y concisas."""
            
        else:
            instrucciones = """Eres Lili, una IA avanzada y carismática. REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL."""

        mensajes_para_groq = [{"role": "system", "content": instrucciones}]
        for msg in mensajes_actuales:
            mensajes_para_groq.append({"role": msg["role"], "content": msg["content"]})
        mensajes_para_groq.append({"role": "user", "content": texto_usuario})

        try:
            with st.spinner("Pensando..."):
                respuesta = cliente.chat.completions.create(
                    model="openai/gpt-oss-20b", messages=mensajes_para_groq, temperature=0.7, max_tokens=1024
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
