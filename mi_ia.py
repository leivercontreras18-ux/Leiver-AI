"""
Mis Finanzas · finanzas personales con perfiles separados
Stack: Streamlit + Pandas + SQLite local (sin internet, sin APIs).
Cada perfil (con su PIN) tiene sus propios movimientos, presupuestos y metas.
"""
import calendar
import datetime
import hashlib
import hmac
import html
import math
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import altair as alt  # ya viene instalado junto con Streamlit
import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mis Finanzas",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Perfiles: nombre -> color del avatar. Agrega o cambia nombres aquí.
# El PRIMERO hereda los datos que ya tenías guardados antes de usar perfiles.
PERFILES = {"Leiver": "#00e5ff", "Winderly": "#f472b6"}
PERFIL_ORIGINAL = next(iter(PERFILES))

MONEDA = "$"
DB_PATH = Path(__file__).with_name("finanzas_leiver.db")  # siempre junto a este archivo

CATEGORIAS = {
    "Gasto": {
        "Comida": "🍽️", "Transporte": "🚌", "Ropa": "👕", "Servicios": "💡",
        "Hogar": "🏠", "Salud": "🩺", "Ocio": "🎬", "Otros": "📦",
    },
    "Ingreso": {"Sueldo": "💼", "Ventas": "🛍️", "Regalo": "🎁", "Otros": "✨"},
}
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
TODO = "Todo el historial"

CIAN, ROSA, MUTED = "#00e5ff", "#fb7185", "#8b98ab"
PALETA = ["#00e5ff", "#7c5cff", "#34d399", "#fbbf24", "#fb7185", "#60a5fa", "#f472b6", "#a3e635"]

# ─────────────────────────────────────────────────────────────
# ESTILOS
# ─────────────────────────────────────────────────────────────
CSS = """
<style>
:root{
  --bg:#0a0e17; --surface:#111827; --surface-2:#0f1623; --line:rgba(255,255,255,.07);
  --cyan:#00e5ff; --violet:#7c5cff; --green:#34d399; --rose:#fb7185; --amber:#fbbf24;
  --text:#e8eef7; --muted:#8b98ab;
}
.stApp, .stApp p, .stApp label, .stApp input, .stApp button, .stApp textarea{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
}
.stApp{
  background:radial-gradient(1200px 520px at 50% -10%, #16223a 0%, var(--bg) 65%) !important;
  color:var(--text) !important;
}

/* Quitar elementos de Streamlit, pero conservar el botón del sidebar */
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stMainMenu"],
[data-testid="stAppDeployButton"], .stDeployButton, [data-testid="stToolbarActions"]{display:none !important;}
header[data-testid="stHeader"], [data-testid="stToolbar"]{background:transparent !important;}
[data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"]{
  visibility:visible !important; opacity:1 !important; color:var(--cyan) !important;
}
.block-container{padding:2.2rem 2rem 4rem !important; max-width:1120px !important;}

/* Encabezado */
.app-title{font-size:1.9rem; font-weight:700; letter-spacing:-.02em; line-height:1.15;}
.app-sub{color:var(--muted); font-size:.95rem; margin-top:4px;}
.sec{font-size:1rem; font-weight:600; margin:10px 0 12px; letter-spacing:-.01em;}

/* Tarjetas KPI */
.kpi{background:var(--surface); border:1px solid var(--line); border-radius:18px;
     padding:20px 22px; min-height:140px;}
.kpi.hero{background:linear-gradient(135deg, rgba(0,229,255,.16), rgba(124,92,255,.14) 60%, rgba(17,24,39,.92));
          border-color:rgba(0,229,255,.25);}
.kpi-top{display:flex; justify-content:space-between; align-items:center;}
.kpi-label{color:var(--muted); font-size:.74rem; font-weight:600; letter-spacing:.09em; text-transform:uppercase;}
.kpi-icon{width:34px; height:34px; display:grid; place-items:center; border-radius:10px;
          background:rgba(255,255,255,.05); font-size:1.05rem;}
.kpi-value{font-size:2.05rem; font-weight:700; letter-spacing:-.02em; margin:12px 0 10px;
           font-variant-numeric:tabular-nums;}
.kpi.hero .kpi-value{font-size:2.6rem;}
.kpi-value.neg-val{color:var(--rose);}
.chip{display:inline-block; font-size:.76rem; font-weight:600; padding:3px 10px; border-radius:999px;}
.chip.pos{background:rgba(52,211,153,.12); color:var(--green);}
.chip.neg{background:rgba(251,113,133,.12); color:var(--rose);}
.chip.neutral{background:rgba(255,255,255,.06); color:var(--muted);}

/* Desglose por categoría */
.cat-card{background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:20px 20px 10px;}
.stack{display:flex; gap:3px; height:12px; border-radius:999px; overflow:hidden; margin-bottom:16px;}
.stack > div{height:100%;}
.cat-row{display:flex; align-items:center; gap:10px; padding:9px 0; border-top:1px solid var(--line); font-size:.92rem;}
.cat-row:first-of-type{border-top:none;}
.dot{width:10px; height:10px; border-radius:50%; flex:none;}
.cat-name{flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.cat-pct{color:var(--muted); font-size:.8rem; width:38px; text-align:right;}
.cat-amt{font-weight:600; font-variant-numeric:tabular-nums; min-width:80px; text-align:right;}

/* Lista de movimientos estilo app bancaria */
.tx-wrap{background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:6px 18px;}
.tx{display:flex; align-items:center; gap:14px; padding:13px 0; border-bottom:1px solid var(--line);}
.tx:last-child{border-bottom:none;}
.tx-ico{width:40px; height:40px; border-radius:12px; background:rgba(255,255,255,.05);
        display:grid; place-items:center; font-size:1.15rem; flex:none;}
.tx-main{flex:1; min-width:0;}
.tx-title{font-weight:600; font-size:.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.tx-sub{color:var(--muted); font-size:.8rem;}
.tx-amt{font-weight:700; font-variant-numeric:tabular-nums;}
.tx-amt.in{color:var(--green);}

/* Presupuestos y metas */
.bud{background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin-bottom:12px;}
.bud-head{display:flex; justify-content:space-between; gap:12px; font-size:.92rem; margin-bottom:10px;}
.bud-head b{font-weight:600;}
.bud-head span{color:var(--muted); font-variant-numeric:tabular-nums;}
.bar{height:8px; border-radius:999px; background:rgba(255,255,255,.07); overflow:hidden;}
.bar > div{height:100%; border-radius:999px; background:linear-gradient(90deg, var(--cyan), #5ad7ff);}
.bar.warn > div{background:var(--amber);}
.bar.over > div{background:var(--rose);}
.bud-foot{color:var(--muted); font-size:.8rem; margin-top:8px;}
.goal-big{font-size:1.5rem; font-weight:700; letter-spacing:-.01em; margin-bottom:4px;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:6px; border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"]{height:44px; padding:0 14px; color:var(--muted); background:transparent;}
.stTabs [aria-selected="true"]{color:var(--cyan) !important;}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--cyan) !important;}

/* Sidebar */
[data-testid="stSidebar"]{background:#0c111c !important; border-right:1px solid var(--line) !important;}
[data-testid="stSidebar"] [data-testid="stForm"]{border:none !important; padding:0 !important;}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{
  color:var(--muted); font-size:.72rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
}
.who{display:flex; align-items:center; gap:12px; padding:14px; margin:2px 0 22px;
     background:var(--surface); border:1px solid var(--line); border-radius:16px;}
.avatar{width:42px; height:42px; border-radius:14px; display:grid; place-items:center;
        font-weight:800; font-size:1.1rem; color:#04121a; flex:none;}
.who-name{font-weight:700; font-size:1rem; line-height:1.2;}
.who-sub{color:var(--muted); font-size:.78rem;}
[data-testid="stNumberInput"] input{font-size:1.35rem !important; font-weight:700 !important;}
button[data-testid="stBaseButton-pills"], button[data-testid="stBaseButton-segmented_control"]{
  border-radius:999px !important; border:1px solid var(--line) !important; background:var(--surface-2) !important;
}
button[data-testid="stBaseButton-pillsActive"], button[data-testid="stBaseButton-segmented_controlActive"]{
  border-radius:999px !important; border:1px solid var(--cyan) !important; background:rgba(0,229,255,.14) !important;
  color:var(--cyan) !important;
}

/* Pantalla de acceso */
.login-logo{font-size:3rem; text-align:center; margin-bottom:6px;}
.login-card{background:var(--surface); border:1px solid var(--line); border-radius:20px;
            padding:24px 12px 14px; text-align:center; margin-bottom:10px;}
.avatar-lg{width:64px; height:64px; border-radius:20px; display:grid; place-items:center; margin:0 auto 10px;
           font-weight:800; font-size:1.7rem; color:#04121a;}
.login-name{font-weight:700; font-size:1.05rem;}

/* Inputs */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div, textarea{
  background:var(--surface-2) !important; border-color:rgba(255,255,255,.08) !important;
  border-radius:10px !important; color:var(--text) !important;
}
[data-testid="stExpander"]{background:var(--surface); border:1px solid var(--line) !important; border-radius:14px;}

/* Botones */
.stButton > button, [data-testid="stFormSubmitButton"] > button{
  background:var(--cyan) !important; color:#04121a !important; font-weight:700 !important;
  border:none !important; border-radius:12px !important; padding:.55rem 1rem !important; width:100%;
  transition:transform .15s ease, box-shadow .15s ease;
}
.stButton > button p, [data-testid="stFormSubmitButton"] > button p{color:#04121a !important;}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover{
  transform:translateY(-1px); box-shadow:0 8px 24px rgba(0,229,255,.25);
}
.stButton > button:disabled{opacity:.35;}
.st-key-logout button, .st-key-volver button{
  background:transparent !important; color:var(--muted) !important; border:1px solid var(--line) !important;
}
.st-key-logout button p, .st-key-volver button p{color:var(--muted) !important;}
.stDownloadButton > button{
  background:transparent !important; color:var(--cyan) !important; font-weight:600 !important;
  border:1px solid rgba(0,229,255,.35) !important; border-radius:12px !important; width:100%;
}
.stDownloadButton > button p{color:var(--cyan) !important;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# BASE DE DATOS (SQLite local)
# Una conexión corta por operación: evita conexiones colgadas
# cuando Streamlit vuelve a ejecutar el script (st.rerun).
# ─────────────────────────────────────────────────────────────
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columnas(conn, tabla):
    return [fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")]


def _existe(conn, tabla):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    ).fetchone() is not None


@st.cache_resource
def init_db():
    """Crea tablas y migra datos viejos (sin perfil) al perfil original."""
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL")

        # Movimientos
        conn.execute(
            """CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT, categoria TEXT, monto REAL, descripcion TEXT, fecha TEXT,
                perfil TEXT
            )"""
        )
        if "perfil" not in _columnas(conn, "transacciones"):
            conn.execute("ALTER TABLE transacciones ADD COLUMN perfil TEXT")
        conn.execute("UPDATE transacciones SET perfil = ? WHERE perfil IS NULL OR perfil = ''",
                     (PERFIL_ORIGINAL,))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_perfil_fecha ON transacciones(perfil, fecha)")

        # Presupuestos (clave: perfil + categoría)
        if _existe(conn, "presupuestos") and "perfil" not in _columnas(conn, "presupuestos"):
            conn.execute("ALTER TABLE presupuestos RENAME TO presupuestos_old")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS presupuestos (
                perfil TEXT NOT NULL, categoria TEXT NOT NULL, limite REAL NOT NULL,
                PRIMARY KEY (perfil, categoria)
            )"""
        )
        if _existe(conn, "presupuestos_old"):
            conn.execute(
                "INSERT OR IGNORE INTO presupuestos (perfil, categoria, limite) "
                "SELECT ?, categoria, limite FROM presupuestos_old", (PERFIL_ORIGINAL,))
            conn.execute("DROP TABLE presupuestos_old")

        # Ajustes (clave: perfil + clave)
        if _existe(conn, "ajustes") and "perfil" not in _columnas(conn, "ajustes"):
            conn.execute("ALTER TABLE ajustes RENAME TO ajustes_old")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS ajustes (
                perfil TEXT NOT NULL, clave TEXT NOT NULL, valor TEXT,
                PRIMARY KEY (perfil, clave)
            )"""
        )
        if _existe(conn, "ajustes_old"):
            conn.execute(
                "INSERT OR IGNORE INTO ajustes (perfil, clave, valor) "
                "SELECT ?, clave, valor FROM ajustes_old", (PERFIL_ORIGINAL,))
            conn.execute("DROP TABLE ajustes_old")

        # PIN de cada perfil (guardado con hash, nunca en texto plano)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS perfiles (nombre TEXT PRIMARY KEY, pin_hash TEXT, sal TEXT)"
        )
    return True


# ── PIN ──
def _hash_pin(pin, sal_hex):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal_hex), 120_000).hex()


def perfil_tiene_pin(nombre):
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM perfiles WHERE nombre = ?", (nombre,)).fetchone() is not None


def crear_pin(nombre, pin):
    sal = secrets.token_hex(16)
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO perfiles (nombre, pin_hash, sal) VALUES (?, ?, ?)",
                     (nombre, _hash_pin(pin, sal), sal))


def verificar_pin(nombre, pin):
    with get_conn() as conn:
        fila = conn.execute("SELECT pin_hash, sal FROM perfiles WHERE nombre = ?", (nombre,)).fetchone()
    return bool(fila) and hmac.compare_digest(fila[0], _hash_pin(pin, fila[1]))


# ── Datos del perfil activo ──
def agregar_transaccion(perfil, tipo, categoria, monto, descripcion, fecha):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transacciones (tipo, categoria, monto, descripcion, fecha, perfil) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tipo, categoria, float(monto), descripcion, str(fecha), perfil),
        )


def eliminar_transaccion(perfil, id_):
    with get_conn() as conn:
        conn.execute("DELETE FROM transacciones WHERE id = ? AND perfil = ?", (int(id_), perfil))


def obtener_datos(perfil):
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT id, tipo, categoria, monto, descripcion, fecha FROM transacciones "
            "WHERE perfil = ? ORDER BY fecha DESC, id DESC",
            conn, params=(perfil,),
        )
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha"]).copy()
    df["descripcion"] = df["descripcion"].fillna("")
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    return df


def obtener_presupuestos(perfil):
    with get_conn() as conn:
        filas = conn.execute("SELECT categoria, limite FROM presupuestos WHERE perfil = ?",
                             (perfil,)).fetchall()
    return {c: l for c, l in filas}


def guardar_presupuesto(perfil, categoria, limite):
    with get_conn() as conn:
        if limite <= 0:
            conn.execute("DELETE FROM presupuestos WHERE perfil = ? AND categoria = ?", (perfil, categoria))
        else:
            conn.execute(
                "INSERT INTO presupuestos (perfil, categoria, limite) VALUES (?, ?, ?) "
                "ON CONFLICT(perfil, categoria) DO UPDATE SET limite = excluded.limite",
                (perfil, categoria, float(limite)),
            )


def get_ajuste(perfil, clave, default=""):
    with get_conn() as conn:
        fila = conn.execute("SELECT valor FROM ajustes WHERE perfil = ? AND clave = ?",
                            (perfil, clave)).fetchone()
    return fila[0] if fila else default


def set_ajuste(perfil, clave, valor):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ajustes (perfil, clave, valor) VALUES (?, ?, ?) "
            "ON CONFLICT(perfil, clave) DO UPDATE SET valor = excluded.valor",
            (perfil, clave, str(valor)),
        )


# ─────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────
def dinero(x):
    return f"-{MONEDA}{abs(x):,.2f}" if x < 0 else f"{MONEDA}{x:,.2f}"


def etiqueta_mes(ym):
    y, m = ym.split("-")
    return f"{MESES[int(m) - 1]} {y}"


def etiqueta_corta(ym):
    y, m = ym.split("-")
    return f"{MESES[int(m) - 1][:3]} {y[2:]}"


def mes_anterior(ym):
    y, m = map(int, ym.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def totales(df):
    ing = df.loc[df["tipo"] == "Ingreso", "monto"].sum()
    gas = df.loc[df["tipo"] == "Gasto", "monto"].sum()
    return ing, gas, ing - gas


def variacion(actual, anterior):
    if anterior and anterior > 0:
        return (actual - anterior) / anterior * 100
    return None


def stretch(fn, *args, **kwargs):
    """Ancho completo compatible con versiones nuevas y viejas de Streamlit."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except Exception:
        return fn(*args, use_container_width=True, **kwargs)


def icono(tipo, categoria):
    return CATEGORIAS.get(tipo, {}).get(categoria, "💳")


def avatar(nombre, grande=False):
    color = PERFILES.get(nombre, CIAN)
    clase = "avatar-lg" if grande else "avatar"
    return f'<div class="{clase}" style="background:{color}">{html.escape(nombre[:1].upper())}</div>'


def tarjeta(titulo, valor, ico, delta=None, sube_es_bueno=True, hero=False,
            nota=None, negativo=False):
    if delta is not None:
        bueno = (delta >= 0) == sube_es_bueno
        flecha = "▲" if delta >= 0 else "▼"
        pie = f'<span class="chip {"pos" if bueno else "neg"}">{flecha} {abs(delta):.0f}% vs mes anterior</span>'
    else:
        pie = f'<span class="chip neutral">{html.escape(nota or "Sin mes anterior para comparar")}</span>'
    cls = "kpi hero" if hero else "kpi"
    vcls = "kpi-value neg-val" if negativo else "kpi-value"
    return (
        f'<div class="{cls}"><div class="kpi-top"><span class="kpi-label">{titulo}</span>'
        f'<span class="kpi-icon">{ico}</span></div>'
        f'<div class="{vcls}">{valor}</div>{pie}</div>'
    )


def barra(pct):
    estado = "" if pct < 80 else ("warn" if pct <= 100 else "over")
    return f'<div class="bar {estado}"><div style="width:{min(pct, 100):.1f}%"></div></div>'


def desglose_categorias(gc):
    total = gc["monto"].sum()
    segmentos, filas = [], []
    for i, r in enumerate(gc.itertuples()):
        color = PALETA[i % len(PALETA)]
        pct = r.monto / total * 100
        segmentos.append(f'<div style="width:{pct:.2f}%;background:{color}"></div>')
        filas.append(
            f'<div class="cat-row"><span class="dot" style="background:{color}"></span>'
            f'<span class="cat-name">{icono("Gasto", r.categoria)} {html.escape(r.categoria)}</span>'
            f'<span class="cat-pct">{pct:.0f}%</span><span class="cat-amt">{dinero(r.monto)}</span></div>'
        )
    return f'<div class="cat-card"><div class="stack">{"".join(segmentos)}</div>{"".join(filas)}</div>'


def lista_movimientos(df_):
    filas = []
    for r in df_.itertuples():
        es_ing = r.tipo == "Ingreso"
        titulo = html.escape(r.descripcion) if r.descripcion else html.escape(r.categoria)
        signo = "+" if es_ing else "−"
        filas.append(
            f'<div class="tx"><div class="tx-ico">{icono(r.tipo, r.categoria)}</div>'
            f'<div class="tx-main"><div class="tx-title">{titulo}</div>'
            f'<div class="tx-sub">{html.escape(r.categoria)} · {r.fecha:%d/%m/%Y}</div></div>'
            f'<div class="tx-amt {"in" if es_ing else ""}">{signo}{MONEDA}{r.monto:,.2f}</div></div>'
        )
    return f'<div class="tx-wrap">{"".join(filas)}</div>'


# ─────────────────────────────────────────────────────────────
# PANTALLA DE ACCESO (elegir perfil + PIN)
# ─────────────────────────────────────────────────────────────
def pantalla_acceso():
    st.markdown("<div style='height:5vh'></div>", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.6, 1])
    with centro:
        st.markdown(
            '<div class="login-logo">💰</div>'
            '<div class="app-title" style="text-align:center">Mis Finanzas</div>'
            '<div class="app-sub" style="text-align:center;margin-bottom:26px">¿Quién va a entrar?</div>',
            unsafe_allow_html=True,
        )
        elegido = st.session_state.get("perfil_elegido")

        if elegido not in PERFILES:
            columnas = st.columns(len(PERFILES))
            for col, nombre in zip(columnas, PERFILES):
                with col:
                    st.markdown(
                        f'<div class="login-card">{avatar(nombre, True)}'
                        f'<div class="login-name">{html.escape(nombre)}</div></div>',
                        unsafe_allow_html=True,
                    )
                    if st.button("Entrar", key=f"sel_{nombre}"):
                        st.session_state["perfil_elegido"] = nombre
                        st.rerun()
            return

        tiene_pin = perfil_tiene_pin(elegido)
        st.markdown(
            f'<div class="login-card">{avatar(elegido, True)}'
            f'<div class="login-name">Hola, {html.escape(elegido)}</div></div>',
            unsafe_allow_html=True,
        )
        with st.form("form_pin"):
            if tiene_pin:
                pin = st.text_input("PIN", type="password", max_chars=6)
                pin2 = None
            else:
                st.caption("Primera vez: crea un PIN de 4 a 6 dígitos para proteger tus finanzas.")
                pin = st.text_input("Crea tu PIN", type="password", max_chars=6)
                pin2 = st.text_input("Repite tu PIN", type="password", max_chars=6)
            continuar = st.form_submit_button("Continuar")

        if continuar:
            if tiene_pin:
                if verificar_pin(elegido, pin):
                    st.session_state["perfil"] = elegido
                    st.session_state.pop("perfil_elegido", None)
                    st.rerun()
                else:
                    st.error("PIN incorrecto.")
            elif not (pin.isdigit() and 4 <= len(pin) <= 6):
                st.error("El PIN debe tener entre 4 y 6 números.")
            elif pin != pin2:
                st.error("Los PIN no coinciden.")
            else:
                crear_pin(elegido, pin)
                st.session_state["perfil"] = elegido
                st.session_state.pop("perfil_elegido", None)
                st.rerun()

        if st.button("← Cambiar de perfil", key="volver"):
            st.session_state.pop("perfil_elegido", None)
            st.rerun()


# ─────────────────────────────────────────────────────────────
# ARRANQUE: acceso por perfil
# ─────────────────────────────────────────────────────────────
init_db()

perfil = st.session_state.get("perfil")
if perfil not in PERFILES:
    pantalla_acceso()
    st.stop()

df = obtener_datos(perfil)
hoy = datetime.date.today()
mes_actual = hoy.strftime("%Y-%m")

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")


def elegir_tipo():
    fmt = {"Gasto": "💸 Gasto", "Ingreso": "💵 Ingreso"}.get
    if hasattr(st, "segmented_control"):
        return st.segmented_control("Tipo", ["Gasto", "Ingreso"], default="Gasto", format_func=fmt,
                                    key="tipo_mov", label_visibility="collapsed") or "Gasto"
    return st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True, format_func=fmt,
                    key="tipo_mov", label_visibility="collapsed")


def elegir_categoria(tipo_):
    opciones = list(CATEGORIAS[tipo_])
    fmt = lambda c: f"{CATEGORIAS[tipo_][c]} {c}"
    if hasattr(st, "pills"):
        return st.pills("Categoría", opciones, selection_mode="single", default=opciones[0],
                        format_func=fmt, key=f"cat_{tipo_}")
    return st.selectbox("Categoría", opciones, format_func=fmt)


# ─────────────────────────────────────────────────────────────
# BARRA LATERAL
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="who">{avatar(perfil)}<div><div class="who-name">{html.escape(perfil)}</div>'
        f'<div class="who-sub">Mis finanzas</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sec">Nuevo movimiento</div>', unsafe_allow_html=True)

    # El tipo va FUERA del formulario para que las categorías cambien al instante
    tipo = elegir_tipo()

    with st.form("form_transaccion", clear_on_submit=True):
        categoria = elegir_categoria(tipo)
        monto = st.number_input(f"Monto ({MONEDA})", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        descripcion = st.text_input("Descripción", placeholder="Opcional", max_chars=80)
        fecha = st.date_input("Fecha", hoy, format="DD/MM/YYYY")
        guardar = st.form_submit_button("Guardar movimiento")

    if guardar:
        if categoria is None:
            st.error("Elige una categoría.")
        elif monto <= 0:
            st.error("El monto debe ser mayor a 0.")
        else:
            agregar_transaccion(perfil, tipo, categoria, round(monto, 2), descripcion.strip(), fecha)
            st.session_state["flash"] = f"{tipo} de {dinero(monto)} guardado"
            st.session_state["periodo"] = fecha.strftime("%Y-%m")  # saltar al mes del movimiento
            st.rerun()

    st.markdown("---")
    if not df.empty:
        respaldo = (
            df[["fecha", "tipo", "categoria", "monto", "descripcion"]]
            .assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m-%d"))
            .to_csv(index=False)
            .encode("utf-8-sig")
        )
        st.download_button("⬇️ Respaldo (CSV)", respaldo,
                           file_name=f"finanzas_{perfil.lower()}_respaldo.csv", mime="text/csv")
    if st.button("Cambiar de perfil", key="logout"):
        st.session_state.clear()
        st.rerun()
    st.markdown(
        "<p style='color:#8b98ab; font-size:.78rem; text-align:center; margin-top:12px;'>"
        "🔒 Datos locales · cada perfil tiene su PIN.</p>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────
# ENCABEZADO + SELECTOR DE PERIODO
# ─────────────────────────────────────────────────────────────
meses_disponibles = sorted(set(df["mes"]) | {mes_actual}, reverse=True)
opciones_periodo = meses_disponibles + [TODO]
if st.session_state.get("periodo") not in opciones_periodo:
    st.session_state["periodo"] = mes_actual

col_t, col_f = st.columns([3, 1.3], vertical_alignment="center")
with col_t:
    st.markdown(
        f'<div class="app-title">Hola, {html.escape(perfil)} 👋</div>'
        '<div class="app-sub">Así van tus finanzas.</div>',
        unsafe_allow_html=True,
    )
with col_f:
    periodo = st.selectbox(
        "Periodo", opciones_periodo, key="periodo", label_visibility="collapsed",
        format_func=lambda p: p if p == TODO else etiqueta_mes(p),
    )

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

if df.empty:
    st.info("👈 Usa la barra lateral para registrar tu primer ingreso o gasto.")
    st.stop()

# Datos del periodo elegido
if periodo == TODO:
    df_p, df_prev, mes_ref = df, None, mes_actual
else:
    df_p = df[df["mes"] == periodo]
    df_prev = df[df["mes"] == mes_anterior(periodo)]
    mes_ref = periodo

ing, gas, bal = totales(df_p)
if df_prev is not None and not df_prev.empty:
    ing_prev, gas_prev, _ = totales(df_prev)
    d_ing, d_gas = variacion(ing, ing_prev), variacion(gas, gas_prev)
else:
    d_ing = d_gas = None
nota_periodo = "Todo el historial" if periodo == TODO else None

tab_res, tab_mov, tab_pre, tab_meta = st.tabs(
    ["📊 Resumen", "🧾 Movimientos", "🎯 Presupuestos", "🏆 Metas"]
)

# ─────────────────────────────────────────────────────────────
# TAB 1 · RESUMEN
# ─────────────────────────────────────────────────────────────
with tab_res:
    c1, c2, c3 = st.columns([1.4, 1, 1])
    c1.markdown(tarjeta("Balance", dinero(bal), "📊", hero=True,
                        nota="Ingresos − gastos", negativo=bal < 0), unsafe_allow_html=True)
    c2.markdown(tarjeta("Ingresos", dinero(ing), "💵", d_ing, True, nota=nota_periodo),
                unsafe_allow_html=True)
    c3.markdown(tarjeta("Gastos", dinero(gas), "💸", d_gas, False, nota=nota_periodo),
                unsafe_allow_html=True)

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    g1, g2 = st.columns(2)

    with g1:
        st.markdown('<div class="sec">En qué se va tu dinero</div>', unsafe_allow_html=True)
        gc = (
            df_p[df_p["tipo"] == "Gasto"]
            .groupby("categoria", as_index=False)["monto"].sum()
            .sort_values("monto", ascending=False)
        )
        if gc.empty:
            st.info("Aún no hay gastos en este periodo.")
        else:
            st.markdown(desglose_categorias(gc), unsafe_allow_html=True)

    with g2:
        gastos_p = df_p[df_p["tipo"] == "Gasto"]
        if periodo == TODO:
            st.markdown('<div class="sec">Gastos por mes</div>', unsafe_allow_html=True)
            base = (df[df["tipo"] == "Gasto"].groupby("mes", as_index=False)["monto"].sum()
                    .sort_values("mes").tail(12))
            base["etiqueta"] = base["mes"].map(etiqueta_corta)
            eje_x = alt.X("etiqueta:N", sort=base["etiqueta"].tolist(), title=None,
                          axis=alt.Axis(labelAngle=0, labelColor=MUTED, ticks=False, domain=False))
            titulo_x, pie_chart = "Mes", None
        else:
            st.markdown('<div class="sec">Gasto diario</div>', unsafe_allow_html=True)
            anio, mes_n = map(int, periodo.split("-"))
            n_dias = calendar.monthrange(anio, mes_n)[1]
            por_dia = gastos_p.groupby(gastos_p["fecha"].dt.day)["monto"].sum()
            base = pd.DataFrame({"etiqueta": list(range(1, n_dias + 1))})
            base["monto"] = base["etiqueta"].map(por_dia).fillna(0.0)
            eje_x = alt.X("etiqueta:O", title=None,
                          axis=alt.Axis(labelAngle=0, labelColor=MUTED, ticks=False, domain=False,
                                        labelOverlap=True))
            titulo_x = "Día"
            dias_transcurridos = hoy.day if periodo == mes_actual else n_dias
            pie_chart = f"Promedio diario: **{dinero(gas / max(dias_transcurridos, 1))}**"

        if gastos_p.empty:
            st.info("Aún no hay gastos en este periodo.")
        else:
            barras = (
                alt.Chart(base)
                .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, color=CIAN, opacity=0.9)
                .encode(
                    x=eje_x,
                    y=alt.Y("monto:Q", title=None,
                            axis=alt.Axis(labelColor=MUTED, gridColor="rgba(255,255,255,0.06)",
                                          domain=False, ticks=False)),
                    tooltip=[alt.Tooltip("etiqueta", title=titulo_x),
                             alt.Tooltip("monto:Q", title="Gastado", format=",.2f")],
                )
                .properties(height=250)
                .configure_view(strokeWidth=0)
                .configure(background="transparent")
            )
            stretch(st.altair_chart, barras)
            if pie_chart:
                st.caption(pie_chart)

    st.markdown('<div class="sec">Últimos movimientos</div>', unsafe_allow_html=True)
    if df_p.empty:
        st.info("No hay movimientos en este periodo.")
    else:
        st.markdown(lista_movimientos(df_p.head(6)), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# TAB 2 · MOVIMIENTOS
# ─────────────────────────────────────────────────────────────
with tab_mov:
    f1, f2 = st.columns([1.3, 1.7], vertical_alignment="center")
    with f1:
        filtro_tipo = st.radio("Mostrar", ["Todos", "Ingresos", "Gastos"], horizontal=True,
                               label_visibility="collapsed")
    with f2:
        busqueda = st.text_input("Buscar", placeholder="🔎 Buscar por descripción o categoría",
                                 label_visibility="collapsed")

    df_f = df_p
    if filtro_tipo != "Todos":
        df_f = df_f[df_f["tipo"] == ("Ingreso" if filtro_tipo == "Ingresos" else "Gasto")]
    if busqueda.strip():
        q = busqueda.strip()
        df_f = df_f[
            df_f["descripcion"].str.contains(q, case=False, na=False, regex=False)
            | df_f["categoria"].str.contains(q, case=False, na=False, regex=False)
        ]

    if df_f.empty:
        st.info("No hay movimientos con esos filtros.")
    else:
        tabla = df_f[["fecha", "tipo", "categoria", "monto", "descripcion"]].copy()
        tabla["fecha"] = tabla["fecha"].dt.date

        def colorear_tipo(col):
            return [
                "color:#34d399;font-weight:600" if v == "Ingreso" else "color:#fb7185;font-weight:600"
                for v in col
            ]

        stretch(
            st.dataframe,
            tabla.style.apply(colorear_tipo, subset=["tipo"]),
            hide_index=True,
            column_config={
                "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                "tipo": st.column_config.TextColumn("Tipo"),
                "categoria": st.column_config.TextColumn("Categoría"),
                "monto": st.column_config.NumberColumn("Monto", format=f"{MONEDA}%.2f"),
                "descripcion": st.column_config.TextColumn("Descripción"),
            },
        )
        st.caption(f"{len(df_f)} movimientos · ingresos {dinero(totales(df_f)[0])} · "
                   f"gastos {dinero(totales(df_f)[1])}")

        csv = (
            tabla.assign(fecha=lambda d: d["fecha"].astype(str))
            .to_csv(index=False).encode("utf-8-sig")
        )
        nombre_csv = "historial" if periodo == TODO else periodo
        st.download_button("⬇️ Exportar esta vista a CSV", csv,
                           file_name=f"finanzas_{perfil.lower()}_{nombre_csv}.csv", mime="text/csv")

        with st.expander("🗑️ Eliminar un movimiento"):
            etiquetas = {
                int(r.id): f"{r.fecha:%d/%m/%Y} · {r.categoria} · {dinero(r.monto)}"
                           + (f" · {r.descripcion}" if r.descripcion else "")
                for r in df_f.head(100).itertuples()
            }
            elegido = st.selectbox("Movimiento", list(etiquetas), format_func=etiquetas.get,
                                   label_visibility="collapsed")
            confirmar = st.checkbox("Confirmo que quiero eliminarlo")
            if st.button("Eliminar movimiento", disabled=not confirmar):
                eliminar_transaccion(perfil, elegido)
                st.session_state["flash"] = "Movimiento eliminado"
                st.rerun()

# ─────────────────────────────────────────────────────────────
# TAB 3 · PRESUPUESTOS (por categoría, mensuales)
# ─────────────────────────────────────────────────────────────
with tab_pre:
    presupuestos = obtener_presupuestos(perfil)
    gastado_mes = (
        df[(df["mes"] == mes_ref) & (df["tipo"] == "Gasto")]
        .groupby("categoria")["monto"].sum().to_dict()
    )
    if periodo == TODO:
        st.caption(f"Los presupuestos son mensuales. Mostrando {etiqueta_mes(mes_ref)}.")

    if not presupuestos:
        st.info("Aún no tienes presupuestos. Define un límite mensual por categoría para controlar tus gastos.")
    else:
        total_l = sum(presupuestos.values())
        total_g = sum(gastado_mes.get(c, 0) for c in presupuestos)
        st.markdown(
            f'<div class="sec">{etiqueta_mes(mes_ref)} · {dinero(total_g)} de {dinero(total_l)} presupuestado</div>',
            unsafe_allow_html=True,
        )
        for cat, limite in sorted(presupuestos.items()):
            g = gastado_mes.get(cat, 0)
            pct = g / limite * 100
            resto = limite - g
            pie = f"Te quedan {dinero(resto)}" if resto >= 0 else f"Excedido por {dinero(-resto)}"
            st.markdown(
                f'<div class="bud"><div class="bud-head"><b>{icono("Gasto", cat)} {html.escape(cat)}</b>'
                f'<span>{dinero(g)} / {dinero(limite)}</span></div>{barra(pct)}'
                f'<div class="bud-foot">{pct:.0f}% usado · {pie}</div></div>',
                unsafe_allow_html=True,
            )

    with st.expander("➕ Definir o editar un presupuesto", expanded=not presupuestos):
        with st.form("form_presupuesto", clear_on_submit=True):
            cat_p = st.selectbox("Categoría", list(CATEGORIAS["Gasto"]),
                                 format_func=lambda c: f"{CATEGORIAS['Gasto'][c]}  {c}")
            limite_p = st.number_input(f"Límite mensual ({MONEDA}) — usa 0 para quitarlo",
                                       min_value=0.0, value=0.0, step=10.0, format="%.2f")
            if st.form_submit_button("Guardar presupuesto"):
                guardar_presupuesto(perfil, cat_p, limite_p)
                st.session_state["flash"] = "Presupuesto actualizado"
                st.rerun()

# ─────────────────────────────────────────────────────────────
# TAB 4 · METAS DE AHORRO
# ─────────────────────────────────────────────────────────────
with tab_meta:
    meta_nombre = get_ajuste(perfil, "meta_nombre", "")
    try:
        meta_obj = float(get_ajuste(perfil, "meta_objetivo", "0"))
    except ValueError:
        meta_obj = 0.0

    _, _, balance_total = totales(df)

    if meta_obj > 0:
        pct = max(0.0, min(balance_total / meta_obj * 100, 100))
        falta = meta_obj - balance_total
        titulo_meta = html.escape(meta_nombre or "Mi meta de ahorro")
        barra_meta = f'<div class="bar"><div style="width:{pct:.1f}%"></div></div>'
        st.markdown(
            f'<div class="bud"><div class="goal-big">🏆 {titulo_meta}</div>'
            f'<div class="bud-head"><span>Llevas {dinero(balance_total)}</span>'
            f'<span>Meta {dinero(meta_obj)}</span></div>'
            f'{barra_meta}'
            f'<div class="bud-foot">{pct:.0f}% completado</div></div>',
            unsafe_allow_html=True,
        )
        if falta <= 0:
            st.success("🎉 ¡Meta alcanzada! Puedes definir una nueva abajo.")
        else:
            neto = df["monto"].where(df["tipo"] == "Ingreso", -df["monto"])
            prom = neto.groupby(df["mes"]).sum().sort_index().tail(3).mean()
            if prom > 0:
                st.info(f"Te faltan **{dinero(falta)}**. Con tu ahorro promedio de "
                        f"**{dinero(prom)}/mes** (últimos meses) llegarías en unos "
                        f"**{math.ceil(falta / prom)} mes(es)**.")
            else:
                st.warning(f"Te faltan **{dinero(falta)}**. Tus últimos meses cerraron sin ahorro neto; "
                           "revisa tus presupuestos para recuperar ritmo.")
        st.caption("El progreso usa tu balance acumulado: todos los ingresos menos todos los gastos.")
    else:
        st.info("Define una meta (un viaje, inventario nuevo, fondo de emergencia) y sigue tu avance aquí.")

    with st.expander("✏️ Definir o cambiar mi meta", expanded=meta_obj <= 0):
        with st.form("form_meta"):
            nuevo_nombre = st.text_input("¿Para qué estás ahorrando?", value=meta_nombre,
                                         placeholder="Ej: Fondo de emergencia", max_chars=60)
            nuevo_obj = st.number_input(f"Monto objetivo ({MONEDA})", min_value=0.0,
                                        value=meta_obj, step=50.0, format="%.2f")
            if st.form_submit_button("Guardar meta"):
                set_ajuste(perfil, "meta_nombre", nuevo_nombre.strip())
                set_ajuste(perfil, "meta_objetivo", nuevo_obj)
                st.session_state["flash"] = "Meta guardada"
                st.rerun()
