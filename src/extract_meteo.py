import requests
import json
import pandas as pd
import duckdb
from pathlib import Path
from datetime import date, timedelta


DB_PATH = "data/processed/qualitat_aire.duckdb"

# Coordenades del centre de Barcelona
LAT = 41.3874
LON = 2.1686

URL = "https://archive-api.open-meteo.com/v1/archive"

def extract_meteo(data_inici="2023-08-23", data_fi=None):
    if data_fi is None:
            # Open-Meteo archive té ~5 dies de retard
            data_fi = (date.today() - timedelta(days=6)).isoformat()


    print("=== EXTRACT METEO: descarregant Open-Meteo ===")
    print(f"  Rang: {data_inici} → {data_fi}")

    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": data_inici,
        "end_date": data_fi,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,surface_pressure",
        "timezone": "Europe/Madrid"
    }
    
    response = requests.get(URL, params=params)
    response.raise_for_status()
    data = response.json()
    
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    with open("data/raw/meteo.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"  {len(data['hourly']['time'])} registres horaris descarregats")
    return data


def load_bronze_meteo(data):
    print("=== LOAD: carregant meteo a Bronze ===")
    
    df = pd.DataFrame(data["hourly"])
    
    conn = duckdb.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS bronze_meteo")
    conn.execute("CREATE TABLE bronze_meteo AS SELECT * FROM df")
    
    total = conn.execute("SELECT COUNT(*) FROM bronze_meteo").fetchone()[0]
    print(f"  Bronze meteo: {total} files")
    print(f"  Columnes: {list(df.columns)}")
    
    conn.close()


if __name__ == "__main__":
    data = extract_meteo()
    load_bronze_meteo(data)