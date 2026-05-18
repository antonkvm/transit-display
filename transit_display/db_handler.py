import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent/"config.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weather_config (
        id INT PRIMARY KEY CHECK (id = 1),
        name VARCHAR(255) NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL
    )
    """)
    
    conn.commit()
    conn.close()

def insert_weather_coords(name: str, lat: float, lon: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO weather_config (id, name, lat, lon)
    VALUES (1, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
    name = excluded.name,
    lat = excluded.lat,
    lon = excluded.lon;
    """, (name, lat, lon))
    
    conn.commit()
    conn.close()
    
def get_weather_coords() -> dict[str, str|int]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    row = cursor.execute("""
    SELECT name, lat, lon
    FROM weather_config
    WHERE id = 1
    """).fetchone()

    return {**row}
    
    
if __name__ == "__main__":
    init_database()
    insert_weather_coords("Berlin", 52.520008, 13.404954)
    get_weather_coords()