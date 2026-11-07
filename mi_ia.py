import streamlit as st
import pandas as pd
import sqlite3
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Finanzas Leiver", page_icon="💰", layout="wide")

# --- CSS PERSONALIZADO (Conservando tu estilo oscuro y elegante) ---
st.markdown("""
<style>
    :root { --bg-deep-space: #0e121b; --cyan-neon: #00e5ff; --text-muted: #8a99ad; --glass: rgba(24,29,40,0.7); }
    .stApp { background: radial-gradient(circle at 50% 0%, #1b2436 0%, var(--bg-deep-space) 70%) !important; color: #fff !important; font-family: 'Inter', -apple-system, sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 2rem !important; max-width: 1100px !important; }
    
    /* Tarjetas de Métricas (Ingresos, Gastos, Balance) */
    [data-testid="stMetricValue"] { color: #00e5ff !important; font-size: 2rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #8a99ad !important; font-size: 0.9rem !important; text-transform: uppercase; letter-spacing: 1px; }
    [data-testid="stMetric"] { background: var(--glass) !important; border: 1px solid rgba(0, 229, 255, 0.15) !important; padding: 20px !important; border-radius: 16px !important; box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0f1420 !important; border-right: 1px solid rgba(255,255,255,0.05) !important; }
    .stButton button { background-color: #00e5ff !important; color: #000 !important; font-weight: 700 !important; border-radius: 8px !important; width: 100%; height: 45px; }
    .stButton button:hover { background-color: #00b8cc !important; color: #fff !important; }
    
    /* Títulos */
    h1, h2, h3 { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

# --- CONEXIÓN A LA BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect('finanzas.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            categoria TEXT,
            monto REAL,
            descripcion TEXT,
            fecha TEXT
        )
    ''')
    conn.commit()
    return conn

conn = conectar_db()
c = conn.cursor()

# --- FUNCIONES ---
def agregar_transaccion(tipo, categoria, monto, descripcion, fecha):
    c.execute('INSERT INTO transacciones (tipo, categoria, monto, descripcion, fecha) VALUES (?, ?, ?, ?, ?)',
              (tipo, categoria, monto, descripcion, str(fecha)))
    conn.commit()

def obtener_datos():
    query = "SELECT * FROM transacciones ORDER BY fecha DESC"
    return pd.read_sql_query(query, conn)

# --- BARRA LATERAL (FORMULARIO) ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #00e5ff;'>💸 Registrar</h2>", unsafe_allow_html=True)
    
    with st.form("form_transaccion", clear_on_submit=True):
        tipo = st.selectbox("Tipo de movimiento", ["Gasto", "Ingreso"])
        
        if tipo == "Gasto":
            categorias = ["Comida", "Transporte", "Ropa", "Servicios", "Ocio", "Salud", "Otros"]
        else:
            categorias = ["Sueldo", "Ventas", "Regalo", "Inversión", "Otros"]
            
        categoria = st.selectbox("Categoría", categorias)
        monto = st.number_input("Monto ($)", min_value=0.01, step=1.0, format="%.2f")
        descripcion = st.text_input("Descripción (opcional)")
        fecha = st.date_input("Fecha", datetime.date.today())
        
        submitted = st.form_submit_button("Guardar")
        
        if submitted:
            if monto > 0:
                agregar_transaccion(tipo, categoria, monto, descripcion, fecha)
                st.success("¡Guardado con éxito!")
                st.rerun()
            else:
                st.error("El monto debe ser mayor a 0.")

    st.markdown("---")
    # Botón para descargar los datos (para que no se pierdan si la app se reinicia)
    df_actual = obtener_datos()
    if not df_actual.empty:
        csv = df_actual.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar historial (CSV)",
            data=csv,
            file_name='finanzas_leiver.csv',
            mime='text/csv',
        )

# --- PANTALLA PRINCIPAL ---
st.markdown("<h1 style='text-align: center;'>💰 Panel de Finanzas</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8a99ad; margin-bottom: 30px;'>Controla tus ingresos y gastos de forma sencilla.</p>", unsafe_allow_html=True)

df = obtener_datos()

if not df.empty:
    ingresos = df[df['tipo'] == 'Ingreso']['monto'].sum()
    gastos = df[df['tipo'] == 'Gasto']['monto'].sum()
    balance = ingresos - gastos

    # Fila de métricas
    col1, col2, col3 = st.columns(3)
    col1.metric("💵 Ingresos Totales", f"${ingresos:,.2f}")
    col2.metric("💸 Gastos Totales", f"${gastos:,.2f}")
    col3.metric("📊 Balance Actual", f"${balance:,.2f}")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Gráfico y Tabla
    col_graf, col_tabla = st.columns([1, 1.5])

    with col_graf:
        st.markdown("### 📈 Gastos por Categoría")
        gastos_por_categoria = df[df['tipo'] == 'Gasto'].groupby('categoria')['monto'].sum().reset_index()
        if not gastos_por_categoria.empty:
            st.bar_chart(gastos_por_categoria.set_index('categoria'), color="#00e5ff", use_container_width=True)
        else:
            st.info("Aún no hay gastos registrados.")

    with col_tabla:
        st.markdown("### 📝 Historial de Movimientos")
        df_mostrar = df.copy()
        df_mostrar['monto'] = df_mostrar['monto'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df_mostrar[['fecha', 'tipo', 'categoria', 'monto', 'descripcion']], use_container_width=True, hide_index=True)

else:
    st.info("👈 Usa la barra lateral para registrar tu primer ingreso o gasto.")

conn.close()
