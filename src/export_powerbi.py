import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = "data/processed/qualitat_aire.duckdb"
OUT = Path("data/processed/powerbi")


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(DB_PATH)

    taules = {
        "dim_estacio": "SELECT * FROM dim_estacio",
        "dim_contaminant": "SELECT * FROM dim_contaminant",
        "dim_temps": "SELECT * FROM dim_temps",
        "dim_meteo": "SELECT * FROM dim_meteo",
    }

    taules["fets_diari"] = """
        SELECT
            f.codi_eoi,
            f.magnitud,
            f.id_temps,
            ROUND(AVG(f.valor), 2) AS valor_mitja,
            ROUND(MAX(f.valor), 2) AS valor_max,
            ROUND(MIN(f.valor), 2) AS valor_min,
            COUNT(*) AS hores_amb_dada
        FROM fets_mesures f
        GROUP BY f.codi_eoi, f.magnitud, f.id_temps
    """

    taules["perfil_horari"] = """
        SELECT
            f.codi_eoi,
            f.magnitud,
            t."any",
            f.hora,
            ROUND(AVG(f.valor), 2) AS valor_mitja
        FROM fets_mesures f
        JOIN dim_temps t ON f.id_temps = t.id_temps
        GROUP BY f.codi_eoi, f.magnitud, t."any", f.hora
    """

    taules["gold_features_ml"] = "SELECT * FROM gold_features_ml"

    for nom, sql in taules.items():
        df = conn.execute(sql).df()
        fitxer = OUT / f"{nom}.csv"
        df.to_csv(fitxer, index=False, encoding="utf-8")
        print(f"  {nom}: {len(df):>8} files -> {fitxer}")

    conn.close()
    print(f"\nCSVs exportats a {OUT}")


if __name__ == "__main__":
    export()