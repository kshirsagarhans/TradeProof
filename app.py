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
    DEFAULT_MODEL, COLOR_MATCH, COLOR_MISMATCH, COLOR_WARNING, COLOR_MISSING,
    AZURE_DEFAULT_DEPLOYMENT, AZURE_DEFAULT_API_VERSION
)
from core.extractor import extract_bl_data, extract_sb_data, extract_seal_data
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
    /* Better text targeting for dark theme */
    .stApp, .stMarkdown, p, h1, h2, h3, h4, h5, h6 {
        color: #f8fafc;
    }
    
    /* Fix top-right 3-dots menu text (it has a white background) */
    ul[data-testid="main-menu-list"] span, ul[data-testid="main-menu-list"] p {
        color: #0f172a !important;
    }

    /* Style secondary buttons (like Clear Results, Browse Files) to match dark theme */
    button[kind="secondary"] {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    button[kind="secondary"]:hover {
        background-color: rgba(255, 255, 255, 0.2) !important;
        border: 1px solid #38bdf8 !important;
        color: #38bdf8 !important;
    }
    
    /* Fix file uploader small text */
    div[data-testid="stFileUploadDropzone"] small {
        color: #cbd5e1 !important;
    }

    /* Main Header Glass */
    .main-header {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        padding: 24px 32px; 
        border-radius: 16px; 
        margin-bottom: 24px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
    }
    .main-header h1 { font-size: 32px; margin: 0; font-weight: 800; background: -webkit-linear-gradient(45deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .main-header p  { font-size: 14px; opacity: 0.9; margin: 4px 0 0; color: #cbd5e1; }
    
    /* Glass Panels */
    .glass-panel {
        background: rgba(15, 23, 42, 0.5);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    /* Metric Cards */
    .glass-metric {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .glass-metric:hover {
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(56, 189, 248, 0.15);
        border: 1px solid rgba(56, 189, 248, 0.4);
    }
    .metric-value { font-size: 32px; font-weight: 800; margin: 0; background: -webkit-linear-gradient(45deg, #f8fafc, #cbd5e1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .metric-label { font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }

    /* Make Streamlit containers transparent so video shows through */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: transparent !important;
        background-image: none !important;
    }
    
    /* Sidebar Glassmorphism */
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.7) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
    }

    /* Override Uploader Dropzones */
    div[data-testid="stFileUploadDropzone"] {
        background: rgba(30, 41, 59, 0.5) !important;
        border: 2px dashed rgba(255, 255, 255, 0.2) !important;
        border-radius: 16px !important;
        transition: all 0.3s ease;
    }
    div[data-testid="stFileUploadDropzone"]:hover {
        background: rgba(30, 41, 59, 0.8) !important;
        border-color: #38bdf8 !important;
    }

    /* Expander Glass */
    div[data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
    }

    .block-container {
        z-index: 1;
        position: relative;
        padding-top: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Video Background Injection ────────────────────────────────────────────────
st.markdown(f"""
    <style>
    .video-background {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 0;
        opacity: 0.4; /* Adjust this for watermark intensity */
        pointer-events: none;
        object-fit: cover;
    }}
    </style>
    <video id="bg-video" autoplay loop muted playsinline class="video-background">
        <source src="app/static/bg_video.mp4" type="video/mp4">
    </video>
    <img src="data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==" onload="var v=document.getElementById('bg-video'); if(v){{v.muted=true; v.play();}}" style="display:none;">
    """, unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {APP_EMOJI} {APP_NAME}")
    st.caption(f"v{APP_VERSION} | {APP_TAGLINE}")
    st.divider()

    st.subheader("⚙️ Configuration")
    provider_choice = st.selectbox("AI Provider", ["Google Gemini", "Azure OpenAI"])
    
    ai_config = {"provider": "gemini", "credentials": {}}
    
    if provider_choice == "Google Gemini":
        ai_config["provider"] = "gemini"
        api_key_input = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.getenv("GEMINI_API_KEY", ""),
            help="Enter your Google Gemini API key. Get one at https://aistudio.google.com"
        )
        ai_config["credentials"]["api_key"] = api_key_input
        
    elif provider_choice == "Azure OpenAI":
        ai_config["provider"] = "azure"
        azure_endpoint = st.text_input(
            "Azure Endpoint", 
            value=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            help="e.g. https://your-resource-name.openai.azure.com/"
        )
        azure_api_key = st.text_input(
            "Azure API Key",
            type="password",
            value=os.getenv("AZURE_OPENAI_API_KEY", "")
        )
        azure_deployment = st.text_input(
            "Deployment Name",
            value=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", AZURE_DEFAULT_DEPLOYMENT)
        )
        azure_api_version = st.text_input(
            "API Version",
            value=os.getenv("AZURE_OPENAI_API_VERSION", AZURE_DEFAULT_API_VERSION)
        )
        ai_config["credentials"]["endpoint"] = azure_endpoint
        ai_config["credentials"]["api_key"] = azure_api_key
        ai_config["credentials"]["deployment_name"] = azure_deployment
        ai_config["credentials"]["api_version"] = azure_api_version
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
    st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
    st.markdown("### 📥 Document Upload Pipeline")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 1. Master BL")
        bl_file = st.file_uploader("Upload Master BL (PDF)", type=["pdf"], key="bl_file", label_visibility="collapsed")
    with col2:
        st.markdown("#### 2. Shipping Bills")
        sb_files = st.file_uploader("Upload Shipping Bills (PDFs)", type=["pdf"], accept_multiple_files=True, key="sb_files", label_visibility="collapsed")
    with col3:
        st.markdown("#### 3. Physical Seals")
        seal_photos = st.file_uploader("Upload Container Seal Photos (JPG/PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="seal_photos", label_visibility="collapsed")
    
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Floating Action Button ───────────────────────────────────────────────────
    run_btn = st.button("🚀 EXECUTE VESSEL CLEARANCE AUDIT", type="primary", use_container_width=True, disabled=not (bl_file and sb_files))

    # ── Processing & Results ──────────────────────────────────────────────────────
    if run_btn:
        if not ai_config["credentials"].get("api_key"):
            st.error(f"Please enter an API Key for {provider_choice} in the sidebar.")
            st.stop()
            
        if provider_choice == "Azure OpenAI" and not ai_config["credentials"].get("endpoint"):
            st.error("Please enter your Azure Endpoint in the sidebar.")
            st.stop()

        with st.status("Executing Customs Audit...", expanded=True) as status:
            # 1. Extract BL
            st.write("Extracting Bill of Lading...")
            bl_bytes = bl_file.read()
            bl_res = extract_bl_data(bl_bytes, ai_config)

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
                sb_res = extract_sb_data(sb_bytes, sb_f.name, ai_config)
                if not sb_res["success"]:
                    status.update(label=f"Failed to extract SB {sb_f.name}", state="error", expanded=True)
                    st.error(f"Failed to extract SB {sb_f.name}: {sb_res.get('error')}")
                    st.stop()
                sb_data_list.append(sb_res["data"])

            # 3. Extract Physical Seals
            seal_data = None
            if seal_photos:
                st.write(f"Extracting Physical Verification data from {len(seal_photos)} photo(s)...")
                seal_bytes_list = [p.read() for p in seal_photos]
                seal_res = extract_seal_data(seal_bytes_list, ai_config)
                if not seal_res["success"]:
                    st.warning(f"Failed to extract physical seals: {seal_res.get('error')}")
                else:
                    seal_data = seal_res["data"]

            # 4. Reconcile
            st.write("Running reconciliation engine...")
            report = run_full_reconciliation(bl_res["data"], sb_data_list, seal_data)
            st.session_state["report"] = report
            save_report(report)
            status.update(label="Audit Complete!", state="complete", expanded=False)
            st.toast("Audit Complete!", icon="✅")

    if "report" in st.session_state:
        report = st.session_state["report"]

        st.divider()
        st.subheader(f"🚢 Cargo Audit Report — {report.bl_number}")
        st.info(report.summary)

        # Dashboard Top Metrics (Glassmorphism)
        st.markdown(f"""
        <div style="display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap;">
            <div class="glass-metric" style="flex: 1; min-width: 150px;">
                <p class="metric-label">Integrity</p>
                <p class="metric-value">{report.match_rate_pct}%</p>
            </div>
            <div class="glass-metric" style="flex: 1; min-width: 150px;">
                <p class="metric-label">Total Checks</p>
                <p class="metric-value">{report.total_checks}</p>
            </div>
            <div class="glass-metric" style="flex: 1; min-width: 150px;">
                <p class="metric-label">Cleared ✅</p>
                <p class="metric-value" style="background: -webkit-linear-gradient(45deg, #4ade80, #22c55e); -webkit-background-clip: text;">{report.match_count}</p>
            </div>
            <div class="glass-metric" style="flex: 1; min-width: 150px;">
                <p class="metric-label">Discrepancies ❌</p>
                <p class="metric-value" style="background: -webkit-linear-gradient(45deg, #f87171, #dc2626); -webkit-background-clip: text;">{report.mismatch_count}</p>
            </div>
            <div class="glass-metric" style="flex: 1; min-width: 150px;">
                <p class="metric-label">Holds ⚠️</p>
                <p class="metric-value" style="background: -webkit-linear-gradient(45deg, #fbbf24, #d97706); -webkit-background-clip: text;">{report.warning_count + report.missing_count}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

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

        with tab_disc:
            st.markdown("### Actionable Discrepancies")
            
            # Show checks that are mismatch/warning AND not already overridden
            discrepancies = [c for c in report.checks if c.status in ("MISMATCH", "WARNING", "MISSING") and not getattr(c, "is_overridden", False)]
            
            if not discrepancies:
                st.success("No unacknowledged discrepancies found! All checks match perfectly or have been overridden.")
            else:
                for c in discrepancies:
                    icon = "⚠️" if c.status == "WARNING" else "❌"
                    with st.expander(f"{icon} {c.check_name} ({c.category})", expanded=False):
                        col_d1, col_d2 = st.columns([2, 1])
                        with col_d1:
                            st.markdown(f"**Details:** {c.details}")
                            st.markdown(f"**BL Value:** `{c.bl_value}`")
                            st.markdown(f"**SB Value:** `{c.sb_value}`")
                        with col_d2:
                            st.markdown("**Human Override**")
                            txt_key = f"override_txt_{c.check_id}"
                            override_reason = st.text_input("Override Reason:", key=txt_key, placeholder="e.g. Known typo...")
                            
                            if st.button("Acknowledge & Override", key=f"btn_ovr_{c.check_id}", type="primary"):
                                if not override_reason:
                                    st.error("Please provide a reason to override.")
                                else:
                                    # Modify check inline
                                    c.is_overridden = True
                                    c.override_reason = override_reason
                                    # Update metrics & save
                                    report.update_metrics()
                                    save_report(report)
                                    st.success("Override applied!")
                                    st.rerun()

        with tab_audit:
            st.markdown("### All Checks")
            
            check_dicts = []
            for c in report.checks:
                status_display = c.status
                if getattr(c, "is_overridden", False):
                    status_display = f"OVERRIDDEN ({c.status})"
                    
                check_dicts.append({
                    "Category": c.category,
                    "Check": c.check_name,
                    "Status": status_display,
                    "Severity": c.severity,
                    "BL Value": c.bl_value or "-",
                    "SB Value": c.sb_value or "-",
                    "Details": c.details,
                    "Override Reason": getattr(c, "override_reason", "") or "-"
                })
            df_checks = pd.DataFrame(check_dicts)
            
            st.dataframe(
                df_checks,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Status": st.column_config.TextColumn("Status"),
                    "Severity": st.column_config.TextColumn("Severity"),
                    "BL Value": st.column_config.TextColumn("BL Value", width="medium"),
                    "SB Value": st.column_config.TextColumn("SB Value", width="medium"),
                    "Details": st.column_config.TextColumn("Details", width="large"),
                    "Override Reason": st.column_config.TextColumn("Override Reason"),
                }
            )


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
