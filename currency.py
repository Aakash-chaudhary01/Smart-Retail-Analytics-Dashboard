"""
currency.py
===========
Centralized currency configuration, conversion engine, and Indian number formatting (₹).
Supports Lakh (1,00,000) and Crore (1,00,00,000) compact representations.
"""

from __future__ import annotations
import math
from typing import Optional, Union, Tuple, List
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Currency Configuration
# ---------------------------------------------------------------------------
BASE_CURRENCY = "INR"
CURRENCY_SYMBOL = "₹"

# Single editable constant for USD to INR conversion rate (no live API)
USD_TO_INR_RATE = 83.50

# List of known monetary columns to convert
MONETARY_COLUMNS = [
    "total_sales",
    "net_revenue",
    "est_profit",
    "est_unit_cost",
    "unit_price",
    "discount_amount",
    "shipping_cost",
    "profit",
    "sales",
    "revenue",
    "cost",
]

# Non-monetary columns that must NEVER be converted
NON_MONETARY_COLUMNS = [
    "quantity",
    "order_id",
    "customer_id",
    "discount_pct",
    "margin_pct",
    "growth_3m_pct",
    "trend_slope_pct",
    "forecast_growth_pct",
    "volatility_cv",
    "health_score",
    "return_rate_pct",
    "replace_rate_pct",
    "cancel_rate_pct",
    "current_stock",
    "reorder_point",
    "lead_time_days",
    "recent_loss_months",
    "days_since_prev_order",
    "customer_total_orders",
]

# ---------------------------------------------------------------------------
# Formatting Engine: Indian Number System
# ---------------------------------------------------------------------------
def _format_indian_integer(n: int) -> str:
    """Format an integer using Indian numbering grouping: 12,34,567."""
    s = str(abs(n))
    if len(s) <= 3:
        return s
    last3 = s[-3:]
    remaining = s[:-3]
    parts = []
    while len(remaining) > 2:
        parts.append(remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        parts.append(remaining)
    parts.reverse()
    return ",".join(parts) + "," + last3

def format_inr(val: Optional[Union[float, int]], decimals: int = 2, show_symbol: bool = True) -> str:
    """
    Format a numeric amount with Indian digit grouping (e.g., ₹1,25,000 / ₹12,50,000.00).
    Properly handles negatives (-₹1,25,000.00) and zero (₹0.00).
    """
    if val is None or (isinstance(val, (float, np.floating)) and (np.isnan(val) or np.isinf(val))):
        return f"{CURRENCY_SYMBOL}0.00" if show_symbol else "0.00"

    num = float(val)
    is_neg = num < 0
    abs_num = abs(num)

    rounded_num = round(abs_num, decimals)
    int_part = int(math.floor(rounded_num)) if decimals == 0 else int(math.floor(abs_num))
    formatted_int = _format_indian_integer(int_part)

    if decimals > 0:
        dec_fmt = f"{abs_num:.{decimals}f}"
        dec_part = dec_fmt.split(".")[1] if "." in dec_fmt else "0" * decimals
        formatted_str = f"{formatted_int}.{dec_part}"
    else:
        formatted_str = formatted_int

    prefix = f"{CURRENCY_SYMBOL}" if show_symbol else ""
    if is_neg:
        return f"-{prefix}{formatted_str}"
    return f"{prefix}{formatted_str}"

def format_inr_compact(val: Optional[Union[float, int]], decimals: int = 2, show_symbol: bool = True) -> str:
    """
    Compact Indian currency formatting for cards and chart axes:
    - >= 1,00,00,000: ₹X.XX Cr (Crore)
    - >= 1,00,000: ₹X.XX Lakh
    - >= 1,000: ₹X,XXX
    """
    if val is None or (isinstance(val, (float, np.floating)) and (np.isnan(val) or np.isinf(val))):
        return f"{CURRENCY_SYMBOL}0" if show_symbol else "0"

    num = float(val)
    if num == 0:
        return f"{CURRENCY_SYMBOL}0" if show_symbol else "0"

    is_neg = num < 0
    abs_num = abs(num)
    prefix = f"{CURRENCY_SYMBOL}" if show_symbol else ""
    sign = "-" if is_neg else ""

    if abs_num >= 10_000_000:  # 1 Crore = 10 Million
        val_cr = abs_num / 10_000_000.0
        return f"{sign}{prefix}{val_cr:.{decimals}f} Cr"
    elif abs_num >= 100_000:   # 1 Lakh = 100 Thousand
        val_lakh = abs_num / 100_000.0
        return f"{sign}{prefix}{val_lakh:.{decimals}f} Lakh"
    elif abs_num >= 1_000:
        return format_inr(val, decimals=0 if decimals == 0 else 2, show_symbol=show_symbol)
    else:
        return format_inr(val, decimals=decimals, show_symbol=show_symbol)

def get_inr_ticks(max_val: float, num_ticks: int = 5) -> Tuple[List[float], List[str]]:
    """
    Generates clean tick values and Indian-formatted tick text (Lakh / Crore)
    for Plotly axes to avoid US-centric standard formatting.
    """
    if max_val <= 0:
        return [0.0], [f"{CURRENCY_SYMBOL}0"]

    # Pick scale step based on magnitude
    if max_val >= 10_000_000:
        raw_step = max_val / num_ticks
        # Round step to nearest 50 Lakh or 1 Crore
        step = max(5_000_000.0, round(raw_step / 5_000_000.0) * 5_000_000.0)
    elif max_val >= 100_000:
        raw_step = max_val / num_ticks
        step = max(100_000.0, round(raw_step / 100_000.0) * 100_000.0)
    else:
        raw_step = max_val / num_ticks
        step = max(1_000.0, round(raw_step / 1_000.0) * 1_000.0)

    tickvals = []
    curr = 0.0
    while curr <= max_val * 1.15:
        tickvals.append(curr)
        curr += step

    ticktext = [format_inr_compact(v, decimals=1 if v >= 100_000 else 0) for v in tickvals]
    return tickvals, ticktext

# ---------------------------------------------------------------------------
# Conversion Engine
# ---------------------------------------------------------------------------
def convert_amount(
    amount: Union[float, int, pd.Series, np.ndarray],
    from_currency: str = "USD",
    to_currency: str = "INR",
    rate: float = USD_TO_INR_RATE
) -> Union[float, pd.Series, np.ndarray]:
    """Convert a scalar or vector amount between USD and INR."""
    from_c = from_currency.upper().strip()
    to_c = to_currency.upper().strip()

    if from_c == to_c:
        return amount

    if from_c == "USD" and to_c == "INR":
        return amount * rate
    elif from_c == "INR" and to_c == "USD":
        return amount / rate
    return amount

def detect_dataset_currency(df: pd.DataFrame) -> Optional[str]:
    """
    Detect the currency of the dataset from column headers or contents.
    Returns 'INR', 'USD', or None (if indeterminate).
    """
    if df.empty:
        return None

    # 1. Check for dedicated currency column
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if col_clean in ["currency", "curr"]:
            vals = df[col].dropna().astype(str).str.upper()
            if not vals.empty:
                if (vals == "INR").sum() > (vals == "USD").sum():
                    return "INR"
                elif (vals == "USD").sum() > 0:
                    return "USD"

    # 2. Check for currency symbols in column headers
    for col in df.columns:
        c_str = str(col)
        if "₹" in c_str or "(inr)" in c_str.lower():
            return "INR"
        if "$" in c_str or "(usd)" in c_str.lower():
            return "USD"

    # 3. Check text samples in string columns
    for col in df.select_dtypes(include=["object"]).columns:
        sample = df[col].dropna().astype(str).head(100)
        has_rupee = sample.str.contains("₹|INR", regex=True, case=False).sum()
        has_dollar = sample.str.contains(r"\$|USD", regex=True, case=False).sum()
        if has_rupee > 5:
            return "INR"
        if has_dollar > 5:
            return "USD"

    return None

def convert_dataframe_currency(
    df: pd.DataFrame,
    from_currency: str,
    to_currency: str = "INR",
    rate: float = USD_TO_INR_RATE
) -> pd.DataFrame:
    """
    Converts every monetary column in the DataFrame exactly once.
    Leaves original unchanged and does not convert quantities, counts, or ratios.
    """
    if from_currency == to_currency or rate == 1.0:
        return df.copy()

    df_converted = df.copy()

    for col in df_converted.columns:
        col_lower = str(col).lower().strip()
        if col_lower in NON_MONETARY_COLUMNS:
            continue
        if any(m in col_lower for m in ["sales", "revenue", "profit", "price", "unit_cost"]):
            if pd.api.types.is_numeric_dtype(df_converted[col]):
                df_converted[col] = convert_amount(df_converted[col], from_currency, to_currency, rate)

    return df_converted
