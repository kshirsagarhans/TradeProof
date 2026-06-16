import sys

with open("app.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_main = False
for i, line in enumerate(lines):
    # Insert database imports at line 18
    if "from core.reporter import" in line:
        new_lines.append(line)
        new_lines.append("from core.database import init_db, save_report, get_all_reports, get_report_by_id\n")
        continue
        
    # Insert init_db() after set_page_config
    if "st.set_page_config(" in line:
        new_lines.append(line)
        continue
    if "initial_sidebar_state=" in line:
        new_lines.append(line)
        new_lines.append(")\n")
        new_lines.append("init_db()  # Initialize database\n")
        continue
    if line.strip() == ")" and "init_db" in new_lines[-1]:
        # we already closed it
        continue
        
    # Insert save_report at line 145
    if "st.session_state[\"report\"] = report" in line:
        new_lines.append(line)
        new_lines.append("        save_report(report)\n")
        continue

    # Setup the tabs right before File Uploads
    if "# ── File Uploads " in line:
        new_lines.append("# ── Main Layout ───────────────────────────────────────────────────────────────\n")
        new_lines.append("tab_new_audit, tab_history = st.tabs([\"🚀 New Audit\", \"🗄️ Past Audits\"])\n\n")
        new_lines.append("with tab_new_audit:\n")
        new_lines.append("    " + line)
        in_main = True
        continue
        
    if "st.divider()" in line and "st.markdown(\"<p style='text-align" in lines[min(i+1, len(lines)-1)]:
        # End of the file, we can break out
        in_main = False
        # Add the history tab
        new_lines.append("\nwith tab_history:\n")
        new_lines.append("    st.markdown(\"### 🗄️ Past Vessel Clearance Audits\")\n")
        new_lines.append("    past_reports = get_all_reports()\n")
        new_lines.append("    if not past_reports:\n")
        new_lines.append("        st.info(\"No past audits found. Run your first audit to see history here!\")\n")
        new_lines.append("    else:\n")
        new_lines.append("        df_history = pd.DataFrame(past_reports)\n")
        new_lines.append("        st.dataframe(df_history, use_container_width=True)\n")
        new_lines.append("        st.divider()\n")
        new_lines.append("        st.markdown(\"**Load Past Audit**\")\n")
        new_lines.append("        selected_id = st.selectbox(\"Select Report ID to load\", [r[\"report_id\"] for r in past_reports])\n")
        new_lines.append("        if st.button(\"Load Audit\", type=\"primary\"):\n")
        new_lines.append("            st.session_state[\"report\"] = get_report_by_id(selected_id)\n")
        new_lines.append("            st.rerun()\n\n")

    if in_main:
        if line.strip() == "":
            new_lines.append("\n")
        else:
            new_lines.append("    " + line)
    else:
        new_lines.append(line)

with open("app.py", "w") as f:
    f.writelines(new_lines)

print("app.py refactored successfully.")
