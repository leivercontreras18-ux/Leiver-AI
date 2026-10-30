import streamlit as st
import google.generativeai as genai

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Leiver AI", page_icon="🤖", layout="wide")
st.title("🤖 Leiver AI - Asistente de Programación")
st.markdown("Sube tu código, pídeme cambios y te devolveré el archivo completo.")

# --- CONFIGURACIÓN DEL CEREBRO (GEMINI) ---
try:
    # Lee la API Key desde los Secrets de Streamlit de forma segura
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    # Usamos el modelo que te recomendé, el más estable
    modelo = genai.GenerativeModel('gemini-2.5-flash')

    # --- INICIALIZAR EL HISTORIAL DE CHAT ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- MOSTRAR HISTORIAL ---
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- SUBIR ARCHIVO ---
    archivo_subido = st.file_uploader("Sube tu archivo de código aquí (ej. app.py)", type=["py", "txt", "html", "css", "js"])
    codigo_actual = ""
    if archivo_subido is not None:
        codigo_actual = archivo_subido.read().decode("utf-8")
        st.success(f"Archivo '{archivo_subido.name}' cargado correctamente ({len(codigo_actual.splitlines())} líneas).")

    # --- CUADRO DE TEXTO PARA HABLAR ---
    prompt = st.chat_input("Ej: Añade un botón de descarga en app.py...")

    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        contexto_ia = prompt
        if codigo_actual:
            contexto_ia = f"Te adjunto el código actual del archivo:\n\n```python\n{codigo_actual}\n```\n\nMi petición es: {prompt}\n\nPor favor, devuélveme el código completo modificado dentro de un bloque de código."

        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                try:
                    respuesta = modelo.generate_content(contexto_ia)
                    st.markdown(respuesta.text)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta.text})
                except Exception as e:
                    st.error(f"Error: {e}")
except KeyError:
    st.warning("⚠️ Falta la API Key. Por favor, configúrala en los Secrets de Streamlit Cloud.")
