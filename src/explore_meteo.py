import duckdb

conn = duckdb.connect("data/processed/qualitat_aire.duckdb")

print("=== NO2 SEGONS EL VENT ===")
print(conn.execute("""
    SELECT
        m.categoria_vent,
        ROUND(AVG(f.valor), 1) as no2_mitja,
        COUNT(*) as num_mesures
    FROM fets_mesures f
    JOIN dim_contaminant c ON f.magnitud = c.magnitud
    JOIN dim_meteo m ON f.id_temps = m.id_temps AND f.hora = m.hora
    WHERE c.contaminant = 'NO2'
    GROUP BY m.categoria_vent
    ORDER BY no2_mitja DESC
""").df())

print("\n=== NO2 SEGONS SI PLOU ===")
print(conn.execute("""
    SELECT
        m.plou,
        ROUND(AVG(f.valor), 1) as no2_mitja,
        COUNT(*) as num_mesures
    FROM fets_mesures f
    JOIN dim_contaminant c ON f.magnitud = c.magnitud
    JOIN dim_meteo m ON f.id_temps = m.id_temps AND f.hora = m.hora
    WHERE c.contaminant = 'NO2'
    GROUP BY m.plou
""").df())

print("\n=== NO2 LABORABLE vs CAP DE SETMANA ===")
print(conn.execute("""
    SELECT
        t.es_cap_setmana,
        ROUND(AVG(f.valor), 1) as no2_mitja
    FROM fets_mesures f
    JOIN dim_contaminant c ON f.magnitud = c.magnitud
    JOIN dim_temps t ON f.id_temps = t.id_temps
    WHERE c.contaminant = 'NO2'
    GROUP BY t.es_cap_setmana
""").df())

print("\n=== NO2 PER MES (estacionalitat) ===")
print(conn.execute("""
    SELECT
        t.mes,
        ROUND(AVG(f.valor), 1) as no2_mitja,
        ROUND(AVG(m.temperatura), 1) as temp_mitja
    FROM fets_mesures f
    JOIN dim_contaminant c ON f.magnitud = c.magnitud
    JOIN dim_temps t ON f.id_temps = t.id_temps
    JOIN dim_meteo m ON f.id_temps = m.id_temps AND f.hora = m.hora
    WHERE c.contaminant = 'NO2'
    GROUP BY t.mes
    ORDER BY t.mes
""").df())

print("\n=== CORRELACIÓ NO2 amb variables meteo ===")
print(conn.execute("""
    SELECT
        ROUND(CORR(f.valor, m.temperatura), 3)    as corr_temperatura,
        ROUND(CORR(f.valor, m.vent_velocitat), 3) as corr_vent,
        ROUND(CORR(f.valor, m.humitat), 3)        as corr_humitat,
        ROUND(CORR(f.valor, m.pressio), 3)        as corr_pressio
    FROM fets_mesures f
    JOIN dim_contaminant c ON f.magnitud = c.magnitud
    JOIN dim_meteo m ON f.id_temps = m.id_temps AND f.hora = m.hora
    WHERE c.contaminant = 'NO2'
""").df())

conn.close()