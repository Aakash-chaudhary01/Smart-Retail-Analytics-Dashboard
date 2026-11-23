"""
upload.py
=========
Handles report upload (.csv, .xlsx), sheet selection, auto-detection
of columns, interactive column mapping, validation, and session-state loading.
"""

from __future__ import annotations
import io
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import streamlit as st

from config import COLUMN_ALIASES, PRODUCT_CATEGORY_MAP, get_logger
from analysis import clean_and_derive_features
from utils import generate_blank_template, to_csv_bytes

logger = get_logger("upload")

REQUIRED_COLUMNS = ["order_date", "product", "quantity", "total_sales"]
OPTIONAL_COLUMNS = [
    "customer_id", "category", "order_status", "region", 
    "channel", "discount", "profit", "order_id"
]

def auto_detect_columns(available_columns: List[str]) -> Dict[str, Optional[str]]:
    """
    Matches available raw column names against known aliases for required and optional fields.
    """
    mapping: Dict[str, Optional[str]] = {}
    lower_cols = {str(c).strip().lower(): c for c in available_columns}

    for target_col, aliases in COLUMN_ALIASES.items():
        matched = None
        for alias in aliases:
            clean_alias = alias.lower().replace(" ", "").replace("_", "").replace("(inr)", "").replace("(usd)", "").replace("₹", "").replace("$", "").replace("(", "").replace(")", "")
            for low_c, orig_c in lower_cols.items():
                clean_raw = low_c.replace(" ", "").replace("_", "").replace("(inr)", "").replace("(usd)", "").replace("₹", "").replace("$", "").replace("(", "").replace(")", "")
                if clean_raw == clean_alias:
                    matched = orig_c
                    break
            if matched:
                break
        mapping[target_col] = matched

    return mapping

def render_upload_interface() -> Tuple[pd.DataFrame, Dict[str, Any], bool]:
    """
    Renders the upload component in Streamlit.
    Returns:
        (df: pd.DataFrame, dq_report: Dict[str, Any], is_uploaded: bool)
    """
    st.sidebar.markdown("### 📁 Data Source")
    
    # Template download button
    template_df = generate_blank_template()
    st.sidebar.download_button(
        label="📥 Download CSV Template",
        data=to_csv_bytes(template_df),
        file_name="sales_report_template.csv",
        mime="text/csv",
        help="Download standard schema template with an example row."
    )

    dataset_source = st.sidebar.radio(
        "Active Dataset:",
        options=[
            "Sales Report (sales_report_combined_template_only.csv)",
            "Sample Dataset (retail_sales_combined.csv)"
        ],
        index=0,
        help="Select which dataset to load when no external file is uploaded."
    )

    uploaded_file = st.sidebar.file_uploader(
        "Upload Sales Report (.csv, .xlsx)",
        type=["csv", "xlsx", "xls"],
        help="Upload custom sales file. Processed in-memory in st.session_state only."
    )

    # Privacy notice
    st.sidebar.caption("🔒 *Uploaded data is processed entirely in memory in your session and never saved permanently to disk.*")

    if uploaded_file is None:
        chosen_path = (
            "data/sales_report_combined_template_only.csv"
            if "template_only" in dataset_source
            else "data/retail_sales_combined.csv"
        )
        try:
            default_df = pd.read_csv(chosen_path)
            cleaned_df, dq_report = clean_and_derive_features(default_df)
            return cleaned_df, dq_report, False
        except Exception as e:
            st.error(f"Error loading {chosen_path}: {e}")
            return pd.DataFrame(), {}, False

    # Read uploaded file
    try:
        if uploaded_file.name.endswith(".csv"):
            raw_df = pd.read_csv(uploaded_file)
        else:
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_names = excel_file.sheet_names
            if len(sheet_names) > 1:
                selected_sheet = st.sidebar.selectbox("Select Excel Sheet", sheet_names)
            else:
                selected_sheet = sheet_names[0]
            raw_df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
    except Exception as exc:
        st.sidebar.error(f"Could not read uploaded file: {exc}")
        return pd.DataFrame(), {}, True

    # Column Mapping UI Modal/Expander
    with st.expander("🛠️ Column Mapping & Upload Validation", expanded=True):
        st.markdown(
            "Verify or adjust the mapping between your file's columns and the dashboard fields below. "
            "**Required fields:** Date, Product, Quantity, Total Sales."
        )
        st.write("##### File Preview (First 5 Rows)")
        st.dataframe(raw_df.head(5), use_container_width=True)

        raw_columns = list(raw_df.columns)
        auto_mapped = auto_detect_columns(raw_columns)

        col1, col2 = st.columns(2)
        user_mapping: Dict[str, Optional[str]] = {}

        with col1:
            st.markdown("**Required Columns**")
            for req in REQUIRED_COLUMNS:
                default_idx = 0
                options = ["-- Select Column --"] + raw_columns
                if auto_mapped.get(req) and auto_mapped[req] in raw_columns:
                    default_idx = raw_columns.index(auto_mapped[req]) + 1
                
                choice = st.selectbox(
                    f"{req.replace('_', ' ').title()} *",
                    options=options,
                    index=default_idx,
                    key=f"map_{req}"
                )
                user_mapping[req] = choice if choice != "-- Select Column --" else None

        with col2:
            st.markdown("**Optional Columns**")
            for opt in OPTIONAL_COLUMNS:
                default_idx = 0
                options = ["-- None / Not Available --"] + raw_columns
                if auto_mapped.get(opt) and auto_mapped[opt] in raw_columns:
                    default_idx = raw_columns.index(auto_mapped[opt]) + 1

                choice = st.selectbox(
                    f"{opt.replace('_', ' ').title()}",
                    options=options,
                    index=default_idx,
                    key=f"map_{opt}"
                )
                user_mapping[opt] = choice if choice != "-- None / Not Available --" else None

        # Missing order_status choice
        missing_status_action = "Delivered"
        if user_mapping.get("order_status") is None:
            missing_status_action = st.radio(
                "Notice: 'Order Status' column not specified. How should orders be treated?",
                options=["Delivered (Assume all delivered)", "Skip Status Breakdown"],
                index=0
            )
            default_status_val = "Delivered" if "Delivered" in missing_status_action else None
        else:
            default_status_val = "Delivered"

        # Validation check
        missing_required = [req for req in REQUIRED_COLUMNS if user_mapping.get(req) is None]
        if missing_required:
            st.error(f"⚠️ Please map all mandatory columns: {', '.join(missing_required)}")
            return pd.DataFrame(), {}, True

    # Construct renamed DataFrame
    rename_dict = {orig: target for target, orig in user_mapping.items() if orig is not None}
    working_df = raw_df[list(rename_dict.keys())].rename(columns=rename_dict)

    # Process & Clean
    try:
        cleaned_df, dq_report = clean_and_derive_features(
            working_df, 
            default_status=default_status_val
        )
        st.session_state["uploaded_sales_df"] = cleaned_df
        st.session_state["uploaded_dq_report"] = dq_report
        st.success(f"✅ Successfully validated and loaded **{len(cleaned_df):,}** rows!")
        return cleaned_df, dq_report, True
    except Exception as exc:
        st.error(f"Data Processing Error: {exc}")
        return pd.DataFrame(), {}, True

