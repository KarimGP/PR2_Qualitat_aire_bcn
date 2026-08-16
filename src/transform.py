import duckdb

DB_PATH = "data/processed/qualitat_aire.duckdb"

def silver():
    print("=== SILVER: unpivot, neteja i correccions ===")
    conn = duckdb.connect(DB_PATH)
    
    conn.execute("DROP TABLE IF EXISTS silver_mesures")
    conn.execute("""
        CREATE TABLE silver_mesures AS
        SELECT
            codi_eoi,
            nom_estacio,
            CAST(data AS DATE) AS data,
            magnitud,
            contaminant,
            -- normalitza les unitats (ug/m3 i µg/m3 son el mateix)
            REPLACE(unitats, 'ug/m3', 'µg/m3') AS unitats,
            tipus_estacio,
            area_urbana,
            municipi,
            nom_comarca,
            CAST(altitud AS INTEGER) AS altitud,
            -- corregeix coordenades mal escalades
            CASE
                WHEN CAST(latitud AS DOUBLE) > 100
                THEN CAST(latitud AS DOUBLE) / 100000
                ELSE CAST(latitud AS DOUBLE)
            END AS latitud,
            CASE
                WHEN CAST(longitud AS DOUBLE) > 100
                THEN CAST(longitud AS DOUBLE) / 10000000
                ELSE CAST(longitud AS DOUBLE)
            END AS longitud,
            CAST(SUBSTR(hora_col, 2, 2) AS INTEGER) AS hora,
            CAST(valor AS DOUBLE) AS valor
        FROM bronze_qualitat_aire
        UNPIVOT (
            valor FOR hora_col IN (
                h01, h02, h03, h04, h05, h06, h07, h08,
                h09, h10, h11, h12, h13, h14, h15, h16,
                h17, h18, h19, h20, h21, h22, h23, h24
            )
        )
        WHERE valor IS NOT NULL
          AND TRY_CAST(valor AS DOUBLE) IS NOT NULL
          AND TRY_CAST(valor AS DOUBLE) >= 0
          AND TRY_CAST(valor AS DOUBLE) < 1000
          AND codi_eoi IS NOT NULL
          AND contaminant IS NOT NULL
    """)
    
    total = conn.execute("SELECT COUNT(*) FROM silver_mesures").fetchone()[0]
    print(f"  Silver: {total} mesures horàries")
    
    # TESTS DE QUALITAT
    print("\n  --- Tests de qualitat ---")
    
    lat_err = conn.execute("""
        SELECT COUNT(*) FROM silver_mesures
        WHERE latitud < 40 OR latitud > 43
    """).fetchone()[0]
    print(f"  Latituds fora de rang Catalunya: {lat_err} {'OK' if lat_err == 0 else 'ERROR'}")
    
    lon_err = conn.execute("""
        SELECT COUNT(*) FROM silver_mesures
        WHERE longitud < 0 OR longitud > 4
    """).fetchone()[0]
    print(f"  Longituds fora de rang Catalunya: {lon_err} {'OK' if lon_err == 0 else 'ERROR'}")
    
    hora_err = conn.execute("""
        SELECT COUNT(*) FROM silver_mesures
        WHERE hora < 1 OR hora > 24
    """).fetchone()[0]
    print(f"  Hores fora de rang 1-24: {hora_err} {'OK' if hora_err == 0 else 'ERROR'}")
    
    nulls = conn.execute("""
        SELECT COUNT(*) FROM silver_mesures
        WHERE valor IS NULL OR codi_eoi IS NULL
    """).fetchone()[0]
    print(f"  Valors nuls crítics: {nulls} {'OK' if nulls == 0 else 'ERROR'}")
    
    conn.close()

def gold():
    print("=== GOLD: star schema ===")
    conn = duckdb.connect(DB_PATH)
    
    # dim_estacio
    # dim_estacio (una sola fila per estació)
    conn.execute("DROP TABLE IF EXISTS dim_estacio")
    conn.execute("""
        CREATE TABLE dim_estacio AS
        SELECT
            codi_eoi,
            ANY_VALUE(nom_estacio)   AS nom_estacio,
            ANY_VALUE(tipus_estacio) AS tipus_estacio,
            ANY_VALUE(area_urbana)   AS area_urbana,
            ANY_VALUE(municipi)      AS municipi,
            ANY_VALUE(nom_comarca)   AS nom_comarca,
            ANY_VALUE(altitud)       AS altitud,
            ROUND(AVG(latitud), 6)   AS latitud,
            ROUND(AVG(longitud), 6)  AS longitud
        FROM silver_mesures
        GROUP BY codi_eoi
    """)
    
    # dim_contaminant (una sola fila per contaminant)
    conn.execute("DROP TABLE IF EXISTS dim_contaminant")
    conn.execute("""
        CREATE TABLE dim_contaminant AS
        SELECT
            magnitud,
            ANY_VALUE(contaminant) AS contaminant,
            ANY_VALUE(unitats)     AS unitats
        FROM silver_mesures
        GROUP BY magnitud
    """)
    
    # dim_temps
    # dim_temps: calendari continu sense buits
    conn.execute("DROP TABLE IF EXISTS dim_temps")
    conn.execute("""
        CREATE TABLE dim_temps AS
        WITH rang AS (
            SELECT MIN(data) AS ini, MAX(data) AS fi
            FROM silver_mesures
        ),
        calendari AS (
            SELECT UNNEST(generate_series(
                (SELECT ini FROM rang),
                (SELECT fi FROM rang),
                INTERVAL 1 DAY
            ))::DATE AS data
        )
        SELECT
            CAST(STRFTIME(data, '%Y%m%d') AS INTEGER) AS id_temps,
            data,
            YEAR(data)      AS "any",
            MONTH(data)     AS mes,
            QUARTER(data)   AS trimestre,
            DAYOFWEEK(data) AS dia_setmana_num,
            DAYNAME(data)   AS dia_setmana,
            MONTHNAME(data) AS nom_mes,
            CASE WHEN DAYOFWEEK(data) IN (0, 6) THEN TRUE ELSE FALSE END AS es_cap_setmana,
            CASE
                WHEN MONTH(data) IN (12, 1, 2)  THEN 'Hivern'
                WHEN MONTH(data) IN (3, 4, 5)   THEN 'Primavera'
                WHEN MONTH(data) IN (6, 7, 8)   THEN 'Estiu'
                ELSE 'Tardor'
            END AS estacio_any
        FROM calendari
    """)
    
    # fets_mesures
    conn.execute("DROP TABLE IF EXISTS fets_mesures")
    conn.execute("""
        CREATE TABLE fets_mesures AS
        SELECT
            ROW_NUMBER() OVER ()                       AS id_mesura,
            codi_eoi,
            magnitud,
            CAST(STRFTIME(data, '%Y%m%d') AS INTEGER)  AS id_temps,
            hora,
            valor
        FROM silver_mesures
    """)
    
    for t in ["dim_estacio", "dim_contaminant", "dim_temps", "fets_mesures"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n} files")
    
    conn.close()

def silver_meteo():
    print("=== SILVER METEO: neteja i normalització ===")
    conn = duckdb.connect(DB_PATH)
    
    conn.execute("DROP TABLE IF EXISTS silver_meteo")
    conn.execute("""
        CREATE TABLE silver_meteo AS
        SELECT
            CAST(time AS DATE)                       AS data,
            -- Open-Meteo dona hores 0-23, nosaltres usem 1-24
            EXTRACT(HOUR FROM CAST(time AS TIMESTAMP)) + 1 AS hora,
            CAST(temperature_2m AS DOUBLE)           AS temperatura,
            CAST(relative_humidity_2m AS DOUBLE)     AS humitat,
            CAST(precipitation AS DOUBLE)            AS precipitacio,
            CAST(wind_speed_10m AS DOUBLE)           AS vent_velocitat,
            CAST(wind_direction_10m AS DOUBLE)       AS vent_direccio,
            CAST(surface_pressure AS DOUBLE)         AS pressio
        FROM bronze_meteo
        WHERE temperature_2m IS NOT NULL
    """)
    
    total = conn.execute("SELECT COUNT(*) FROM silver_meteo").fetchone()[0]
    print(f"  Silver meteo: {total} registres horaris")
    
    # Tests de qualitat
    print("\n  --- Tests de qualitat meteo ---")
    
    temp_err = conn.execute("""
        SELECT COUNT(*) FROM silver_meteo
        WHERE temperatura < -20 OR temperatura > 50
    """).fetchone()[0]
    print(f"  Temperatures impossibles: {temp_err} {'OK' if temp_err == 0 else 'ERROR'}")
    
    hum_err = conn.execute("""
        SELECT COUNT(*) FROM silver_meteo
        WHERE humitat < 0 OR humitat > 100
    """).fetchone()[0]
    print(f"  Humitats fora 0-100%: {hum_err} {'OK' if hum_err == 0 else 'ERROR'}")
    
    hora_err = conn.execute("""
        SELECT COUNT(*) FROM silver_meteo
        WHERE hora < 1 OR hora > 24
    """).fetchone()[0]
    print(f"  Hores fora de rang: {hora_err} {'OK' if hora_err == 0 else 'ERROR'}")
    
    conn.close()


def gold_meteo():
    print("=== GOLD METEO: dim_meteo ===")
    conn = duckdb.connect(DB_PATH)
    
    conn.execute("DROP TABLE IF EXISTS dim_meteo")
    conn.execute("""
        CREATE TABLE dim_meteo AS
        SELECT
            CAST(STRFTIME(data, '%Y%m%d') AS INTEGER) AS id_temps,
            hora,
            temperatura,
            humitat,
            precipitacio,
            vent_velocitat,
            vent_direccio,
            pressio,
            CASE WHEN precipitacio > 0 THEN TRUE ELSE FALSE END AS plou,
            CASE
                WHEN vent_velocitat < 5  THEN 'Calma'
                WHEN vent_velocitat < 15 THEN 'Moderat'
                ELSE 'Fort'
            END AS categoria_vent
        FROM silver_meteo
    """)
    
    n = conn.execute("SELECT COUNT(*) FROM dim_meteo").fetchone()[0]
    print(f"  dim_meteo: {n} files")
    
    # Verificar que es pot fer JOIN amb els fets
    match = conn.execute("""
        SELECT COUNT(*)
        FROM fets_mesures f
        JOIN dim_meteo m ON f.id_temps = m.id_temps AND f.hora = m.hora
    """).fetchone()[0]
    total_fets = conn.execute("SELECT COUNT(*) FROM fets_mesures").fetchone()[0]
    print(f"  Mesures amb meteo associada: {match} de {total_fets} ({round(100*match/total_fets,1)}%)")
    
    conn.close()

def gold_features_ml():
    print("=== GOLD: features per al model ML (diari + lags) ===")
    conn = duckdb.connect(DB_PATH)
    
    # Primer construïm la base diària
    conn.execute("DROP TABLE IF EXISTS gold_features_base")
    conn.execute("""
        CREATE TABLE gold_features_base AS
        SELECT
            t.data                          AS data,
            ROUND(AVG(f.valor), 2)          AS no2_mitja,
            ROUND(MAX(f.valor), 2)          AS no2_max,
            ROUND(AVG(m.temperatura), 2)    AS temperatura,
            ROUND(AVG(m.humitat), 2)        AS humitat,
            ROUND(SUM(m.precipitacio), 2)   AS precipitacio,
            ROUND(AVG(m.vent_velocitat), 2) AS vent_velocitat,
            ROUND(MAX(m.vent_velocitat), 2) AS vent_max,
            ROUND(AVG(m.pressio), 2)        AS pressio,
            ANY_VALUE(t.dia_setmana_num)    AS dia_setmana_num,
            ANY_VALUE(t.es_cap_setmana)     AS es_cap_setmana,
            ANY_VALUE(t.mes)                AS mes,
            ANY_VALUE(t."any")              AS any_,
            COUNT(*)                        AS hores_amb_dada
        FROM fets_mesures f
        JOIN dim_contaminant c ON f.magnitud = c.magnitud
        JOIN dim_estacio e     ON f.codi_eoi = e.codi_eoi
        JOIN dim_temps t       ON f.id_temps = t.id_temps
        JOIN dim_meteo m       ON f.id_temps = m.id_temps AND f.hora = m.hora
        WHERE c.contaminant = 'NO2'
          AND e.nom_estacio = 'Barcelona (Eixample)'
        GROUP BY t.data
        HAVING COUNT(*) >= 18
        ORDER BY t.data
    """)
    
    # Ara afegim lag features amb window functions
    conn.execute("DROP TABLE IF EXISTS gold_features_ml")
    conn.execute("""
        CREATE TABLE gold_features_ml AS
        SELECT
            *,
            -- Lag: valor de dies anteriors
            LAG(no2_mitja, 1) OVER (ORDER BY data) AS no2_lag1,
            LAG(no2_mitja, 2) OVER (ORDER BY data) AS no2_lag2,
            LAG(no2_mitja, 7) OVER (ORDER BY data) AS no2_lag7,
            
            -- Mitjanes mòbils
            ROUND(AVG(no2_mitja) OVER (
                ORDER BY data ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
            ), 2) AS no2_mm3,
            ROUND(AVG(no2_mitja) OVER (
                ORDER BY data ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
            ), 2) AS no2_mm7,
            
            -- Meteo del dia anterior (persistència d'episodis)
            LAG(vent_velocitat, 1) OVER (ORDER BY data) AS vent_lag1,
            LAG(precipitacio, 1) OVER (ORDER BY data)   AS precip_lag1,
            
            -- Features cícliques (dia de l'any en sinus/cosinus)
            ROUND(SIN(2 * PI() * DAYOFYEAR(data) / 365.0), 4) AS dia_any_sin,
            ROUND(COS(2 * PI() * DAYOFYEAR(data) / 365.0), 4) AS dia_any_cos
        FROM gold_features_base
        ORDER BY data
    """)
    
    n = conn.execute("SELECT COUNT(*) FROM gold_features_ml").fetchone()[0]
    n_valid = conn.execute("""
        SELECT COUNT(*) FROM gold_features_ml WHERE no2_lag7 IS NOT NULL
    """).fetchone()[0]
    
    print(f"  gold_features_ml: {n} dies ({n_valid} amb lags complets)")
    
    # Correlació dels lags amb el target
    print("\n  --- Correlació de les features amb NO2 ---")
    print(conn.execute("""
        SELECT
            ROUND(CORR(no2_mitja, no2_lag1), 3)       AS lag1,
            ROUND(CORR(no2_mitja, no2_mm3), 3)        AS mitjana_3d,
            ROUND(CORR(no2_mitja, no2_mm7), 3)        AS mitjana_7d,
            ROUND(CORR(no2_mitja, vent_velocitat), 3) AS vent,
            ROUND(CORR(no2_mitja, temperatura), 3)    AS temperatura
        FROM gold_features_ml
        WHERE no2_lag7 IS NOT NULL
    """).df().to_string())
    
    conn.close()

if __name__ == "__main__":
    silver()
    gold()
    silver_meteo()
    gold_meteo()
    gold_features_ml()
