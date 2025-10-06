
import io
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

st.set_page_config(page_title="Resumen mensual Treble.ai", page_icon="📊", layout="wide")

# ------------- Utilidades -------------

@st.cache_data
def load_csv(file_bytes, sep=None, encoding="utf-8"):
    return pd.read_csv(io.BytesIO(file_bytes), sep=sep or None, engine="python", encoding=encoding)

def try_fix_mojibake_df(df):
    import unicodedata
    def fix_text(x):
        if not isinstance(x, str):
            return x
        try:
            # typical mojibake fix: text was UTF-8 decoded as latin1 -> re-encode latin1, decode utf-8
            return x.encode("latin1").decode("utf-8")
        except Exception:
            return x
    # fix column names
    df = df.rename(columns={c: fix_text(c) for c in df.columns})
    # fix string cells (best-effort)
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = df[c].astype(str).map(fix_text)
    return df

def normalize_str_series(s):
    import unicodedata
    def norm(x):
        if not isinstance(x, str):
            x = "" if pd.isna(x) else str(x)
        x = unicodedata.normalize("NFKD", x)
        x = "".join(ch for ch in x if not unicodedata.combining(ch))
        return x.casefold().strip()
    return s.astype(str).map(norm)

@st.cache_data
def load_excel(file_bytes):
    return pd.read_excel(io.BytesIO(file_bytes))

def coerce_datetime(series):
    return pd.to_datetime(series, errors="coerce", utc=False, dayfirst=True, infer_datetime_format=True)

def month_label(dt_series):
    return pd.to_datetime(dt_series).dt.strftime("%Y-%m")

def pct(n, d):
    return (n / d * 100.0) if (d is not None and d != 0) else np.nan

def trend_arrow(curr, prev):
    if pd.isna(curr) or pd.isna(prev):
        return "➡"
    if curr > prev:
        return "⬆"
    if curr < prev:
        return "⬇"
    return "➡"

def fmt_int(x):
    return f"{int(x):,}".replace(",", ".") if pd.notna(x) else ""

def fmt_pct(x):
    return f"{x:.1f}%" if pd.notna(x) else ""

# ------------- UI -------------
st.title("📊 Resumen mensual de base Treble.ai — con Panel KPI")


with st.expander("📥 Cargar datos", expanded=True):
    st.write("**Si ves acentos raros (Ã³, Ã±, etc.) usa 'latin1' o habilita 'Reparar acentos'.**")
    encoding_choice = st.selectbox("Codificación del archivo", ["utf-8", "latin1", "cp1252"], index=0)
    fix_mojibake = st.checkbox("Reparar acentos (mojibake típico UTF-8↔Latin1)", value=True)

    file = st.file_uploader("Sube un archivo CSV o XLSX", type=["csv", "xlsx"])
    
delimiter = st.selectbox("Delimitador", [",",";","\\t","|","(autodetect)"], index=4)
custom_delim = st.text_input("Delimitador personalizado (opcional)", value="")
chosen_sep = None if delimiter=="(autodetect)" and not custom_delim else (custom_delim if custom_delim else ("\t" if delimiter=="\\t" else delimiter))

    sheet_name = st.text_input("Nombre de hoja (XLSX, opcional)", value="")

    df = None
    if file is not None:
        try:
            if file.type.endswith("csv"):
                raw = file.read()
                df = load_csv(raw, sep=chosen_sep, encoding=encoding_choice)
                if fix_mojibake:
                    df = try_fix_mojibake_df(df)
            else:
                content = file.read()
                if sheet_name.strip():
                    df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name.strip())
                else:
                    df = load_excel(content)
                if fix_mojibake:
                    df = try_fix_mojibake_df(df)
        except Exception as e:
            st.error(f"Error leyendo el archivo: {e}")

    st.markdown("**Columnas esperadas (sugeridas):** `Celular`, `Fecha del despliegue`, `Estado del despliegue`, `Estado de la conversación`, `Estado de la sesión`, `última actividad`, `deployment_squad`, `hubspot_firstname`, `hubspot_mensaje_2`, `hubspot_treble_avances_emp_0`, `hubspot_transferir_asesor`.")

if df is None:
    st.info("Carga un archivo para continuar. También puedes probar con el *sample_data.csv* del repo.")
    st.stop()

df.columns = [c.strip() for c in df.columns]
# recortar espacios en celdas string
for c in df.columns:
    if df[c].dtype == "object":
        df[c] = df[c].astype(str).str.strip()


candidate_date_cols = [
    "Fecha del despliegue", "fecha_del_despliegue", "fecha", "Fecha", "created_at", "timestamp", "última actividad", "ultima actividad", "ultima_actividad", "updated_at"
]

date_col = st.selectbox("Selecciona la columna de fecha principal", [c for c in df.columns if c in candidate_date_cols] or list(df.columns), index=0)
fallback_date_col = st.selectbox("Columna de fecha de respaldo (opcional)", ["(ninguna)"] + list(df.columns), index=0)

date_parse_mode = st.radio("Formato de fecha", ["Auto (inferir)","Día primero (DD/MM/YYYY)","Mes primero (MM/DD/YYYY)","ISO (YYYY-MM-DD HH:mm:ss)"], horizontal=True)

def parse_dates(series, mode):
    s = series.astype(str).str.strip()
    if mode == "Día primero (DD/MM/YYYY)":
        return pd.to_datetime(s, errors="coerce", dayfirst=True, infer_datetime_format=True)
    if mode == "Mes primero (MM/DD/YYYY)":
        return pd.to_datetime(s, errors="coerce", dayfirst=False, infer_datetime_format=True)
    if mode == "ISO (YYYY-MM-DD HH:mm:ss)":
        return pd.to_datetime(s, errors="coerce", format="%Y-%m-%d %H:%M:%S")
    return pd.to_datetime(s, errors="coerce", infer_datetime_format=True, dayfirst=True)

df["_dt_main"] = parse_dates(df[date_col], date_parse_mode)
if fallback_date_col != "(ninguna)":
    df["_dt_fallback"] = parse_dates(df[fallback_date_col], date_parse_mode)
    df["_dt"] = df["_dt_main"].fillna(df["_dt_fallback"])
else:
    df["_dt"] = df["_dt_main"]



invalid_dates = df["_dt"].isna().sum()
total_rows_loaded = len(df)
if invalid_dates > 0:
    st.warning(f"Se cargarón {total_rows_loaded} filas; **{invalid_dates}** no tienen fecha válida y serán excluidas del resumen. Revisa el delimitador/formato de fecha.")

df_valid = df[~df["_dt"].isna()].copy()
if df_valid.empty:
    st.error("No hay filas con fecha válida. Ajusta delimitador o formato de fecha.")
    st.stop()

df_valid["_month"] = pd.to_datetime(df_valid["_dt"]).dt.strftime("%Y-%m")
df = df_valid


# ======= Sección existente: Resumen por mes (filtrado rápido) =======
st.markdown("## 📅 Resumen mensual (filtrado por Año/Mes)")
years_sorted = sorted(pd.to_datetime(df[date_col]).dt.year.unique().tolist(), reverse=True)
selected_year = st.selectbox("Año", years_sorted, index=0)
months = sorted(pd.to_datetime(df[df[date_col].dt.year == selected_year][date_col]).dt.month.unique().tolist())
month_names = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
month_display = [f"{m:02d} - {month_names[m]}" for m in months]
selected_month_disp = st.selectbox("Mes", month_display, index=len(month_display)-1)
selected_month = int(selected_month_disp.split(" - ")[0])
selected_ym = f"{selected_year}-{selected_month:02d}"

# Columnas a resumir (conteo por valor)
default_cols = [c for c in [
    "Estado del despliegue","Estado de la conversación","Estado de la sesión",
    "deployment_squad","hubspot_firstname","hubspot_mensaje_2",
    "hubspot_treble_avances_emp_0","hubspot_transferir_asesor"
] if c in df.columns]
cols_to_summarize = st.multiselect("Columnas a resumir (conteos por valor)", options=list(df.columns), default=default_cols)

month_df = df[df["_month"] == selected_ym].copy()
total_registros = len(month_df)
total_celulares = month_df["Celular"].nunique() if "Celular" in month_df.columns else None

k1, k2 = st.columns(2)
k1.metric("Registros (filas) en el mes", f"{total_registros:,}")
if total_celulares is not None:
    k2.metric("Celulares únicos en el mes", f"{total_celulares:,}")

st.dataframe(month_df, use_container_width=True, height=260)

st.markdown("### 🔎 Conteos por columna (mes seleccionado)")
for c in cols_to_summarize:
    if c in month_df.columns:
        tbl = (month_df.assign(**{c: month_df[c].astype(str).replace({"nan":"Sin dato"})})
                        .groupby(c).size().sort_values(ascending=False).rename("conteo").reset_index())
        st.subheader(c)
        st.dataframe(tbl, use_container_width=True)


with st.expander("🧪 Diagnóstico de carga", expanded=False):
    st.write(f"Filas cargadas: **{total_rows_loaded}**")
    st.write(f"Filas con fecha inválida: **{invalid_dates}**")
    st.write("Ejemplos de fechas no parseadas:")
    if invalid_dates > 0:
        bad_samples = (df[pd.isna(df["_dt"])][[date_col] + ([fallback_date_col] if fallback_date_col!="(ninguna)" else [])]
                       .head(10))
        st.dataframe(bad_samples, use_container_width=True)
    st.write("Distribución por mes detectado (todas las filas válidas):")
    st.dataframe(df["_month"].value_counts().sort_index().rename_axis("Mes").reset_index(name="Filas"), use_container_width=True)


st.markdown("---")

# ======= NUEVO: Panel KPI tipo “Envios/Entregas/Clics/Avance” =======
st.markdown("## 🧭 Panel KPI mensual (tipo '1 Envío - 30 Min')")

st.caption("Define cómo se calcula cada KPI: por **conteo de filas con un valor categórico** o por **suma de una columna numérica**.")

calc_mode = st.radio("Modo de cálculo de KPIs", ["Conteo por valor categórico", "Suma de columna numérica"], horizontal=True)

def kpi_selector(name):
    if calc_mode == "Conteo por valor categórico":
        col = st.selectbox(f"{name}: columna categórica", options=list(df.columns), key=f"cat_{name}")
        values = sorted(df[col].astype(str).unique().tolist())
        val = st.multiselect(f"{name}: valores que cuentan", options=values, key=f"vals_{name}")
        return {"mode": "count_by_value", "column": col, "values": val}
    else:
        col = st.selectbox(f"{name}: columna numérica (se sumará)", options=list(df.columns), key=f"num_{name}")
        return {"mode": "sum_numeric", "column": col}

colA, colB = st.columns(2)
with colA:
    rule_envios = kpi_selector("Envios")
    rule_entregas = kpi_selector("Entregas")
with colB:
    rule_clicks = kpi_selector("Clics")
    rule_avance = kpi_selector("Avance")

# Sugerencias de default si existen columnas típicas
suggested = False
if calc_mode == "Conteo por valor categórico":
    def try_set(rule, col_name, ok_vals):
        return {"mode":"count_by_value", "column": col_name, "values": ok_vals}
    if "Estado del despliegue" in df.columns and "ENVIADO" in df["Estado del despliegue"].astype(str).unique():
        rule_envios = try_set(rule_envios, "Estado del despliegue", ["ENVIADO"]); suggested=True
    if "Estado del despliegue" in df.columns and "ENTREGADO" in df["Estado del despliegue"].astype(str).unique():
        rule_entregas = try_set(rule_entregas, "Estado del despliegue", ["ENTREGADO"]); suggested=True
    if "Estado de la conversación" in df.columns:
        vals = df["Estado de la conversación"].astype(str).unique().tolist()
        if any(v for v in vals if v.upper().startswith("CLICK")):
            rule_clicks = try_set(rule_clicks, "Estado de la conversación", [v for v in vals if v.upper().startswith("CLICK")]); suggested=True
    if "hubspot_treble_avances_emp_0" in df.columns:
        # asumir que valores distintos a "0" significan avance
        nonzero = [v for v in df["hubspot_treble_avances_emp_0"].astype(str).unique().tolist() if str(v) not in ["0","nan",""]]
        if nonzero:
            rule_avance = try_set(rule_avance, "hubspot_treble_avances_emp_0", nonzero); suggested=True

if suggested:
    st.info("Se pre-cargaron reglas sugeridas con base en los nombres de columnas detectados. Ajusta si es necesario.")


def apply_rule(group_df, rule):
    if rule["mode"] == "count_by_value":
        col = rule["column"]
        vals = [str(v) for v in rule.get("values", [])]
        if col not in group_df.columns or len(vals) == 0:
            return np.nan
        # normalize both sides (case/accents tolerant and robust to mojibake)
        left = normalize_str_series(group_df[col])
        right = [v for v in normalize_str_series(pd.Series(vals)).tolist()]
        return left.isin(right).sum()
    else:
        col = rule["column"]
        if col not in group_df.columns:
            return np.nan
        return pd.to_numeric(group_df[col], errors="coerce").fillna(0).sum()

# Agregación mensual
kpi_months = []
for ym, g in df.groupby("_month"):
    env = apply_rule(g, rule_envios)
    ent = apply_rule(g, rule_entregas)
    clk = apply_rule(g, rule_clicks)
    av = apply_rule(g, rule_avance)
    paso = pct(av, clk)
    ent_vs_av = pct(av, ent)
    kpi_months.append({"Mes": ym, "Envios": env, "Entregas": ent, "Clics": clk, "Avance": av,
                       "Paso Perfilamiento (%)": paso, "Entregas vs Avance (%)": ent_vs_av})

kpi_df = pd.DataFrame(kpi_months).sort_values("Mes")

# Tabla formateada con flechas MoM
disp_rows = []
prev = None
for _, r in kpi_df.iterrows():
    row = {"Mes": r["Mes"]}
    for key in ["Envios","Entregas","Clics","Avance"]:
        arrow = trend_arrow(r[key], (prev[key] if prev is not None else np.nan))
        row[key] = f"{fmt_int(r[key])} {arrow}".strip()
    for key in ["Paso Perfilamiento (%)","Entregas vs Avance (%)"]:
        arrow = trend_arrow(r[key], (prev[key] if prev is not None else np.nan))
        row[key] = f"{fmt_pct(r[key])} {arrow}".strip()
    disp_rows.append(row)
    prev = r

disp_df = pd.DataFrame(disp_rows)

st.markdown("### Panel KPI mensual")
st.dataframe(disp_df.rename(columns={
    "Paso Perfilamiento (%)":"Paso Perfilamiento",
    "Entregas vs Avance (%)":"Entregas vs Avance"
}), use_container_width=True)

# Descargas
col1, col2 = st.columns(2)
col1.download_button("⬇ Descargar KPI (crudo, CSV)", data=kpi_df.to_csv(index=False).encode("utf-8"),
                     file_name="kpi_mensual_crudo.csv", mime="text/csv")
col2.download_button("⬇ Descargar KPI (formateado, CSV)", data=disp_df.to_csv(index=False).encode("utf-8"),
                     file_name="kpi_mensual_formateado.csv", mime="text/csv")

st.caption("Configura las reglas según tu export real (valores/columnas). Si necesitas reglas compuestas (ej. múltiples columnas/condiciones), dímelo y lo extiendo.")
