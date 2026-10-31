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
VERSION = "v15.8 - Natural Rhythm"
ARCHIVO_CHATS = "chats_lili.json"

st.set_page_config(page_title=NOMBRE_IA, page_icon="💜", layout="wide")

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
    # 1. Quitar Markdown
    texto_limpio = re.sub(r'[*#_`]', '', texto)
    texto_limpio = re.sub(r'^\s*-\s*', '', texto_limpio, flags=re.MULTILINE)
    
    # 2. Quitar Emojis (para que no diga "cara sonriente")
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F" u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF" u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0" u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    texto_limpio = emoji_pattern.sub(r'', texto_limpio)
    
    # 3. Quitar comas de números grandes (1,500 -> 1500)
    texto_limpio = re.sub(r'(?<=\d),(?=\d)', '', texto_limpio) 
    
    # 4. Limpiar espacios dobles que hayan quedado
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio)
    
    # 🔥 NOTA: AQUÍ NO BORRAMOS LOS PUNTOS NI LAS COMAS. 
    # Se los dejamos al motor de voz para que haga pausas naturales.
    
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
        archivos = [f['path'] for f in tree if f['type'] == 'blob' and f['path'].endswith(extensiones_validas)]
        return archivos
    return []

def descargar_archivo_github(usuario, repo, archivo, token):
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/repos/{usuario}/{repo}/contents/{archivo}"
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return True, base64.b64decode(res.json()['content']).decode('utf-8')
    return False, f"Error {res.status_code}: No se pudo descargar."

# --- CSS AVANZADO ---
st.markdown("""
<style>
    .stApp { background-color: #121214 !important; }
    .glow-1 { position: fixed; top: 25%; left: 25%; width: 384px; height: 384px; border-radius: 50%; background: rgba(88, 28, 135, 0.2); filter: blur(120px); pointer-events: none; z-index: 0; }
    .glow-2 { position: fixed; bottom: 33%; right: 25%; width: 400px; height: 400px; border-radius: 50%; background: rgba(131, 24, 67, 0.1); filter: blur(150px); pointer-events: none; z-index: 0; }
    .glow-3 { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 320px; height: 320px; border-radius: 50%; background: rgba(49, 46, 129, 0.2); filter: blur(100px); pointer-events: none; z-index: 0; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header { background: transparent !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 0 !important; max-width: 95% !important; height: 100vh !important; overflow: hidden !important; }
    
    @keyframes blob { 0%, 100% { border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%; transform: scale(1); } 33% { border-radius: 70% 30% 52% 48% / 60% 40% 60% 40%; transform: scale(1.03) rotate(4deg); } 66% { border-radius: 28% 72% 35% 65% / 40% 60% 30% 70%; transform: scale(0.97) rotate(-4deg); } }
    .orb-wrapper { position: relative; display: flex; align-items: center; justify-content: center; width: 300px; height: 300px; margin: 0 auto; }
    .orb-glow { position: absolute; width: 300px; height: 300px; border-radius: 50%; background: linear-gradient(to top right, rgba(168, 85, 247, 0.4), rgba(99, 102, 241, 0.2), rgba(236, 72, 153, 0.4)); filter: blur(60px); animation: pulse 3s infinite alternate; }
    .orb-body { width: 256px; height: 256px; background: linear-gradient(to right, rgba(192, 132, 252, 0.4), rgba(249, 168, 212, 0.5), rgba(129, 140, 248, 0.4)); backdrop-filter: blur(12px); box-shadow: inset 0 0 40px rgba(255, 255, 255, 0.2); animation: blob 8s infinite ease-in-out; border: 1px solid rgba(255, 255, 255, 0.2); position: relative; overflow: hidden; }
    .orb-inner { position: absolute; inset: 0; background: linear-gradient(to bottom left, rgba(236, 72, 153, 0.2), transparent, rgba(147, 51, 234, 0.3)); mix-blend-mode: overlay; animation: spin 12s infinite linear; }
    @keyframes pulse { 0% { opacity: 0.6; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1.1); } } @keyframes spin { 100% { transform: rotate(360deg); } }
    .nova-title { font-size: 36px; font-weight: 200; letter-spacing: 0.2em; background: linear-gradient(to right, #e9d5ff, #f1f5f9, #fbcfe8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 20px; margin-bottom: 0; text-align: center; }
    .nova-subtitle { font-size: 14px; color: rgba(233, 213, 255, 0.6); text-align: center; margin-top: 5px; }
    
    div[data-testid="stVerticalBlockBorderWrapper"] { background: rgba(255, 255, 255, 0.02) !important; border: none !important; backdrop-filter: blur(30px) !important; border-radius: 30px !important; box-shadow: 0 10px 40px 0 rgba(0, 0, 0, 0.4) !important; padding: 20px !important; overflow: hidden !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] > div { background: transparent !important; }
    div[data-testid="stChatMessageAvatarUser"], div[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
    div[data-testid="stChatMessage"] button { display: none !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { background: linear-gradient(135deg, rgba(147, 51, 234, 0.4), rgba(88, 28, 135, 0.4)) !important; border: 1px solid rgba(168, 85, 247, 0.3) !important; color: #f3e8ff !important; border-radius: 25px 25px 5px 25px !important; margin-left: auto !important; width: fit-content !important; max-width: 85% !important; padding: 14px 20px !important; margin-bottom: 15px !important; backdrop-filter: blur(10px) !important; }
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) { background: linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02)) !important; border: 1px solid rgba(255, 255, 255, 0.05) !important; color: rgba(252, 231, 243, 0.95) !important; border-radius: 25px 25px 25px 5px !important; margin-right: auto !important; width: fit-content !important; max-width: 85% !important; padding: 14px 20px !important; margin-bottom: 15px !important; backdrop-filter: blur(10px) !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] ::-webkit-scrollbar { width: 6px !important; } ::-webkit-scrollbar-track { background: transparent !important; } ::-webkit-scrollbar-thumb { background: rgba(168, 85, 247, 0.4) !important; border-radius: 10px !important; }
    
    [data-testid="stBottom"], [data-testid="stBottom"] > div { background: transparent !important; }
    [data-testid="stBottomBlockContainer"] { background: transparent !important; padding-bottom: 2rem !important; max-width: 800px !important; margin: 0 auto !important; }
    [data-testid="stChatInput"] { background: rgba(20, 20, 30, 0.4) !important; border: 1px solid rgba(168, 85, 247, 0.4) !important; border-radius: 30px !important; backdrop-filter: blur(20px) !important; box-shadow: 0 0 20px rgba(168, 85, 247, 0.15) !important; }
    [data-testid="stChatInput"] > div, [data-testid="stChatInput"] div, [data-testid="stChatInput"] div[data-baseweb="base-input"], [data-testid="stChatInput"] div[data-baseweb="textarea"], [data-testid="stChatInput"] textarea, [data-testid="stChatInput"] input { background-color: transparent !important; border: none !important; outline: none !important; box-shadow: none !important; color: #ffffff !important; }
    [data-testid="stChatInput"]:focus-within { border: 1px solid rgba(168, 85, 247, 0.8) !important; box-shadow: 0 0 25px rgba(168, 85, 247, 0.3) !important; }
    audio, div[data-testid="stAudio"] { display: none !important; }
    
    [data-testid="stSidebar"] { background-color: #0b0b12 !important; border-right: 1px solid rgba(168, 85, 247, 0.15) !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-weight: 200 !important; letter-spacing: 2px; color: #e9d5ff !important; text-transform: uppercase; font-size: 14px !important; }
    [data-testid="stFileUploader"] { display: none !important; }
    [data-testid="stAudioInput"] { background-color: rgba(0, 242, 254, 0.05) !important; border: 1px solid rgba(0, 242, 254, 0.2) !important; border-radius: 15px !important; padding: 10px !important; }

    [data-testid="stSidebar"] button { background: rgba(168, 85, 247, 0.1) !important; color: #e9d5ff !important; border: 1px solid rgba(168, 85, 247, 0.3) !important; border-radius: 8px !important; text-align: center !important; transition: all 0.2s ease !important; }
    [data-testid="stSidebar"] button:hover { background: rgba(168, 85, 247, 0.3) !important; color: #ffffff !important; box-shadow: 0 0 10px rgba(168, 85, 247, 0.5) !important; }
    
    div[data-testid="stVerticalBlock"] > div:has(> div > div > div > button[kind="secondary"]) [data-testid="stSidebar"] button { background: transparent !important; border: none !important; text-align: left !important; color: #a78bfa !important; font-size: 14px !important; }
    div[data-testid="stVerticalBlock"] > div:has(> div > div > div > button[kind="secondary"]) [data-testid="stSidebar"] button:hover { background: rgba(168, 85, 247, 0.1) !important; }

    .streamlit-expanderHeader { background-color: rgba(255, 255, 255, 0.02) !important; border: 1px solid rgba(168, 85, 247, 0.2) !important; border-radius: 8px !important; color: #e9d5ff !important; font-size: 14px !important; }
    .streamlit-expanderContent { background-color: rgba(0, 0, 0, 0.2) !important; border: 1px solid rgba(168, 85, 247, 0.1) !important; border-top: none !important; }

    div[data-testid="stNotification"] { background-color: rgba(20, 20, 30, 0.85) !important; backdrop-filter: blur(15px) !important; border-radius: 10px !important; padding: 10px !important; margin-bottom: 10px !important; }
    div[data-testid="stNotification"]:has(div[data-testid="stNotificationContentSuccess"]) { border: 1px solid #34d399 !important; }
    div[data-testid="stNotification"]:has(div[data-testid="stNotificationContentSuccess"]) * { color: #a7f3d0 !important; font-size: 12px; }
    div[data-testid="stNotification"] svg { display: none !important; }
    
    @media (max-width: 768px) {
        .block-container { height: auto !important; overflow: auto !important; padding-bottom: 5rem !important; }
        .orb-wrapper { width: 180px; height: 180px; margin-bottom: 10px; } .orb-body { width: 150px; height: 150px; } .orb-glow { width: 180px; height: 180px; filter: blur(30px); }
        .nova-title { font-size: 24px; margin-top: 10px; } .nova-subtitle { font-size: 11px; }
        div[data-testid="stVerticalBlockBorderWrapper"] { height: 400px !important; margin-top: 20px; }
        [data-testid="stChatInput"] { width: 95% !important; margin: 0 auto !important; }
    }
</style>
""", unsafe_allow_html=True)

# --- INYECTAR GLOWS DE FONDO ---
st.markdown('<div class="glow-1"></div><div class="glow-2"></div><div class="glow-3"></div>', unsafe_allow_html=True)

# --- FUNCIONES DE AUDIO ---
async def generar_audio_edge(texto, voz):
    # 🔥 AQUÍ ESTÁ EL CAMBIO: +5% (Casi velocidad normal, con pausas naturales)
    comunicar = edge_tts.Communicate(texto, voz, rate="+5%")
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

# --- LÓGICA MULTI-CHAT ---
if "todos_los_chats" not in st.session_state:
    st.session_state.todos_los_chats = cargar_todos_los_chats()
    
if "chat_actual_id" not in st.session_state:
    st.session_state.chat_actual_id = datetime.datetime.now().strftime("%d/%m %H:%M")

if st.session_state.chat_actual_id not in st.session_state.todos_los_chats:
    st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []

if "audio_pendiente" not in st.session_state:
    st.session_state.audio_pendiente = None
if "mic_key" not in st.session_state:
    st.session_state.mic_key = 0
if "codigo_github" not in st.session_state:
    st.session_state.codigo_github = ""
if "archivo_cargado_nombre" not in st.session_state:
    st.session_state.archivo_cargado_nombre = ""

# --- SIDEBAR (HISTORIAL Y CONFIGURACIÓN) ---
with st.sidebar:
    if st.button("➕ Nuevo Chat", use_container_width=True):
        nuevo_id = datetime.datetime.now().strftime("%d/%m %H:%M")
        st.session_state.chat_actual_id = nuevo_id
        st.session_state.todos_los_chats[nuevo_id] = []
        st.rerun()

    st.markdown("### Historial")
    for chat_id in sorted(st.session_state.todos_los_chats.keys(), reverse=True):
        if len(st.session_state.todos_los_chats[chat_id]) > 0:
            prefijo = "👉 " if chat_id == st.session_state.chat_actual_id else "💬 "
            if st.button(f"{prefijo} {chat_id}", key=f"btn_{chat_id}", use_container_width=True):
                st.session_state.chat_actual_id = chat_id
                st.rerun()
    
    st.markdown("---")

    with st.expander("⚙️ Ajustes del Sistema", expanded=False):
        voz_activa = st.checkbox("🔊 Voz activa", value=True)
        
        st.markdown("---")
        st.markdown("#### 🐙 GitHub")
        token = st.secrets.get("GITHUB_TOKEN")
        usuario_github = "leivercontreras18-ux"

        if token:
            repos = obtener_repositorios(token, usuario_github)
            if repos:
                repo_seleccionado = st.selectbox("Repositorio", repos)
                archivos = obtener_archivos(usuario_github, repo_seleccionado, token)
                if archivos:
                    archivo_seleccionado = st.selectbox("Archivo", archivos)
                    if st.button("📥 Leer archivo", use_container_width=True):
                        with st.spinner("Descargando..."):
                            exito, resultado = descargar_archivo_github(usuario_github, repo_seleccionado, archivo_seleccionado, token)
                            if exito:
                                st.session_state.codigo_github = resultado
                                st.session_state.archivo_cargado_nombre = archivo_seleccionado
                                st.rerun()
                            else:
                                st.error(resultado)
                else:
                    st.info("No hay archivos válidos.")
            
            if st.session_state.archivo_cargado_nombre:
                st.success(f"✅ Leyendo: {st.session_state.archivo_cargado_nombre}")
        else:
            st.warning("Falta el token de GitHub.")

    st.markdown("---")
    if st.button("🗑️ Borrar este Chat", use_container_width=True):
        if st.session_state.chat_actual_id in st.session_state.todos_los_chats:
            del st.session_state.todos_los_chats[st.session_state.chat_actual_id]
            guardar_todos_los_chats(st.session_state.todos_los_chats)
        st.session_state.chat_actual_id = datetime.datetime.now().strftime("%d/%m %H:%M")
        st.session_state.todos_los_chats[st.session_state.chat_actual_id] = []
        st.rerun()

# --- CONEXIÓN CON GROQ ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("Error: Falta la API Key de Groq en los Secrets de Streamlit.")
    st.stop()

cliente = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- LAYOUT PRINCIPAL ---
col_izq, col_der = st.columns([1, 1.2], gap="large")

with col_izq:
    st.markdown(f"""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 70vh;">
        <div class="orb-wrapper">
            <div class="orb-glow"></div>
            <div class="orb-body">
                <div class="orb-inner"></div>
            </div>
        </div>
        <div class="nova-title">{NOMBRE_IA.upper()}</div>
        <div class="nova-subtitle">How can I help you today?</div>
    </div>
    """, unsafe_allow_html=True)

with col_der:
    with st.container(border=True, height=550):
        mensajes_actuales = st.session_state.todos_los_chats[st.session_state.chat_actual_id]
        for message in mensajes_actuales:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

# --- PROCESAMIENTO DE ENTRADA ---
prompt = st.chat_input(f"Ask {NOMBRE_IA}...")

if prompt:
    texto_usuario = prompt
    
    if texto_usuario:
        st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "user", "content": texto_usuario})
        guardar_todos_los_chats(st.session_state.todos_los_chats)
        
        codigo_actual = st.session_state.codigo_github
        
        if len(codigo_actual) > 10000: 
            codigo_actual_para_groq = codigo_actual[:10000] + "\n\n...[Código truncado por ser muy largo]..."
        else:
            codigo_actual_para_groq = codigo_actual

        tz_venezuela = timezone(timedelta(hours=-4))
        ahora = datetime.datetime.now(tz_venezuela)
        fecha_hora_str = ahora.strftime("%A, %d de %B de %Y, a las %I:%M %p")
        dias = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"}
        meses = {"January": "Enero", "February": "Febrero", "March": "Marzo", "April": "Abril", "May": "Mayo", "June": "Junio", "July": "Julio", "August": "Agosto", "September": "Septiembre", "October": "Octubre", "November": "Noviembre", "December": "Diciembre"}
        for en, es in dias.items(): fecha_hora_str = fecha_hora_str.replace(en, es)
        for en, es in meses.items(): fecha_hora_str = fecha_hora_str.replace(en, es)

        instrucciones = f"""Eres {NOMBRE_IA}, una asistente de inteligencia artificial avanzada, pero actúas como una amiga muy inteligente, cercana y carismática. Tienes un toque de humor natural y eres empática.
        
        REGLA DE ORO: DEBES RESPONDER SIEMPRE EN ESPAÑOL.
        
        CONTEXTO TEMPORAL: Hoy es {fecha_hora_str} (Hora de Venezuela, UTC-4).
        
        CONTEXTO DEL USUARIO: Tu usuario se llama Leiver, vive en Venezuela y es sumamente curioso y preguntón. Trabaja en proyectos de programación.
        
        REGLA DE PROGRAMACIÓN QUIRÚRGICA: 
        Cuando Leiver te pida cambiar o agregar algo en su código, NUNCA le devuelvas el archivo completo. Dile exactamente:
        1. "Borra desde la línea X hasta la línea Y".
        2. Luego, dale el bloque de código exacto que debe pegar.
        
        CÓMO DEBES ESCRIBIR (PARA EL CHAT):
        - Escribe de forma natural, cálida y conversacional.
        - Usa buena ortografía, comas y puntos donde corresponda.
        - Puedes usar emojis finos (😊, 🚀, 💡, ✨) para darle vida a tus respuestas.
        - SI ALGO ES GRACIOSO, RÍETE DE FORMA NATURAL. Escribe "jajaja" o "jejeje" cuando lo amerite."""
        
        if codigo_actual_para_groq:
            instrucciones += f"\n\nEl usuario está trabajando con el siguiente código:\n```\n{codigo_actual_para_groq}\n```"

        mensajes_para_groq = [{"role": "system", "content": instrucciones}]
        for msg in mensajes_actuales:
            mensajes_para_groq.append({"role": msg["role"], "content": msg["content"]})
        mensajes_para_groq.append({"role": "user", "content": texto_usuario})

        try:
            with st.spinner("Pensando..."):
                respuesta = cliente.chat.completions.create(
                    model="openai/gpt-oss-20b", 
                    messages=mensajes_para_groq,
                    temperature=0.9, 
                    max_tokens=1024
                )
                
                texto_respuesta = respuesta.choices[0].message.content
                
                st.session_state.todos_los_chats[st.session_state.chat_actual_id].append({"role": "assistant", "content": texto_respuesta})
                guardar_todos_los_chats(st.session_state.todos_los_chats)
                
                if voz_activa: 
                    try:
                        texto_para_hablar = limpiar_texto_para_voz(texto_respuesta)
                        audio_buffer = asyncio.run(generar_audio_edge(texto_para_hablar, VOZ_FIJA))
                        st.session_state.audio_pendiente = audio_buffer
                    except Exception as e:
                        print(f"Error de voz: {e}")
                
                st.session_state.mic_key += 1
                st.rerun()
            
        except Exception as e:
            st.error(f"Error de Groq: {e}")

if st.session_state.audio_pendiente:
    autoplay_audio(st.session_state.audio_pendiente)
    st.session_state.audio_pendiente = None