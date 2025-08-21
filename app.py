import os
import json
from flask import Flask, jsonify, Response
from flask_caching import Cache
from dotenv import load_dotenv
import mysql.connector
from datetime import datetime
import time
from dataclasses import dataclass, asdict

# Cargar variables de entorno desde .env
load_dotenv()

# Inicializar la aplicación Flask
app = Flask(__name__)

# Configurar caché para mejorar el rendimiento de los endpoints
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutos
cache = Cache(app)

# Definir la estructura de datos para la respuesta con el orden exacto de las claves
@dataclass
class Passenger:
    """Clase de datos para la información de un pasajero."""
    passengerId: int
    dni: str
    name: str
    age: int
    country: str
    boardingPassId: int
    purchaseId: int
    seatTypeId: int
    seatId: int

@dataclass
class FlightData:
    """Clase de datos para la información del vuelo y sus pasajeros."""
    flightId: int
    takeoffDateTime: int
    takeoffAirport: str
    landingDateTime: int
    landingAirport: str
    airplaneId: int
    passengers: list[Passenger]

# Configuración de la base de datos
def get_db_connection(max_retries=3, retry_delay=5):
    """
    Establece conexión con la base de datos remota con reintentos para mayor robustez.
    """
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
            print(f"✅ Conexión a la base de datos remota exitosa en el intento {attempt + 1}")
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

# Helper para convertir datetime a timestamp epoch
def to_epoch(dt):
    """
    Convierte un objeto datetime a un timestamp de época (epoch) en segundos.
    Si ya es un entero, lo retorna directamente.
    """
    if isinstance(dt, datetime):
        return int(dt.timestamp())
    elif isinstance(dt, int):
        return dt  # Ya es un timestamp, lo retornamos sin cambios
    elif dt is None:
        return None
    else:
        # Intenta manejar otros formatos si es necesario
        try:
            return int(dt)
        except (ValueError, TypeError):
            return None

@app.route('/health', methods=['GET'])
@cache.cached(timeout=30)
def health_check():
    """Endpoint para verificar el estado del servicio y la conexión a la base de datos."""
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
        # Asegurarse de cerrar la conexión
        try:
            if 'cursor' in locals():
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
        except Exception:
            pass

@app.route('/flights/<int:flight_id>/passengers', methods=['GET'])
def get_passengers(flight_id):
    """
    Endpoint principal para obtener información de un vuelo y sus pasajeros.
    Retorna los datos con las claves en el orden especificado.
    """
    conn = None
    cursor = None
    
    try:
        # Establecer conexión
        conn = get_db_connection()
        if conn is None:
            return jsonify({"code": 400, "errors": "could not connect to db"}), 400
        
        cursor = conn.cursor(dictionary=True)

        # 1. Obtener información del vuelo
        cursor.execute("""
            SELECT flight_id, takeoff_date_time, takeoff_airport, 
                   landing_date_time, landing_airport, airplane_id 
            FROM flight 
            WHERE flight_id = %s
        """, (flight_id,))
        flight = cursor.fetchone()
        
        if not flight:
            return jsonify({"code": 404, "data": {}}), 404

        # 2. Obtener pasajeros del vuelo
        cursor.execute("""
            SELECT 
                p.passenger_id, p.dni, p.name, p.age, p.country,
                bp.boarding_pass_id, bp.purchase_id, bp.seat_type_id, bp.seat_id
            FROM passenger p
            JOIN boarding_pass bp ON p.passenger_id = bp.passenger_id
            WHERE bp.flight_id = %s
        """, (flight_id,))
        passengers = cursor.fetchall()

        # 3. Obtener asientos disponibles
        cursor.execute("SELECT * FROM seat WHERE airplane_id = %s", (flight['airplane_id'],))
        seats = cursor.fetchall()

        # 4. Aplicar lógica de asignación de asientos
        # Nota: La función 'assign_seats' no se proporciona, por lo que se asume que existe y funciona correctamente.
        from seating import assign_seats
        passengers_assigned = assign_seats(passengers, seats)

        # 5. Construir la lista de objetos Passenger para garantizar el orden de los campos
        passengers_list = []
        for p in passengers_assigned:
            passengers_list.append(Passenger(
                passengerId=p['passenger_id'],
                dni=str(p['dni']),
                name=p['name'],
                age=p['age'],
                country=p['country'],
                boardingPassId=p['boarding_pass_id'],
                purchaseId=p['purchase_id'],
                seatTypeId=p['seat_type_id'],
                seatId=p['seat_id']
            ))

        # 6. Construir el objeto principal del vuelo con los campos en el orden correcto
        flight_data_obj = FlightData(
            flightId=flight['flight_id'],
            takeoffDateTime=to_epoch(flight['takeoff_date_time']),
            takeoffAirport=flight['takeoff_airport'],
            landingDateTime=to_epoch(flight['landing_date_time']),
            landingAirport=flight['landing_airport'],
            airplaneId=flight['airplane_id'],
            passengers=passengers_list
        )

        # 7. Serializar el objeto de datos a un diccionario
        final_response_dict = {
            "code": 200,
            "data": asdict(flight_data_obj)
        }
        
        # 8. Devolver la respuesta como una cadena JSON con un tipo de contenido explícito
        # Esto evita cualquier reordenamiento potencial de `jsonify`
        json_string = json.dumps(final_response_dict, indent=4)
        return Response(json_string, mimetype='application/json')

    except Exception as e:
        # Manejo de errores genérico para evitar fallas completas de la API
        print(f"Error inesperado: {e}")
        return jsonify({"code": 500, "errors": "internal server error"}), 500
    
    finally:
        # Asegurarse de cerrar el cursor y la conexión de la base de datos
        try:
            if cursor:
                cursor.close()
        except Exception:
            pass
        
        try:
            if conn and conn.is_connected():
                conn.close()
        except Exception:
            pass

if __name__ == '__main__':
    # Obtener el puerto de las variables de entorno para su despliegue en Render
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)