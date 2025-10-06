
import io
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import streamlit as st

st.set_page_config(page_title="Resumen mensual Treble.ai", page_icon="📊", layout="wide")

# ------------- Utilidades -------------
@st.cache_data
def load_csv(file_bytes, sep=None):
    # intenta autodetectar separador
    return pd.read_csv(io.BytesIO(file_bytes), sep=sep or None, engine="python")

@st.cache_data
def load_excel(file_bytes):
    return pd.read_excel(io.BytesIO(file_bytes))

def coerce_datetime(series):
    # Intenta convertir a datetime con formato flexible
    return pd.to_datetime(series, errors="coerce", utc=False, dayfirst=True, infer_datetime_format=True)

def month_floor(d):
    return pd.to_datetime(d.dt.to_period("M").dt.start_time)

def month_label(dt_series):
    return dt_series.dt.strftime("%Y-%m")

def safe_col(df, name_options, default=None):
    for n in name_options:
        if n in df.columns:
            return n
    return default

def summarize_month(df, dt_col, month_ym, cols_to_summarize):
    # Filtra por mes YYYY-MM
    df = df.copy()
    df["_month"] = month_label(df[dt_col])
    month_df = df[df["_month"] == month_ym].copy()
    total_registros = len(month_df)
    total_celulares = month_df["Celular"].nunique() if "Celular" in month_df.columns else None

    summaries = {}
    for c in cols_to_summarize:
        if c in month_df.columns:
            cnt = (month_df
                   .assign(**{c: month_df[c].astype(str).replace({"nan": "Sin dato"})})
                   .groupby(c)
                   .size()
                   .sort_values(ascending=False)
                   .rename("conteo")
                   .reset_index())
            summaries[c] = cnt

    return month_df, total_registros, total_celulares, summaries

def monthly_trends(df, dt_col, cols_to_summarize):
    df = df.copy()
    df["_month"] = month_label(df[dt_col])
    trends = {}
    for c in cols_to_summarize:
        if c in df.columns:
            pivot = (df.assign(**{c: df[c].astype(str).replace({"nan": "Sin dato"})})
                       .pivot_table(index="_month", columns=c, values=df.columns[0], aggfunc="count", fill_value=0))
            pivot = pivot.sort_index()
            trends[c] = pivot
    totals = df["_month"].value_counts().sort_index()
    if "Celular" in df.columns:
        unique_by_month = df.groupby("_month")["Celular"].nunique().reindex(totals.index, fill_value=0)
    else:
        unique_by_month = None
    return totals, unique_by_month, trends

# ------------- UI -------------
st.title("📊 Resumen mensual de base Treble.ai")
st.caption("Selecciona año y mes para ver el resumen. Carga tu CSV/XLSX exportado de Treble.ai (o tabla equivalente).")

with st.expander("📥 Cargar datos", expanded=True):
    file = st.file_uploader("Sube un archivo CSV o XLSX", type=["csv", "xlsx"])
    delimiter = st.text_input("Delimitador (opcional, deja vacío para autodetectar)", value="")
    sheet_name = st.text_input("Nombre de hoja (XLSX, opcional)", value="")

    df = None
    if file is not None:
        try:
            if file.type.endswith("csv"):
                df = load_csv(file.read(), sep=delimiter or None)
            else:
                content = file.read()
                if sheet_name.strip():
                    df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name.strip())
                else:
                    df = load_excel(content)
        except Exception as e:
            st.error(f"Error leyendo el archivo: {e}")

    st.markdown("**Columnas esperadas (sugeridas):** `Celular`, `Fecha del despliegue`, `Estado del despliegue`, `Estado de la conversación`, `Estado de la sesión`, `última actividad`, `deployment_squad`, `hubspot_firstname`, `hubspot_mensaje_2`, `hubspot_treble_avances_emp_0`, `hubspot_transferir_asesor`.")

if df is None:
    st.info("Carga un archivo para continuar. También puedes probar con el *sample_data.csv* del repo.")
    st.stop()

# Normaliza nombres de columnas eliminando espacios duplicados y manteniendo acentos
df.columns = [c.strip() for c in df.columns]

# Selección de columna de fecha (por si el export cambia)
candidate_date_cols = [
    "Fecha del despliegue", "fecha_del_despliegue", "fecha", "Fecha", "created_at", "timestamp", "última actividad", "ultima actividad", "ultima_actividad", "updated_at"
]
date_col = st.selectbox("Selecciona la columna de fecha", [c for c in df.columns if c in candidate_date_cols] or list(df.columns), index=0)

df[date_col] = coerce_datetime(df[date_col])
df = df[~df[date_col].isna()].copy()
if df.empty:
    st.error("No hay filas con fecha válida. Revisa el archivo/columna seleccionada.")
    st.stop()

# Añade columnas auxiliares
df["_year"] = df[date_col].dt.year
df["_month_num"] = df[date_col].dt.month
df["_month"] = month_label(df[date_col])

# Dropdowns dinámicos
years_sorted = sorted(df["_year"].unique().tolist(), reverse=True)
selected_year = st.selectbox("Año", years_sorted, index=0)
months = sorted(df.loc[df["_year"] == selected_year, "_month_num"].unique().tolist())
month_names = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
month_display = [f"{m:02d} - {month_names[m]}" for m in months]
selected_month_disp = st.selectbox("Mes", month_display, index=len(month_display)-1)
selected_month = int(selected_month_disp.split(" - ")[0])

selected_ym = f"{selected_year}-{selected_month:02d}"

# Qué columnas resumir (pre-seleccionadas)
default_cols = [
    col for col in [
        "Estado del despliegue",
        "Estado de la conversación",
        "Estado de la sesión",
        "deployment_squad",
        "hubspot_firstname",
        "hubspot_mensaje_2",
        "hubspot_treble_avances_emp_0",
        "hubspot_transferir_asesor"
    ] if col in df.columns
]
cols_to_summarize = st.multiselect("Columnas a resumir (conteos por valor)", options=list(df.columns), default=default_cols, help="Se calculará un conteo de filas por cada valor distinto en el mes seleccionado.")

# Resumen del mes seleccionado
month_df, total_registros, total_celulares, summaries = summarize_month(df, date_col, selected_ym, cols_to_summarize)

st.markdown(f"### 📅 Resumen — {selected_ym}")
k1, k2 = st.columns(2)
k1.metric("Registros (filas) en el mes", f"{total_registros:,}")
if total_celulares is not None:
    k2.metric("Celulares únicos en el mes", f"{total_celulares:,}")

st.dataframe(month_df, use_container_width=True, height=300)

# Sección: Conteos por columna
st.markdown("### 🔎 Conteos por columna (mes seleccionado)")
for c, tbl in summaries.items():
    st.subheader(c)
    st.dataframe(tbl, use_container_width=True)

# Exportables del resumen mensual
def to_excel_bytes(dfs_dict):
    import io
    from pandas import ExcelWriter
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, d in dfs_dict.items():
            d.to_excel(writer, sheet_name=name[:31], index=False)
    return output.getvalue()

export_tabs = st.tabs(["📄 CSVs", "📘 Excel"])
with export_tabs[0]:
    colA, colB = st.columns(2)
    colA.download_button("Descargar mes filtrado (CSV)", data=month_df.to_csv(index=False).encode("utf-8"), file_name=f"treble_mes_{selected_ym}.csv", mime="text/csv")
    # Exportar cada conteo
    zip_buf = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c, tbl in summaries.items():
            zf.writestr(f"conteo_{c}.csv", tbl.to_csv(index=False))
    st.download_button("Descargar conteos por columna (ZIP)", data=zip_buf.getvalue(), file_name=f"conteos_{selected_ym}.zip", mime="application/zip")

with export_tabs[1]:
    excel_bytes = to_excel_bytes({"registros_mes": month_df} | {f"conteo_{c}": t for c, t in summaries.items()})
    st.download_button("Descargar resumen mensual (Excel)", data=excel_bytes, file_name=f"resumen_{selected_ym}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Tendencias mensuales (MoM)
st.markdown("---")
st.markdown("### 📈 Tendencias por mes (toda la base)")
totals, unique_by_month, trends = monthly_trends(df, date_col, cols_to_summarize)

c1, c2 = st.columns(2)
c1.bar_chart(totals.rename("Registros por mes"))
if unique_by_month is not None:
    c2.line_chart(unique_by_month.rename("Celulares únicos por mes"))

st.markdown("#### Pivot por columna (Mes × Valor)")
for c, pivot in trends.items():
    st.subheader(c)
    st.dataframe(pivot, use_container_width=True)

# Filtros opcionales
with st.expander("🧰 Filtros opcionales (avanzado)"):
    # Permitir filtro por deployment_squad o estados, si existen
    filter_cols = [c for c in ["deployment_squad", "Estado del despliegue", "Estado de la conversación", "Estado de la sesión"] if c in df.columns]
    active_filters = {}
    for c in filter_cols:
        choices = sorted(df[c].astype(str).unique().tolist())
        selected = st.multiselect(f"Filtrar {c}", options=choices, default=[])
        if selected:
            active_filters[c] = selected
    if active_filters:
        df_f = df.copy()
        for c, vals in active_filters.items():
            df_f = df_f[df_f[c].astype(str).isin(vals)]
        st.info(f"Filtrado activo en {len(active_filters)} columna(s).")
        st.dataframe(df_f, use_container_width=True, height=250)

st.caption("Hecho con ❤️ en Streamlit. Listo para desplegar en Streamlit Community Cloud.")
