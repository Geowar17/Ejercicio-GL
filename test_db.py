import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def test_takeoff_fields_exist():
    """Verifica que existan valores en takeoff_date_time y takeoff_airport en la tabla flight"""

    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", 3306)),
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT flight_id, takeoff_date_time, takeoff_airport 
        FROM flight 
        WHERE takeoff_date_time IS NOT NULL AND takeoff_airport IS NOT NULL
        LIMIT 5
    """)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # ✅ Validación
    assert len(rows) > 0, "No existen vuelos con takeoff_date_time y takeoff_airport definidos"
    for row in rows:
        assert row["takeoff_date_time"] is not None
        assert row["takeoff_airport"] is not None
        print(f"Vuelo {row['flight_id']} -> {row['takeoff_airport']} / {row['takeoff_date_time']}")
