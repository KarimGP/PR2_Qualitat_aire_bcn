import requests
import json
import pandas as pd
import duckdb
from pathlib import Path

URL = "https://analisi.transparenciacatalunya.cat/resource/tasf-thgu.json"
DB_PATH = "data/processed/qualitat_aire.duckdb"

def extract(limit=50000, municipi="Barcelona"):
    print("=== EXTRACT: descarregant dades ===")
    
    params = {
        "$limit": limit,
        "$where": f"municipi='{municipi}'",
        "$order": "data DESC"
    }
    
    response = requests.get(URL, params=params)
    response.raise_for_status()
    data = response.json()
    
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    with open("data/raw/qualitat_aire.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"  {len(data)} registres descarregats")
    return data


def load_bronze(data):
    print("=== LOAD: carregant a Bronze (sense transformar) ===")
    
    df = pd.DataFrame(data)
    
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(DB_PATH)
    
    conn.execute("DROP TABLE IF EXISTS bronze_qualitat_aire")
    conn.execute("CREATE TABLE bronze_qualitat_aire AS SELECT * FROM df")
    
    total = conn.execute("SELECT COUNT(*) FROM bronze_qualitat_aire").fetchone()[0]
    print(f"  Bronze: {total} files carregades en brut")
    
    conn.close()


if __name__ == "__main__":
    data = extract()
    load_bronze(data)