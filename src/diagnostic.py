import duckdb
import pandas as pd

conn = duckdb.connect("data/processed/qualitat_aire.duckdb")

print("=== DISTRIBUCIÓ DEL NO2 ===")
print(conn.execute("""
    SELECT
        ROUND(MIN(no2),1) as minim,
        ROUND(AVG(no2),1) as mitjana,
        ROUND(MEDIAN(no2),1) as mediana,
        ROUND(MAX(no2),1) as maxim,
        ROUND(STDDEV(no2),1) as desviacio,
        COUNT(*) FILTER (WHERE no2 = 0) as num_zeros,
        COUNT(*) FILTER (WHERE no2 < 5) as num_sota_5
    FROM gold_features_ml
""").df())

print("\n=== ÚLTIMS 30 DIES (el període de test) ===")
print(conn.execute("""
    SELECT
        ROUND(MIN(no2),1) as minim,
        ROUND(AVG(no2),1) as mitjana,
        ROUND(MAX(no2),1) as maxim,
        COUNT(*) as n
    FROM gold_features_ml
    WHERE datetime >= (SELECT MAX(datetime) FROM gold_features_ml) - INTERVAL 30 DAY
""").df())

print("\n=== MITJANA PER MES (per veure l'estacionalitat) ===")
print(conn.execute("""
    SELECT
        "any", mes,
        ROUND(AVG(no2),1) as no2_mitja,
        COUNT(*) as n
    FROM gold_features_ml
    GROUP BY "any", mes
    ORDER BY "any", mes
""").df().to_string())

print("\n=== BUITS A LA SÈRIE (dies sense dades) ===")
print(conn.execute("""
    WITH dies AS (
        SELECT DISTINCT data FROM gold_features_ml
    ),
    rang AS (
        SELECT MIN(data) as ini, MAX(data) as fi FROM gold_features_ml
    )
    SELECT
        (SELECT DATEDIFF('day', ini, fi) + 1 FROM rang) as dies_esperats,
        (SELECT COUNT(*) FROM dies) as dies_amb_dades
""").df())

conn.close()