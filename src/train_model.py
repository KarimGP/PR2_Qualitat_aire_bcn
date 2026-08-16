import duckdb
import pandas as pd
import mlflow
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
from pathlib import Path

DB_PATH = "data/processed/qualitat_aire.duckdb"


def carrega_dades():
    print("=== Carregant features de Gold ===")
    conn = duckdb.connect(DB_PATH)
    df = conn.execute("""
        SELECT
            data AS ds,
            no2_mitja AS y,
            temperatura,
            vent_velocitat,
            precipitacio,
            pressio,
            humitat
        FROM gold_features_ml
        ORDER BY data
    """).df()
    conn.close()
    print(f"  {len(df)} dies carregats")
    return df


def entrena(df, usa_meteo=True, dies_test=60):
    print(f"\n=== Entrenant Prophet (meteo={usa_meteo}) ===")
    
    train = df.iloc[:-dies_test].copy()
    test = df.iloc[-dies_test:].copy()
    print(f"  Train: {len(train)} dies | Test: {len(test)} dies")
    
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_mode='additive'
    )
    
    regressors = []
    if usa_meteo:
        regressors = ['vent_velocitat', 'temperatura', 'precipitacio', 'pressio']
        for r in regressors:
            model.add_regressor(r)
    
    model.fit(train)
    
    future = test[['ds'] + regressors].copy()
    forecast = model.predict(future)
    
    y_true = test['y'].values
    y_pred = forecast['yhat'].values
    
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    r2 = 1 - np.sum((y_true - y_pred)**2) / np.sum((y_true - np.mean(y_true))**2)
    
    print(f"  MAE:  {mae:.2f} µg/m³")
    print(f"  RMSE: {rmse:.2f} µg/m³")
    print(f"  MAPE: {mape:.1f}%")
    print(f"  R²:   {r2:.3f}")
    
    return model, forecast, test, {"mae": mae, "rmse": rmse, "mape": mape, "r2": r2}


def guarda_grafic(forecast, test, nom):
    Path("images").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(test['ds'], test['y'], label='Real', color='#1f77b4', marker='o', markersize=3)
    ax.plot(test['ds'], forecast['yhat'], label='Predicció', color='#d62728', linewidth=2)
    ax.fill_between(test['ds'], forecast['yhat_lower'], forecast['yhat_upper'],
                     color='#d62728', alpha=0.2, label='Interval 80%')
    ax.axhline(40, color='orange', linestyle='--', label='Límit Anual UE (40 µg/m³)')
    ax.set_title(f'Predicció NO2 diari - Barcelona Eixample ({nom})')
    ax.set_xlabel('Data')
    ax.set_ylabel('NO2 mitjà (µg/m³)')
    ax.legend()
    plt.tight_layout()
    plt.savefig(f'images/prediccio_{nom}.png', dpi=100)
    plt.close()
    print(f"  Gràfic: images/prediccio_{nom}.png")


def main():
    df = carrega_dades()
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("qualitat_aire_bcn")
    
    with mlflow.start_run(run_name="prophet_diari_sense_meteo"):
        _, fc1, t1, m1 = entrena(df, usa_meteo=False)
        mlflow.log_param("granularitat", "diaria")
        mlflow.log_param("regressors", "cap")
        mlflow.log_metrics(m1)
        guarda_grafic(fc1, t1, "diari_sense_meteo")
        mlflow.log_artifact("images/prediccio_diari_sense_meteo.png")
    
    with mlflow.start_run(run_name="prophet_diari_amb_meteo"):
        _, fc2, t2, m2 = entrena(df, usa_meteo=True)
        mlflow.log_param("granularitat", "diaria")
        mlflow.log_param("regressors", "vent, temp, precip, pressio")
        mlflow.log_metrics(m2)
        guarda_grafic(fc2, t2, "diari_amb_meteo")
        mlflow.log_artifact("images/prediccio_diari_amb_meteo.png")
    
    print("\n=== COMPARACIÓ ===")
    print(f"  Sense meteo: MAE {m1['mae']:.2f} | R² {m1['r2']:.3f}")
    print(f"  Amb meteo:   MAE {m2['mae']:.2f} | R² {m2['r2']:.3f}")
    millora = (m1['mae'] - m2['mae']) / m1['mae'] * 100
    print(f"  Millora amb meteo: {millora:.1f}%")


if __name__ == "__main__":
    main()