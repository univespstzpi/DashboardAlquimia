# -*- coding: utf-8 -*-
"""
predicao_diaria_e_item.py
- Lê os 3 arquivos Excel (nomes esperados no mesmo diretório).
- Constrói:
    A) Modelo diário para prever total diário (target: total_diario)
    B) Modelos separados por item (cada item tem seu próprio modelo)
- Gera features de calendário, lags, rolling windows (3,7,30 dias).
- Treina 5 modelos (KNN, Linear, MLP, RF, SVR) com GridSearch (TimeSeriesSplit).
- Salva modelos, métricas, previsões e gráficos em ./prediction_outputs
- NÃO usa feriados externos; usa somente dados das planilhas.
"""
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# ========== Config ==========
FILES = [
    Path("Historico_Itens_Vendidos de 01-01-23 à 31-12-23.xlsx"),
    Path("Historico_Itens_Vendidos de 01-01-24 à 31-12-24.xlsx"),
    Path("Historico_Itens_Vendidos de 01-01-25 à 30-08-25.xlsx"),
]
# Output dir (next to script or cwd)
try:
    BASE_DIR = Path(__file__).parent
except NameError:
    BASE_DIR = Path.cwd()
OUT_DIR = BASE_DIR / "prediction_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MIN_DAYS_ITEM = 90   # mínimo de dias com vendas para treinar modelo por item
TEST_DAYS = 14       # últimos N dias para teste (diário)
N_LAGS = [1,7,30]    # lags to create
ROLL_WINDOWS = [3,7,30]  # rolling windows
RANDOM_STATE = 42

# ========== Imports ==========
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import sys
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ========== Helper functions ==========
def read_and_concat(paths):
    dfs = []
    for p in paths:
        if not p.exists():
            print(f"Aviso: arquivo não encontrado: {p} (ignorando)")
            continue
        try:
            d = pd.read_excel(p)
            dfs.append(d)
        except Exception as e:
            print(f"Falha ao ler {p}: {e}")
    if not dfs:
        raise FileNotFoundError("Nenhum arquivo válido encontrado.")
    df = pd.concat(dfs, ignore_index=True, sort=False)
    return df

def ensure_datetime(df, col_candidates):
    for col in col_candidates:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
                if df[col].notna().sum() > 0:
                    return col
            except Exception:
                continue
    # fallback try to parse any column
    for col in df.columns:
        try:
            tmp = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            if tmp.notna().sum() > 0:
                df[col] = tmp
                return col
        except Exception:
            continue
    return None

def create_calendar_feats(df, date_col=None):
    """
    Se date_col for None assume que o índice do DataFrame é DatetimeIndex.
    Se date_col for uma string, usa essa coluna (converte para datetime se necessário).
    Retorna df com colunas: day_of_week, is_weekend, day, month, month_sin, month_cos
    """
    df = df.copy()
    if date_col is None:
        # usa índice
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("create_calendar_feats: índice não é DatetimeIndex e date_col não foi informado.")
        idx = df.index
        df["day_of_week"] = idx.weekday
        df["is_weekend"] = (idx.weekday >= 5).astype(int)
        df["day"] = idx.day
        df["month"] = idx.month
    else:
        # usa coluna
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        if df[date_col].isna().all():
            raise ValueError(f"create_calendar_feats: coluna {date_col} não contém datas válidas.")
        df["day_of_week"] = df[date_col].dt.weekday
        df["is_weekend"] = df["day_of_week"].isin([5,6]).astype(int)
        df["day"] = df[date_col].dt.day
        df["month"] = df[date_col].dt.month

    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


def create_lags_and_rolls(series, lags=N_LAGS, rolls=ROLL_WINDOWS):
    df = pd.DataFrame({"y": series})
    for lag in lags:
        df[f"lag_{lag}"] = df["y"].shift(lag)
    for w in rolls:
        df[f"roll_mean_{w}"] = df["y"].shift(1).rolling(window=w, min_periods=1).mean()
        df[f"roll_std_{w}"] = df["y"].shift(1).rolling(window=w, min_periods=1).std().fillna(0)
    return df

def train_and_evaluate(X_train, y_train, X_test, y_test, models_dict, tscv_splits=3):
    results = []
    best_models = {}
    tscv = TimeSeriesSplit(n_splits=tscv_splits)
    for name, (est, grid) in models_dict.items():
        pipe = Pipeline([("scaler", StandardScaler()), ("model", est)])
        # Use neg_mean_squared_error for compatibility; compute RMSE manually.
        gscv = GridSearchCV(pipe, grid, cv=tscv, scoring="neg_mean_squared_error", n_jobs=1, verbose=0)
        try:
            gscv.fit(X_train, y_train)
        except Exception as e:
            print(f"Erro ao treinar {name}: {e}")
            continue
        best = gscv.best_estimator_
        preds = best.predict(X_test)
        mse = mean_squared_error(y_test, preds)
        rmse = float(np.sqrt(mse))
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        results.append({"model": name, "rmse": rmse, "mae": mae, "r2": r2, "best_params": gscv.best_params_})
        best_models[name] = best
    res_df = pd.DataFrame(results).sort_values("rmse")
    return res_df, best_models

# ========== Read data ==========
print("Carregando planilhas...")
df_raw = read_and_concat(FILES)
print("Linhas carregadas:", len(df_raw))
# show columns for debug
print("Colunas detectadas:", list(df_raw.columns))

# ========== Detect date, product, value columns (based on your sample) ==========
# Known names from your sample:
date_candidates = ["Data/Hora Item", "Data Ab. Ped.", "Data Fec. Ped.", "Data/Hora"]
date_col = ensure_datetime(df_raw, date_candidates)
if date_col is None:
    raise ValueError("Não foi possível detectar coluna de data automaticamente.")
print("Usando coluna de data:", date_col)

# quantity column names from sample
qty_col = None
for c in df_raw.columns:
    if str(c).strip().lower().startswith("qtd") or "qtd" in str(c).lower() or "quant" in str(c).lower():
        qty_col = c
        break

# value column candidates: Valor. Tot. Item OR Valor Prod OR Valor. Tot
value_col = None
for c in df_raw.columns:
    lc = str(c).lower()
    if "valor. tot" in lc or "valor tot" in lc or "valor prod" in lc:
        value_col = c
        break
# fallback numeric
if value_col is None:
    numerics = df_raw.select_dtypes(include=[np.number]).columns.tolist()
    if numerics:
        value_col = numerics[0]
if value_col is None:
    raise ValueError("Não foi possível detectar coluna de valor/total nas planilhas.")
print("Usando coluna de valor por linha:", value_col)

# product column
prod_col = None
for c in df_raw.columns:
    lc = str(c).lower()
    if "nome prod" in lc or "nome" in lc or "produto" in lc:
        prod_col = c
        break
print("Usando coluna produto:", prod_col)

# ========== Clean & prepare row-level data ==========
df = df_raw.copy()
df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
df = df.dropna(subset=[date_col]).reset_index(drop=True)
# normalize decimal separators for value column (if strings with comma)
def to_numeric_maybe(s):
    if s.dtype == object:
        return s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    else:
        return s.astype(float)

try:
    df[value_col] = to_numeric_maybe(df[value_col])
except Exception:
    # fallback: coerce
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0.0)

if qty_col is not None:
    try:
        df[qty_col] = to_numeric_maybe(df[qty_col])
    except Exception:
        df[qty_col] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0.0)
else:
    # create a quantity 1 if missing
    df["__qty_dummy"] = 1.0
    qty_col = "__qty_dummy"

# ========== Create daily aggregates ==========

df["date_only"] = df[date_col].dt.floor("D")
# total daily sales (monetary), qty, num_orders (unique Cod. Ped.), num_lines, unique_products_count
order_col = None
for c in df.columns:
    if "cod" in str(c).lower() and ("ped" in str(c).lower() or "pedido" in str(c).lower()):
        order_col = c
        break

daily = df.groupby("date_only").agg(
    total_diario = (value_col, "sum"),
    qtd_diario = (qty_col, "sum"),
    num_linhas = (value_col, "size"),
)
if order_col is not None:
    daily["num_pedidos"] = df.groupby("date_only")[order_col].nunique()
else:
    daily["num_pedidos"] = df.groupby("date_only")[value_col].size()

if prod_col is not None:
    daily["unique_products"] = df.groupby("date_only")[prod_col].nunique()
else:
    daily["unique_products"] = 0

# fill nan and sort
daily = daily.sort_index().fillna(0.0)
print("Período diário:", daily.index.min().date(), "até", daily.index.max().date())
daily["ticket_medio"] = (daily["total_diario"] / daily["num_pedidos"]).replace([np.inf, -np.inf], 0).fillna(0)

# calendar features
daily = create_calendar_feats(daily.reset_index().rename(columns={"date_only":"date"}).set_index("date"), date_col=None)
# create_lags and rolls for daily target
lagroll = create_lags_and_rolls(daily["total_diario"], lags=N_LAGS, rolls=ROLL_WINDOWS)
daily_features = lagroll.join(daily[["qtd_diario","num_pedidos","num_linhas","unique_products","ticket_medio","day_of_week","is_weekend","month","month_sin","month_cos"]], how="left")
daily_features = daily_features.dropna().copy()
print("Exemplo features diárias:")
print(daily_features.head())

# ========== MODEL DEFINITION ==========
models_dict = {
    "KNN": (KNeighborsRegressor(), {"model__n_neighbors":[3,5], "model__weights":["uniform","distance"]}),
    "Linear": (LinearRegression(), {"model__fit_intercept":[True, False]}),
    "MLP": (MLPRegressor(max_iter=1000, random_state=RANDOM_STATE), {"model__hidden_layer_sizes":[(50,), (100,)], "model__alpha":[1e-4,1e-3]}),
    "RandomForest": (RandomForestRegressor(random_state=RANDOM_STATE), {"model__n_estimators":[50,100], "model__max_depth":[3,5,None]}),
    "SVR": (SVR(), {"model__C":[0.1,1], "model__epsilon":[0.01, 0.1], "model__kernel":["rbf"]}),
}

# ========== TRAIN/TEST SPLIT for daily model ==========
if len(daily_features) <= TEST_DAYS + 30:
    print("Atenção: poucos dias disponíveis. Ajuste TEST_DAYS ou verifique dados.")
train_daily = daily_features.iloc[:-TEST_DAYS]
test_daily = daily_features.iloc[-TEST_DAYS:]

X_train_d = train_daily.drop(columns=["y"])
y_train_d = train_daily["y"]
X_test_d = test_daily.drop(columns=["y"])
y_test_d = test_daily["y"]

print("Treinando modelo diário (total de vendas)...")
res_daily, best_models_daily = train_and_evaluate(X_train_d, y_train_d, X_test_d, y_test_d, models_dict, tscv_splits=min(3, max(2, len(X_train_d)//5)))
res_daily.to_csv(OUT_DIR / "results_daily_models.csv", index=False)
print("Resultados (diário):")
print(res_daily)

# Save best daily model (the one with lowest RMSE)
if not res_daily.empty:
    best_daily_name = res_daily.iloc[0]["model"]
    best_daily_model = best_models_daily[best_daily_name]
    with open(OUT_DIR / f"best_model_daily_{best_daily_name}.pkl", "wb") as f:
        pickle.dump(best_daily_model, f)

# save predictions & plots for daily
preds_table = pd.DataFrame(index=X_test_d.index)
for name, model in best_models_daily.items():
    preds = model.predict(X_test_d)
    preds_table[name] = preds
preds_table["actual"] = y_test_d
preds_table.to_csv(OUT_DIR / "predictions_daily_models.csv")

# plot actual vs predicted for daily
for name, model in best_models_daily.items():
    preds = model.predict(X_test_d)
    plt.figure(figsize=(8,4))
    plt.plot(y_test_d.index, y_test_d.values, marker='o', label="actual")
    plt.plot(y_test_d.index, preds, marker='o', linestyle="--", label="pred_"+name)
    plt.title(f"Daily - actual vs pred - {name}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_DIR / f"daily_actual_vs_pred_{name}.png")
    plt.close()

# ========== PER-ITEM MODELS (Option A: separate model per item) ==========
print("\nPreparando séries por item...")
# create daily pivot table: index=date, columns=item_name, values=sum(value_col)
if prod_col is None:
    raise ValueError("Coluna de produto não detectada; impossivel treinar modelos por item.")
pivot = df.groupby([ "date_only", prod_col ])[value_col].sum().unstack(fill_value=0).sort_index()
# Also create qty pivot (if needed)
qty_pivot = df.groupby(["date_only", prod_col])[qty_col].sum().unstack(fill_value=0).sort_index()

# For each product (column) with at least MIN_DAYS_ITEM non-zero days, train a model
item_results = []
per_item_models = {}

for item in pivot.columns:
    series = pivot[item].rename("y")
    # require at least MIN_DAYS_ITEM days with non-zero sales (or total length)
    non_zero_days = (series != 0).sum()
    if non_zero_days < MIN_DAYS_ITEM or len(series) < (MIN_DAYS_ITEM + TEST_DAYS):
        # skip small series to avoid overfitting
        print(f"Pulando item '{item}' - dias com vendas: {non_zero_days}, total dias: {len(series)}")
        continue

    # build features for this item: lags + rolls + calendar + other daily aggregates (optional)
    df_item = create_lags_and_rolls(series, lags=N_LAGS, rolls=ROLL_WINDOWS)
    # join some global daily features (to give context): ticket_medio, qtd_diario, month_sin/cos, day_of_week
    context_cols = daily[["qtd_diario","ticket_medio","month_sin","month_cos","day_of_week","is_weekend"]]
    df_item = df_item.join(context_cols, how="left").dropna()
    if len(df_item) <= TEST_DAYS + 30:
        print(f"Pulando item '{item}' por poucos registros após criação de features.")
        continue

    train_item = df_item.iloc[:-TEST_DAYS]
    test_item = df_item.iloc[-TEST_DAYS:]
    X_train_i = train_item.drop(columns=["y"])
    y_train_i = train_item["y"]
    X_test_i = test_item.drop(columns=["y"])
    y_test_i = test_item["y"]

    # train
    try:
        res_i, bests = train_and_evaluate(X_train_i, y_train_i, X_test_i, y_test_i, models_dict, tscv_splits=min(3, max(2, len(X_train_i)//5)))
    except Exception as e:
        print(f"Erro treinando item {item}: {e}")
        continue

    # store top model results
    if res_i.empty:
        continue
    res_i["item"] = item
    res_i["n_nonzero_days"] = non_zero_days
    # choose best
    best_name = res_i.iloc[0]["model"]
    per_item_models[item] = bests[best_name]
    # save per-item metrics and predictions
    res_i.to_csv(OUT_DIR / f"results_item_{str(item)[:30].replace(' ','_')}.csv", index=False)
    preds_item = pd.DataFrame(index=X_test_i.index)
    for mname, mmodel in bests.items():
        preds_item[mname] = mmodel.predict(X_test_i)
    preds_item["actual"] = y_test_i
    preds_item.to_csv(OUT_DIR / f"preds_item_{str(item)[:30].replace(' ','_')}.csv")
    # plot actual vs best
    plt.figure(figsize=(8,4))
    best_preds = per_item_models[item].predict(X_test_i)
    plt.plot(y_test_i.index, y_test_i.values, marker='o', label="actual")
    plt.plot(y_test_i.index, best_preds, marker='o', linestyle="--", label=f"pred_{best_name}")
    plt.title(f"Item '{item}' - actual vs pred ({best_name})")
    plt.legend()
    plt.tight_layout()
    safe_item_name = str(item)[:30].replace("/","_").replace("\\","_").replace(" ","_")
    plt.savefig(OUT_DIR / f"item_{safe_item_name}_best_{best_name}.png")
    plt.close()

    # top-line summary
    top_row = res_i.iloc[0].to_dict()
    item_results.append(top_row)
    # Save model
    with open(OUT_DIR / f"model_item_{safe_item_name}_{best_name}.pkl", "wb") as f:
        pickle.dump(per_item_models[item], f)
    print(f"Treinado item: {item} | melhor modelo: {best_name}")

# Save summary for all items
if item_results:
    pd.DataFrame(item_results).to_csv(OUT_DIR / "results_items_summary.csv", index=False)
else:
    print("Nenhum modelo por item foi treinado (sem items com dados suficientes).")

# Save processed daily features for inspection
daily_features.to_csv(OUT_DIR / "processed_daily_features.csv")
pivot.to_csv(OUT_DIR / "pivot_daily_items.csv")
qty_pivot.to_csv(OUT_DIR / "pivot_daily_qty.csv")

print("\nArquivos gerados em:", OUT_DIR)
for f in sorted(OUT_DIR.iterdir()):
    print("-", f.name)

print("\nFim do script.")

