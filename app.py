from pathlib import Path
from io import BytesIO

import pandas as pd
import streamlit as st

from parser_izipay import read_folder

st.set_page_config(page_title="Izipay Caffeto - Lector de Vouchers", layout="wide")

st.title("Lector de Vouchers IZIPAY - Caffeto")
st.caption("Lee PDFs desde una carpeta, extrae Fecha, Hora, Monto, Propina, Total, ID y Tipo, y exporta a Excel.")

with st.sidebar:
    st.header("Configuración")
    folder_default = str(Path.cwd() / "pdfs")
    folder_path = st.text_input("Carpeta de PDFs", value=folder_default)
    st.caption("Ejemplo Windows: C:\\Users\\Usuario\\Desktop\\izipay_pdfs")
    st.caption("Ejemplo Mac: /Users/usuario/Desktop/izipay_pdfs")
    refresh = st.button("Actualizar lectura", type="primary")

@st.cache_data(show_spinner=False)
def load_data(path: str, cache_buster: int):
    return read_folder(path)

# Cache buster simple: cambia cada vez que se presiona Actualizar.
if "refresh_counter" not in st.session_state:
    st.session_state.refresh_counter = 0
if refresh:
    st.session_state.refresh_counter += 1

df = load_data(folder_path, st.session_state.refresh_counter)

if df.empty:
    st.warning("No se encontraron PDFs en la carpeta indicada o la carpeta no existe.")
    st.stop()

# Preparar fecha para filtros.
df["Fecha_dt"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
df["Año"] = df["Fecha_dt"].dt.year
df["Mes"] = df["Fecha_dt"].dt.month

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    years = sorted([int(y) for y in df["Año"].dropna().unique()])
    selected_years = st.multiselect("Filtrar por año", years, default=years)
with col2:
    months = sorted([int(m) for m in df["Mes"].dropna().unique()])
    selected_months = st.multiselect("Filtrar por mes", months, default=months)
with col3:
    medios = sorted([m for m in df["Medio"].dropna().unique()])
    selected_medios = st.multiselect("Filtrar por medio", medios, default=medios)

filtered = df.copy()
if selected_years:
    filtered = filtered[filtered["Año"].isin(selected_years)]
if selected_months:
    filtered = filtered[filtered["Mes"].isin(selected_months)]
if selected_medios:
    filtered = filtered[filtered["Medio"].isin(selected_medios)]

# Ordenar por fecha y hora
filtered = filtered.sort_values(["Fecha_dt", "Hora", "Archivo"], na_position="last")

monto_total = filtered["Monto"].fillna(0).sum()
propina_total = filtered["Propina"].fillna(0).sum()
total_total = filtered["Total"].fillna(0).sum()
n_ops = len(filtered)

k1, k2, k3, k4 = st.columns(4)
k1.metric("N° operaciones", f"{n_ops:,}")
k2.metric("Monto", f"S/ {monto_total:,.2f}")
k3.metric("Propina", f"S/ {propina_total:,.2f}")
k4.metric("Total", f"S/ {total_total:,.2f}")

st.subheader("Detalle de vouchers")
show_cols = ["Fecha", "Hora", "Monto", "Propina", "Total", "ID", "Tipo", "Medio", "Billetera", "REF", "AP", "Lote", "Term", "Archivo"]
st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

# Exportar a Excel
output = BytesIO()
export_df = filtered[show_cols].copy()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    export_df.to_excel(writer, index=False, sheet_name="Ventas")
    resumen = pd.DataFrame({
        "Indicador": ["N° operaciones", "Monto", "Propina", "Total"],
        "Valor": [n_ops, monto_total, propina_total, total_total]
    })
    resumen.to_excel(writer, index=False, sheet_name="Resumen")

st.download_button(
    label="Exportar a Excel",
    data=output.getvalue(),
    file_name="ventas_izipay_caffeto.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.info("Para incorporar nuevos PDFs, copia los archivos a la carpeta y presiona 'Actualizar lectura'.")
