"""
utils.py
========
Shared utility functions for formatting, data exports (CSV, Excel, PDF),
and UI components with Indian Rupee (INR - ₹) number formatting.
"""

from __future__ import annotations
import io
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from config import get_logger
from currency import (
    BASE_CURRENCY,
    CURRENCY_SYMBOL,
    USD_TO_INR_RATE,
    format_inr,
    format_inr_compact,
    MONETARY_COLUMNS,
)

logger = get_logger("utils")

# ---------------------------------------------------------------------------
# Numerical & String Formatters
# ---------------------------------------------------------------------------
def format_currency(val: Optional[float], decimals: int = 2, compact: bool = False) -> str:
    """Format a number as INR (₹) currency with Indian digit grouping or compact notation."""
    if compact:
        return format_inr_compact(val, decimals=decimals)
    return format_inr(val, decimals=decimals)

def format_percentage(val: Optional[float], decimals: int = 1) -> str:
    """Format a ratio or percentage number."""
    if val is None or pd.isna(val):
        return "0.0%"
    return f"{val:.{decimals}f}%"

def format_number(val: Optional[int | float], decimals: int = 0) -> str:
    """Format general integers or counts using Indian number grouping."""
    if val is None or pd.isna(val):
        return "0"
    num = float(val)
    if decimals == 0:
        return format_inr(int(round(num)), decimals=0, show_symbol=False)
    return format_inr(num, decimals=decimals, show_symbol=False)

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
def _add_inr_to_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renames monetary columns to include '(INR)' in headers while keeping numbers numeric."""
    df_out = df.copy()
    rename_dict = {}
    for col in df_out.columns:
        col_lower = str(col).lower().strip()
        if any(m in col_lower for m in ["sales", "revenue", "profit", "price", "unit_cost"]):
            if "(inr)" not in col_lower and "₹" not in col_lower:
                rename_dict[col] = f"{col} (INR)"
    if rename_dict:
        df_out = df_out.rename(columns=rename_dict)
    return df_out

def to_csv_bytes(
    df: pd.DataFrame,
    rate: float = USD_TO_INR_RATE,
    original_currency: str = "USD"
) -> bytes:
    """
    Convert a DataFrame to CSV bytes with numeric values kept intact,
    '(INR)' appended to monetary column headers, and a metadata header note.
    """
    df_export = _add_inr_to_columns(df)
    csv_str = df_export.to_csv(index=False)
    # Prepend an audit comment line documenting currency and conversion rate
    header_comment = f"# Currency: INR (₹) | Source Currency: {original_currency} | Conversion Rate: 1 USD = ₹{rate:.2f}\n"
    return (header_comment + csv_str).encode("utf-8")

def to_excel_bytes(
    sheets: Dict[str, pd.DataFrame],
    rate: float = USD_TO_INR_RATE,
    original_currency: str = "USD"
) -> bytes:
    """
    Convert multiple DataFrames into a single multi-tab Excel file.
    Applies Indian currency format to monetary columns and appends '(INR)' in headers.
    Adds a dedicated 'Audit & Currency Notes' sheet documenting conversion parameters.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df_sheet in sheets.items():
            clean_sheet = _add_inr_to_columns(df_sheet)
            # Clean tz-aware or incompatible objects
            for col in clean_sheet.columns:
                if pd.api.types.is_datetime64_any_dtype(clean_sheet[col]):
                    clean_sheet[col] = clean_sheet[col].astype(str)
            clean_sheet.to_excel(writer, sheet_name=sheet_name[:31], index=False)

            # Apply Indian-style Excel number format to numeric monetary columns
            ws = writer.sheets[sheet_name[:31]]
            # Excel Indian currency format pattern:
            # [>=10000000]₹##\,##\,##\,##0.00;[>=100000]₹##\,##\,##0.00;₹##,##0.00
            inr_excel_format = "[>=10000000]₹##\\,##\\,##\\,##0.00;[>=100000]₹##\\,##\\,##0.00;₹##,##0.00"

            for col_idx, col_name in enumerate(clean_sheet.columns, 1):
                if "(INR)" in str(col_name):
                    for row_idx in range(2, len(clean_sheet) + 2):
                        cell = ws.cell(row=row_idx, column=col_idx)
                        if isinstance(cell.value, (int, float)):
                            cell.number_format = inr_excel_format

        # Add Audit Notes sheet
        notes_df = pd.DataFrame({
            "Parameter": [
                "Base / Reporting Currency",
                "Currency Symbol",
                "Source Dataset Currency",
                "Applied USD to INR Rate",
                "Monetary Column Status",
                "Indian Number Grouping Rule"
            ],
            "Value": [
                "INR",
                "₹",
                original_currency,
                f"1 USD = ₹{rate:.2f}",
                "Headers suffixed with (INR), numbers preserved as unrounded numeric floats",
                "First 3 digits from right, then grouped in pairs of 2 digits (Lakhs & Crores)"
            ]
        })
        notes_df.to_excel(writer, sheet_name="Currency & Notes", index=False)

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

        # Replace Rupee symbol with 'Rs. ' for standard Helvetica/Latin-1 PDF font compatibility
        clean_text = report_text.replace("₹", "Rs. ")
        clean_text = clean_text.encode("latin-1", "replace").decode("latin-1")
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
# Blank CSV Upload Template Generator (INR Updated)
# ---------------------------------------------------------------------------
def generate_blank_template(currency: str = "INR", rate: float = USD_TO_INR_RATE) -> pd.DataFrame:
    """Return a template dataframe with INR values and expected headers."""
    unit_p = round(999.00 * rate, 2) if currency == "INR" else 999.00
    sales_v = round(1898.10 * rate, 2) if currency == "INR" else 1898.10
    profit_v = round(698.10 * rate, 2) if currency == "INR" else 698.10

    data = {
        "order_id": ["ORD-1001"],
        "order_date": ["2024-01-15"],
        "product": ["Laptop"],
        "category": ["Computers & Peripherals"],
        "quantity": [2],
        f"unit_price ({currency})": [unit_p],
        "discount_pct": [0.05],
        f"total_sales ({currency})": [sales_v],
        "order_status": ["Delivered"],
        "customer_id": ["CPH-0001"],
        "channel": ["Online Store"],
        "region": ["East"],
        f"est_profit ({currency})": [profit_v],
    }
    return pd.DataFrame(data)
