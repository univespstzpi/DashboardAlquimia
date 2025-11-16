# dashboard_predicoes_alquimia.py
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import pickle
from datetime import timedelta
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Dashboard de Previsões Alquimia", layout="wide")
st.title("🍻 Dashboard de Previsões de Vendas - Cervejaria Alquimia")

# -------- Configuração ----------
MODEL_FOLDER = "prediction_outputs"
ITEMS_TO_USE = [
    "Growler Witbier", "Suco de Laranja Afrutte 300ml", "Growler Pilsen",
    "Água sem gás 500ml", "Gelo E Limao", "Energetico Monster 473ml",
    "Caneca Pilsen", "Coca Cola 350ml", "Couvert Artístico", "Água com Gás 500ml"
]
N_LAGS = [1, 7, 30]
ROLL_WINDOWS = [3, 7, 30]

# ----------------- Funções auxiliares -----------------
def ensure_datetime(df, col_candidates):
    for col in col_candidates:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
                if df[col].notna().sum() > 0:
                    return col
            except:
                continue
    for col in df.columns:
        try:
            tmp = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            if tmp.notna().sum() > 0:
                df[col] = tmp
                return col
        except:
            continue
    return None

def create_calendar_feats(df, date_col=None):
    df = df.copy()
    if date_col is None:
        idx = df.index
        df["day_of_week"] = idx.weekday
        df["is_weekend"] = (idx.weekday >= 5).astype(int)
        df["day"] = idx.day
        df["month"] = idx.month
    else:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
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

def to_numeric_maybe(s):
    if s.dtype == object:
        return s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    else:
        return s.astype(float)

# ----------------- Seleção do arquivo mais recente -----------------
st.header("1) Arquivo de histórico")
folder = "."
arquivos = [f for f in os.listdir(folder) if f.startswith("Historico_Itens_Vendidos de") and f.endswith(".xlsx")]
if not arquivos:
    st.error("Nenhum arquivo 'Historico_Itens_Vendidos' encontrado.")
    st.stop()

def extrair_data_final(nome):
    try:
        parte = nome.split("de",1)[1].rsplit(".xlsx",1)[0].strip()
        if "à" in parte:
            final_txt = parte.split("à")[1].strip()
        elif "a" in parte:
            final_txt = parte.split("a")[1].strip()
        else:
            found = re.findall(r"(\d{2}-\d{2}-\d{2})", nome)
            final_txt = found[-1] if found else "01-01-1900"
        return pd.to_datetime(final_txt, dayfirst=True, errors="coerce") or pd.to_datetime("1900-01-01")
    except:
        return pd.to_datetime("1900-01-01")

arquivo_mais_recente = max(arquivos, key=extrair_data_final)
file_path = os.path.join(folder, arquivo_mais_recente)
st.write(f"Arquivo selecionado: **{arquivo_mais_recente}**")

df_raw = pd.read_excel(file_path)
st.write("Colunas detectadas:", list(df_raw.columns))

date_col = ensure_datetime(df_raw, ["Data/Hora Item","Data Ab. Ped.","Data Fec. Ped.","Data/Hora","Data","date"])
if date_col is None:
    st.error("Não foi possível detectar coluna de data.")
    st.stop()

# detectar colunas de quantidade, valor e produto
qty_col = next((c for c in df_raw.columns if "qtd" in str(c).lower() or "quant" in str(c).lower()), None)
value_col = next((c for c in df_raw.columns if any(x in str(c).lower() for x in ["valor. tot","valor tot","valor prod","valor"])), None)
if value_col is None:
    numerics = df_raw.select_dtypes(include=[np.number]).columns.tolist()
    value_col = numerics[0] if numerics else None
prod_col = next((c for c in df_raw.columns if any(x in str(c).lower() for x in ["nome prod","nome","produto"])), None)

# limpeza
df = df_raw.copy()
df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
df = df.dropna(subset=[date_col]).reset_index(drop=True)
df[value_col] = to_numeric_maybe(df[value_col]) if value_col else 0
if qty_col:
    df[qty_col] = to_numeric_maybe(df[qty_col])
else:
    df["__qty_dummy"] = 1.0
    qty_col = "__qty_dummy"

# agregados diários
df["date_only"] = df[date_col].dt.floor("D")
order_col = next((c for c in df.columns if "cod" in str(c).lower() and ("ped" in str(c).lower() or "pedido" in str(c).lower())), None)

daily = df.groupby("date_only").agg(
    total_diario=(value_col,"sum"),
    qtd_diario=(qty_col,"sum"),
    num_linhas=(value_col,"size")
)
daily["num_pedidos"] = df.groupby("date_only")[order_col].nunique() if order_col else df.groupby("date_only")[value_col].size()
daily["unique_products"] = df.groupby("date_only")[prod_col].nunique() if prod_col else 0
daily = daily.sort_index().fillna(0)
daily["ticket_medio"] = (daily["total_diario"]/daily["num_pedidos"]).replace([np.inf,-np.inf],0).fillna(0)
daily = create_calendar_feats(daily.reset_index().rename(columns={"date_only":"date"}).set_index("date"))

lagroll = create_lags_and_rolls(daily["total_diario"])
daily_features = lagroll.join(daily[["qtd_diario","num_pedidos","num_linhas","unique_products","ticket_medio",
                                     "day_of_week","is_weekend","month","month_sin","month_cos"]], how="left")

st.write("Período diário disponível:", daily.index.min().date(), "até", daily.index.max().date())

# ----------------- Funcão para features do próximo dia -----------------
def build_features_next_day(daily):
    last_date = daily.index.max()
    next_date = last_date + pd.Timedelta(days=1)
    y = daily["total_diario"]
    features = {f"lag_{lag}": float(y.iloc[-lag]) if len(y)>=lag else np.nan for lag in N_LAGS}
    for w in ROLL_WINDOWS:
        vals = y.iloc[-w:]
        features[f"roll_mean_{w}"] = float(vals.mean()) if len(vals)>0 else np.nan
        features[f"roll_std_{w}"] = float(vals.std(ddof=0)) if len(vals)>0 else 0.0
    # proxies
    for col in ["qtd_diario","num_pedidos","num_linhas","unique_products","ticket_medio","day_of_week","is_weekend","month","month_sin","month_cos"]:
        features[col] = float(daily[col].iloc[-1]) if col in daily.columns else 0.0
    # override calendário
    features["day_of_week"] = int(next_date.weekday())
    features["is_weekend"] = int(next_date.weekday()>=5)
    features["month"] = int(next_date.month)
    features["month_sin"] = np.sin(2*np.pi*next_date.month/12)
    features["month_cos"] = np.cos(2*np.pi*next_date.month/12)
    return pd.DataFrame([features], index=[next_date])

feat_next_day = build_features_next_day(daily)
st.subheader("2) Previsão diária (features para inferência)")
st.dataframe(feat_next_day.T)

# ----------------- Inferência diária -----------------
st.header("3) Inferência diária")
daily_model_file = next((os.path.join(MODEL_FOLDER,f) for f in os.listdir(MODEL_FOLDER)
                         if f.startswith("best_model_daily_") and f.endswith(".pkl")), None)
if daily_model_file is None:
    st.error("Modelo diário não encontrado.")
else:
    with open(daily_model_file,"rb") as fh:
        model_daily = pickle.load(fh)
    X_input = feat_next_day.reindex(columns=feat_next_day.columns)
    try:
        pred_daily = model_daily.predict(X_input)[0]
        st.metric(label=f"Previsão total diária ({feat_next_day.index[0].date()})", value=f"{pred_daily:.2f}")
    except Exception as e:
        st.error(f"Erro ao predizer com modelo diário: {e}")

# ----------------- Inferência por item (robusta) -----------------
st.header("4) Inferência por item")
if prod_col is None:
    st.warning("Coluna de produto não detectada; pulando predições por item.")
else:
    # pivot diário por item
    pivot = df.groupby(["date_only", prod_col])[value_col].sum().unstack(fill_value=0).sort_index()
    pivot.index = pd.to_datetime(pivot.index)
    rows, preds_dict = [], {}

    for item in ITEMS_TO_USE:
        safe_item_name = str(item)[:30].replace("/","_").replace("\\","_").replace(" ","_")
        model_path = os.path.join(MODEL_FOLDER,f"model_item_{safe_item_name}_Linear.pkl")
        if not os.path.exists(model_path):
            found = next((os.path.join(MODEL_FOLDER,f) for f in os.listdir(MODEL_FOLDER)
                          if f.startswith(f"model_item_{safe_item_name}_") and f.endswith(".pkl")), None)
            model_path = found
        if model_path is None or not os.path.exists(model_path):
            rows.append([item,"modelo não encontrado","--"])
            continue
        try:
            with open(model_path,"rb") as fh:
                model_item = pickle.load(fh)
        except Exception as e:
            rows.append([item,"erro ao carregar modelo",str(e)])
            continue
        if item not in pivot.columns:
            rows.append([item,"sem série no histórico","--"])
            continue
        series = pivot[item].astype(float)
        feat_item = {f"lag_{lag}": float(series.iloc[-lag]) if len(series)>=lag else np.nan for lag in N_LAGS}
        for w in ROLL_WINDOWS:
            vals = series.iloc[-w:]
            feat_item[f"roll_mean_{w}"] = float(vals.mean()) if len(vals)>0 else np.nan
            feat_item[f"roll_std_{w}"] = float(vals.std(ddof=0)) if len(vals)>0 else 0.0
        for col in ["qtd_diario","ticket_medio","month_sin","month_cos","day_of_week","is_weekend"]:
            feat_item[col] = float(daily[col].iloc[-1]) if col in daily.columns else 0.0
        next_date = daily.index.max() + pd.Timedelta(days=1)
        feat_item["day_of_week"] = int(next_date.weekday())
        feat_item["is_weekend"] = int(next_date.weekday()>=5)
        feat_item["month_sin"] = np.sin(2*np.pi*next_date.month/12)
        feat_item["month_cos"] = np.cos(2*np.pi*next_date.month/12)
        feat_item_df = pd.DataFrame([feat_item], index=[next_date])
        try:
            pred_item = model_item.predict(feat_item_df)[0]
            preds_dict[item] = pred_item
            last_val = float(series.iloc[-1]) if len(series)>0 else 0.0
            rows.append([item,last_val,pred_item])
        except Exception as e:
            rows.append([item,"erro ao predizer",str(e)])

    df_items_pred = pd.DataFrame(rows, columns=["Item","Último valor observado","Previsão próximo dia"])
    def format_numeric(x):
        try:
            return "{:.2f}".format(float(x))
        except:
            return x
    st.dataframe(df_items_pred.style.format({
        "Último valor observado": format_numeric,
        "Previsão próximo dia": format_numeric
    }))

    if preds_dict:
        st.subheader("📊 Previsões por item (gráfico)")
        df_plot = pd.DataFrame.from_dict(preds_dict, orient="index", columns=["Previsão"])
        fig = px.bar(df_plot, y="Previsão", labels={"index":"Item"})
        st.plotly_chart(fig, use_container_width=True)

# ----------------- Visualizações finais -----------------
st.header("5) Visualizações adicionais")
col1, col2 = st.columns(2)
with col1:
    st.subheader("Série total diária (últimos 120 dias)")
    if len(daily)>0:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily.index[-120:], y=daily["total_diario"][-120:], mode="lines", name="Total diário"))
        st.plotly_chart(fig, use_container_width=True)
with col2:
    st.subheader("Roll mean 7 (últimos 120 dias)")
    if "total_diario" in daily.columns:
        roll7 = daily["total_diario"].shift(1).rolling(window=7,min_periods=1).mean()
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=daily.index[-120:], y=roll7[-120:], mode="lines", name="Roll mean 7"))
        st.plotly_chart(fig2, use_container_width=True)

st.success(
    "Dashboard pronto. Observação: variáveis diárias desconhecidas (qtd_diario, num_pedidos, ticket_medio) "
    "usam último valor observado como proxy. Para previsões multi-dia, esquema recursivo é necessário."
)
st.markdown("© 2025 **Cervejaria Alquimia** - Transformando dados em insights para a sua operação 🍻")




