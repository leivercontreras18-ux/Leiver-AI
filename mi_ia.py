import streamlit as st
import io
import asyncio
import base64
import re
import uuid
import threading
import requests
import edge_tts
import urllib.parse
from groq import Groq
from supabase import create_client

# =====================================================================
# CONFIGURACIÓN
# =====================================================================
NOMBRE_IA = "Lili"
VOZ_FIJA = "es-VE-PaolaNeural"
VERSION = "v44.2 - Copys Mejorados y Estables"

USUARIO_GITHUB = "leivercontreras18-ux"
REPO_DEFECTO = "leiver-ai"

MODELO_TEXTO = "openai/gpt-oss-120b"
MODELO_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"

MAX_ARCHIVOS_RAG = 60
MAX_BYTES_ARCHIVO = 60_000

MODOS_CHAT = ["Programación", "Chat General"]
MODOS_STUDIO = ["Modo Moda", "YouTube Kids"]

st.set_page_config(page_title=NOMBRE_IA, page_icon="✨", layout="wide")

# =====================================================================
# CLIENTES (Groq y Supabase)
# =====================================================================
for clave in ("GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"):
    if clave not in st.secrets:
        st.error(f"Falta el secreto {clave} en Streamlit.")
        st.stop()

@st.cache_resource
def get_groq():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])

@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

cliente = get_groq()
sb = get_supabase()

# =====================================================================
# BASE DE DATOS (Supabase)
# =====================================================================
def db_listar_chats(modo):
    try:
        r = sb.table("chats").select("id,titulo").eq("modo", modo).order("creado_en", desc=True).limit(30).execute()
        return r.data or []
    except Exception as e:
        st.sidebar.error(f"Error leyendo chats: {e}")
        return []

def db_crear_chat(modo, titulo="Nuevo chat"):
    chat_id = uuid.uuid4().hex
    sb.table("chats").insert({"id": chat_id, "modo": modo, "titulo": titulo}).execute()
    return chat_id

def db_cargar_mensajes(chat_id):
    try:
        r = sb.table("mensajes").select("role,content").eq("chat_id", chat_id).order("creado_en").execute()
        return r.data or []
    except Exception as e:
        st.error(f"Error cargando mensajes: {e}")
        return []

def db_guardar_mensaje(chat_id, role, content):
    try:
        sb.table("mensajes").insert({"chat_id": chat_id, "role": role, "content": content}).execute()
    except Exception as e:
        st.warning(f"No se pudo guardar el mensaje: {e}")

def db_borrar_chat(chat_id):
    try:
        sb.table("chats").delete().eq("id", chat_id).execute()
    except Exception as e:
        st.sidebar.error(f"No se pudo borrar: {e}")

# =====================================================================
# GITHUB (RAG)
# =====================================================================
def _headers(token):
    return {"Authorization": f"token {token}"}

def obtener_repositorios(token):
    res = requests.get("https://api.github.com/user/repos?per_page=100&sort=updated", headers=_headers(token), timeout=15)
    return [r["name"] for r in res.json()] if res.status_code == 200 else []

def obtener_archivos_codigo(usuario, repo, token):
    info = requests.get(f"https://api.github.com/repos/{usuario}/{repo}", headers=_headers(token), timeout=15)
    if info.status_code != 200: return []
    rama = info.json().get("default_branch", "main")
    res = requests.get(f"https://api.github.com/repos/{usuario}/{repo}/git/trees/{rama}?recursive=1", headers=_headers(token), timeout=20)
    if res.status_code != 200: return []
    ext = (".py", ".html", ".css", ".js", ".md", ".txt")
    return [f["path"] for f in res.json().get("tree", []) if f["type"] == "blob" and f["path"].endswith(ext) and f.get("size", 0) <= MAX_BYTES_ARCHIVO][:MAX_ARCHIVOS_RAG]

def descargar_archivo_github(usuario, repo, archivo, token):
    res = requests.get(f"https://api.github.com/repos/{usuario}/{repo}/contents/{archivo}", headers=_headers(token), timeout=15)
    if res.status_code == 200:
        return True, base64.b64decode(res.json()["content"]).decode("utf-8", errors="ignore")
    return False, ""

# =====================================================================
# MOTOR RAG (ChromaDB)
# =====================================================================
@st.cache_resource
def obtener_cliente_chroma():
    import chromadb
    return chromadb.Client()

def chunk_texto(texto, tamano=1500, solapamiento=200):
    return [texto[i:i + tamano] for i in range(0, len(texto), tamano - solapamiento)]

def indexar_repositorio(usuario, repo, token):
    cli = obtener_cliente_chroma()
    try: cli.delete_collection("codigo_repo")
    except Exception: pass
    coleccion = cli.create_collection("codigo_repo")
    archivos = obtener_archivos_codigo(usuario, repo, token)
    if not archivos: return False
    docs, metas, ids = [], [], []
    for archivo in archivos:
        ok, contenido = descargar_archivo_github(usuario, repo, archivo, token)
        if ok and contenido:
            for pedazo in chunk_texto(contenido):
                docs.append(pedazo)
                metas.append({"archivo": archivo})
                ids.append(f"id_{len(ids)}")
    if docs: coleccion.add(documents=docs, metadatas=metas, ids=ids)
    return True

def buscar_contexto_codigo(pregunta):
    try:
        res = obtener_cliente_chroma().get_collection("codigo_repo").query(query_texts=[pregunta], n_results=4)
        return "".join(f"\n\n--- Archivo: {m['archivo']} ---\n{d}" for d, m in zip(res["documents"][0], res["metadatas"][0]))
    except Exception: return "No se encontró contexto de código."

# =====================================================================
# AUDIO
# =====================================================================
def generar_audio_seguro(texto, voz):
    buffer = io.BytesIO()
    def tarea():
        try:
            async def generar():
                async for chunk in edge_tts.Communicate(texto, voz, rate="+8%").stream():
                    if chunk["type"] == "audio": buffer.write(chunk["data"])
            asyncio.run(generar())
        except Exception: pass
    hilo = threading.Thread(target=tarea)
    hilo.start(); hilo.join(); buffer.seek(0)
    return buffer

def limpiar_texto_para_voz(texto):
    return re.sub(r"\s+", " ", re.sub(r"[*#_`]", "", texto)).strip()

# =====================================================================
# LLM
# =====================================================================
def llamar_llm(mensajes, modelo=MODELO_TEXTO, temperatura=0.7, max_tokens=2048):
    r = cliente.chat.completions.create(model=modelo, messages=mensajes, temperature=temperatura, max_tokens=max_tokens)
    return r.choices[0].message.content

# =====================================================================
# CSS
# =====================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');
    :root { --bg: #0e121b; --surface: rgba(255,255,255,0.03); --border: rgba(255,255,255,0.07); --cyan: #00e5ff; --muted: #8a99ad; --text: #e6edf7; }
    .stApp { background: radial-gradient(circle at 65% 0%, #1b2436 0%, var(--bg) 60%) !important; color: var(--text) !important; font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif; }
    #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
    header { background: transparent !important; }
    .block-container { padding-top: 1.5rem !important; padding-bottom: 7rem !important; max-width: 920px !important; }
    [data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }
    [data-testid="stChatInput"] { background: rgba(24,29,40,0.85) !important; border: 1px solid rgba(0,229,255,0.18) !important; border-radius: 28px !important; box-shadow: 0 8px 30px rgba(0,0,0,0.35) !important; backdrop-filter: blur(10px); transition: all .25s ease; }
    [data-testid="stChatInput"]:focus-within { border-color: var(--cyan) !important; box-shadow: 0 8px 30px rgba(0,0,0,0.4), 0 0 0 3px rgba(0,229,255,0.12) !important; }
    [data-testid="stChatInput"] > div, [data-testid="stChatInput"] [data-baseweb="textarea"], [data-testid="stChatInput"] [data-baseweb="base-input"] { background: transparent !important; border: none !important; }
    [data-testid="stChatInput"] textarea { color: var(--text) !important; background: transparent !important; }
    [data-testid="stChatInputSubmitButton"] { background: rgba(0,229,255,0.15) !important; color: var(--cyan) !important; border-radius: 50% !important; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #0f1420 0%, #0b0f17 100%) !important; border-right: 1px solid var(--border) !important; min-width: 290px !important; }
    [data-testid="stSidebarUserContent"] { padding: 1.4rem 0.9rem !important; }
    .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: .2em; font-size: 1.05rem; color: #fff; padding-left: 6px; }
    .brand-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 14px var(--cyan); }
    .brand-ver { color: #5d6b80; font-size: .7rem; margin: 4px 0 0 26px; }
    .side-label { font-size: .66rem; letter-spacing: .16em; font-weight: 600; color: #5d6b80; margin: 22px 0 6px 8px; text-transform: uppercase; }
    [data-testid="stSidebar"] .stButton button { width: 100%; justify-content: flex-start !important; gap: 10px; background: transparent !important; border: 1px solid transparent !important; color: var(--muted) !important; border-radius: 10px !important; padding: 8px 14px !important; font-weight: 500 !important; font-size: .92rem !important; transition: all .2s ease; }
    [data-testid="stSidebar"] .stButton button > div { justify-content: flex-start !important; width: 100%; }
    [data-testid="stSidebar"] .stButton button p { text-align: left !important; margin: 0 !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    [data-testid="stSidebar"] .stButton button:hover { background: rgba(255,255,255,0.05) !important; color: #fff !important; }
    [data-testid="stSidebar"] .stButton button[kind="primary"] { background: rgba(0,229,255,0.10) !important; border: 1px solid rgba(0,229,255,0.28) !important; color: var(--cyan) !important; }
    [data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: 12px !important; background: var(--surface) !important; }
    [data-testid="stChatMessage"] { background: rgba(24,29,40,0.6) !important; backdrop-filter: blur(12px); border-radius: 16px !important; padding: 14px 20px !important; margin-bottom: 14px !important; border: 1px solid var(--border) !important; width: fit-content !important; max-width: 82% !important; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { margin-left: auto !important; background: linear-gradient(135deg, rgba(0,229,255,0.12), rgba(0,119,255,0.10)) !important; border-color: rgba(0,229,255,0.2) !important; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) { margin-right: auto !important; border-left: 3px solid var(--cyan) !important; }
    [data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
    [data-testid="stFileUploaderDropzone"] { background: rgba(24,29,40,0.5) !important; border: 1px dashed rgba(0,229,255,0.25) !important; border-radius: 12px !important; }
    .center-display { display: flex; flex-direction: column; align-items: center; margin-top: 3vh; padding: 20px 0 0; }
    .reactor { position: relative; width: 170px; height: 170px; display: flex; align-items: center; justify-content: center; }
    .reactor-ring-outer { position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(0,229,255,0.1); border-top: 2px solid var(--cyan); border-bottom: 2px solid var(--cyan); animation: spin 3s linear infinite; opacity: .35; }
    .reactor-ring-mid { position: absolute; inset: 18px; border-radius: 50%; border: 1px dashed rgba(0,229,255,0.25); animation: spin-reverse 8s linear infinite; opacity: .35; }
    .reactor-core { width: 64px; height: 64px; border-radius: 50%; background: radial-gradient(circle, #fff 0%, var(--cyan) 40%, #0077ff 100%); box-shadow: 0 0 45px var(--cyan), inset 0 0 18px #fff; animation: pulse 2s ease-in-out infinite; z-index: 10; }
    .display-text { margin-top: 22px; font-size: 11px; letter-spacing: 4px; color: var(--cyan); text-transform: uppercase; font-weight: 600; font-family: 'JetBrains Mono', monospace; background: rgba(24,29,40,0.8); padding: 6px 16px; border-radius: 20px; border: 1px solid rgba(0,229,255,0.3); }
    .hero-title { text-align: center; font-size: 2.1rem; font-weight: 700; margin: 22px 0 4px; background: linear-gradient(90deg, #fff, #9fdcff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .hero-sub { text-align: center; color: var(--muted); font-size: .98rem; margin-bottom: 26px; }
    @keyframes spin { 100% { transform: rotate(360deg); } }
    @keyframes spin-reverse { 100% { transform: rotate(-360deg); } }
    @keyframes pulse { 0%,100% { transform: scale(0.95); } 50% { transform: scale(1.05); } }
    .st-key-quick button { background: rgba(24,29,40,0.6) !important; border: 1px solid var(--border) !important; border-radius: 14px !important; color: #cfd8e6 !important; padding: 14px 16px !important; min-height: 74px; height: 100%; text-align: left !important; justify-content: flex-start !important; transition: all .2s ease; }
    .st-key-quick button p { text-align: left !important; font-size: .88rem; }
    .st-key-quick button:hover { border-color: var(--cyan) !important; background: rgba(0,229,255,0.06) !important; color: #fff !important; transform: translateY(-2px); }
    .dash-card { background: rgba(24,29,40,0.5); border: 1px solid var(--border); border-radius: 16px; padding: 24px; text-align: center; height: 100%; transition: .3s; }
    .dash-card:hover { border-color: var(--cyan); background: rgba(0,229,255,0.05); transform: translateY(-3px); }
    .dash-icon { font-size: 38px; margin-bottom: 14px; }
    .dash-title { font-size: 17px; font-weight: 700; margin-bottom: 8px; }
    .dash-desc { font-size: 13px; color: var(--muted); line-height: 1.5; }
    .badge-soon { background: rgba(255,165,0,0.15); color: #ffa500; border: 1px solid rgba(255,165,0,.5); border-radius: 20px; padding: 4px 12px; font-size: 11px; font-weight: 600; display: inline-block; margin-top: 14px; text-transform: uppercase; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# ESTADO
# =====================================================================
S = st.session_state
S.setdefault("modo_actual", "Programación")
S.setdefault("chat_id", None)
S.setdefault("cache_mensajes", {})
S.setdefault("audio_pendiente", None)
S.setdefault("mic_key", 0)
S.setdefault("uploader_key", 0)
S.setdefault("repo_seleccionado", REPO_DEFECTO)
S.setdefault("repo_indexado", None)

def cambiar_modo(modo):
    S.modo_actual = modo
    S.chat_id = None

def abrir_chat(chat_id):
    S.chat_id = chat_id
    S.cache_mensajes[chat_id] = db_cargar_mensajes(chat_id)

# =====================================================================
# SIDEBAR
# =====================================================================
token_gh = st.secrets.get("GITHUB_TOKEN")

with st.sidebar:
    st.markdown(f"<div class='brand'><span class='brand-dot'></span>LILI OS</div><div class='brand-ver'>{VERSION}</div>", unsafe_allow_html=True)

    st.markdown("<div class='side-label'>Chats</div>", unsafe_allow_html=True)
    for modo, icono in (("Programación", ":material/terminal:"), ("Chat General", ":material/chat_bubble:")):
        if st.button(modo, key=f"menu_{modo}", icon=icono, use_container_width=True,
                     type="primary" if S.modo_actual == modo else "secondary"):
            cambiar_modo(modo); st.rerun()

    st.markdown("<div class='side-label'>Studios</div>", unsafe_allow_html=True)
    for modo, icono in (("Modo Moda", ":material/checkroom:"), ("YouTube Kids", ":material/movie:")):
        if st.button(modo, key=f"menu_{modo}", icon=icono, use_container_width=True,
                     type="primary" if S.modo_actual == modo else "secondary"):
            cambiar_modo(modo); st.rerun()

    if S.modo_actual in MODOS_CHAT:
        st.markdown("<div class='side-label'>Historial</div>", unsafe_allow_html=True)
        if st.button("Nuevo chat", key="nuevo_chat", icon=":material/add:", use_container_width=True):
            S.chat_id = None; st.rerun()
        for c in db_listar_chats(S.modo_actual):
            col_a, col_b = st.columns([5, 1])
            if col_a.button(c["titulo"] or "Chat", key=f"chat_{c['id']}", use_container_width=True,
                            type="primary" if S.chat_id == c["id"] else "secondary"):
                abrir_chat(c["id"]); st.rerun()
            if col_b.button("✕", key=f"del_{c['id']}", help="Borrar chat"):
                db_borrar_chat(c["id"])
                if S.chat_id == c["id"]: S.chat_id = None
                st.rerun()

    if S.modo_actual == "Programación" and token_gh:
        repos = obtener_repositorios(token_gh)
        if repos:
            idx = repos.index(S.repo_seleccionado) if S.repo_seleccionado in repos else 0
            st.markdown("<div class='side-label'>Repositorio</div>", unsafe_allow_html=True)
            repo_sel = st.selectbox("Repo", repos, index=idx, label_visibility="collapsed")
            if repo_sel != S.repo_seleccionado:
                S.repo_seleccionado = repo_sel
                S.repo_indexado = None
                st.rerun()

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    with st.expander("Configuración", icon=":material/settings:"):
        voz_activa = st.checkbox("Voz activa", value=True)
        audio_grabado = st.audio_input("Graba", key=f"mic_{S.mic_key}", label_visibility="collapsed")

# =====================================================================
# STUDIOS
# =====================================================================
def tarjeta(icono, titulo, desc, estado="En Desarrollo"):
    st.markdown(f"""<div class="dash-card"><div class="dash-icon">{icono}</div><div class="dash-title">{titulo}</div>
    <div class="dash-desc">{desc}</div><div class="badge-soon">{estado}</div></div>""", unsafe_allow_html=True)

def render_modo_moda():
    st.markdown("<h2 style='text-align:center;'>🛍️ Studio: Modo Moda</h2>", unsafe_allow_html=True)
    tab_copy, tab_guion, tab_foto = st.tabs(["✍️ Copy para Redes", "🎬 Guiones de Video", "📸 Generador de Fotos"])

    with tab_copy:
        st.markdown("### ✍️ Generador de Copys para Redes")
        col1, col2 = st.columns(2)
        with col1:
            producto = st.text_input("Prenda / producto", placeholder="Vestido satinado verde esmeralda", key="moda_prod")
        with col2:
            plataforma = st.selectbox("Plataforma", ["Instagram (Feed)", "Instagram (Stories/Reels)", "WhatsApp", "TikTok"], key="moda_plataforma")
            
        precio = st.text_input("Precio (opcional)", key="moda_precio")
        tono = st.selectbox("Tono", ["Elegante y exclusivo", "Cercano y amigable", "Divertido y juvenil", "Urgente (Oferta)"], key="moda_tono")
        
        if st.button("Generar 3 Opciones de Copy", key="moda_copy_btn") and producto:
            with st.spinner("Escribiendo opciones de venta..."):
                prompt_copy = f"""
                Eres un experto copywriter de moda para 'Lewin Boutique', una tienda online en Venezuela.
                Producto: {producto}
                Plataforma: {plataforma}
                Precio: {precio or 'No especificado'}
                Tono: {tono}
                
                Genera exactamente 3 opciones de copy diferentes, separadas por líneas:
                
                **Opción 1: Directa (Corta)**
                [Texto corto, de 2 a 3 líneas. Máximo 5 emojis. Llamado a la acción claro]
                
                **Opción 2: Storytelling (Más larga)**
                [Texto de 4 a 6 líneas contando una historia, resaltando la calidad o cómo hace sentir la prenda. Incluye emojis]
                
                **Opción 3: Enfoque de Venta/Urgencia**
                [Texto enfocado en escasez, oferta o beneficio inmediato. Llamado a la acción fuerte]
                
                Al final de las 3 opciones, agrega una sección llamada **Hashtags** con 10 hashtags mezclando moda en Venezuela, ropa, y estilo.
                """
                
                resultado = llamar_llm([
                    {"role": "system", "content": "Eres un copywriter experto en ventas de moda. Responde en español y usa formato Markdown para organizar el texto."},
                    {"role": "user", "content": prompt_copy}
                ])
                st.markdown(resultado)

    with tab_guion:
        idea = st.text_input("Prenda o idea del video", key="moda_idea")
        if st.button("Generar guion de 15 s", key="moda_guion_btn") and idea:
            with st.spinner("Escribiendo..."):
                st.markdown(llamar_llm([
                    {"role": "system", "content": "Eres guionista de Reels/TikTok de moda. Responde en español."},
                    {"role": "user", "content": f"Guion de 15 segundos para: {idea}. Tabla con: segundo, escena, texto en pantalla, voz en off."}]))

    with tab_foto:
        st.markdown("### 🎨 Generador de Imágenes de Moda")
        st.markdown("Describe la foto que necesitas y Lili la creará para ti. *(Nota: La versión gratuita permite 1 foto cada 45 segundos).*")
        descripcion_foto = st.text_input("Describe la foto:", placeholder="Ej: Vestido rojo de verano, modelo en la playa, luz de atardecer")
        estilo = st.selectbox("Estilo", ["Fotografía realista", "Estilo 3D (Pixar)", "Ilustración de moda", "Fondo de estudio limpio"])
        
        if st.button("Generar Foto", key="moda_foto_btn") and descripcion_foto:
            with st.spinner("🎨 Lili está diseñando tu imagen... (esto toma unos segundos)"):
                prompt_artistico = llamar_llm([
                    {"role": "system", "content": "You are a world-class fashion photographer and AI prompt engineer. Translate the user's idea into a highly detailed, professional image generation prompt in English. You MUST include technical terms like '8k resolution, photorealistic, cinematic lighting, fashion editorial, shot on 35mm lens, highly detailed'. Output ONLY the prompt, no extra text."},
                    {"role": "user", "content": f"Product: {descripcion_foto}. Style: {estilo}. Make it look incredibly professional for a high-end clothing brand."}
                ], temperatura=0.6)
                
                prompt_codificado = urllib.parse.quote(prompt_artistico)
                
                url_imagen = f"https://image.pollinations.ai/prompt/{prompt_codificado}?width=1024&height=1024&nologo=true&model=flux"
                
                st.image(url_imagen, caption=f"Generado por Lili para: {descripcion_foto}", use_container_width=True)
                with st.expander("Ver Prompt Técnico usado por Lili"):
                    st.code(prompt_artistico, language="text")

def render_youtube_kids():
    st.markdown("<h2 style='text-align:center;'>🎬 Studio: YouTube Kids</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: tarjeta("📝", "Guiones Mágicos", "Cuentos infantiles con moraleja, rimas y personajes consistentes.")
    with c2: tarjeta("🗣️", "Voces de Personajes", "Audio del cuento con voces tiernas o narradores de película.")
    with c3: tarjeta("🎨", "Director de Arte 3D", "Imágenes escena por escena para montar en CapCut o Canva.")

STUDIOS = {"Modo Moda": render_modo_moda, "YouTube Kids": render_youtube_kids}

if S.modo_actual in STUDIOS:
    STUDIOS[S.modo_actual]()
    st.stop()

# =====================================================================
# CHAT (Programación / Chat General)
# =====================================================================
mensajes = S.cache_mensajes.get(S.chat_id, []) if S.chat_id else []

for m in mensajes:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

SUGERENCIAS = {
    "Programación": ["Revisa mi repositorio y dime qué puedo mejorar",
                     "Explícame cómo funciona el código principal",
                     "Ayúdame a encontrar y corregir un error"],
    "Chat General": ["Dame ideas de contenido para Lewin Boutique",
                     "Ayúdame a organizar mi semana de trabajo",
                     "Redacta un mensaje amable para un cliente"],
}

def usar_sugerencia(texto):
    S.prompt_rapido = texto

if not mensajes:
    es_prog = S.modo_actual == "Programación"
    st.markdown(f"""
        <div class="center-display">
            <div class="reactor"><div class="reactor-ring-outer"></div><div class="reactor-ring-mid"></div><div class="reactor-core"></div></div>
            <div class="display-text">{"DEV ENVIRONMENT" if es_prog else "SYSTEM ONLINE"}</div>
        </div>
        <div class="hero-title">Hola, Leiver</div>
        <div class="hero-sub">{"Tu entorno de desarrollo está listo. ¿Qué construimos hoy?" if es_prog else "¿Qué hacemos hoy?"}</div>
    """, unsafe_allow_html=True)
    with st.container(key="quick"):
        cols = st.columns(3)
        for col, texto in zip(cols, SUGERENCIAS[S.modo_actual]):
            col.button(texto, key=f"sug_{texto}", on_click=usar_sugerencia, args=(texto,), use_container_width=True)

with st.expander("Adjuntar imagen", icon=":material/attach_file:"):
    imagen_subida = st.file_uploader("Adjuntar imagen", type=["png", "jpg", "jpeg"], label_visibility="collapsed", key=f"uploader_{S.uploader_key}")
    if imagen_subida:
        st.image(imagen_subida, caption="Imagen adjunta", use_container_width=True)

prompt = st.chat_input("Pregúntame sobre el código..." if S.modo_actual == "Programación" else "Escribe tu mensaje...")
if not prompt:
    prompt = S.pop("prompt_rapido", None)

if audio_grabado or prompt:
    texto_usuario = prompt or ""
    if audio_grabado and not prompt:
        with st.spinner("Escuchando..."):
            try:
                texto_usuario = cliente.audio.transcriptions.create(
                    file=("audio.wav", audio_grabado.read()), model="whisper-large-v3", language="es").text
            except Exception as e:
                st.error(f"Error de audio: {e}")

    if texto_usuario:
        if S.chat_id is None:
            S.chat_id = db_crear_chat(S.modo_actual, texto_usuario[:40])
            S.cache_mensajes[S.chat_id] = []
        mensajes = S.cache_mensajes[S.chat_id]

        texto_guardado = f"{texto_usuario} [Imagen Adjunta]" if imagen_subida else texto_usuario
        mensajes.append({"role": "user", "content": texto_guardado})
        db_guardar_mensaje(S.chat_id, "user", texto_guardado)
        with st.chat_message("user"):
            st.markdown(texto_guardado)

        modelo = MODELO_TEXTO
        contenido_actual = texto_usuario
        if imagen_subida:
            b64 = base64.b64encode(imagen_subida.getvalue()).decode("utf-8")
            contenido_actual = [{"type": "text", "text": texto_usuario},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]
            modelo = MODELO_VISION

        if S.modo_actual == "Programación":
            repo = S.repo_seleccionado
            if token_gh and S.repo_indexado != repo:
                with st.spinner(f"🧠 Estudiando {repo}..."):
                    if indexar_repositorio(USUARIO_GITHUB, repo, token_gh):
                        S.repo_indexado = repo
            contexto = buscar_contexto_codigo(texto_usuario)
            instrucciones = f"""Eres Lili Dev, mentora experta en programación.
REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL. CONTEXTO: Leiver de Venezuela.
Analizando el repositorio '{repo}'.
Contexto del código:
{contexto}

FORMATO DE RESPUESTA OBLIGATORIO:
1. Saludo amigable.
2. "Diagnóstico rápido".
3. "La solución paso a paso" (con bloques de código).
4. "Consejo Pro".
Sé didáctica."""
        else:
            instrucciones = "Eres Lili, una IA avanzada y carismática. REGLA DE ORO: RESPONDE SIEMPRE EN ESPAÑOL."

        historial = [{"role": "system", "content": instrucciones}]
        for m in mensajes[:-1][-20:]:
            historial.append({"role": m["role"], "content": m["content"].replace(" [Imagen Adjunta]", "")})
        historial.append({"role": "user", "content": contenido_actual})

        try:
            with st.chat_message("assistant"):
                with st.spinner("Redactando respuesta..."):
                    respuesta = llamar_llm(historial, modelo=modelo)
                st.markdown(respuesta)
            mensajes.append({"role": "assistant", "content": respuesta})
            db_guardar_mensaje(S.chat_id, "assistant", respuesta)

            if voz_activa:
                S.audio_pendiente = generar_audio_seguro(limpiar_texto_para_voz(respuesta), VOZ_FIJA)
            S.mic_key += 1
            S.uploader_key += 1
            st.rerun()
        except Exception as e:
            st.error(f"Error de Groq: {e}")

if S.audio_pendiente:
    b64 = base64.b64encode(S.audio_pendiente.read()).decode()
    st.markdown(f'<audio autoplay="true" src="data:audio/mp3;base64,{b64}"></audio>', unsafe_allow_html=True)
    S.audio_pendiente = None
