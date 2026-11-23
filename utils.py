"""
utils.py
========
Shared utility functions for formatting, data exports (CSV, Excel, PDF),
and UI components.
"""

from __future__ import annotations
import io
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from config import get_logger

logger = get_logger("utils")

# ---------------------------------------------------------------------------
# Numerical & String Formatters
# ---------------------------------------------------------------------------
def format_currency(val: Optional[float], decimals: int = 2) -> str:
    """Format a number as USD currency with commas."""
    if val is None or pd.isna(val):
        return "$0.00"
    if abs(val) >= 1_000_000:
        return f"${val / 1_000_000:.2f}M"
    if abs(val) >= 10_000:
        return f"${val / 1_000:.1f}k"
    return f"${val:,.{decimals}f}"

def format_percentage(val: Optional[float], decimals: int = 1) -> str:
    """Format a ratio or percentage number."""
    if val is None or pd.isna(val):
        return "0.0%"
    return f"{val:.{decimals}f}%"

def format_number(val: Optional[int | float], decimals: int = 0) -> str:
    """Format general integers or counts with thousands commas."""
    if val is None or pd.isna(val):
        return "0"
    if decimals == 0:
        return f"{int(val):,}"
    return f"{val:,.{decimals}f}"

def format_delta_arrow(val: Optional[float], suffix: str = "%") -> str:
    """Return a directional arrow and delta text."""
    if val is None or pd.isna(val):
        return "—"
    if val > 0:
        return f"↑ +{val:.1f}{suffix}"
    elif val < 0:
        return f"↓ {val:.1f}{suffix}"
    return f"→ 0.0{suffix}"

# ---------------------------------------------------------------------------
# Data Export Helpers (In-Memory Streams)
# ---------------------------------------------------------------------------
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Convert a DataFrame to CSV bytes for download."""
    return df.to_csv(index=False).encode("utf-8")

def to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    """Convert multiple DataFrames into a single multi-tab Excel file."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df_sheet in sheets.items():
            clean_sheet = df_sheet.copy()
            # Clean tz-aware or incompatible objects
            for col in clean_sheet.columns:
                if pd.api.types.is_datetime64_any_dtype(clean_sheet[col]):
                    clean_sheet[col] = clean_sheet[col].astype(str)
            clean_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()

def create_pdf_report(report_text: str, title: str = "Executive Sales & AI Insights Report") -> bytes:
    """Generate a clean PDF report using fpdf2 or fallback plain text buffer."""
    try:
        from fpdf import FPDF

        class PDF(FPDF):
            def header(self):
                self.set_font("Helvetica", "B", 14)
                self.cell(0, 10, title, border=False, align="C")
                self.ln(12)

            def footer(self):
                self.set_y(-15)
                self.set_font("Helvetica", "I", 8)
                self.cell(0, 10, f"Page {self.page_no()}", align="C")

        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)

        # Sanitize text for Latin-1/Helvetica encoding
        clean_text = report_text.encode("latin-1", "replace").decode("latin-1")
        for line in clean_text.split("\n"):
            if line.startswith("# "):
                pdf.set_font("Helvetica", "B", 13)
                pdf.cell(0, 8, line.replace("# ", ""), ln=True)
                pdf.set_font("Helvetica", size=10)
            elif line.startswith("## "):
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 7, line.replace("## ", ""), ln=True)
                pdf.set_font("Helvetica", size=10)
            else:
                pdf.multi_cell(0, 5, line)
                pdf.ln(1)

        output = pdf.output()
        if isinstance(output, (bytearray, memoryview)):
            return bytes(output)
        elif isinstance(output, str):
            return output.encode("latin-1")
        return bytes(output)
    except Exception as exc:
        logger.warning(f"FPDF generation encountered error ({exc}), falling back to text stream.")
        return report_text.encode("utf-8")

# ---------------------------------------------------------------------------
# Blank CSV Upload Template Generator
# ---------------------------------------------------------------------------
def generate_blank_template() -> pd.DataFrame:
    """Return a template dataframe with expected columns and one sample row."""
    data = {
        "order_id": ["ORD-1001"],
        "order_date": ["2024-01-15"],
        "product": ["Laptop"],
        "category": ["Computers & Peripherals"],
        "quantity": [2],
        "unit_price": [999.00],
        "discount_pct": [0.05],
        "total_sales": [1898.10],
        "order_status": ["Delivered"],
        "customer_id": ["CPH-0001"],
        "channel": ["Online Store"],
        "region": ["East"],
        "est_profit": [698.10],
    }
    return pd.DataFrame(data)

