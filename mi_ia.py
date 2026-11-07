"""
Mis Finanzas · finanzas personales en la nube (Streamlit + Supabase)
- Cada perfil (con su PIN) tiene sus propios movimientos, presupuestos y metas.
- Los datos viven en Supabase: se pueden usar desde el teléfono y la PC.
- Diseñada primero para teléfono (sin barra lateral: todo está en pestañas).
"""
import calendar
import datetime
import hashlib
import hmac
import html
import math
import secrets

import altair as alt  # ya viene instalado junto con Streamlit
import pandas as pd
import streamlit as st
from supabase import create_client

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo("America/Caracas")
except Exception:  # por si el sistema no trae zonas horarias
    ZONA = datetime.timezone(datetime.timedelta(hours=-4))

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
PERFILES = {"Leiver": "#00e5ff", "Winderly": "#f472b6"}

MONEDA = "$"

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

CIAN, MUTED = "#00e5ff", "#8b98ab"
PALETA = ["#00e5ff", "#7c5cff", "#34d399", "#fbbf24", "#fb7185", "#60a5fa", "#f472b6", "#a3e635"]

# ─────────────────────────────────────────────────────────────
# ESTILOS (pensados primero para teléfono)
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
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stMainMenu"],
[data-testid="stAppDeployButton"], .stDeployButton, [data-testid="stToolbarActions"]{
  display:none !important;
}
header[data-testid="stHeader"], [data-testid="stToolbar"]{background:transparent !important;}
/* Botones para abrir/cerrar la barra lateral: siempre visibles */
[data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"]{
  visibility:visible !important; opacity:1 !important; color:var(--cyan) !important;
}
/* Barra lateral */
[data-testid="stSidebar"]{background:#0c111c !important; border-right:1px solid var(--line) !important;}
[data-testid="stSidebar"] [data-testid="stForm"]{border:none !important; background:transparent !important; padding:0 !important;}
.block-container{padding:2rem 2rem 4rem !important; max-width:1120px !important;}

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
.tx-amt{font-weight:700; font-variant-numeric:tabular-nums; white-space:nowrap;}
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

/* Sueldo fijo */
.sueldo{background:rgba(0,229,255,.10); border:1px solid rgba(0,229,255,.28); border-radius:16px;
        padding:16px 18px; margin-bottom:16px;}
.sueldo-label{color:var(--muted); font-size:.78rem; margin-bottom:4px;}
.sueldo-val{font-size:1.9rem; font-weight:700; letter-spacing:-.02em; font-variant-numeric:tabular-nums;}
.sueldo-val small{font-size:.85rem; color:var(--muted); font-weight:500;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:4px; border-bottom:1px solid var(--line); overflow-x:auto;}
.stTabs [data-baseweb="tab"]{height:46px; padding:0 14px; color:var(--muted); background:transparent; white-space:nowrap;}
.stTabs [aria-selected="true"]{color:var(--cyan) !important;}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--cyan) !important;}

/* Formularios */
[data-testid="stForm"]{border:1px solid var(--line) !important; border-radius:18px !important;
                       background:var(--surface); padding:18px !important;}
[data-testid="stForm"] [data-testid="stWidgetLabel"] p{
  color:var(--muted); font-size:.72rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
}
[data-testid="stNumberInput"] input{font-size:1.35rem !important; font-weight:700 !important;}
button[data-testid="stBaseButton-pills"], button[data-testid="stBaseButton-segmented_control"]{
  border-radius:999px !important; border:1px solid var(--line) !important; background:var(--surface-2) !important;
}
button[data-testid="stBaseButton-pillsActive"], button[data-testid="stBaseButton-segmented_controlActive"]{
  border-radius:999px !important; border:1px solid var(--cyan) !important; background:rgba(0,229,255,.14) !important;
  color:var(--cyan) !important;
}

/* Perfil / acceso */
.avatar{width:42px; height:42px; border-radius:14px; display:grid; place-items:center;
        font-weight:800; font-size:1.1rem; color:#04121a; flex:none;}
.who{display:flex; align-items:center; gap:12px; padding:14px; margin:4px 0 14px;
     background:var(--surface); border:1px solid var(--line); border-radius:16px;}
.who-name{font-weight:700; font-size:1rem; line-height:1.2;}
.who-sub{color:var(--muted); font-size:.78rem;}
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
  border:none !important; border-radius:12px !important; padding:.65rem 1rem !important; width:100%;
  transition:transform .15s ease, box-shadow .15s ease;
}
.stButton > button p, [data-testid="stFormSubmitButton"] > button p{color:#04121a !important;}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover{
  transform:translateY(-1px); box-shadow:0 8px 24px rgba(0,229,255,.25);
}
.stButton > button:disabled{opacity:.35;}
.st-key-logout button, .st-key-logout_side button, .st-key-volver button{
  background:transparent !important; color:var(--muted) !important; border:1px solid var(--line) !important;
}
.st-key-logout button p, .st-key-logout_side button p, .st-key-volver button p{color:var(--muted) !important;}
.stDownloadButton > button{
  background:transparent !important; color:var(--cyan) !important; font-weight:600 !important;
  border:1px solid rgba(0,229,255,.35) !important; border-radius:12px !important; width:100%;
  padding:.65rem 1rem !important;
}
.stDownloadButton > button p{color:var(--cyan) !important;}

/* ── TELÉFONO ── */
@media (max-width: 640px){
  .block-container{padding:1rem .8rem 3rem !important;}
  .app-title{font-size:1.45rem;}
  .kpi{padding:14px 16px; min-height:0; border-radius:16px;}
  .kpi-value{font-size:1.7rem; margin:8px 0;}
  .kpi.hero .kpi-value{font-size:2.15rem;}
  .tx-wrap, .cat-card{padding-left:14px; padding-right:14px;}
  .cat-amt{min-width:64px;}
  .stTabs [data-baseweb="tab"]{padding:0 11px; font-size:.9rem;}
  [data-testid="stForm"]{padding:14px !important;}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# CONEXIÓN A SUPABASE
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def _crear_cliente(url, key):
    return create_client(url, key)


def conectar():
    try:
        url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    except Exception:
        st.error("Faltan las claves de Supabase. Agrégalas en *Secrets* (SUPABASE_URL y SUPABASE_KEY).")
        st.stop()
    return _crear_cliente(url, key)


db = conectar()

if "db_ok" not in st.session_state:
    try:
        db.table("perfiles").select("nombre").limit(1).execute()
    except Exception as e:
        st.error("No pude conectar con Supabase. Revisa la URL, la clave y que hayas ejecutado el script SQL.")
        st.caption(f"Detalle técnico: {e}")
        st.stop()
    try:
        db.table("fijos").select("id").limit(1).execute()
        db.table("transacciones").select("origen,fijo_id,mes_fijo,pagado").limit(1).execute()
    except Exception as e:
        st.error("Falta un paso en Supabase: ejecuta el script de actualización "
                 "(supabase_actualizacion_fijos.sql) en el SQL Editor y recarga esta página.")
        st.caption(f"Detalle técnico: {e}")
        st.stop()
    st.session_state["db_ok"] = True


def intentar(fn, *args, **kwargs):
    """Ejecuta una acción de escritura y avisa en español si algo falla."""
    try:
        fn(*args, **kwargs)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error("No se pudo completar la acción. Revisa tu conexión e inténtalo de nuevo.")
        st.caption(f"Detalle técnico: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# DATOS
# ─────────────────────────────────────────────────────────────
COLUMNAS = ["id", "tipo", "categoria", "monto", "descripcion", "fecha", "origen", "fijo_id", "pagado"]


# ── PIN (se guarda con hash, nunca en texto plano) ──
def _hash_pin(pin, sal_hex):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(sal_hex), 120_000).hex()


def perfil_tiene_pin(nombre):
    return bool(db.table("perfiles").select("nombre").eq("nombre", nombre).execute().data)


def _guardar_pin(nombre, pin):
    sal = secrets.token_hex(16)
    db.table("perfiles").upsert(
        {"nombre": nombre, "pin_hash": _hash_pin(pin, sal), "sal": sal}, on_conflict="nombre"
    ).execute()


def crear_pin(nombre, pin):
    return intentar(_guardar_pin, nombre, pin)


def verificar_pin(nombre, pin):
    filas = db.table("perfiles").select("pin_hash,sal").eq("nombre", nombre).execute().data
    return bool(filas) and hmac.compare_digest(filas[0]["pin_hash"], _hash_pin(pin, filas[0]["sal"]))


# ── Movimientos ──
@st.cache_data(ttl=120, show_spinner=False)
def obtener_datos(perfil):
    filas, desde, paso = [], 0, 1000  # Supabase entrega máximo 1000 filas por consulta
    while True:
        lote = (
            db.table("transacciones").select(",".join(COLUMNAS)).eq("perfil", perfil)
            .order("fecha", desc=True).order("id", desc=True)
            .range(desde, desde + paso - 1).execute().data
        )
        filas.extend(lote)
        if len(lote) < paso:
            break
        desde += paso
    df = pd.DataFrame(filas, columns=COLUMNAS)
    df["monto"] = pd.to_numeric(df["monto"])
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha"]).copy()
    df["descripcion"] = df["descripcion"].fillna("")
    df["origen"] = df["origen"].fillna("")
    df["pagado"] = df["pagado"].fillna(False).astype(bool)
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    return df


def _insertar(perfil, tipo, categoria, monto, descripcion, fecha):
    db.table("transacciones").insert({
        "perfil": perfil, "tipo": tipo, "categoria": categoria,
        "monto": float(monto), "descripcion": descripcion, "fecha": str(fecha),
    }).execute()


def agregar_transaccion(*args):
    return intentar(_insertar, *args)


def _borrar(perfil, id_):
    db.table("transacciones").delete().eq("id", int(id_)).eq("perfil", perfil).execute()


def eliminar_transaccion(perfil, id_):
    return intentar(_borrar, perfil, id_)


def _insertar_lote(registros):
    for i in range(0, len(registros), 200):
        db.table("transacciones").insert(registros[i:i + 200]).execute()


def importar_registros(registros):
    return intentar(_insertar_lote, registros)


# ── Presupuestos y metas ──
@st.cache_data(ttl=120, show_spinner=False)
def obtener_presupuestos(perfil):
    filas = db.table("presupuestos").select("categoria,limite").eq("perfil", perfil).execute().data
    return {f["categoria"]: float(f["limite"]) for f in filas}


def _guardar_presupuesto(perfil, categoria, limite):
    if limite <= 0:
        db.table("presupuestos").delete().eq("perfil", perfil).eq("categoria", categoria).execute()
    else:
        db.table("presupuestos").upsert(
            {"perfil": perfil, "categoria": categoria, "limite": float(limite)},
            on_conflict="perfil,categoria",
        ).execute()


def guardar_presupuesto(perfil, categoria, limite):
    return intentar(_guardar_presupuesto, perfil, categoria, limite)


@st.cache_data(ttl=120, show_spinner=False)
def obtener_ajustes(perfil):
    filas = db.table("ajustes").select("clave,valor").eq("perfil", perfil).execute().data
    return {f["clave"]: f["valor"] for f in filas}


def _guardar_ajustes(perfil, pares):
    db.table("ajustes").upsert(
        [{"perfil": perfil, "clave": k, "valor": str(v)} for k, v in pares.items()],
        on_conflict="perfil,clave",
    ).execute()


def guardar_ajustes(perfil, pares):
    return intentar(_guardar_ajustes, perfil, pares)


# ── Sueldo fijo y gastos fijos ──
def fecha_en_mes(ym, dia):
    y, m = map(int, ym.split("-"))
    return datetime.date(y, m, min(int(dia), calendar.monthrange(y, m)[1]))


@st.cache_data(ttl=120, show_spinner=False)
def obtener_fijos(perfil):
    return (db.table("fijos").select("id,nombre,categoria,monto,dia")
            .eq("perfil", perfil).order("dia").order("id").execute().data)


def _leer_sueldo(perfil):
    aj = obtener_ajustes(perfil)
    try:
        monto = float(aj.get("sueldo_monto", "0") or 0)
    except ValueError:
        monto = 0.0
    try:
        dia = int(float(aj.get("sueldo_dia", "1") or 1))
    except ValueError:
        dia = 1
    return monto, min(max(dia, 1), 31)


def _mov_sueldo(perfil, monto, dia, ym):
    return {"perfil": perfil, "tipo": "Ingreso", "categoria": "Sueldo", "monto": float(monto),
            "descripcion": "Sueldo fijo", "fecha": str(fecha_en_mes(ym, dia)),
            "origen": "sueldo", "mes_fijo": ym, "pagado": True}


def _mov_fijo(perfil, f, ym, dia=None):
    return {"perfil": perfil, "tipo": "Gasto", "categoria": f["categoria"], "monto": float(f["monto"]),
            "descripcion": f["nombre"], "fecha": str(fecha_en_mes(ym, dia or f["dia"])),
            "origen": "fijo", "fijo_id": f["id"], "mes_fijo": ym, "pagado": False}


def _generar_fijos(perfil, ym):
    """Crea el sueldo y los gastos fijos del mes que todavía no existan."""
    ya = (db.table("transacciones").select("origen,fijo_id")
          .eq("perfil", perfil).eq("mes_fijo", ym).execute().data)
    tiene_sueldo = any(r["origen"] == "sueldo" for r in ya)
    con_fijo = {r["fijo_id"] for r in ya if r["origen"] == "fijo"}
    nuevos = []
    sueldo, dia_s = _leer_sueldo(perfil)
    if sueldo > 0 and not tiene_sueldo:
        nuevos.append(_mov_sueldo(perfil, sueldo, dia_s, ym))
    for f in obtener_fijos(perfil):
        if f["id"] not in con_fijo:
            nuevos.append(_mov_fijo(perfil, f, ym))
    for fila in nuevos:
        try:
            db.table("transacciones").insert(fila).execute()
        except Exception:
            pass  # ya existía (el índice único evita duplicados)


def generar_mes(perfil, ym):
    """Se ejecuta una sola vez por mes y perfil, al abrir la app."""
    try:
        if obtener_ajustes(perfil).get(f"gen_{ym}") == "1":
            return
        _generar_fijos(perfil, ym)
        _guardar_ajustes(perfil, {f"gen_{ym}": "1"})
        st.cache_data.clear()
    except Exception as e:
        st.warning("No pude preparar tus fijos de este mes. Recarga la página para intentarlo de nuevo.")
        st.caption(f"Detalle técnico: {e}")


def _guardar_sueldo(perfil, monto, dia, ym):
    _guardar_ajustes(perfil, {"sueldo_monto": monto, "sueldo_dia": dia})
    ya = (db.table("transacciones").select("id")
          .eq("perfil", perfil).eq("origen", "sueldo").eq("mes_fijo", ym).execute().data)
    if monto <= 0:
        if ya:
            db.table("transacciones").delete().eq("perfil", perfil).eq("origen", "sueldo").eq("mes_fijo", ym).execute()
    elif ya:
        db.table("transacciones").update(
            {"monto": float(monto), "fecha": str(fecha_en_mes(ym, dia))}
        ).eq("perfil", perfil).eq("origen", "sueldo").eq("mes_fijo", ym).execute()
    else:
        db.table("transacciones").insert(_mov_sueldo(perfil, monto, dia, ym)).execute()


def guardar_sueldo(perfil, monto, dia, ym):
    return intentar(_guardar_sueldo, perfil, monto, dia, ym)


def _agregar_fijo(perfil, nombre, categoria, monto, dia, ym):
    fila = db.table("fijos").insert({"perfil": perfil, "nombre": nombre, "categoria": categoria,
                                     "monto": float(monto), "dia": int(dia)}).execute().data[0]
    db.table("transacciones").insert(_mov_fijo(perfil, fila, ym)).execute()


def agregar_fijo(*args):
    return intentar(_agregar_fijo, *args)


def _actualizar_fijo(perfil, id_, monto, dia, ym):
    db.table("fijos").update({"monto": float(monto), "dia": int(dia)}).eq("id", int(id_)).eq("perfil", perfil).execute()
    db.table("transacciones").update(
        {"monto": float(monto), "fecha": str(fecha_en_mes(ym, dia))}
    ).eq("perfil", perfil).eq("fijo_id", int(id_)).eq("mes_fijo", ym).execute()


def actualizar_fijo(*args):
    return intentar(_actualizar_fijo, *args)


def _quitar_fijo(perfil, id_, ym):
    # Si ya lo pagaste este mes, ese movimiento se queda; si no, se quita junto con el fijo
    (db.table("transacciones").delete().eq("perfil", perfil).eq("fijo_id", int(id_))
     .eq("mes_fijo", ym).eq("origen", "fijo").eq("pagado", False).execute())
    db.table("fijos").delete().eq("id", int(id_)).eq("perfil", perfil).execute()


def quitar_fijo(*args):
    return intentar(_quitar_fijo, *args)


def _marcar_pagado(perfil, id_, valor):
    db.table("transacciones").update({"pagado": bool(valor)}).eq("id", int(id_)).eq("perfil", perfil).execute()


def marcar_pagado(*args):
    return intentar(_marcar_pagado, *args)


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
        etiqueta_fijo = " · 📌 fijo" if r.origen in ("fijo", "sueldo") else ""
        filas.append(
            f'<div class="tx"><div class="tx-ico">{icono(r.tipo, r.categoria)}</div>'
            f'<div class="tx-main"><div class="tx-title">{titulo}</div>'
            f'<div class="tx-sub">{html.escape(r.categoria)} · {r.fecha:%d/%m/%Y}{etiqueta_fijo}</div></div>'
            f'<div class="tx-amt {"in" if es_ing else ""}">{signo}{MONEDA}{r.monto:,.2f}</div></div>'
        )
    return f'<div class="tx-wrap">{"".join(filas)}</div>'


# ─────────────────────────────────────────────────────────────
# PANTALLA DE ACCESO (elegir perfil + PIN)
# ─────────────────────────────────────────────────────────────
def pantalla_acceso():
    st.markdown("<div style='height:3vh'></div>", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.6, 1])
    with centro:
        st.markdown(
            '<div class="login-logo">💰</div>'
            '<div class="app-title" style="text-align:center">Mis Finanzas</div>'
            '<div class="app-sub" style="text-align:center;margin-bottom:22px">¿Quién va a entrar?</div>',
            unsafe_allow_html=True,
        )
        elegido = st.session_state.get("perfil_elegido")

        if elegido not in PERFILES:
            for nombre in PERFILES:
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
                st.caption("Primera vez: crea un PIN de 4 a 6 números para proteger tus finanzas.")
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
            elif crear_pin(elegido, pin):
                st.session_state["perfil"] = elegido
                st.session_state.pop("perfil_elegido", None)
                st.rerun()

        if st.button("← Cambiar de perfil", key="volver"):
            st.session_state.pop("perfil_elegido", None)
            st.rerun()


# ─────────────────────────────────────────────────────────────
# ARRANQUE: acceso por perfil
# ─────────────────────────────────────────────────────────────
perfil = st.session_state.get("perfil")
if perfil not in PERFILES:
    pantalla_acceso()
    st.stop()

hoy = datetime.datetime.now(ZONA).date()  # hora de Venezuela, aunque el servidor esté en otro país
mes_actual = hoy.strftime("%Y-%m")

if st.session_state.get("gen_ok") != (perfil, mes_actual):
    generar_mes(perfil, mes_actual)  # sueldo y gastos fijos del mes, una sola vez
    st.session_state["gen_ok"] = (perfil, mes_actual)

df = obtener_datos(perfil)

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")


def elegir_tipo(prefijo):
    fmt = {"Gasto": "💸 Gasto", "Ingreso": "💵 Ingreso"}.get
    if hasattr(st, "segmented_control"):
        return st.segmented_control("Tipo", ["Gasto", "Ingreso"], default="Gasto", format_func=fmt,
                                    key=f"{prefijo}_tipo", label_visibility="collapsed") or "Gasto"
    return st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True, format_func=fmt,
                    key=f"{prefijo}_tipo", label_visibility="collapsed")


def elegir_categoria(tipo_, prefijo):
    opciones = list(CATEGORIAS[tipo_])
    fmt = lambda c: f"{CATEGORIAS[tipo_][c]} {c}"
    if hasattr(st, "pills"):
        return st.pills("Categoría", opciones, selection_mode="single", default=opciones[0],
                        format_func=fmt, key=f"{prefijo}_cat_{tipo_}")
    return st.selectbox("Categoría", opciones, format_func=fmt, key=f"{prefijo}_cat_{tipo_}")


def formulario_movimiento(prefijo):
    """Formulario de nuevo movimiento. Se usa en la barra lateral (PC) y en la pestaña Agregar (teléfono)."""
    # El tipo va FUERA del formulario para que las categorías cambien al instante
    tipo = elegir_tipo(prefijo)
    with st.form(f"form_mov_{prefijo}", clear_on_submit=True):
        categoria = elegir_categoria(tipo, prefijo)
        monto = st.number_input(f"Monto ({MONEDA})", min_value=0.0, value=0.0, step=1.0,
                                format="%.2f", key=f"{prefijo}_monto")
        descripcion = st.text_input("Descripción", placeholder="Opcional", max_chars=80,
                                    key=f"{prefijo}_desc")
        fecha = st.date_input("Fecha", hoy, format="DD/MM/YYYY", key=f"{prefijo}_fecha")
        guardar = st.form_submit_button("Guardar movimiento")

    if guardar:
        if categoria is None:
            st.error("Elige una categoría.")
        elif monto <= 0:
            st.error("El monto debe ser mayor a 0.")
        elif agregar_transaccion(perfil, tipo, categoria, round(monto, 2), descripcion.strip(), fecha):
            st.session_state["flash"] = f"{tipo} de {dinero(monto)} guardado"
            st.session_state["periodo"] = fecha.strftime("%Y-%m")  # saltar al mes del movimiento
            st.rerun()


# ─────────────────────────────────────────────────────────────
# BARRA LATERAL (en el teléfono se abre con la flecha de arriba a la izquierda)
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="who">{avatar(perfil)}<div><div class="who-name">{html.escape(perfil)}</div>'
        f'<div class="who-sub">Mis finanzas</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sec">Nuevo movimiento</div>', unsafe_allow_html=True)
    formulario_movimiento("side")

    st.markdown("---")
    if not df.empty:
        respaldo_lateral = (
            df[["fecha", "tipo", "categoria", "monto", "descripcion"]]
            .assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m-%d"))
            .to_csv(index=False)
            .encode("utf-8-sig")
        )
        st.download_button("⬇️ Respaldo (CSV)", respaldo_lateral, key="dl_side",
                           file_name=f"finanzas_{perfil.lower()}_respaldo.csv", mime="text/csv")
    if st.button("Cambiar de perfil", key="logout_side"):
        st.session_state.clear()
        st.rerun()
    st.markdown(
        "<p style='color:#8b98ab; font-size:.78rem; text-align:center; margin-top:12px;'>"
        "🔒 Datos en la nube · cada perfil tiene su PIN.</p>",
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

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

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

tab_res, tab_add, tab_mov, tab_fijos, tab_pre, tab_meta, tab_cuenta = st.tabs(
    ["📊 Resumen", "➕ Agregar", "🧾 Historial", "📌 Fijos", "🎯 Presupuesto", "🏆 Metas", "⚙️ Cuenta"]
)

# ─────────────────────────────────────────────────────────────
# TAB · RESUMEN
# ─────────────────────────────────────────────────────────────
with tab_res:
    if df.empty:
        st.info("Aún no tienes movimientos. Ve a la pestaña **➕ Agregar** para registrar el primero.")
    else:
        c1, c2, c3 = st.columns([1.4, 1, 1])
        c1.markdown(tarjeta("Balance", dinero(bal), "📊", hero=True,
                            nota="Ingresos − gastos", negativo=bal < 0), unsafe_allow_html=True)
        c2.markdown(tarjeta("Ingresos", dinero(ing), "💵", d_ing, True, nota=nota_periodo),
                    unsafe_allow_html=True)
        c3.markdown(tarjeta("Gastos", dinero(gas), "💸", d_gas, False, nota=nota_periodo),
                    unsafe_allow_html=True)

        sueldo_p = df_p.loc[df_p["origen"] == "sueldo", "monto"].sum()
        fijos_p = df_p.loc[(df_p["tipo"] == "Gasto") & (df_p["origen"] == "fijo"), "monto"].sum()
        if sueldo_p > 0 or fijos_p > 0:
            st.caption(f"Sueldo {dinero(sueldo_p)} · Bonos y extras {dinero(ing - sueldo_p)} · "
                       f"Fijos {dinero(fijos_p)} · Variables {dinero(gas - fijos_p)}")

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
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
            pie_chart = None
            if periodo == TODO:
                st.markdown('<div class="sec">Gastos por mes</div>', unsafe_allow_html=True)
                base = (df[df["tipo"] == "Gasto"].groupby("mes", as_index=False)["monto"].sum()
                        .sort_values("mes").tail(12))
                base["etiqueta"] = base["mes"].map(etiqueta_corta)
                eje_x = alt.X("etiqueta:N", sort=base["etiqueta"].tolist(), title=None,
                              axis=alt.Axis(labelAngle=0, labelColor=MUTED, ticks=False, domain=False))
                titulo_x = "Mes"
            else:
                st.markdown('<div class="sec">Gasto diario (sin fijos)</div>', unsafe_allow_html=True)
                gastos_p = gastos_p[gastos_p["origen"] != "fijo"]
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
                pie_chart = (f"Promedio diario sin fijos: "
                             f"**{dinero(gastos_p['monto'].sum() / max(dias_transcurridos, 1))}**")

            if gastos_p.empty:
                st.info("Aún no hay gastos variables en este periodo.")
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
                    .properties(height=230)
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
# TAB · AGREGAR
# ─────────────────────────────────────────────────────────────
with tab_add:
    st.markdown('<div class="sec">Nuevo movimiento</div>', unsafe_allow_html=True)
    formulario_movimiento("tab")

# ─────────────────────────────────────────────────────────────
# TAB · HISTORIAL
# ─────────────────────────────────────────────────────────────
with tab_mov:
    filtro_tipo = st.radio("Mostrar", ["Todos", "Ingresos", "Gastos"], horizontal=True,
                           label_visibility="collapsed")
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
        st.caption(f"{len(df_f)} movimientos · ingresos {dinero(totales(df_f)[0])} · "
                   f"gastos {dinero(totales(df_f)[1])}")
        ver_tabla = st.toggle("Vista de tabla", value=False)

        if not ver_tabla:
            st.markdown(lista_movimientos(df_f.head(60)), unsafe_allow_html=True)
            if len(df_f) > 60:
                st.caption("Mostrando los 60 más recientes. Activa «Vista de tabla» para ver todos.")
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
                if eliminar_transaccion(perfil, elegido):
                    st.session_state["flash"] = "Movimiento eliminado"
                    st.rerun()

# ─────────────────────────────────────────────────────────────
# TAB · FIJOS (sueldo fijo + gastos fijos mensuales)
# ─────────────────────────────────────────────────────────────
def _cambiar_pagado(id_, clave):
    marcar_pagado(st.session_state["perfil"], id_, st.session_state[clave])


with tab_fijos:
    sueldo, dia_sueldo = _leer_sueldo(perfil)
    fijos_def = obtener_fijos(perfil)
    mov_fijos = df[(df["mes"] == mes_ref) & (df["origen"] == "fijo")].sort_values(["fecha", "id"])

    # ── Sueldo fijo ──
    if sueldo > 0:
        st.markdown(
            f'<div class="sueldo"><div class="sueldo-label">Sueldo fijo</div>'
            f'<div class="sueldo-val">{dinero(sueldo)} <small>/ mes · cobras el día {dia_sueldo}</small></div>'
            f'<div class="bud-foot">Entra solo cada mes. Bonos y extras se agregan aparte como ingresos.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("Define tu sueldo fijo y se sumará solo cada mes como ingreso. "
                "Bonos y extras los agregas aparte.")

    with st.expander("✏️ Cambiar mi sueldo fijo", expanded=sueldo <= 0):
        with st.form("form_sueldo"):
            nuevo_sueldo = st.number_input(f"Sueldo mensual ({MONEDA}) · 0 para quitarlo", min_value=0.0,
                                           value=sueldo, step=10.0, format="%.2f")
            nuevo_dia_s = st.number_input("Día de cobro", min_value=1, max_value=31,
                                          value=dia_sueldo, step=1)
            if st.form_submit_button("Guardar sueldo"):
                if guardar_sueldo(perfil, nuevo_sueldo, int(nuevo_dia_s), mes_actual):
                    st.session_state["flash"] = "Sueldo fijo guardado"
                    st.rerun()

    # ── Gastos fijos del mes ──
    st.markdown('<div class="sec">Gastos fijos</div>', unsafe_allow_html=True)
    if periodo == TODO:
        st.caption(f"Mostrando {etiqueta_mes(mes_ref)}.")

    if mov_fijos.empty:
        st.info("Aún no tienes gastos fijos este mes. Agrega el primero abajo (alquiler, internet, luz…).")
    else:
        total_f = mov_fijos["monto"].sum()
        pagado_f = mov_fijos.loc[mov_fijos["pagado"], "monto"].sum()
        pct_pagado = pagado_f / total_f * 100 if total_f else 0
        st.markdown(
            f'<div class="bud"><div class="bud-head"><b>{etiqueta_mes(mes_ref)}</b>'
            f'<span>Pagado {dinero(pagado_f)} de {dinero(total_f)}</span></div>'
            f'<div class="bar"><div style="width:{pct_pagado:.1f}%"></div></div></div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            for r in mov_fijos.itertuples():
                clave = f"pag_{int(r.id)}"
                st.checkbox(
                    f"{icono('Gasto', r.categoria)}  {r.descripcion} · día {r.fecha.day} · {dinero(r.monto)}",
                    value=bool(r.pagado), key=clave,
                    on_change=_cambiar_pagado, args=(int(r.id), clave),
                )
        st.caption("Marca cada gasto cuando lo pagues. Los fijos ya cuentan en tu balance desde el día 1.")

    with st.expander("➕ Agregar gasto fijo", expanded=not fijos_def):
        with st.form("form_nuevo_fijo", clear_on_submit=True):
            nombre_f = st.text_input("Nombre", placeholder="Ej: Alquiler", max_chars=40)
            cat_f = st.selectbox("Categoría", list(CATEGORIAS["Gasto"]),
                                 format_func=lambda c: f"{CATEGORIAS['Gasto'][c]}  {c}")
            monto_f = st.number_input(f"Monto mensual ({MONEDA})", min_value=0.0, value=0.0,
                                      step=1.0, format="%.2f")
            dia_f = st.number_input("Día de pago", min_value=1, max_value=31, value=1, step=1)
            if st.form_submit_button("Agregar gasto fijo"):
                if not nombre_f.strip():
                    st.error("Ponle un nombre al gasto.")
                elif monto_f <= 0:
                    st.error("El monto debe ser mayor a 0.")
                elif agregar_fijo(perfil, nombre_f.strip(), cat_f, round(monto_f, 2), int(dia_f), mes_actual):
                    st.session_state["flash"] = f"{nombre_f.strip()} agregado a tus fijos"
                    st.rerun()

    if fijos_def:
        with st.expander("✏️ Editar o quitar un gasto fijo"):
            opciones_f = {f["id"]: f'{f["nombre"]} · {dinero(float(f["monto"]))}' for f in fijos_def}
            elegido_f = st.selectbox("Gasto fijo", list(opciones_f), format_func=opciones_f.get,
                                     label_visibility="collapsed")
            f_sel = next(f for f in fijos_def if f["id"] == elegido_f)
            with st.form("form_editar_fijo"):
                nuevo_monto_f = st.number_input(f"Monto mensual ({MONEDA})", min_value=0.01,
                                                value=float(f_sel["monto"]), step=1.0, format="%.2f",
                                                key=f"edm_{elegido_f}")
                nuevo_dia_f = st.number_input("Día de pago", min_value=1, max_value=31,
                                              value=int(f_sel["dia"]), step=1, key=f"edd_{elegido_f}")
                col_g, col_q = st.columns(2)
                guardar_cambio = col_g.form_submit_button("Guardar cambio")
                quitar = col_q.form_submit_button("Quitar")
            if guardar_cambio:
                if actualizar_fijo(perfil, elegido_f, round(nuevo_monto_f, 2), int(nuevo_dia_f), mes_actual):
                    st.session_state["flash"] = "Gasto fijo actualizado"
                    st.rerun()
            elif quitar:
                if quitar_fijo(perfil, elegido_f, mes_actual):
                    st.session_state["flash"] = f"{f_sel['nombre']} quitado de tus fijos"
                    st.rerun()
            st.caption("Los cambios valen desde este mes en adelante. Los meses anteriores no se modifican.")

    # ── Libre para gastar ──
    df_m = df[df["mes"] == mes_ref]
    ing_m, gas_m, bal_m = totales(df_m)
    fijos_m = df_m.loc[(df_m["tipo"] == "Gasto") & (df_m["origen"] == "fijo"), "monto"].sum()
    if ing_m > 0 or fijos_m > 0:
        pct_fijos = min(fijos_m / ing_m * 100, 100) if ing_m > 0 else 100
        detalle = f"Variables gastados: {dinero(gas_m - fijos_m)}"
        if mes_ref == mes_actual and bal_m > 0:
            anio_m, mes_m = map(int, mes_ref.split("-"))
            dias_restantes = calendar.monthrange(anio_m, mes_m)[1] - hoy.day + 1
            detalle += f" · unos {dinero(bal_m / max(dias_restantes, 1))} por día hasta fin de mes"
        color_libre = "var(--green)" if bal_m >= 0 else "var(--rose)"
        st.markdown(
            f'<div class="bud" style="margin-top:14px"><div class="bud-foot" style="margin:0 0 4px">Libre para gastar · {etiqueta_mes(mes_ref)}</div>'
            f'<div class="goal-big" style="color:{color_libre}">{dinero(bal_m)}</div>'
            f'<div class="stack" style="margin:12px 0 8px"><div style="width:{pct_fijos:.1f}%;background:var(--amber)"></div>'
            f'<div style="flex:1;background:var(--cyan)"></div></div>'
            f'<div class="bud-head"><span>Fijos {dinero(fijos_m)}</span><span>Ingresos {dinero(ing_m)}</span></div>'
            f'<div class="bud-foot">{detalle}</div></div>',
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────────────────────
# TAB · PRESUPUESTO (por categoría, mensuales)
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
            limite_p = st.number_input(f"Límite mensual ({MONEDA}) · 0 para quitarlo",
                                       min_value=0.0, value=0.0, step=10.0, format="%.2f")
            if st.form_submit_button("Guardar presupuesto"):
                if guardar_presupuesto(perfil, cat_p, limite_p):
                    st.session_state["flash"] = "Presupuesto actualizado"
                    st.rerun()

# ─────────────────────────────────────────────────────────────
# TAB · METAS DE AHORRO
# ─────────────────────────────────────────────────────────────
with tab_meta:
    ajustes = obtener_ajustes(perfil)
    meta_nombre = ajustes.get("meta_nombre", "")
    try:
        meta_obj = float(ajustes.get("meta_objetivo", "0"))
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
        elif not df.empty:
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
                if guardar_ajustes(perfil, {"meta_nombre": nuevo_nombre.strip(), "meta_objetivo": nuevo_obj}):
                    st.session_state["flash"] = "Meta guardada"
                    st.rerun()

# ─────────────────────────────────────────────────────────────
# TAB · CUENTA
# ─────────────────────────────────────────────────────────────
with tab_cuenta:
    st.markdown(
        f'<div class="who">{avatar(perfil)}<div><div class="who-name">{html.escape(perfil)}</div>'
        f'<div class="who-sub">Perfil activo · datos en la nube</div></div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Cambiar de perfil / cerrar sesión", key="logout"):
        st.session_state.clear()
        st.rerun()

    st.markdown('<div class="sec">Respaldo</div>', unsafe_allow_html=True)
    if df.empty:
        st.caption("Cuando tengas movimientos podrás descargar un respaldo aquí.")
    else:
        respaldo = (
            df[["fecha", "tipo", "categoria", "monto", "descripcion"]]
            .assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m-%d"))
            .to_csv(index=False)
            .encode("utf-8-sig")
        )
        st.download_button("⬇️ Descargar respaldo (CSV)", respaldo, key="dl_cuenta",
                           file_name=f"finanzas_{perfil.lower()}_respaldo.csv", mime="text/csv")

    with st.expander("⬆️ Importar movimientos desde un CSV"):
        st.caption("Sirve para traer los datos de la versión anterior de la app. "
                   "Columnas necesarias: fecha, tipo, categoria, monto (y descripcion, opcional). "
                   "Importa el archivo una sola vez para no duplicar movimientos.")
        n_csv = st.session_state.get("csv_n", 0)
        archivo = st.file_uploader("Archivo CSV", type="csv", key=f"csv_{n_csv}")
        if archivo is not None and st.button("Importar a mi perfil"):
            try:
                imp = pd.read_csv(archivo)
                imp.columns = [str(c).strip().lower() for c in imp.columns]
                faltan = {"fecha", "tipo", "categoria", "monto"} - set(imp.columns)
                if faltan:
                    st.error(f"Al archivo le faltan columnas: {', '.join(sorted(faltan))}")
                else:
                    if "descripcion" not in imp.columns:
                        imp["descripcion"] = ""
                    imp["fecha"] = pd.to_datetime(imp["fecha"], errors="coerce")
                    imp["monto"] = pd.to_numeric(imp["monto"], errors="coerce")
                    imp["tipo"] = imp["tipo"].astype(str).str.strip().str.capitalize()
                    imp = imp[imp["tipo"].isin(["Gasto", "Ingreso"]) & imp["fecha"].notna() & (imp["monto"] > 0)]
                    registros = [
                        {"perfil": perfil, "tipo": r.tipo, "categoria": str(r.categoria).strip(),
                         "monto": round(float(r.monto), 2),
                         "descripcion": "" if pd.isna(r.descripcion) else str(r.descripcion).strip(),
                         "fecha": r.fecha.strftime("%Y-%m-%d")}
                        for r in imp.itertuples()
                    ]
                    if not registros:
                        st.warning("No encontré movimientos válidos en el archivo.")
                    elif importar_registros(registros):
                        st.session_state["csv_n"] = n_csv + 1
                        st.session_state["flash"] = f"{len(registros)} movimientos importados"
                        st.rerun()
            except Exception as e:
                st.error("No pude leer ese archivo. Asegúrate de que sea el CSV de respaldo.")
                st.caption(f"Detalle técnico: {e}")

    st.caption("🔒 Cada perfil tiene su propio PIN y sus propios datos.")
