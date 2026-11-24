# 🛍️ Retail Sales Intelligence Dashboard & AI Product Decision Engine

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B.svg)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-5.18%2B-3F4F75.svg)](https://plotly.com/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4.svg)](https://aistudio.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An enterprise-grade, end-to-end retail intelligence web application built with **Python**, **Streamlit**, **Plotly**, **statsmodels**, and **Google Gemini**. The dashboard enables retail leaders and supply chain managers to monitor multi-channel sales performance, analyze fulfillment quality (returns, replacements, cancellations), evaluate customer cohort retention, forecast quarterly demand, and receive algorithmic and AI-driven recommendations on product lifecycle actions (**Increase Production**, **Discontinue**, **Review / Reprice**, or **Maintain**).

---

## 📌 Table of Contents
1. [Problem Statement](#-problem-statement)
2. [Dataset Description & Real-World Nuances](#-dataset-description--real-world-nuances)
3. [Architecture & Methodology](#-architecture--methodology)
4. [Decision Engine & Recommendation Rules](#-decision-engine--recommendation-rules)
5. [Dashboard Tour & Screenshots](#-dashboard-tour--screenshots)
6. [Quickstart & Installation](#-quickstart--installation)
7. [Deploying to Streamlit Community Cloud](#-deploying-to-streamlit-community-cloud)
8. [Viva & Project Presentation Q&A](#-viva--project-presentation-qa)
9. [Limitations & Future Scope](#-limitations--future-scope)

---

## 🎯 Problem Statement
Modern multi-channel retailers generate substantial transaction volume across direct physical stores, online web storefronts, regional wholesale operations, and customer purchase orders. However, merchandising and procurement teams encounter critical friction:
- **Product Portfolio Blindspots:** Popular top-line revenue drivers often mask severe return rates, excessive replacement requests, or margin erosion caused by aggressive promotional discounting.
- **Data Fragmentations:** Physical retail POS walk-ins lack persistent digital identifiers, while e-commerce channels track customer IDs with low repeat frequencies (typical for electronics/furniture).
- **Delayed Capital Allocation:** Identifying when to decommission unprofitable products or expand inventory buffers for high-velocity items often happens quarters after margins have deteriorated.

This project delivers a unified diagnostic and prescriptive engine that automates data ingestion, standardizes fulfillment metrics, forecasts forward revenue, and delivers grounded, evidence-backed strategic actions via **Claude**.

---

## 📊 Dataset Description & Real-World Nuances
The default dataset (`data/retail_sales_combined.csv`) comprises **6,500 transactions** spanning **January 2023 through June 2025** (30 consecutive months) across 7 products and 4 sales channels.

### Essential Data Characteristics
* **Catalogue:**
  * *Computers & Peripherals:* Laptop, Monitor, Printer
  * *Mobiles & Tablets:* Phone, Tablet
  * *Furniture:* Chair, Desk
* **Sales Channels:**
  * `Customer Purchase` (CPH- prefix, direct corporate invoices)
  * `Online Store` (ONL- prefix, e-commerce storefront)
  * `Regional Sales` (REG- prefix, B2B wholesale with tiered discount schedules)
  * `Retail Store` (Physical brick-and-mortar POS walk-ins; no customer IDs)
* **Revenue Calculation Rule:**
  $$\text{Net Revenue} = \begin{cases} \text{Total Sales (Gross Billed)}, & \text{if Delivered or Replaced} \\ 0.0, & \text{if Returned or Cancelled} \end{cases}$$
* **Estimated Profit (`est_profit`):**
  $$\text{Estimated Profit} = \text{Net Revenue} - (\text{Estimated Unit Cost} \times \text{Quantity})$$
  *(Unit costs are derived from the companion inventory catalog; labeled strictly as "Estimated Profit" across all reports).*
* **Order Statuses & Demonstration Simulation:**
  * Statuses include `Delivered` (~82%), `Returned` (~7%), `Replaced` (~4%), and `Cancelled` (~7%).
  * For two channels (Online Store and Retail Store POS), status categories and replacement splits are simulated for academic/demonstration purposes and flagged with a transparency note in the UI.

---

## ⚙️ Architecture & Methodology

```
sales-dashboard/
├── data/
│   ├── retail_sales_combined.csv   # 6,500 rows base dataset
│   ├── customer_summary.csv        # Aggregated customer lifetime summary
│   └── inventory_summary.csv       # Stock, reorder points, unit costs
├── app.py                          # Streamlit 8-tab web dashboard UI
├── upload.py                       # File uploader, fuzzy column auto-mapper
├── analysis.py                     # Data cleaning, derivations & KPI engine
├── customers.py                    # Cohort heatmap, RFM clustering & CLV
├── forecasting.py                  # Holt-Winters exponential smoothing & MAPE
├── decision_engine.py              # Health score (0-100), ABC/BCG & action rules
├── ai_insights.py                  # Google Gemini API prompt & Q&A engine
├── config.py                       # Configurable thresholds, colors, models
├── utils.py                        # Currency/pct formatters, CSV/Excel/PDF export
├── tests/
│   └── test_metrics.py             # Pytest test suite (10 comprehensive tests)
├── requirements.txt                # Pinned dependencies
├── .env.example                    # Sample environment credentials
└── README.md                       # Comprehensive documentation
```

### Core Analytical Pipelines
1. **Cleaning & Validation:** Enforces positive non-zero quantities, non-negative gross sales, resolves date hierarchies, and flags sales outliers using the $3.0 \times \text{IQR}$ rule.
2. **Customer Lineage & Cohort Logic:**
   * A customer is classified as **"Returning"** in month $M$ if and only if their initial valid purchase occurred in an earlier month $M_{0} < M$.
   * **Buying Frequency Segments:** One-time buyer ($=1$), Repeat buyer ($=2$), Loyal buyer ($\ge 3$). Walk-in customers are safely isolated from denominator calculations.
3. **Statistical Forecasting:**
   * Fits additive **Holt-Winters Exponential Smoothing** models over monthly series.
   * Benchmarks predictive reliability using a 3-month holdout test split evaluated via **MAPE** (Mean Absolute Percentage Error).
   * Fallback to rolling moving averages for short series with explicit "Low Confidence" badges.
4. **AI Strategic Synthesis:**
   * Strictly feeds aggregated JSON summary tables into Google Gemini (no customer PII or raw transaction rows are ever transmitted).
   * Enforces numeric grounding: the AI may only reason from provided KPIs.
   * Responses are cached in session state to prevent redundant API queries.

---

## 🧠 Decision Engine & Recommendation Rules

Every product is evaluated across multiple dimensions:

### 1. Product Health Score ($0 - 100$)
$$\text{Health Score} = 0.30 \cdot S_{\text{growth}} + 0.30 \cdot S_{\text{margin}} + 0.20 \cdot S_{\text{rev\_share}} + 0.10 \cdot S_{\text{returns}} + 0.10 \cdot S_{\text{consistency}}$$

* $S_{\text{growth}}$: Normalized 3-month vs previous 3-month sales growth
* $S_{\text{margin}}$: Estimated profit margin percentage
* $S_{\text{rev\_share}}$: Revenue contribution relative to portfolio lead
* $S_{\text{returns}}$: Penalty function for combined return and replacement rates
* $S_{\text{consistency}}$: Inverse coefficient of variation ($\text{CV} = \sigma / \mu$)

### 2. Prescriptive Action Triggers (Configurable in Sidebar)
* **`INCREASE PRODUCTION`:**
  $$\text{Growth}_{3\text{M}} > 15\% \quad \text{AND} \quad \text{Margin} > 15\% \quad \text{AND} \quad \text{Forecast} \ge 0\% \quad \text{AND} \quad \text{Return Rate} < 8\%$$
  *(If warehouse stock is below reorder point, an urgent supply chain alert is added).*
* **`DISCONTINUE`:**
  $$\left(\text{Growth}_{3\text{M}} < -15\% \;\text{AND}\; (\text{Margin} < 5\% \;\text{OR}\; \text{Rev Share} < 2\%)\right) \quad \text{OR} \quad \text{Loss Months} \ge 3 \quad \text{OR} \quad \text{Return Rate} \ge 20\%$$
* **`REVIEW / REPRICE`:**
  $$\text{Margin} \le 10\% \quad \text{OR} \quad \text{Return Rate} \ge 15\% \quad \text{OR} \quad \text{Replacement Rate} \ge 8\%$$
* **`MAINTAIN`:**
  All other stable products exhibiting standard performance.

---

## 🖥️ Dashboard Tour & Screenshots

| Tab | Functionality & Visualizations |
|---|---|
| **1️⃣ Overview** | 11 Executive KPI cards with MoM arrows, monthly revenue trend with 3M moving average, dual-axis revenue vs estimated profit, channel bar charts, regional sales distribution. |
| **2️⃣ Category & Products** | Category sales comparison & donut share, top & bottom product rankings by revenue and profit, seasonality category $\times$ month heatmap, and discount vs profit scatter chart. |
| **3️⃣ Order Status** | Fulfillment donut chart, monthly stacked status volume, product status composition, and sales channel return/replacement risk comparison. |
| **4️⃣ Customer Dynamics** | Identified vs walk-in metrics, new vs returning monthly customer bars, returning % trend line, buying frequency distribution, RFM segmentation, and cohort retention percentage matrix. |
| **5️⃣ Demand Forecast** | 3-month forward projections with 90% confidence bands, backtested MAPE error metrics, and category-level growth projections. |
| **6️⃣ Product Decision Engine** | BCG portfolio matrix with recommendation overlays, color-coded interactive product decisions table, health scores, and triggered business rationales. |
| **7️⃣ AI Insights Engine** | 10-section strategic executive report generated by Google Gemini, rule-based fallback, PDF/TXT report download, and interactive natural language "Chat with your data" interface. |
| **8️⃣ Data & Upload Report** | Interactive custom file uploader (.csv/.xlsx), column auto-detection and remapping tool, data quality audit expander, raw data preview, and CSV/Excel download center. |

---

## 🚀 Quickstart & Installation

### Prerequisites
* Python 3.10, 3.11, or 3.12
* Git

### Step-by-Step Setup
```bash
# 1. Clone the repository
git clone https://github.com/your-username/sales-dashboard.git
cd sales-dashboard

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. (Optional) Configure Google Gemini API Key
cp .env.example .env
# Open .env and add your GEMINI_API_KEY=AIzaSy...

# 5. Run unit tests
PYTHONPATH=. pytest -v tests/

# 6. Launch the dashboard
streamlit run app.py
```
Access the dashboard at `http://localhost:8501`.

---

## ☁️ Deploying to Streamlit Community Cloud

1. Push your repository to GitHub.
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **"New app"**, select your repository, branch (`main`), and set **Main file path** to `app.py`.
4. In **Advanced settings** $\rightarrow$ **Secrets**, add your Google Gemini credentials:
   ```toml
   GEMINI_API_KEY = "AIzaSy-your-actual-api-key"
   GEMINI_MODEL = "gemini-2.5-flash"
   ```
5. Click **"Deploy!"**. Your dashboard is now live on the web with automatic HTTPS and secret encryption.

---

## 🔮 Limitations & Future Scope
* **Limitations:**
  * Sample dataset order statuses for Online and Retail channels are partially simulated to showcase edge cases.
  * Product costs are modeled using static averages rather than dynamic FIFO/LIFO warehouse lots.
  * Customer repeat purchase frequency is naturally low ($< 20\%$) due to the durable nature of computers and furniture.
* **Future Scope:**
  * **Dynamic Inventory Replenishment:** Integration with live ERP systems (SAP, NetSuite) for real-time lead-time stock forecasting.
  * **Price Elasticity Modeling:** Machine learning demand curves to simulate revenue outcomes before price changes.
  * **Customer Churn Probability:** Survival analysis and probabilistic BTYD (Buy 'Til You Die) models for non-contractual customer lifetime value predictions.

---
*Developed with ❤️ as a production-quality Data Science & Full-Stack Python Portfolio Project.*

