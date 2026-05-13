from io import BytesIO

import pandas as pd
import streamlit as st

from parser_izipay import parse_izipay_uploaded_file

st.set_page_config(page_title="Izipay Caffeto - Lector de Vouchers", layout="wide")

st.title("Lector de Vouchers IZIPAY - Caffeto")
st.caption("Sube vouchers PDF, extrae Fecha, Hora, Monto, Propina, Total, ID y Tipo, y exporta a Excel.")

SHOW_COLS = ["Fecha", "Hora", "Monto", "Propina", "Total", "ID", "Tipo", "Medio", "Billetera", "REF", "AP", "Lote", "Term", "Archivo"]

if "rows" not in st.session_state:
    st.session_state.rows = []
if "processed_keys" not in st.session_state:
    st.session_state.processed_keys = set()

with st.sidebar:
    st.header("Carga de PDFs")
    st.write("Sube uno o varios vouchers PDF. Puedes volver a cargar más archivos y se agregarán a la lista de la sesión.")
    uploaded_files = st.file_uploader(
        "Subir vouchers PDF",
        type=["pdf"],
        accept_multiple_files=True,
        help="Selecciona uno o varios PDFs de IZIPAY."
    )

    process = st.button("Procesar PDFs cargados", type="primary")
    clear = st.button("Limpiar sesión")

    st.divider()
    st.caption("Nota: en Streamlit Cloud los datos permanecen durante la sesión. Para guardar el histórico permanente, descarga el Excel.")

if clear:
    st.session_state.rows = []
    st.session_state.processed_keys = set()
    st.success("Sesión limpiada.")

if process:
    if not uploaded_files:
        st.warning("Primero sube uno o varios PDFs.")
    else:
        nuevos = 0
        duplicados = 0
        errores = 0
        for uploaded_file in uploaded_files:
            try:
                uploaded_file.seek(0)
                row = parse_izipay_uploaded_file(uploaded_file)

                # Llave para evitar duplicados. Preferimos ID; si no existe, usamos archivo + fecha + hora + total.
                key = row.get("ID") or f"{row.get('Archivo')}|{row.get('Fecha')}|{row.get('Hora')}|{row.get('Total')}"
                if key in st.session_state.processed_keys:
                    duplicados += 1
                    continue

                st.session_state.rows.append(row)
                st.session_state.processed_keys.add(key)
                nuevos += 1
            except Exception as exc:
                errores += 1
                st.session_state.rows.append({
                    "Fecha": None, "Hora": None, "Monto": None, "Propina": None, "Total": None,
                    "ID": None, "Tipo": None, "Medio": None, "Billetera": None, "REF": None, "AP": None,
                    "Lote": None, "Term": None, "Archivo": uploaded_file.name, "Ruta": None, "Error": str(exc),
                })
        st.success(f"Procesamiento terminado: {nuevos} nuevos, {duplicados} duplicados omitidos, {errores} errores.")

if not st.session_state.rows:
    st.info("Sube tus vouchers PDF desde el panel izquierdo y presiona 'Procesar PDFs cargados'.")
    st.stop()

df = pd.DataFrame(st.session_state.rows)
for col in SHOW_COLS:
    if col not in df.columns:
        df[col] = None

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

filtered = filtered.sort_values(["Fecha_dt", "Hora", "Archivo"], na_position="last")

monto_total = pd.to_numeric(filtered["Monto"], errors="coerce").fillna(0).sum()
propina_total = pd.to_numeric(filtered["Propina"], errors="coerce").fillna(0).sum()
total_total = pd.to_numeric(filtered["Total"], errors="coerce").fillna(0).sum()
n_ops = len(filtered)

k1, k2, k3, k4 = st.columns(4)
k1.metric("N° operaciones", f"{n_ops:,}")
k2.metric("Monto", f"S/ {monto_total:,.2f}")
k3.metric("Propina", f"S/ {propina_total:,.2f}")
k4.metric("Total", f"S/ {total_total:,.2f}")

st.subheader("Detalle de vouchers")
st.dataframe(filtered[SHOW_COLS], use_container_width=True, hide_index=True)

output = BytesIO()
export_df = filtered[SHOW_COLS].copy()
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

if "Error" in filtered.columns and filtered["Error"].notna().any():
    with st.expander("Ver errores de lectura"):
        st.dataframe(filtered[filtered["Error"].notna()][["Archivo", "Error"]], use_container_width=True, hide_index=True)
