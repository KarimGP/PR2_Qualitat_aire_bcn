"""Pipeline complet: extracció, transformació i export per a Power BI."""

from extract import extract, load_bronze
from extract_meteo import extract_meteo, load_bronze_meteo
from transform import silver, gold, silver_meteo, gold_meteo, gold_features_ml
from export_powerbi import export


def run_pipeline():
    print("\n########## PAS 1/4: EXTRACCIÓ ##########")
    data_aire = extract()
    load_bronze(data_aire)

    data_meteo = extract_meteo()
    load_bronze_meteo(data_meteo)

    print("\n########## PAS 2/4: SILVER ##########")
    silver()
    silver_meteo()

    print("\n########## PAS 3/4: GOLD ##########")
    gold()
    gold_meteo()
    gold_features_ml()

    print("\n########## PAS 4/4: EXPORT POWER BI ##########")
    export()

    print("\n########## PIPELINE COMPLETAT CORRECTAMENT ##########")


if __name__ == "__main__":
    run_pipeline()