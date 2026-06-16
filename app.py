"""
TradeProof — Streamlit Web Application
Intelligent Trade Document Reconciliation Platform
"""
import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
from datetime import datetime
import os

from config import (
    APP_NAME, APP_VERSION, APP_TAGLINE, APP_EMOJI,
    DEFAULT_MODEL, COLOR_MATCH, COLOR_MISMATCH, COLOR_WARNING, COLOR_MISSING
)
from core.extractor import extract_bl_data, extract_sb_data
from core.reconciler import run_full_reconciliation
from core.reporter import generate_html_report, generate_json_report, generate_excel_report
from core.database import init_db, save_report, get_all_reports, get_report_by_id

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — Vessel Clearance Audit",
    page_icon=APP_EMOJI,
    layout="wide",
    initial_sidebar_state="expanded"
)
init_db()  # Initialize database

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #06142e 0%, #1b3358 100%), repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.03) 10px, rgba(255,255,255,0.03) 20px);
        padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;
        color: white;
    }
    .main-header h1 { font-size: 28px; margin: 0; letter-spacing: -0.5px; }
    .main-header p  { font-size: 13px; opacity: 0.7; margin: 4px 0 0; }
    .metric-card {
        background: white; border: 1px solid #e2e8f0;
        border-radius: 10px; padding: 16px; text-align: center;
    }
    .status-match   { color: #16a34a; font-weight: 700; }
    .status-mismatch{ color: #dc2626; font-weight: 700; }
    .status-warning { color: #d97706; font-weight: 700; }
    .status-missing { color: #64748b; font-weight: 700; }
    div[data-testid="stFileUploadDropzone"] { border: 2px dashed #cbd5e1 !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {APP_EMOJI} {APP_NAME}")
    st.caption(f"v{APP_VERSION} | {APP_TAGLINE}")
    st.divider()

    st.subheader("⚙️ Configuration")
    api_key_input = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.getenv("GEMINI_API_KEY", ""),
        help="Enter your Google Gemini API key. Get one at https://aistudio.google.com"
    )
    model_choice = st.selectbox(
        "Gemini Model",
        ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        index=0
    )
    st.divider()
    if st.button("🔄 Clear Results", use_container_width=True):
        if "report" in st.session_state:
            del st.session_state["report"]
        st.rerun()
    st.divider()
    st.markdown("""
    **📋 Ingestion Workflow:**
    1. Enter your Gemini API key
    2. Upload the Master Bill of Lading (BL)
    3. Attach Supporting Shipping Bills (SB)
    4. Execute **Customs Audit**
    5. Review discrepancies & export report
    """)
    st.divider()
    st.markdown("""
    **Reconciliation Checks:**
    - 🔵 Identifiers (7 fields)
    - 🟣 SB Documentation
    - 🟠 Package Count
    - 🟠 Gross Weight
    - 🔴 Container & Seals
    - 🟢 HS Classification
    - 💰 Invoice (if present)
    """)

# ── Main Header ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
    <h1>{APP_EMOJI} {APP_NAME}</h1>
    <p>{APP_TAGLINE}</p>
</div>
""", unsafe_allow_html=True)

# ── Main Layout ───────────────────────────────────────────────────────────────
tab_new_audit, tab_history = st.tabs(["🚀 New Audit", "🗄️ Past Audits"])

with tab_new_audit:
    # ── File Uploads ──────────────────────────────────────────────────────────────
    st.markdown("#### Step 1: Master Bill of Lading")
    bl_file = st.file_uploader("Upload Master BL (PDF)", type=["pdf"], key="bl_file", label_visibility="collapsed")

    st.markdown("#### Step 2: Supporting Shipping Bills")
    sb_files = st.file_uploader("Upload Shipping Bills (PDFs)", type=["pdf"], accept_multiple_files=True, key="sb_files", label_visibility="collapsed")

    st.markdown("#### Step 3: Execute Audit")
    run_btn = st.button("⚓ Run Vessel Clearance Audit", type="primary", use_container_width=True, disabled=not (bl_file and sb_files))

    # ── Processing & Results ──────────────────────────────────────────────────────
    if run_btn:
        if not api_key_input:
            st.error("Please enter a Gemini API Key in the sidebar.")
            st.stop()

        with st.status("Executing Customs Audit...", expanded=True) as status:
            # 1. Extract BL
            st.write("Extracting Bill of Lading...")
            bl_bytes = bl_file.read()
            bl_res = extract_bl_data(bl_bytes, api_key_input)

            if not bl_res["success"]:
                status.update(label="Failed to extract BL", state="error", expanded=True)
                st.error(f"Failed to extract BL: {bl_res.get('error')}")
                st.stop()

            # 2. Extract SBs
            st.write(f"Extracting {len(sb_files)} Shipping Bill(s)...")
            sb_data_list = []
            for sb_f in sb_files:
                st.write(f"- Processing {sb_f.name}...")
                sb_bytes = sb_f.read()
                sb_res = extract_sb_data(sb_bytes, sb_f.name, api_key_input)
                if not sb_res["success"]:
                    status.update(label=f"Failed to extract SB {sb_f.name}", state="error", expanded=True)
                    st.error(f"Failed to extract SB {sb_f.name}: {sb_res.get('error')}")
                    st.stop()
                sb_data_list.append(sb_res["data"])

            # 3. Reconcile
            st.write("Running reconciliation engine...")
            report = run_full_reconciliation(bl_res["data"], sb_data_list)
        st.session_state["report"] = report
        save_report(report)
            status.update(label="Audit Complete!", state="complete", expanded=False)
            st.toast("Audit Complete!", icon="✅")

    if "report" in st.session_state:
        report = st.session_state["report"]

        st.divider()
        st.subheader(f"🚢 Cargo Audit Report — {report.bl_number}")
        st.info(report.summary)

        # Metrics
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Documentation Integrity", f"{report.match_rate_pct}%")
        m2.metric("Total Checks", report.total_checks)
        m3.metric("Cleared Checks ✅", report.match_count)
        m4.metric("Customs Discrepancies ❌", report.mismatch_count)
        m5.metric("Clearance Holds ⚠️", report.warning_count + report.missing_count)

        st.divider()

        # Dashboard Tabs
        tab_dash, tab_disc, tab_audit = st.tabs(["📊 Dashboard", "⚠️ Discrepancies", "📋 Full Audit Log"])

        with tab_dash:
            r_col1, r_col2 = st.columns([1, 1])
            with r_col1:
                labels = ['Match', 'Mismatch', 'Missing', 'Warning']
                values = [report.match_count, report.mismatch_count, report.missing_count, report.warning_count]
                colors = [COLOR_MATCH, COLOR_MISMATCH, COLOR_MISSING, COLOR_WARNING]

                fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5, marker_colors=colors)])
                fig.update_layout(title_text="Check Distribution", showlegend=True, margin=dict(t=40, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

            with r_col2:
                st.markdown("### Export Reports")
                html_report = generate_html_report(report)
                json_report = generate_json_report(report)
                excel_report = generate_excel_report(report)

                st.download_button("📊 Download Excel Report", data=excel_report, file_name=f"TradeProof_Report_{report.bl_number}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                st.download_button("📄 Download HTML Report", data=html_report, file_name=f"TradeProof_Report_{report.bl_number}.html", mime="text/html", use_container_width=True)
                st.download_button("📋 Download JSON Report", data=json_report, file_name=f"TradeProof_Report_{report.bl_number}.json", mime="application/json", use_container_width=True)

            # Cargo Route Map
            st.divider()
            st.markdown("### 🗺️ Cargo Route")
            if getattr(report, "port_of_loading_lat", None) and getattr(report, "port_of_discharge_lat", None):
                route_data = pd.DataFrame({
                    "start_lat": [report.port_of_loading_lat],
                    "start_lon": [report.port_of_loading_lon],
                    "end_lat": [report.port_of_discharge_lat],
                    "end_lon": [report.port_of_discharge_lon]
                })
                
                st.pydeck_chart(pdk.Deck(
                    map_style="mapbox://styles/mapbox/dark-v10",
                    initial_view_state=pdk.ViewState(
                        latitude=(report.port_of_loading_lat + report.port_of_discharge_lat) / 2,
                        longitude=(report.port_of_loading_lon + report.port_of_discharge_lon) / 2,
                        zoom=2,
                        pitch=45,
                    ),
                    layers=[
                        pdk.Layer(
                            "ArcLayer",
                            data=route_data,
                            get_source_position="[start_lon, start_lat]",
                            get_target_position="[end_lon, end_lat]",
                            get_source_color=[0, 200, 0, 255],
                            get_target_color=[220, 38, 38, 255],
                            auto_highlight=True,
                            width_scale=0.0001,
                            get_width="outbound",
                            width_min_pixels=3,
                            width_max_pixels=10,
                        ),
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=pd.DataFrame({
                                "lat": [report.port_of_loading_lat, report.port_of_discharge_lat],
                                "lon": [report.port_of_loading_lon, report.port_of_discharge_lon],
                                "name": ["Loading", "Discharge"],
                                "color": [[0, 200, 0, 255], [220, 38, 38, 255]]
                            }),
                            get_position="[lon, lat]",
                            get_fill_color="color",
                            get_radius=150000,
                            pickable=True
                        )
                    ],
                    tooltip={"html": "<b>Port</b>"}
                ))
            else:
                st.info("Route coordinates could not be extracted from the documents.")

        # Prepare DataFrame
        check_dicts = []
        for c in report.checks:
            check_dicts.append({
                "Category": c.category,
                "Check": c.check_name,
                "Status": c.status,
                "Severity": c.severity,
                "BL Value": c.bl_value or "-",
                "SB Value": c.sb_value or "-",
                "Details": c.details
            })
        df_checks = pd.DataFrame(check_dicts)

        def style_dataframe(df):
            return st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Status": st.column_config.TextColumn("Status"),
                    "Severity": st.column_config.TextColumn("Severity"),
                    "BL Value": st.column_config.TextColumn("BL Value", width="medium"),
                    "SB Value": st.column_config.TextColumn("SB Value", width="medium"),
                    "Details": st.column_config.TextColumn("Details", width="large"),
                }
            )

        with tab_disc:
            st.markdown("### Actionable Discrepancies")
            df_disc = df_checks[df_checks["Status"].isin(["MISMATCH", "WARNING", "MISSING"])]
            if df_disc.empty:
                st.success("No discrepancies found! All checks match perfectly.")
            else:
                style_dataframe(df_disc)

        with tab_audit:
            st.markdown("### All Checks")
            style_dataframe(df_checks)


with tab_history:
    st.markdown("### 🗄️ Past Vessel Clearance Audits")
    past_reports = get_all_reports()
    if not past_reports:
        st.info("No past audits found. Run your first audit to see history here!")
    else:
        df_history = pd.DataFrame(past_reports)
        st.dataframe(df_history, use_container_width=True)
        st.divider()
        st.markdown("**Load Past Audit**")
        selected_id = st.selectbox("Select Report ID to load", [r["report_id"] for r in past_reports])
        if st.button("Load Audit", type="primary"):
            st.session_state["report"] = get_report_by_id(selected_id)
            st.rerun()

st.divider()
st.markdown("<p style='text-align: center; color: gray; font-size: 12px;'>Made with grit by Hansraj</p>", unsafe_allow_html=True)
