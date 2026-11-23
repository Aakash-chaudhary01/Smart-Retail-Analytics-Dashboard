"""
tests/test_currency.py
======================
Unit tests for INR currency conversion, Indian digit grouping, and compact Lakh/Crore notation.
"""

import pytest
import pandas as pd
from currency import (
    format_inr,
    format_inr_compact,
    convert_amount,
    detect_dataset_currency,
    convert_dataframe_currency,
    USD_TO_INR_RATE,
)

def test_format_inr_grouping():
    # Basic Indian number groupings
    assert format_inr(125000) == "₹1,25,000.00"
    assert format_inr(1250000) == "₹12,50,000.00"
    assert format_inr(12500000) == "₹1,25,00,000.00"
    assert format_inr(0) == "₹0.00"
    assert format_inr(-125000) == "-₹1,25,000.00"
    assert format_inr(999) == "₹999.00"
    assert format_inr(1000) == "₹1,000.00"
    assert format_inr(1234567.89, decimals=2) == "₹12,34,567.89"
    assert format_inr(125000, decimals=0) == "₹1,25,000"

def test_format_inr_compact():
    # Compact Lakh and Crore notation
    assert format_inr_compact(125000) == "₹1.25 Lakh"
    assert format_inr_compact(12500000) == "₹1.25 Cr"
    assert format_inr_compact(0) == "₹0"
    assert format_inr_compact(-12500000) == "-₹1.25 Cr"
    assert format_inr_compact(-125000) == "-₹1.25 Lakh"
    assert format_inr_compact(500) == "₹500.00"

def test_convert_amount():
    rate = 80.0
    usd_val = 100.0
    inr_val = convert_amount(usd_val, "USD", "INR", rate=rate)
    assert inr_val == 8000.0
    back_to_usd = convert_amount(inr_val, "INR", "USD", rate=rate)
    assert back_to_usd == 100.0

def test_convert_dataframe_monetary_columns():
    df = pd.DataFrame({
        "order_id": ["ORD1"],
        "quantity": [5],
        "total_sales": [100.0],
        "net_revenue": [100.0],
        "est_profit": [30.0],
        "unit_price": [20.0],
        "discount_pct": [0.10],
    })
    rate = 83.5
    converted = convert_dataframe_currency(df, from_currency="USD", to_currency="INR", rate=rate)

    # Monetary columns must be scaled by rate
    assert converted["total_sales"].iloc[0] == 100.0 * rate
    assert converted["net_revenue"].iloc[0] == 100.0 * rate
    assert converted["est_profit"].iloc[0] == 30.0 * rate
    assert converted["unit_price"].iloc[0] == 20.0 * rate

    # Non-monetary columns must NOT be scaled
    assert converted["quantity"].iloc[0] == 5
    assert converted["discount_pct"].iloc[0] == 0.10
    assert converted["order_id"].iloc[0] == "ORD1"

def test_detect_dataset_currency():
    df_usd = pd.DataFrame({"total_sales (USD)": [100, 200]})
    assert detect_dataset_currency(df_usd) == "USD"

    df_inr = pd.DataFrame({"total_sales (INR)": [8000, 16000]})
    assert detect_dataset_currency(df_inr) == "INR"

    df_unknown = pd.DataFrame({"total_sales": [100, 200]})
    assert detect_dataset_currency(df_unknown) is None
