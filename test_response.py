# test_response.py
import requests
import json

def test_flight_response(flight_id):
    """Verifica que la respuesta incluya todos los campos necesarios"""
    url = f"http://localhost:3000/flights/{flight_id}/passengers"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Error: Código de estado {response.status_code}")
        return False
    
    data = response.json()
    
    # Verificar campos obligatorios
    required_fields = ['flightId', 'takeoffDateTime', 'takeoffAirport', 
                      'landingDateTime', 'landingAirport', 'airplaneId', 'passengers']
    
    missing_fields = []
    for field in required_fields:
        if field not in data['data']:
            missing_fields.append(field)
    
    if missing_fields:
        print(f"¡Faltan campos en la respuesta!: {missing_fields}")
        print("Respuesta completa:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return False
    else:
        print("✅ Todos los campos están presentes en la respuesta")
        print("Respuesta completa:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return True

if __name__ == "__main__":
    # Probar con varios flight_id
    for flight_id in [1, 2, 3]:
        print(f"\n--- Probando flight_id: {flight_id} ---")
        success = test_flight_response(flight_id)
        if not success:
            break