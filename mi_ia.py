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
VERSION = "v17.0 - Exact SaaS Replica"
ARCHIVO_CHATS = "chats_lili.json"

st.set_page_config(page_title=NOMBRE_IA, page_icon="✨", layout="wide")

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

# --- CSS AVANZADO (RÉPLICA EXACTA DE LA FOTO) ---
st.markdown("""
<style>
    /* 1. FONDO CON MONTAÑA Y CAPA OSCURA */
    .stApp {
        background-image: url('https://images.unsplash.com/photo-1534447677768-be436bb09401?q=80&w=2094&auto=format&fit=crop'); 
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        background-color: #000000; 
    }
    .stApp::before {
        content: "";
        position: fixed; inset: 0;
        background: rgba(20, 10, 35, 0.6); /* Tinte morado oscuro */
        z-index: -1;
    }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header { background: transparent !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }

    /* 2. BARRA LATERAL FLOTANTE (Como en la foto) */
    [data-testid="stSidebar"] {
        background-color: #1a1a1f !important;
        border: 1px solid #2d2d35 !important;
        border-radius: 16px !important;
        margin: 20px 0 20px 20px !important;
        height: calc(100vh - 40px) !important;
        padding: 15px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
    
    /* Títulos de la barra lateral */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { 
        font-weight: 600 !important; color: #a1a1aa !important; font-size: 11px !important; 
        text-transform: uppercase; letter-spacing: 1px !important; margin: 15px 0 5px 0 !important;
    }
    
    /* Botones de la barra lateral (Texto plano como en la foto) */
    [data-testid="stSidebar"] button {
        background: transparent !important; color: #e4e4e7 !important; border: none !important;
        text-align: left !important; border-radius: 8px !important; padding: 8px 10px !important;
        margin-bottom: 2px !important; font-weight: 500 !important; font-size: 13px !important;
    }
    [data-testid="stSidebar"] button:hover { background: #27272a !important; color: white !important; }
    
    /* Botón de Nuevo Chat (Destacado) */
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:first-child button {
        background: #27272a !important; color: white !important; border: 1px solid #3f3f46 !important;
        text-align: center !important; font-size: 13px !important; margin-bottom: 20px !important;
    }

    /* 3. ÁREA CENTRAL (Orbe, texto, input, tarjetas) */
    .main-container {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100vh;
        margin-left: 280px; /* Espacio para la barra lateral */
        padding-bottom: 80px;
    }

    .saas-orb {
        width: 40px; height: 40px; border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #ffffff, #a78bfa, #4c1d95);
        box-shadow: 0 0 30px #8b5cf6, inset 0 0 10px #ffffff;
        margin-bottom: 20px;
    }
    .welcome-text { font-size: 26px; font-weight: 500; color: white; margin-bottom: 30px; font-family: sans-serif; }
    
    /* Píldoras de arriba del input */
    .pill-container { display: flex; gap: 10px; margin-bottom: 15px; }
    .pill { 
        background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); 
        padding: 6px 14px; border-radius: 20px; color: #d4d4d8; font-size: 12px;
    }

    /* 4. EL INPUT DE CHAT FLOTANTE */
    [data-testid="stBottomBlockContainer"] {
        background: transparent !important;
        position: fixed !important;
        top: 55% !important; /* Lo ponemos en el medio */
        left: 60% !important;
        transform: translate(-50%, -50%) !important;
        width: 100% !important; max-width: 650px !important;
        padding: 0 !important;
        z-index: 1000;
    }
    .stChatInput {
        background: #131316 !important;
        border: 1px solid #3f3f46 !important;
        border-radius: 16px !important;
        box-shadow: 0 10px 40px rgba(0,0,0,0.8) !important;
        padding: 5px !important;
    }
    [data-testid="stChatInput"] textarea { color: white !important; font-size: 14px !important; padding: 15px !important; }
    [data-testid="stChatInput"] button {
        background: #8b5cf6 !important; color: white !important; border-radius: 10px !important;
        width: 35px !important; height: 35px !important; margin: 10px !important;
    }

    /* 5. TARJETAS INFERIORES */
    .card-container { display: flex; gap: 15px; position: fixed; bottom: 30px; left: 60%; transform: translateX(-50%); width: 100%; max-width: 700px; z-index: 10; }
    .saas-card {
        background: rgba(24, 24, 27, 0.8); border: 1px solid #27272a; border-radius: 12px;
        padding: 15px; flex: 1; backdrop-filter: blur(10px);
    }
    .card-title { color: white; font-size: 12px; font-weight: 600; margin-bottom: 5px; }
    .card-desc { color: #a1a1aa; font-size: 10px; line-height: 1.3; margin-bottom: 10px; }
    .card-btn { background: #27272a; color: #e4e4e7; font-size: 9px; padding: 4px 8px; border-radius: 4px; border: 1px solid #3f3f46; display: inline-block; }
    
    /* Ocultar audios y ajustar chat cuando ya hay mensajes */
    audio, div[data-testid="stAudio"] { display: none !important; }
    
    /* Si hay mensajes, movemos el input abajo de nuevo */
    .chat-mode [data-testid="stBottomBlockContainer"] {
        top: auto !important;
        bottom: 20px !important;
    }
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
    st.markdown("<h2 style='color: white; font-size: 18px; font-weight: 600; display: flex; align-items: center; gap: 8px;'>✨ Lili AI</h2>", unsafe_allow_html=True)
    
    if st.button("➕ New Chat", use_container_width=True):
        nuevo_id = datetime.datetime.now().strftime("%d/%m %H:%M")
        st.session_state.chat_actual_id = nuevo_id
        st.session_state.todos_los_chats[nuevo_id] = []
        st.rerun()

    st.markdown("Features")
    st.button("💬 Chat", use_container_width=True)
    st.button("📦 Archived", use_container_width=True)
    st.button("📚 Library", use_container_width=True)
    
    st.markdown("Workspaces")
    st.button("📁 New Project", use_container_width=True)
    
    st.markdown("Historial")
    for chat_id in sorted(st.session_state.todos_los_chats.keys(), reverse=True):
        if len(st.session_state.todos_los_chats[chat_id]) > 0:
            prefijo = "🟣" if chat_id == st.session_state.chat_actual_id else "⚪"
            if st.button(f"{prefijo} {chat_id}", key=f"btn_{chat_id}", use_container_width=True):
                st.session_state.chat_actual_id = chat_id
                st.rerun()

    # Ajustes
    with st.expander("⚙️ Configuración"):
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
                    if st.button("📥 Leer de GitHub", use_container_width=True):
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

# Si no hay mensajes, mostramos la interfaz exacta de la foto
if len(mensajes_actuales) == 0:
    st.markdown("""
        <div class="main-container">
            <div class="saas-orb"></div>
            <div class="welcome-text">Ready to Create Something New?</div>
            <div class="pill-container">
                <div class="pill">✨ Create Image</div>
                <div class="pill">🧠 Brainstorm</div>
                <div class="pill">📝 Make a plan</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Las 3 tarjetas de abajo
    st.markdown("""
        <div class="card-container">
            <div class="saas-card">
                <div class="card-title">🖼️ Image Generator</div>
                <div class="card-desc">Create high-quality images instantly from text.</div>
                <div class="card-btn">Generate Image</div>
            </div>
            <div class="saas-card">
                <div class="card-title">📊 AI Presentation</div>
                <div class="card-desc">Turn ideas into engaging presentations.</div>
                <div class="card-btn">Make Slides</div>
            </div>
            <div class="saas-card">
                <div class="card-title">💻 Dev Assistant</div>
                <div class="card-desc">Generate clean, production-ready code.</div>
                <div class="card-btn">Generate Code</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Si ya hay mensajes, mostramos el chat normal
else:
    # Clase CSS para bajar el input cuando ya hay chat
    st.markdown("<style>.stChatInput { top: auto !important; bottom: 20px !important; }</style>", unsafe_allow_html=True)
    
    st.markdown("<div style='margin-left: 280px; padding: 20px; max-width: 800px; margin-top: 20px;'>", unsafe_allow_html=True)
    for message in mensajes_actuales:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    st.markdown("</div>", unsafe_allow_html=True)

# --- PROCESAMIENTO DE ENTRADA ---
prompt = st.chat_input("Ask Anything...")

# Micrófono oculto en el sidebar pero funcional
with st.sidebar:
    with st.expander("🎤 Voz"):
        audio_grabado = st.audio_input("Graba tu mensaje", key=f"mic_{st.session_state.mic_key}", label_visibility="collapsed")

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
        CONTEXTO DEL USUARIO: Te habla Leiver, de Venezuela. Eres su asistente de programación.
        REGLA DE PROGRAMACIÓN: NUNCA devuelvas archivos completos. Dile: "Borra desde la línea X hasta la Y" y dale el bloque de código exacto."""
        
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