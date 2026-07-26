import os
import sqlite3
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
import streamlit as st
import google.generativeai as genai

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
# 2. Cargar Variables de Entorno y Configuración API
# ----------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("❌ No se encontró la GEMINI_API_KEY ni en Secrets ni en el archivo .env")
    st.stop()

genai.configure(api_key=API_KEY)

# Nombre del archivo SQLite
DB_PATH = BASE_DIR / "concesionaria.db"

# ----------------------------------------------------
# 3. Funciones de Base de Datos con SQLite
# ----------------------------------------------------
def inicializar_db():
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
# 4. Formatear Inventario e Instrucciones
# ----------------------------------------------------
inventario_texto = "\n".join(
    [
        f"- {a.get('marca', '')} {a.get('modelo', '')} | Año: {a.get('anio', '')} | Color: {a.get('color', '')} | Precio: ${a.get('precio', 0):,.2f}"
        for a in lista_autos
    ]
)

@st.cache_resource
def obtener_modelo(text_inventario):
    instrucciones = f"""
    Eres un asesor comercial experto y amable para una concesionaria de autos.

    Inventario disponible:
    {text_inventario}

    Reglas:
    - Responde únicamente usando el inventario disponible.
    - Si un auto no existe, sé amable y ofrece uno similar del inventario.
    - Si el cliente muestra interés claro en comprar o probar un auto, invítalo a completar el formulario de la barra lateral.
    - Sé claro, profesional y conciso.
    """

    # Usamos la sintaxis completa del modelo para evitar el error 404
    return genai.GenerativeModel(
        model_name="models/gemini-1.5-flash",
        system_instruction=instrucciones
    )

modelo = obtener_modelo(inventario_texto)

# ----------------------------------------------------
# 5. Barra Lateral (Sidebar): Formulario y Botón Limpiar
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

    st.markdown("---")
    if st.button("🗑 Limpiar conversación", use_container_width=True):
        st.session_state.mensajes = [
            {
                "role": "assistant",
                "content": "👋 Hola nuevamente. ¿En qué puedo ayudarte?"
            }
        ]
        st.rerun()

# ----------------------------------------------------
# 6. Mostrar Métricas e Inventario en Pandas
# ----------------------------------------------------
st.metric("Autos disponibles en catálogo", len(lista_autos))

with st.expander("📋 Ver inventario disponible"):
    if lista_autos:
        df_autos = pd.DataFrame(lista_autos)
        st.dataframe(
            df_autos,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No hay vehículos cargados en la base de datos.")

# ----------------------------------------------------
# 7. Memoria del Chat y Saludo Inicial
# ----------------------------------------------------
if "mensajes" not in st.session_state:
    st.session_state.mensajes = [
        {
            "role": "assistant",
            "content": "👋 ¡Hola! Soy el asesor virtual de la concesionaria. ¿Qué vehículo estás buscando?"
        }
    ]

for msg in st.session_state.mensajes:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------------------------------
# 8. Entrada del Usuario y Respuesta
# ----------------------------------------------------
if prompt := st.chat_input("Escribí tu pregunta sobre nuestros autos..."):
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🚗 Buscando el vehículo ideal..."):
            try:
                historial_reciente = st.session_state.mensajes[-6:]

                history_gemini = []
                for m in historial_reciente[:-1]:
                    role = "user" if m["role"] == "user" else "model"
                    history_gemini.append({
                        "role": role,
                        "parts": [m["content"]]
                    })

                chat = modelo.start_chat(history=history_gemini)
                response = chat.send_message(prompt)

                st.markdown(response.text)
                st.session_state.mensajes.append({"role": "assistant", "content": response.text})

            # Manejo de errores corregido sin el error de sintaxis DeltaGenerator
            except Exception as e:
                error = str(e)
                if "429" in error:
                    st.warning("⚠️ Se alcanzó el límite de uso de Gemini. Por favor aguardá unos segundos.")
                elif "401" in error:
                    st.error("❌ La API Key no es válida.")
                elif "403" in error:
                    st.error("❌ La API Key no tiene permisos.")
                else:
                    st.error(f"❌ Ocurrió un error inesperado: {error}")