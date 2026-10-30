import streamlit as st
import google.generativeai as genai
import time
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Leiver AI", page_icon="🤖", layout="wide")
st.title("🤖 Leiver AI - Asistente de Programación")
st.markdown("Sube tu código, pídeme cambios y te devolveré el archivo completo.")

# --- CONFIGURACIÓN DEL CEREBRO (GEMINI) ---
try:
    # Lee la API Key desde los Secrets de Streamlit de forma segura
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    
    # Usamos el modelo más reciente que Google recomienda
    modelo = genai.GenerativeModel('gemini-3.8-flash')

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
                max_reintentos = 3
                exito = False
                
                for intento in range(max_reintentos):
                    try:
                        respuesta = modelo.generate_content(contexto_ia)
                        st.markdown(respuesta.text)
                        st.session_state.messages.append({"role": "assistant", "content": respuesta.text})
                        exito = True
                        break  # Si funciona, sale del bucle de reintentos
                    except Exception as e:
                        error_str = str(e)
                        # Detecta si es un error de límite de tasa (429)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                            if intento < max_reintentos - 1:
                                # Extrae el tiempo de espera sugerido por Google
                                match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', error_str)
                                espera = int(match.group(1)) + 2 if match else 30
                                st.warning(f"⏳ Límite de Google alcanzado. Esperando {espera} segundos antes de reintentar automáticamente (Intento {intento + 1}/{max_reintentos})...")
                                time.sleep(espera)
                            else:
                                st.error("❌ Se superó el límite de la API de Google tras varios intentos. Por favor, espera un minuto y vuelve a intentarlo.")
                        else:
                            st.error(f"Error inesperado: {e}")
                            break
                
                if exito:
                    pass # El mensaje ya se mostró en el bucle

except KeyError:
    st.warning("⚠️ Falta la API Key. Por favor, configúrala en los Secrets de Streamlit Cloud.")
