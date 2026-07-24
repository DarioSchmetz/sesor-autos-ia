import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import mysql.connector

# ----------------------------------------------------
# 1. Cargar Variables de Entorno (.env)
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
    print(f"❌ ERROR: No se pudo leer GEMINI_API_KEY desde: {env_path}")
    exit()

# Inicializar cliente oficial de Gemini
client = genai.Client(api_key=API_KEY)

# ----------------------------------------------------
# 2. Función para consultar MySQL
# ----------------------------------------------------
def obtener_autos_de_db():
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
        print(f"❌ Error al conectar con MySQL: {e}")
        return []

# ----------------------------------------------------
# 3. Flujo Principal (Módulo 2 - Chat Continuo)
# ----------------------------------------------------
print("🔍 Cargando datos desde la base de datos MySQL...")
lista_autos = obtener_autos_de_db()

if not lista_autos:
    print("❌ No se encontraron autos o falló la conexión a MySQL. Abortando.")
    exit()

print(f"✅ Se cargaron {len(lista_autos)} autos.")

# Configurar el rol del bot e indicarle la base de datos
instrucciones_sistema = f"""
Eres un asesor comercial experto y amable para una concesionaria de autos.
Tu objetivo es ayudar al cliente a encontrar el vehículo ideal de nuestro inventario.

INVENTARIO REAL DISPONIBLE EN BASE DE DATOS:
{lista_autos}

Reglas:
1. Basándote ÚNICAMENTE en este inventario, responde las preguntas del cliente.
2. Si el cliente pide algo que no está en la lista, infórmalo amablemente y sugiere la alternativa disponible más cercana.
3. Sé breve, claro, profesional y persuasivo.
"""

# Iniciar la sesión de Chat con memoria de conversación
chat = client.chats.create(
    model="gemini-flash-latest",
    config=types.GenerateContentConfig(
        system_instruction=instrucciones_sistema
    )
)

print("\n" + "="*50)
print("🤖 ¡Hola! Soy tu Asistente de Ventas Virtual.")
print("Escribí tu consulta abajo. Para terminar escribí 'salir'.")
print("="*50 + "\n")

# Bucle interactivo
while True:
    mensaje_usuario = input("👤 Tú: ")
    
    if mensaje_usuario.strip().lower() in ["salir", "exit", "chao", "chau"]:
        print("\n🤖 ¡Gracias por tu visita! Que tengas un excelente día. 👋")
        break

    if not mensaje_usuario.strip():
        continue

    try:
        respuesta = chat.send_message(mensaje_usuario)
        print(f"\n🤖 Asistente:\n{respuesta.text}\n")
        print("-" * 50)
    except Exception as err:
        print(f"❌ Error al procesar el mensaje: {err}")