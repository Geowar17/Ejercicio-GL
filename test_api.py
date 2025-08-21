import unittest
import json
import requests
import time
import os
from dotenv import load_dotenv
import mysql.connector

# Cargar variables de entorno
load_dotenv()

BASE_URL = "http://localhost:3000"

# Función de conexión a la base de datos para las pruebas
def get_db_connection():
    """Establece conexión con la base de datos remota"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306)),
            connection_timeout=5
        )
        return conn
    except Exception as e:
        print(f"Error de conexión en prueba: {e}")
        return None

class TestAndesAirlinesAPI(unittest.TestCase):
    
    def are_seats_nearby(self, seat1, seat2):
        """
        Determina si dos asientos están cerca based en fila y columna
        """
        if not seat1 or not seat2:
            return False
            
        # Misma fila y columnas adyacentes
        if seat1['seat_row'] == seat2['seat_row']:
            col_diff = abs(ord(seat1['seat_column']) - ord(seat2['seat_column']))
            if col_diff <= 1:
                return True
                
        # Misma columna y filas adyacentes
        if seat1['seat_column'] == seat2['seat_column']:
            row_diff = abs(seat1['seat_row'] - seat2['seat_row'])
            if row_diff <= 1:
                return True
                
        # Asientos diagonalmente adyacentes
        row_diff = abs(seat1['seat_row'] - seat2['seat_row'])
        col_diff = abs(ord(seat1['seat_column']) - ord(seat2['seat_column']))
        if row_diff == 1 and col_diff == 1:
            return True
            
        return False
    
    def test_01_health_check(self):
        """Prueba el endpoint de health check"""
        response = requests.get(f"{BASE_URL}/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        print("✅ Health check test passed")

    def test_02_nonexistent_flight(self):
        """Prueba un vuelo que no existe"""
        response = requests.get(f"{BASE_URL}/flights/9999/passengers")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["code"], 404)
        self.assertEqual(data["data"], {})
        print("✅ Non-existent flight test passed")

    def test_03_existing_flight_structure(self):
        """Prueba la estructura de respuesta para un vuelo existente"""
        response = requests.get(f"{BASE_URL}/flights/1/passengers")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verificar estructura básica
        self.assertIn("code", data)
        self.assertIn("data", data)
        self.assertEqual(data["code"], 200)
        
        # Verificar estructura de datos del vuelo
        flight_data = data["data"]
        self.assertIn("flightId", flight_data)
        self.assertIn("takeoffDateTime", flight_data)
        self.assertIn("takeoffAirport", flight_data)
        self.assertIn("landingDateTime", flight_data)
        self.assertIn("landingAirport", flight_data)
        self.assertIn("airplaneId", flight_data)
        self.assertIn("passengers", flight_data)
        
        print("✅ Flight structure test passed")

    def test_04_passenger_structure(self):
        """Prueba la estructura de los pasajeros"""
        response = requests.get(f"{BASE_URL}/flights/1/passengers")
        data = response.json()
        passengers = data["data"]["passengers"]
        
        if passengers:  # Solo si hay pasajeros
            passenger = passengers[0]
            # Verificar campos requeridos en camelCase
            self.assertIn("passengerId", passenger)
            self.assertIn("dni", passenger)
            self.assertIn("name", passenger)
            self.assertIn("age", passenger)
            self.assertIn("country", passenger)
            self.assertIn("boardingPassId", passenger)
            self.assertIn("purchaseId", passenger)
            self.assertIn("seatTypeId", passenger)
            self.assertIn("seatId", passenger)
            
            # Verificar tipos de datos
            self.assertIsInstance(passenger["passengerId"], int)
            self.assertIsInstance(passenger["dni"], (int, str))
            self.assertIsInstance(passenger["name"], str)
            self.assertIsInstance(passenger["age"], int)
            self.assertIsInstance(passenger["country"], str)
            self.assertIsInstance(passenger["boardingPassId"], int)
            self.assertIsInstance(passenger["purchaseId"], int)
            self.assertIsInstance(passenger["seatTypeId"], int)
            self.assertTrue(isinstance(passenger["seatId"], int) or passenger["seatId"] is None)
            
        print("✅ Passenger structure test passed")

    def test_05_seat_assignment_rules(self):
        """Prueba que se cumplan las reglas de asignación de asientos"""
        response = requests.get(f"{BASE_URL}/flights/1/passengers")
        data = response.json()
        passengers = data["data"]["passengers"]
        
        # Si no hay pasajeros, la prueba pasa automáticamente
        if not passengers:
            print("✅ No hay pasajeros en este vuelo, prueba de asignación omitida")
            return
        
        # Conectarse a la base de datos para obtener información de asientos
        conn = get_db_connection()
        if conn is None:
            self.skipTest("No se pudo conectar a la base de datos para verificación de asientos")
            return
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT seat_id, seat_row, seat_column FROM seat")
        seats_data = cursor.fetchall()
        conn.close()
        
        # Crear un diccionario de asientos por ID
        seats_info = {s['seat_id']: s for s in seats_data}
        
        # Agrupar pasajeros por purchaseId
        purchases = {}
        for p in passengers:
            purchase_id = p["purchaseId"]
            if purchase_id not in purchases:
                purchases[purchase_id] = []
            purchases[purchase_id].append(p)
        
        # Verificar reglas para cada grupo de compra
        for purchase_id, group in purchases.items():
            # Verificar que menores estén con adultos
            minors = [p for p in group if p["age"] < 18]
            adults = [p for p in group if p["age"] >= 18]
            
            # Si no hay adultos en el grupo, verificar que los menores estén juntos
            if not adults and minors:
                minor_seats = []
                for minor in minors:
                    if minor["seatId"] is not None and minor["seatId"] in seats_info:
                        minor_seats.append(seats_info[minor["seatId"]])
                
                if len(minor_seats) > 1:
                    # Verificar que al menos un par de menores estén cerca
                    found_nearby = False
                    for i in range(len(minor_seats)):
                        for j in range(i + 1, len(minor_seats)):
                            if self.are_seats_nearby(minor_seats[i], minor_seats[j]):
                                found_nearby = True
                                break
                        if found_nearby:
                            break
                    
                    self.assertTrue(
                        found_nearby,
                        f"Los menores del grupo {purchase_id} no están suficientemente cerca"
                    )
                continue
            
            # Si hay menores y adultos en el mismo grupo
            if minors and adults:
                # Verificar que cada menor tenga un adulto cerca
                for minor in minors:
                    if minor["seatId"] is None or minor["seatId"] not in seats_info:
                        continue
                    
                    minor_seat = seats_info[minor["seatId"]]
                    adult_seats = []
                    
                    for adult in adults:
                        if adult["seatId"] is not None and adult["seatId"] in seats_info:
                            adult_seats.append(seats_info[adult["seatId"]])
                    
                    if not adult_seats:
                        continue
                    
                    # Verificar si algún adulto está cerca
                    has_nearby_adult = any(
                        self.are_seats_nearby(minor_seat, adult_seat) for adult_seat in adult_seats
                    )
                    
                    self.assertTrue(
                        has_nearby_adult,
                        f"Minor {minor['passengerId']} not seated near an adult in purchase {purchase_id}. " +
                        f"Minor seat: row {minor_seat['seat_row']}, column {minor_seat['seat_column']}. " +
                        f"Adult seats: {[{'row': a['seat_row'], 'column': a['seat_column']} for a in adult_seats]}"
                    )
        
        print("✅ Seat assignment rules test passed")

    def test_06_multiple_requests(self):
        """Prueba que la API pueda manejar múltiples solicitudes"""
        start_time = time.time()
        
        # Hacer 5 solicitudes en rápida sucesión
        responses = []
        for i in range(5):
            # Usar un vuelo diferente para cada solicitud para evitar caché
            flight_id = i % 3 + 1  # Alternar entre vuelos 1, 2, 3
            response = requests.get(f"{BASE_URL}/flights/{flight_id}/passengers")
            responses.append(response)
        
        end_time = time.time()
        
        # Verificar que todas las respuestas sean exitosas
        for response in responses:
            self.assertEqual(response.status_code, 200)
        
        # Aumentar el tiempo de espera para entornos con base de datos remota
        total_time = end_time - start_time
        self.assertLess(total_time, 15, "Las solicitudes secuenciales tomaron demasiado tiempo")
        
        print("✅ Multiple requests test passed")

    def test_07_database_reconnection(self):
        """Prueba la capacidad de reconexión de la base de datos"""
        # Esta prueba simula una espera mayor a 5 segundos para verificar la reconexión
        print("Esperando 6 segundos para probar reconexión...")
        time.sleep(6)
        
        response = requests.get(f"{BASE_URL}/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        
        print("✅ Database reconnection test passed")

def run_tests():
    """Función para ejecutar todas las pruebas"""
    print("🚀 Iniciando pruebas de la API de Andes Airlines...")
    print("=" * 50)
    
    # Crear suite de pruebas
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAndesAirlinesAPI)
    
    # Ejecutar pruebas
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 50)
    if result.wasSuccessful():
        print("🎉 ¡Todas las pruebas pasaron!")
        return True
    else:
        print("❌ Algunas pruebas fallaron")
        return False

if __name__ == "__main__":
    run_tests()