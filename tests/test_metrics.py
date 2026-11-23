"""
tests/test_metrics.py
=====================
Pytest suite verifying data pipeline calculations, revenue logic, customer lineage,
decision rules, and edge case resilience (zero division, empty series).
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from analysis import clean_and_derive_features, calculate_kpis, get_monthly_metrics
from customers import compute_customer_rfm, compute_cohort_retention, compute_customer_summary_stats
from decision_engine import evaluate_product_decisions
from upload import auto_detect_columns

@pytest.fixture
def sample_sales_data():
    """Provides a controlled synthetic DataFrame with known properties."""
    data = [
        # Customer 1: 1st purchase Jan 2024, 2nd purchase Feb 2024
        {"order_id": "O1", "order_date": "2024-01-10", "customer_id": "C01", "product": "Laptop", "quantity": 1, "total_sales": 1000.0, "order_status": "Delivered", "channel": "Online"},
        {"order_id": "O2", "order_date": "2024-02-15", "customer_id": "C01", "product": "Phone", "quantity": 1, "total_sales": 500.0, "order_status": "Delivered", "channel": "Online"},
        # Customer 2: 1st purchase Jan 2024 (Cancelled), 2nd purchase Jan 2024 (Delivered)
        {"order_id": "O3", "order_date": "2024-01-05", "customer_id": "C02", "product": "Chair", "quantity": 2, "total_sales": 400.0, "order_status": "Cancelled", "channel": "Retail"},
        {"order_id": "O4", "order_date": "2024-01-20", "customer_id": "C02", "product": "Chair", "quantity": 1, "total_sales": 200.0, "order_status": "Delivered", "channel": "Retail"},
        # Customer 3: 1 purchase in Jan 2024 (Returned)
        {"order_id": "O5", "order_date": "2024-01-25", "customer_id": "C03", "product": "Printer", "quantity": 1, "total_sales": 150.0, "order_status": "Returned", "channel": "Online"},
        # Customer 4: 1 purchase in Jan 2024 (Replaced)
        {"order_id": "O6", "order_date": "2024-01-28", "customer_id": "C04", "product": "Monitor", "quantity": 1, "total_sales": 300.0, "order_status": "Replaced", "channel": "Online"},
        # Walk-in: no customer_id
        {"order_id": "O7", "order_date": "2024-02-01", "customer_id": None, "product": "Laptop", "quantity": 1, "total_sales": 1000.0, "order_status": "Delivered", "channel": "Retail Store"},
    ]
    raw_df = pd.DataFrame(data)
    cleaned_df, _ = clean_and_derive_features(raw_df)
    return cleaned_df

def test_net_revenue_calculation(sample_sales_data):
    """
    Test Net Revenue Rule:
    net_revenue = total_sales for Delivered and Replaced, 0 for Returned and Cancelled.
    """
    df = sample_sales_data
    # Delivered (O1: 1000, O2: 500, O4: 200, O7: 1000) -> 2700
    # Replaced (O6: 300) -> 300
    # Returned (O5: 0)
    # Cancelled (O3: 0)
    # Total expected net_revenue = 3000.0
    assert df[df["order_id"] == "O1"]["net_revenue"].iloc[0] == 1000.0
    assert df[df["order_id"] == "O6"]["net_revenue"].iloc[0] == 300.0  # Replaced counts in net revenue
    assert df[df["order_id"] == "O5"]["net_revenue"].iloc[0] == 0.0    # Returned = 0
    assert df[df["order_id"] == "O3"]["net_revenue"].iloc[0] == 0.0    # Cancelled = 0
    assert df["net_revenue"].sum() == 3000.0

def test_new_vs_returning_customer_logic(sample_sales_data):
    """
    Test Returning Logic:
    A customer is 'Returning' in a month if their first valid purchase was in an earlier month; otherwise 'New'.
    """
    df = sample_sales_data
    # C01 bought in Jan 2024 (O1). In Feb 2024 (O2), C01 should be 'Returning'
    c1_feb = df[df["order_id"] == "O2"].iloc[0]
    assert c1_feb["customer_type_in_month"] == "Returning"

    c1_jan = df[df["order_id"] == "O1"].iloc[0]
    assert c1_jan["customer_type_in_month"] == "New"

    # Walk-in has no customer_id -> 'Walk-in (unknown)'
    walkin = df[df["order_id"] == "O7"].iloc[0]
    assert walkin["customer_type_in_month"] == "Walk-in (unknown)"

    # Cancelled -> 'Cancelled (not counted)'
    canc = df[df["order_id"] == "O3"].iloc[0]
    assert canc["customer_type_in_month"] == "Cancelled (not counted)"

def test_frequency_segments(sample_sales_data):
    """
    Test Buying Frequency Segments:
    One-time (1), Repeat (2), Loyal (3+), Not applicable (Walk-in).
    """
    df = sample_sales_data
    # C01 has 2 valid orders (O1 and O2) -> Repeat buyer (2)
    c1_seg = df[df["customer_id"] == "C01"]["frequency_segment"].iloc[0]
    assert c1_seg == "Repeat buyer (2)"

    # C02 has 1 valid order (O4) (O3 was cancelled) -> One-time buyer
    c2_seg = df[df["customer_id"] == "C02"]["frequency_segment"].iloc[0]
    assert c2_seg == "One-time buyer"

    # Walk-in -> Not applicable
    walkin_seg = df[df["order_id"] == "O7"]["frequency_segment"].iloc[0]
    assert walkin_seg == "Not applicable"

def test_rate_calculations(sample_sales_data):
    """
    Test rates:
    Return rate = Returned / non-cancelled orders
    Cancellation rate = Cancelled / all orders
    Replacement rate = Replaced / non-cancelled orders
    """
    df = sample_sales_data
    kpis = calculate_kpis(df)

    total_orders = len(df) # 7
    cancelled_orders = 1 # O3
    valid_orders = total_orders - cancelled_orders # 6
    returned_orders = 1 # O5
    replaced_orders = 1 # O6

    expected_cancel_rate = (1 / 7) * 100.0
    expected_return_rate = (1 / 6) * 100.0
    expected_replace_rate = (1 / 6) * 100.0

    assert pytest.approx(kpis["cancellation_rate_pct"], 0.01) == expected_cancel_rate
    assert pytest.approx(kpis["return_rate_pct"], 0.01) == expected_return_rate
    assert pytest.approx(kpis["replacement_rate_pct"], 0.01) == expected_replace_rate

def test_zero_division_resilience():
    """Ensure calculations never throw ZeroDivisionError on empty dataframes."""
    empty_df = pd.DataFrame(columns=["order_date", "product", "quantity", "total_sales", "order_status"])
    cleaned_df, report = clean_and_derive_features(empty_df)
    kpis = calculate_kpis(cleaned_df)
    assert kpis["net_revenue"] == 0.0
    assert kpis["total_orders"] == 0

    rfm = compute_customer_rfm(cleaned_df)
    assert rfm.empty

    counts, pcts = compute_cohort_retention(cleaned_df)
    assert counts.empty and pcts.empty

    decisions = evaluate_product_decisions(cleaned_df)
    assert decisions.empty

def test_upload_column_auto_detection():
    """Verifies that fuzzy alias detection correctly maps diverse column naming conventions."""
    sample_cols = ["PurchaseDate", "Item Name", "Qty", "Total Amount", "Client_ID", "Status"]
    detected = auto_detect_columns(sample_cols)

    assert detected["order_date"] == "PurchaseDate"
    assert detected["product"] == "Item Name"
    assert detected["quantity"] == "Qty"
    assert detected["total_sales"] == "Total Amount"
    assert detected["customer_id"] == "Client_ID"
    assert detected["order_status"] == "Status"

def test_product_health_score_bounds(sample_sales_data):
    """Product Health Score must strictly be bounded between 0 and 100."""
    decisions = evaluate_product_decisions(sample_sales_data)
    assert not decisions.empty
    assert (decisions["health_score"] >= 0).all()
    assert (decisions["health_score"] <= 100).all()

def test_forecasting_pipeline(sample_sales_data):
    """Test forecasting module returns expected keys and valid projected periods."""
    from forecasting import forecast_series, generate_all_forecasts
    s = pd.Series([100, 120, 110, 130, 140, 150, 160, 170], index=pd.date_range("2024-01-01", periods=8, freq="MS"))
    res = forecast_series(s, horizon=3, test_split=2)
    assert "forecast_df" in res
    assert len(res["forecast_df"]) == 3
    assert "forecast_growth_pct" in res
    assert res["forecast_df"]["yhat"].iloc[0] > 0

def test_utils_formatters():
    """Verify formatting helper functions."""
    from utils import format_currency, format_percentage, format_number, format_delta_arrow
    assert format_currency(1234.56) == "$1,234.56"
    assert format_currency(12500.0) == "$12.5k"
    assert format_currency(2500000.0) == "$2.50M"
    assert format_percentage(15.42) == "15.4%"
    assert format_number(12500) == "12,500"
    assert "↑" in format_delta_arrow(5.2)
    assert "↓" in format_delta_arrow(-3.1)

def test_ai_rule_based_fallback():
    """Verify rule-based fallback produces structured output when API key is omitted."""
    from ai_insights import generate_rule_based_fallback
    dummy_decisions = pd.DataFrame([
        {"product": "Laptop", "category": "Tech", "recommendation": "Increase Production", "reason": "High demand", "health_score": 88.5},
        {"product": "CRT", "category": "Tech", "recommendation": "Discontinue", "reason": "No sales", "health_score": 12.0},
    ])
    dummy_kpis = {"net_revenue": 50000.0, "est_profit": 15000.0, "est_margin_pct": 30.0, "return_rate_pct": 3.0, "cancellation_rate_pct": 2.0, "replacement_rate_pct": 1.0, "returning_pct": 20.0}
    text = generate_rule_based_fallback(dummy_decisions, dummy_kpis)
    assert "Executive Summary" in text
    assert "Laptop" in text
    assert "CRT" in text
    assert "Products to DISCONTINUE" in text

def test_user_template_csv_pipeline():
    """Verify that the user raw CSV file processes completely end to end."""
    import os
    from forecasting import generate_all_forecasts
    csv_path = "data/sales_report_combined_template_only.csv"
    assert os.path.exists(csv_path), "User CSV template must exist in data/"
    
    df_raw = pd.read_csv(csv_path)
    assert len(df_raw) == 6500
    assert "total_sales" in df_raw.columns
    assert "est_profit" in df_raw.columns

    # Pipeline processing
    cleaned_df, dq = clean_and_derive_features(df_raw)
    assert len(cleaned_df) == 6500
    assert "net_revenue" in cleaned_df.columns
    assert "customer_type_in_month" in cleaned_df.columns

    # KPIs
    kpis = calculate_kpis(cleaned_df)
    assert kpis["net_revenue"] > 0
    assert kpis["total_orders"] == 6500
    assert kpis["est_profit"] > 0
    assert 0 <= kpis["return_rate_pct"] <= 100

    # Decision Engine
    decisions = evaluate_product_decisions(cleaned_df)
    assert len(decisions) == 7
    assert (decisions["health_score"] >= 0).all()

    # Forecasting
    forecasts = generate_all_forecasts(cleaned_df, horizon=3)
    assert "overall" in forecasts
    assert len(forecasts["overall"]["forecast_df"]) == 3

