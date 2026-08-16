import duckdb

conn = duckdb.connect("data/processed/qualitat_aire.duckdb")

print("=== ESTACIONS ===")
print(conn.execute("""
    SELECT nom_estacio, tipus_estacio, area_urbana, latitud, longitud
    FROM dim_estacio
    ORDER BY nom_estacio
""").df())

print("\n=== CONTAMINANTS ===")
print(conn.execute("""
    SELECT contaminant, unitats, COUNT(*) OVER () as total
    FROM dim_contaminant
    ORDER BY contaminant
""").df())

print("\n=== RANG TEMPORAL ===")
print(conn.execute("""
    SELECT MIN(data) as des_de, MAX(data) as fins_a, COUNT(*) as dies
    FROM dim_temps
""").df())

print("\n=== NO2 MITJÀ PER ESTACIÓ ===")
print(conn.execute("""
    SELECT
        e.nom_estacio,
        e.tipus_estacio,
        ROUND(AVG(f.valor), 1) as no2_mitja,
        ROUND(MAX(f.valor), 1) as no2_max,
        COUNT(*) as num_mesures
    FROM fets_mesures f
    JOIN dim_estacio e ON f.codi_eoi = e.codi_eoi
    JOIN dim_contaminant c ON f.magnitud = c.magnitud
    WHERE c.contaminant = 'NO2'
    GROUP BY e.nom_estacio, e.tipus_estacio
    ORDER BY no2_mitja DESC
""").df())

print("\n=== NO2 MITJÀ PER HORA DEL DIA ===")
print(conn.execute("""
    SELECT
        f.hora,
        ROUND(AVG(f.valor), 1) as no2_mitja
    FROM fets_mesures f
    JOIN dim_contaminant c ON f.magnitud = c.magnitud
    WHERE c.contaminant = 'NO2'
    GROUP BY f.hora
    ORDER BY f.hora
""").df())

conn.close()