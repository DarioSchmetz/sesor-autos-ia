import os
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from google import genai
from google.genai import types
import mysql.connector

# ----------------------------------------------------
# 1. Configuración de la página web
# ----------------------------------------------------
st.set_page_config(
    page_title="Asesor Virtual - Concesionaria",
    page_icon="🚗",
    layout="centered"
)

st.title("🚗 Asesor de Ventas IA")
st.subheader("Tu concesionaria de confianza")
st.markdown("---")

# ----------------------------------------------------
# 2. Cargar Variables de Entorno (.env)
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("GEMINI_API_KEY")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

if not API_KEY:
    st.error("❌ No se encontró la GEMINI_API_KEY en el archivo .env")
    st.stop()

client = genai.Client(api_key=API_KEY)

# ----------------------------------------------------
# 3. Funciones para MySQL
# ----------------------------------------------------
@st.cache_data(ttl=600)
def obtener_autos():
    try:
        conexion = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM auto")
        autos = cursor.fetchall()
        conexion.close()
        return autos
    except Exception as e:
        st.error(f"❌ Error al conectar con MySQL: {e}")
        return []

def guardar_lead(nombre, telefono, email, auto_interes):
    try:
        conexion = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        cursor = conexion.cursor()
        query = """
            INSERT INTO cliente_interesado (nombre, telefono, email, auto_interes)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (nombre, telefono, email, auto_interes))
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        st.error(f"❌ Error al guardar en la base de datos: {e}")
        return False

lista_autos = obtener_autos()

if not lista_autos:
    st.warning("⚠️ No se pudieron cargar los autos desde la base de datos.")
    st.stop()

# ----------------------------------------------------
# 4. Barra Lateral (Sidebar): Formulario de Contacto
# ----------------------------------------------------
with st.sidebar:
    st.header("📅 Agendar Cita / Prueba de Manejo")
    st.write("Dejanos tus datos y un asesor humano te contactará a la brevedad.")

    nombres_autos = [f"{a.get('marca', '')} {a.get('modelo', '')}" for a in lista_autos]

    with st.form("form_contacto", clear_on_submit=True):
        nombre = st.text_input("Nombre y Apellido *")
        telefono = st.text_input("Teléfono / WhatsApp *")
        email = st.text_input("Email")
        auto_interes = st.selectbox("Auto de tu interés", options=["General / Consulta amplia"] + nombres_autos)
        
        btn_enviar = st.form_submit_button("📩 Enviar datos")

        if btn_enviar:
            if not nombre or not telefono:
                st.warning("⚠️ Por favor completá al menos el Nombre y Teléfono.")
            else:
                exito = guardar_lead(nombre, telefono, email, auto_interes)
                if exito:
                    st.success("✅ ¡Gracias! Un asesor comercial se pondrá en contacto pronto.")

# Desplegable en la pantalla principal para inspeccionar el catálogo de autos
with st.expander("📋 Ver inventario disponible en MySQL"):
    st.json(lista_autos)

# ----------------------------------------------------
# 5. Memoria del Chat y Configuración de Gemini
# ----------------------------------------------------
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

if "chat_session" not in st.session_state:
    instrucciones = f"""
    Eres un asesor comercial experto y amable para una concesionaria de autos.
    Inventario disponible en MySQL:
    {lista_autos}

    Reglas:
    1. Responde basándote ÚNICAMENTE en el inventario provisto.
    2. Si piden algo que no está, sé amable y ofrece una alternativa cercana.
    3. Si el cliente muestra interés claro en comprar o probar un auto, recuérdale que puede dejar sus datos en el formulario de la barra lateral para agendar una cita.
    4. Sé claro, profesional y conciso.
    """
    
    st.session_state.chat_session = client.chats.create(
        model="gemini-flash-latest",
        config=types.GenerateContentConfig(
            system_instruction=instrucciones
        )
    )

for msg in st.session_state.mensajes:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------------------------------
# 6. Entrada del Usuario y Respuesta de la IA
# ----------------------------------------------------
if prompt := st.chat_input("Escribí tu pregunta sobre nuestros autos..."):
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Pensando respuesta..."):
            try:
                response = st.session_state.chat_session.send_message(prompt)
                st.markdown(response.text)
                st.session_state.mensajes.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"❌ Error al comunicarse con Gemini: {e}")