import duckdb
import pandas as pd
import numpy as np
import mlflow
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from pathlib import Path

DB_PATH = "data/processed/qualitat_aire.duckdb"

FEATURES = [
    'no2_lag1', 'no2_lag2', 'no2_lag7',
    'no2_mm3', 'no2_mm7',
    'vent_velocitat', 'vent_max', 'vent_lag1',
    'temperatura', 'humitat', 'precipitacio', 'precip_lag1', 'pressio',
    'dia_setmana_num', 'mes',
    'dia_any_sin', 'dia_any_cos'
]


def carrega_dades():
    print("=== Carregant features ===")
    conn = duckdb.connect(DB_PATH)
    df = conn.execute("""
        SELECT *
        FROM gold_features_ml
        WHERE no2_lag7 IS NOT NULL
          AND no2_mm7 IS NOT NULL
        ORDER BY data
    """).df()
    conn.close()
    
    df['es_cap_setmana'] = df['es_cap_setmana'].astype(int)
    print(f"  {len(df)} dies amb features completes")
    return df


def entrena_xgboost(df, dies_test=60):
    print("\n=== Entrenant XGBoost ===")
    
    train = df.iloc[:-dies_test]
    test = df.iloc[-dies_test:]
    print(f"  Train: {len(train)} dies | Test: {len(test)} dies")
    
    X_train = train[FEATURES]
    y_train = train['no2_mitja']
    X_test = test[FEATURES]
    y_test = test['no2_mitja']
    
    params = {
        'n_estimators': 300,
        'max_depth': 5,
        'learning_rate': 0.05,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42
    }
    
    model = xgb.XGBRegressor(**params)
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
    r2 = 1 - np.sum((y_test - y_pred)**2) / np.sum((y_test - np.mean(y_test))**2)
    
    print(f"  MAE:  {mae:.2f} µg/m³")
    print(f"  RMSE: {rmse:.2f} µg/m³")
    print(f"  MAPE: {mape:.1f}%")
    print(f"  R²:   {r2:.3f}")
    
    metrics = {"mae": mae, "rmse": rmse, "mape": mape, "r2": r2}
    return model, test, y_pred, metrics, params


def grafic_prediccio(test, y_pred, nom):
    Path("images").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(test['data'], test['no2_mitja'], label='Real',
            color='#1f77b4', marker='o', markersize=3)
    ax.plot(test['data'], y_pred, label='Predicció XGBoost',
            color='#2ca02c', linewidth=2)
    ax.axhline(40, color='orange', linestyle='--', label='Límit anual UE (40 µg/m³)')
    ax.set_title('Predicció NO2 diari amb XGBoost - Barcelona Eixample')
    ax.set_xlabel('Data')
    ax.set_ylabel('NO2 mitjà (µg/m³)')
    ax.legend()
    plt.tight_layout()
    plt.savefig(f'images/prediccio_{nom}.png', dpi=100)
    plt.close()
    print(f"  Gràfic: images/prediccio_{nom}.png")


def grafic_importancia(model, nom):
    imp = pd.DataFrame({
        'feature': FEATURES,
        'importancia': model.feature_importances_
    }).sort_values('importancia', ascending=True)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(imp['feature'], imp['importancia'], color='#2ca02c')
    ax.set_title('Importància de les features - XGBoost')
    ax.set_xlabel('Importància relativa')
    plt.tight_layout()
    plt.savefig(f'images/{nom}.png', dpi=100)
    plt.close()
    print(f"  Gràfic: images/{nom}.png")
    
    print("\n  --- Top 8 features més importants ---")
    print(imp.tail(8).sort_values('importancia', ascending=False).to_string(index=False))


def main():
    df = carrega_dades()
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("qualitat_aire_bcn")
    
    with mlflow.start_run(run_name="xgboost_amb_lags"):
        model, test, y_pred, metrics, params = entrena_xgboost(df)
        
        mlflow.log_param("algoritme", "XGBoost")
        mlflow.log_param("num_features", len(FEATURES))
        mlflow.log_param("features", ", ".join(FEATURES[:5]) + "...")
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        
        grafic_prediccio(test, y_pred, "xgboost")
        grafic_importancia(model, "importancia_features")
        
        mlflow.log_artifact("images/prediccio_xgboost.png")
        mlflow.log_artifact("images/importancia_features.png")
        mlflow.xgboost.log_model(model, "model")
    
    print("\n=== Model registrat a MLflow ===")


if __name__ == "__main__":
    main()