# Lector de Vouchers IZIPAY - Caffeto

App en Streamlit para subir vouchers PDF de IZIPAY, extraer datos clave y exportar a Excel.

## Funcionalidades

- Carga múltiple de PDFs desde el navegador.
- Permite agregar más PDFs durante la misma sesión.
- Evita duplicados usando el ID del voucher.
- Extrae Fecha, Hora, Monto, Propina, Total, ID, Tipo, Medio, REF, AP, Lote y Terminal.
- Filtra por año, mes y medio.
- Calcula totales.
- Exporta a Excel.

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue en Streamlit Cloud

- Repository: `mioqui/app_izipay_caffeto`
- Branch: `main`
- Main file path: `app.py`
