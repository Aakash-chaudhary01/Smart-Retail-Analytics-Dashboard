import json
import pandas as pd
from analysis import clean_and_derive_features, calculate_kpis

with open('baseline_kpis.json', 'r') as f:
    baseline = json.load(f)

raw_df = pd.read_csv('data/retail_sales_combined.csv')
raw_df['order_date'] = pd.to_datetime(raw_df['order_date'])
df_clean, dq = clean_and_derive_features(raw_df)

scenarios = {
    '0_default_all': df_clean,
    '1_date_2024': df_clean[(df_clean['order_date'] >= '2024-01-01') & (df_clean['order_date'] <= '2024-12-31')],
    '2_category_furniture': df_clean[df_clean['category'] == 'Furniture'],
    '3_product_laptop': df_clean[df_clean['product'] == 'Laptop'],
    '4_channel_online': df_clean[df_clean['channel'] == 'Online Store'],
    '5_status_delivered': df_clean[df_clean['order_status'] == 'Delivered'],
    '6_region_north': df_clean[df_clean['region'] == 'North'],
    '7_combined': df_clean[(df_clean['category'] == 'Computers & Peripherals') & (df_clean['channel'] == 'Online Store') & (df_clean['order_status'] == 'Delivered')]
}

all_match = True
for name, sub_df in scenarios.items():
    kpis = calculate_kpis(sub_df)
    current = {
        'row_count': len(sub_df),
        'net_revenue': round(kpis['net_revenue'], 2),
        'gross_sales': round(kpis['gross_sales'], 2),
        'est_profit': round(kpis['est_profit'], 2),
        'est_margin_pct': round(kpis['est_margin_pct'], 2),
        'total_orders': kpis['total_orders'],
        'aov': round(kpis['aov'], 2),
        'unique_customers': kpis['unique_customers'],
        'returning_pct': round(kpis['returning_pct'], 2),
        'return_rate_pct': round(kpis['return_rate_pct'], 2),
        'cancellation_rate_pct': round(kpis['cancellation_rate_pct'], 2),
        'replacement_rate_pct': round(kpis['replacement_rate_pct'], 2),
    }
    base = baseline[name]
    diffs = {k: (base[k], current[k]) for k in base if base[k] != current[k]}
    if diffs:
        all_match = False
        print(f"MISMATCH in {name}:", diffs)
    else:
        print(f"MATCH: {name} (Rows: {current['row_count']}, Net Rev: ${current['net_revenue']:,.2f})")

if all_match:
    print("\n>>> ALL 8 FILTER SCENARIOS MATCH BASELINE EXACTLY 100% <<<")
