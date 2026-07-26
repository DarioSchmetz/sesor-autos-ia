import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from google import genai
from google.genai import types

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
# 2. Cargar Variables de Entorno y Conexión
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Buscar clave primero en Secrets de Streamlit Cloud y luego en .env local
API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("❌ No se encontró la GEMINI_API_KEY ni en Secrets ni en el archivo .env")
    st.stop()

# Nombre del archivo SQLite
DB_PATH = BASE_DIR / "concesionaria.db"

# ----------------------------------------------------
# 3. Funciones de Base de Datos con SQLite
# ----------------------------------------------------
def inicializar_db():
    """Crea las tablas automáticas si no existen en SQLite."""
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            color TEXT,
            anio INTEGER,
            precio REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliente_interesado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            email TEXT,
            auto_interes TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conexion.commit()
    conexion.close()

inicializar_db()

@st.cache_data(ttl=600)
def obtener_autos():
    try:
        conexion = sqlite3.connect(DB_PATH)
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
        
        cursor.execute("SELECT * FROM auto")
        filas = cursor.fetchall()
        
        autos = [dict(fila) for fila in filas]
        conexion.close()
        return autos
    except Exception as e:
        st.error(f"❌ Error al conectar con SQLite: {e}")
        return []

def guardar_lead(nombre, telefono, email, auto_interes):
    try:
        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()
        query = """
            INSERT INTO cliente_interesado (nombre, telefono, email, auto_interes)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (nombre, telefono, email, auto_interes))
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        st.error(f"❌ Error al guardar en SQLite: {e}")
        return False

lista_autos = obtener_autos()

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

# Ver inventario
with st.expander("📋 Ver inventario disponible"):
    st.json(lista_autos)

# ----------------------------------------------------
# 5. Memoria del Chat y Configuración de Gemini
# ----------------------------------------------------
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

# Mostrar historial previo en pantalla
for msg in st.session_state.mensajes:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------------------------------
# 6. Entrada del Usuario y Respuesta de la IA
# ----------------------------------------------------
if prompt := st.chat_input("Escribí tu pregunta sobre nuestros autos..."):
    # Guardar y mostrar mensaje del usuario
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Pensando respuesta..."):
            try:
                # Instanciar el cliente con la versión de API 'v1' para asegurar estabilidad
                client = genai.Client(api_key=API_KEY)

                instrucciones = f"""
                Eres un asesor comercial experto y amable para una concesionaria de autos.
                Inventario disponible en la base de datos:
                {lista_autos}

                Reglas:
                1. Responde basándote ÚNICAMENTE en el inventario provisto.
                2. Si piden algo que no está, sé amable y ofrece una alternativa cercana.
                3. Si el cliente muestra interés claro en comprar o probar un auto, recuérdale que puede dejar sus datos en el formulario de la barra lateral para agendar una cita.
                4. Sé claro, profesional y conciso.
                """

                # Formatear historial para la API
                historial_gemini = []
                for m in st.session_state.mensajes:
                    role_gemini = "user" if m["role"] == "user" else "model"
                    historial_gemini.append(
                        types.Content(
                            role=role_gemini,
                            parts=[types.Part.from_text(text=m["content"])]
                        )
                    )

                # Intentamos con gemini-2.0-flash
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=historial_gemini,
                    config=types.GenerateContentConfig(
                        system_instruction=instrucciones
                    )
                )

                st.markdown(response.text)
                st.session_state.mensajes.append({"role": "assistant", "content": response.text})

            except Exception as e:
                st.error(f"❌ Error al comunicarse con Gemini: {e}")