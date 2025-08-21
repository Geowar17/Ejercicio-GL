import os
import mysql.connector
from datetime import datetime
import time



# Configuración de la base de datos
def get_db_connection(max_retries=3, retry_delay=5):
    """Establece conexión con la base de datos remota con reintentos"""
    for attempt in range(max_retries):
        try:
            conn = mysql.connector.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                database=os.getenv("DB_NAME"),
                port=int(os.getenv("DB_PORT", 3306)),
                connection_timeout=10
            )
            print("✅ Conexión a la base de datos remota exitosa")
            return conn
        except mysql.connector.Error as err:
            print(f"❌ Intento {attempt + 1}/{max_retries}: Error de conexión: {err}")
            if attempt < max_retries - 1:
                print(f"⏳ Reintentando en {retry_delay} segundos...")
                time.sleep(retry_delay)
            else:
                print("❌ Todos los intentos de conexión fallaron")
                return None
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return None

