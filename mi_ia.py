"""
Mis Finanzas · app de finanzas personales
Stack: Streamlit + Pandas + SQLite local (sin internet, sin APIs).
"""
import datetime
import html
import math
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

NOMBRE = "Leiver"
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

/* Quitar elementos de Streamlit, pero conservar el botón del sidebar (importante en móvil) */
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stMainMenu"],
[data-testid="stAppDeployButton"], .stDeployButton, [data-testid="stToolbarActions"]{display:none !important;}
header[data-testid="stHeader"], [data-testid="stToolbar"]{background:transparent !important;}
/* Botones para abrir/cerrar la barra lateral: siempre visibles */
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
.side-brand{font-size:1.15rem; font-weight:700; margin:4px 0 18px;}

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


@st.cache_resource
def init_db():
    """Crea las tablas una sola vez por sesión del servidor."""
    with get_conn() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT,
                categoria TEXT,
                monto REAL,
                descripcion TEXT,
                fecha TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_transacciones_fecha ON transacciones(fecha);
            CREATE TABLE IF NOT EXISTS presupuestos (
                categoria TEXT PRIMARY KEY,
                limite REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ajustes (
                clave TEXT PRIMARY KEY,
                valor TEXT
            );
            """
        )
    return True


def agregar_transaccion(tipo, categoria, monto, descripcion, fecha):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transacciones (tipo, categoria, monto, descripcion, fecha) VALUES (?, ?, ?, ?, ?)",
            (tipo, categoria, float(monto), descripcion, str(fecha)),
        )


def eliminar_transaccion(id_):
    with get_conn() as conn:
        conn.execute("DELETE FROM transacciones WHERE id = ?", (int(id_),))


def obtener_datos():
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT id, tipo, categoria, monto, descripcion, fecha FROM transacciones "
            "ORDER BY fecha DESC, id DESC",
            conn,
        )
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha"]).copy()
    df["descripcion"] = df["descripcion"].fillna("")
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    return df


def obtener_presupuestos():
    with get_conn() as conn:
        filas = conn.execute("SELECT categoria, limite FROM presupuestos").fetchall()
    return {c: l for c, l in filas}


def guardar_presupuesto(categoria, limite):
    with get_conn() as conn:
        if limite <= 0:
            conn.execute("DELETE FROM presupuestos WHERE categoria = ?", (categoria,))
        else:
            conn.execute(
                "INSERT INTO presupuestos (categoria, limite) VALUES (?, ?) "
                "ON CONFLICT(categoria) DO UPDATE SET limite = excluded.limite",
                (categoria, float(limite)),
            )


def get_ajuste(clave, default=""):
    with get_conn() as conn:
        fila = conn.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    return fila[0] if fila else default


def set_ajuste(clave, valor):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, str(valor)),
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
# DATOS Y ESTADO
# ─────────────────────────────────────────────────────────────
init_db()
df = obtener_datos()
hoy = datetime.date.today()
mes_actual = hoy.strftime("%Y-%m")

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

# ─────────────────────────────────────────────────────────────
# BARRA LATERAL: registrar movimiento
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="side-brand">💰 Mis Finanzas</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec">Nuevo movimiento</div>', unsafe_allow_html=True)

    # El tipo va FUERA del formulario para que las categorías cambien al instante
    tipo = st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True,
                    label_visibility="collapsed", key="tipo_mov")

    with st.form("form_transaccion", clear_on_submit=True):
        categoria = st.selectbox(
            "Categoría",
            list(CATEGORIAS[tipo]),
            format_func=lambda c: f"{CATEGORIAS[tipo][c]}  {c}",
        )
        monto = st.number_input(f"Monto ({MONEDA})", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        descripcion = st.text_input("Descripción (opcional)", max_chars=80)
        fecha = st.date_input("Fecha", hoy)
        guardar = st.form_submit_button("Guardar movimiento")

    if guardar:
        if monto <= 0:
            st.error("El monto debe ser mayor a 0.")
        else:
            agregar_transaccion(tipo, categoria, round(monto, 2), descripcion.strip(), fecha)
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
        st.download_button("⬇️ Respaldo completo (CSV)", respaldo,
                           file_name="finanzas_respaldo.csv", mime="text/csv")
    st.markdown(
        "<p style='color:#8b98ab; font-size:.78rem; text-align:center; margin-top:12px;'>"
        "🔒 Tus datos viven en una base SQLite local.</p>",
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
        f'<div class="app-title">Hola, {html.escape(NOMBRE)} 👋</div>'
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
        st.markdown('<div class="sec">Gastos por categoría</div>', unsafe_allow_html=True)
        gc = (
            df_p[df_p["tipo"] == "Gasto"]
            .groupby("categoria", as_index=False)["monto"].sum()
            .sort_values("monto", ascending=False)
        )
        if gc.empty:
            st.info("Aún no hay gastos en este periodo.")
        else:
            chart = (
                alt.Chart(gc)
                .mark_bar(cornerRadiusEnd=6, color=CIAN, size=18)
                .encode(
                    y=alt.Y("categoria:N", sort="-x", title=None,
                            axis=alt.Axis(labelColor="#c9d3e0", ticks=False, domain=False, labelLimit=140)),
                    x=alt.X("monto:Q", title=None,
                            axis=alt.Axis(labelColor=MUTED, gridColor="rgba(255,255,255,0.06)",
                                          domain=False, ticks=False)),
                    tooltip=[alt.Tooltip("categoria:N", title="Categoría"),
                             alt.Tooltip("monto:Q", title="Total", format=",.2f")],
                )
                .properties(height=max(180, 44 * len(gc)))
                .configure_view(strokeWidth=0)
                .configure(background="transparent")
            )
            stretch(st.altair_chart, chart)
            top = gc.iloc[0]
            st.caption(f"Tu mayor gasto es **{top['categoria']}** "
                       f"({top['monto'] / gc['monto'].sum() * 100:.0f}% del total).")

    with g2:
        st.markdown('<div class="sec">Evolución mensual</div>', unsafe_allow_html=True)
        res = df.groupby(["mes", "tipo"])["monto"].sum().unstack(fill_value=0)
        for col in ("Ingreso", "Gasto"):
            if col not in res:
                res[col] = 0.0
        res = res[["Ingreso", "Gasto"]].sort_index().tail(6).reset_index()
        res["etiqueta"] = res["mes"].map(etiqueta_corta)
        orden = res["etiqueta"].tolist()
        largo = res.melt(id_vars="etiqueta", value_vars=["Ingreso", "Gasto"],
                         var_name="tipo", value_name="monto")
        linea = (
            alt.Chart(largo)
            .mark_line(point=alt.OverlayMarkDef(size=70), strokeWidth=3, interpolate="monotone")
            .encode(
                x=alt.X("etiqueta:N", sort=orden, title=None,
                        axis=alt.Axis(labelAngle=0, labelColor=MUTED, ticks=False, domain=False)),
                y=alt.Y("monto:Q", title=None,
                        axis=alt.Axis(labelColor=MUTED, gridColor="rgba(255,255,255,0.06)",
                                      domain=False, ticks=False)),
                color=alt.Color("tipo:N",
                                scale=alt.Scale(domain=["Ingreso", "Gasto"], range=[CIAN, ROSA]),
                                legend=alt.Legend(orient="top", title=None, labelColor="#c9d3e0")),
                tooltip=[alt.Tooltip("etiqueta:N", title="Mes"),
                         alt.Tooltip("tipo:N", title="Tipo"),
                         alt.Tooltip("monto:Q", title="Total", format=",.2f")],
            )
            .properties(height=max(180, 44 * max(len(gc), 4)))
            .configure_view(strokeWidth=0)
            .configure(background="transparent")
        )
        stretch(st.altair_chart, linea)

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
                           file_name=f"finanzas_{nombre_csv}.csv", mime="text/csv")

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
                eliminar_transaccion(elegido)
                st.session_state["flash"] = "Movimiento eliminado"
                st.rerun()

# ─────────────────────────────────────────────────────────────
# TAB 3 · PRESUPUESTOS (por categoría, mensuales)
# ─────────────────────────────────────────────────────────────
with tab_pre:
    presupuestos = obtener_presupuestos()
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
                guardar_presupuesto(cat_p, limite_p)
                st.session_state["flash"] = "Presupuesto actualizado"
                st.rerun()

# ─────────────────────────────────────────────────────────────
# TAB 4 · METAS DE AHORRO
# ─────────────────────────────────────────────────────────────
with tab_meta:
    meta_nombre = get_ajuste("meta_nombre", "")
    try:
        meta_obj = float(get_ajuste("meta_objetivo", "0"))
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
                set_ajuste("meta_nombre", nuevo_nombre.strip())
                set_ajuste("meta_objetivo", nuevo_obj)
                st.session_state["flash"] = "Meta guardada"
                st.rerun()
