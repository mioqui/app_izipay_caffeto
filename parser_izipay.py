import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

import pdfplumber
import pandas as pd

MONTHS_ES = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SET": "09", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12",
}

COLUMNS = [
    "Fecha", "Hora", "Monto", "Propina", "Total", "ID", "Tipo", "Medio", "Billetera",
    "REF", "AP", "Lote", "Term", "Archivo", "Ruta"
]


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """Extrae texto de un PDF digital. Si el PDF fuera imagen escaneada, esto puede devolver texto vacío."""
    parts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            parts.append(text)
    return "\n".join(parts)


def _search(pattern: str, text: str, flags: int = re.IGNORECASE) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _money(label: str, text: str) -> Optional[float]:
    # Soporta: TOTAL: S/ 34.00, TOTAL: S/34.00, TOTAL: S/ 1,234.50
    value = _search(rf"{label}\s*:\s*S\/?\s*([0-9,]+(?:\.[0-9]{{1,2}})?)", text)
    if value is None:
        return None
    return float(value.replace(",", ""))


def _format_fecha_l(fecha: Optional[str]) -> Optional[str]:
    # 08/03/26 -> 08/03/2026
    if not fecha:
        return None
    try:
        dt = datetime.strptime(fecha, "%d/%m/%y")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return fecha


def _parse_qr_date(text: str) -> tuple[Optional[str], Optional[str]]:
    # Ejemplo: 08MAR26 18:21
    m = re.search(r"(\d{2})([A-ZÁÉÍÓÚÑ]{3})(\d{2})\s+(\d{1,2}:\d{2})", text, re.IGNORECASE)
    if not m:
        return None, None
    day, mon_txt, year, hour = m.groups()
    mon = MONTHS_ES.get(mon_txt.upper().replace("Á", "A"))
    if not mon:
        return None, hour
    return f"{day}/{mon}/20{year}", hour


def parse_izipay_pdf(pdf_path: str | Path) -> Dict:
    pdf_path = Path(pdf_path)
    text = _extract_text_from_pdf(pdf_path)
    compact = re.sub(r"[ \t]+", " ", text)

    medio = _search(r"\*+\d+\((L|Q)\)", compact)

    # ID: en formato L suele aparecer arriba; en Q aparece al final.
    id_value = _search(r"ID\s*:\s*([A-Z0-9]+)", compact)

    ap = _search(r"AP\s*:\s*([A-Z0-9]+)", compact)
    ref = _search(r"REF\s*:\s*([A-Z0-9]+)", compact)
    lote = _search(r"LOTE\s*:\s*([A-Z0-9]+)", compact)
    term = _search(r"TERM\s*:\s*([A-Z0-9]+)", compact)

    tipo = _search(r"TIPO\s*:\s*([A-Z0-9]+)", compact)
    billetera = _search(r"BILLETERA\s*:\s*([^\n\r]+?)(?:\s+MOZO\s*:|\s+MONTO\s*:|$)", compact)

    fecha = _search(r"FECHA\s*:\s*(\d{2}/\d{2}/\d{2})", compact)
    hora = _search(r"HORA\s*:\s*(\d{1,2}:\d{2})", compact)
    fecha = _format_fecha_l(fecha)

    # QR suele traer fecha/hora como 08MAR26 18:21, sin etiquetas FECHA/HORA.
    if not fecha or not hora:
        fecha_q, hora_q = _parse_qr_date(compact)
        fecha = fecha or fecha_q
        hora = hora or hora_q

    monto = _money("MONTO", compact)
    propina = _money("PROPINA", compact)
    total = _money("TOTAL", compact)

    # Si no existe MONTO ni PROPINA, asumimos monto = total y propina = 0.
    if monto is None and total is not None:
        monto = total
    if propina is None:
        propina = 0.0

    return {
        "Fecha": fecha,
        "Hora": hora,
        "Monto": monto,
        "Propina": propina,
        "Total": total,
        "ID": id_value,
        "Tipo": tipo,
        "Medio": medio,
        "Billetera": billetera,
        "REF": ref,
        "AP": ap,
        "Lote": lote,
        "Term": term,
        "Archivo": pdf_path.name,
        "Ruta": str(pdf_path.resolve()),
    }


def read_folder(folder_path: str | Path) -> pd.DataFrame:
    folder = Path(folder_path).expanduser()
    rows = []
    if not folder.exists():
        return pd.DataFrame(columns=COLUMNS)

    for pdf in sorted(folder.glob("*.pdf")):
        try:
            row = parse_izipay_pdf(pdf)
            rows.append(row)
        except Exception as exc:
            rows.append({
                "Fecha": None, "Hora": None, "Monto": None, "Propina": None, "Total": None,
                "ID": None, "Tipo": None, "Medio": None, "Billetera": None, "REF": None, "AP": None,
                "Lote": None, "Term": None, "Archivo": pdf.name, "Ruta": str(pdf.resolve()),
                "Error": str(exc),
            })

    df = pd.DataFrame(rows)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df
