import os
from flask import Flask, jsonify
from flask_caching import Cache
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime
import time

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configurar caché
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutos
cache = Cache(app)

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

# Helper para convertir snake_case a camelCase
def to_camel(snake_str):
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def dict_to_camel(data):
    if isinstance(data, list):
        return [dict_to_camel(item) for item in data]
    if isinstance(data, dict):
        return {to_camel(key): dict_to_camel(value) for key, value in data.items()}
    return data

def to_epoch(dt):
    """Convierte datetime a timestamp epoch"""
    if isinstance(dt, datetime):
        return int(dt.timestamp())
    return None

@app.route('/health', methods=['GET'])
@cache.cached(timeout=30)
def health_check():
    """Endpoint para verificar el estado del servicio y la base de datos"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"status": "error", "message": "No se pudo conectar a la base de datos remota"}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        return jsonify({"status": "success", "message": "Conexión a la base de datos remota exitosa"})
    except mysql.connector.Error as err:
        return jsonify({"status": "error", "message": f"Error en la base de datos: {err}"}), 500
    finally:
        try:
            if 'cursor' in locals():
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
        except:
            pass

@app.route('/flights/<int:flight_id>/passengers', methods=['GET'])
@cache.cached(timeout=60, query_string=True)
def get_passengers(flight_id):
    """Endpoint principal para obtener información de pasajeros de un vuelo"""
    conn = None
    cursor = None
    
    try:
        # Establecer conexión
        conn = get_db_connection()
        if conn is None:
            return jsonify({"code": 400, "errors": "could not connect to db"}), 400
        
        cursor = conn.cursor(dictionary=True)

        # 1. Obtener información del vuelo (optimizada)
        cursor.execute("""
            SELECT flight_id, takeoff_date_time, takeoff_airport, 
                   landing_date_time, landing_airport, airplane_id 
            FROM flight 
            WHERE flight_id = %s
        """, (flight_id,))
        flight = cursor.fetchone()
        
        if not flight:
            return jsonify({"code": 404, "data": {}}), 404

        # 2. Obtener pasajeros del vuelo (optimizada)
        cursor.execute("""
            SELECT 
                p.passenger_id, p.dni, p.name, p.age, p.country,
                bp.boarding_pass_id, bp.purchase_id, bp.seat_type_id, bp.seat_id
            FROM passenger p
            JOIN boarding_pass bp ON p.passenger_id = bp.passenger_id
            WHERE bp.flight_id = %s
        """, (flight_id,))
        passengers = cursor.fetchall()

        # 3. Obtener asientos disponibles (optimizada)
        cursor.execute("""
            SELECT seat_id, seat_row, seat_column, seat_type_id, airplane_id 
            FROM seat 
            WHERE airplane_id = %s
        """, (flight['airplane_id'],))
        seats = cursor.fetchall()

        # 4. Aplicar lógica de asignación de asientos
        from seating import assign_seats
        passengers_assigned = assign_seats(passengers, seats)

        # 5. Preparar respuesta
        response = {
            "code": 200,
            "data": {
                "flightId": flight['flight_id'],
                "takeoffDateTime": to_epoch(flight['takeoff_date_time']),
                "takeoffAirport": flight['takeoff_airport'],
                "landingDateTime": to_epoch(flight['landing_date_time']),
                "landingAirport": flight['landing_airport'],
                "airplaneId": flight['airplane_id'],
                "passengers": [dict_to_camel(p) for p in passengers_assigned],
            }
        }
        
        return jsonify(response)

    except Exception as e:
        print(f"Error inesperado: {e}")
        return jsonify({"code": 500, "errors": "internal server error"}), 500
    
    finally:
        try:
            if cursor:
                cursor.close()
        except:
            pass
        
        try:
            if conn and conn.is_connected():
                conn.close()
        except:
            pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)