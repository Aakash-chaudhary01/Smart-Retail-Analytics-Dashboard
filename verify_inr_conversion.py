"""
verify_inr_conversion.py
========================
Automated verification for INR (₹) conversion, regression checks, USD vs INR detection,
and export formatting checks (CSV and Excel).
"""

import json
import io
import pandas as pd
import numpy as np

from currency import (
    USD_TO_INR_RATE,
    format_inr,
    format_inr_compact,
    detect_dataset_currency,
    convert_dataframe_currency,
)
from analysis import clean_and_derive_features, calculate_kpis
from utils import to_csv_bytes, to_excel_bytes

print("--- 1. Testing Number Formatting ---")
test_cases = [
    (125000, "₹1,25,000.00", "₹1.25 Lakh"),
    (1250000, "₹12,50,000.00", "₹12.50 Lakh"),
    (12500000, "₹1,25,00,000.00", "₹1.25 Cr"),
    (0, "₹0.00", "₹0"),
    (-125000, "-₹1,25,000.00", "-₹1.25 Lakh"),
    (-12500000, "-₹1,25,00,000.00", "-₹1.25 Cr"),
    (1234.56, "₹1,234.56", "₹1,234.56"),
]
for val, expected_full, expected_compact in test_cases:
    full_res = format_inr(val)
    comp_res = format_inr_compact(val)
    assert full_res == expected_full, f"format_inr({val}) got {full_res}, expected {expected_full}"
    assert comp_res == expected_compact, f"format_inr_compact({val}) got {comp_res}, expected {expected_compact}"
    print(f"PASS: {val:11} -> full: {full_res:16} | compact: {comp_res}")

print("\n--- 2. Default Dataset Baseline x Rate Verification ---")
with open("baseline_inr_preconversion.json", "r") as f:
    baseline = json.load(f)

base_kpis = baseline["kpis"]
raw_df = pd.read_csv("data/retail_sales_combined.csv")
raw_df["order_date"] = pd.to_datetime(raw_df["order_date"])

cleaned_df, dq = clean_and_derive_features(raw_df)

# Convert once immediately after cleaning
converted_df = convert_dataframe_currency(cleaned_df, from_currency="USD", to_currency="INR", rate=USD_TO_INR_RATE)

inr_kpis = calculate_kpis(converted_df)

# Check Monetary KPIs: must equal baseline * rate
expected_net_rev = round(base_kpis["net_revenue"] * USD_TO_INR_RATE, 2)
expected_gross_sales = round(base_kpis["gross_sales"] * USD_TO_INR_RATE, 2)
expected_profit = round(base_kpis["est_profit"] * USD_TO_INR_RATE, 2)
expected_aov = round(base_kpis["aov"] * USD_TO_INR_RATE, 2)

actual_net_rev = round(inr_kpis["net_revenue"], 2)
actual_gross_sales = round(inr_kpis["gross_sales"], 2)
actual_profit = round(inr_kpis["est_profit"], 2)
actual_aov = round(inr_kpis["aov"], 2)

print(f"Net Revenue:   USD ${base_kpis['net_revenue']:,.2f} x {USD_TO_INR_RATE} = INR {format_inr(expected_net_rev)} (Actual: {format_inr(actual_net_rev)})")
print(f"Gross Sales:   USD ${base_kpis['gross_sales']:,.2f} x {USD_TO_INR_RATE} = INR {format_inr(expected_gross_sales)} (Actual: {format_inr(actual_gross_sales)})")
print(f"Est. Profit:   USD ${base_kpis['est_profit']:,.2f} x {USD_TO_INR_RATE} = INR {format_inr(expected_profit)} (Actual: {format_inr(actual_profit)})")
print(f"AOV:           USD ${base_kpis['aov']:,.2f} x {USD_TO_INR_RATE} = INR {format_inr(expected_aov)} (Actual: {format_inr(actual_aov)})")

assert abs(actual_net_rev - expected_net_rev) < 0.5, "Net Revenue mismatch!"
assert abs(actual_gross_sales - expected_gross_sales) < 0.5, "Gross Sales mismatch!"
assert abs(actual_profit - expected_profit) < 0.5, "Profit mismatch!"
assert abs(actual_aov - expected_aov) < 0.5, "AOV mismatch!"

# Check Scale-Invariant Metrics: MUST be 100% IDENTICAL
assert round(inr_kpis["est_margin_pct"], 2) == round(base_kpis["est_margin_pct"], 2), "Margin % drifted!"
assert inr_kpis["total_orders"] == base_kpis["total_orders"], "Total orders drifted!"
assert inr_kpis["unique_customers"] == base_kpis["unique_customers"], "Unique customers drifted!"
assert round(inr_kpis["returning_pct"], 2) == round(base_kpis["returning_pct"], 2), "Returning % drifted!"
assert round(inr_kpis["return_rate_pct"], 2) == round(base_kpis["return_rate_pct"], 2), "Return rate % drifted!"
assert round(inr_kpis["cancellation_rate_pct"], 2) == round(base_kpis["cancellation_rate_pct"], 2), "Cancel rate % drifted!"
assert round(inr_kpis["replacement_rate_pct"], 2) == round(base_kpis["replacement_rate_pct"], 2), "Replace rate % drifted!"
print("PASS: Margin %, order count, customer count, and status rates are 100% identical!")

print("\n--- 3. Testing USD vs INR Dataset Detection & 1x Conversion ---")
# Dataset A: marked USD
df_usd = pd.DataFrame({
    "product": ["Laptop"], "quantity": [1], "total_sales ($)": [1000.0], "net_revenue": [1000.0], "est_profit": [350.0]
})
detected_a = detect_dataset_currency(df_usd)
assert detected_a == "USD", f"Expected USD, got {detected_a}"
conv_a = convert_dataframe_currency(df_usd, from_currency=detected_a, to_currency="INR", rate=USD_TO_INR_RATE)
assert conv_a["net_revenue"].iloc[0] == 1000.0 * USD_TO_INR_RATE
print(f"PASS: USD dataset detected as {detected_a} and converted 1x ({conv_a['net_revenue'].iloc[0]})")

# Dataset B: marked INR
df_inr = pd.DataFrame({
    "product": ["Laptop"], "quantity": [1], "total_sales (INR)": [83500.0], "net_revenue": [83500.0], "est_profit": [29225.0]
})
detected_b = detect_dataset_currency(df_inr)
assert detected_b == "INR", f"Expected INR, got {detected_b}"
conv_b = convert_dataframe_currency(df_inr, from_currency=detected_b, to_currency="INR", rate=USD_TO_INR_RATE)
assert conv_b["net_revenue"].iloc[0] == 83500.0  # NOT converted!
print(f"PASS: INR dataset detected as {detected_b} and NOT converted ({conv_b['net_revenue'].iloc[0]})")

print("\n--- 4. Checking CSV and Excel Exports ---")
csv_bytes = to_csv_bytes(converted_df.head(10), rate=USD_TO_INR_RATE, original_currency="USD")
csv_text = csv_bytes.decode("utf-8")
assert "Currency: INR" in csv_text
assert "(INR)" in csv_text
print("PASS: CSV export has '(INR)' headers and audit note.")

excel_bytes = to_excel_bytes({"Sales": converted_df.head(10)}, rate=USD_TO_INR_RATE, original_currency="USD")
excel_sheets = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=None)
assert "Sales" in excel_sheets
assert "Currency & Notes" in excel_sheets
assert any("(INR)" in str(col) for col in excel_sheets["Sales"].columns)
# Numbers must be numeric in excel, not strings
assert pd.api.types.is_numeric_dtype(excel_sheets["Sales"]["total_sales (INR)"])
print("PASS: Excel export has '(INR)' headers, numeric floats, and dedicated Notes sheet.")

print("\n>>> ALL INR VERIFICATION CHECKS PASSED SUCCESSFULLY 100% <<<")
