"""Generate HTML and JSON reconciliation reports."""
import json
import io
import pandas as pd
from jinja2 import Template
from datetime import datetime
from models.reconciliation import ReconciliationReport
from config import APP_NAME, APP_VERSION

STATUS_EMOJI = {"MATCH": "✅", "MISMATCH": "❌", "MISSING": "⚠️", "WARNING": "⚠️"}
STATUS_COLOR = {
    "MATCH": "#dcfce7", "MISMATCH": "#fee2e2",
    "MISSING": "#f1f5f9", "WARNING": "#fef3c7"
}
STATUS_TEXT_COLOR = {
    "MATCH": "#166534", "MISMATCH": "#991b1b",
    "MISSING": "#475569", "WARNING": "#92400e"
}

REPORT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TradeProof Reconciliation Report — {{ report.bl_number }}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #1e293b; background: #f8fafc; }
  .header { background: #0f172a; color: white; padding: 24px 32px; display: flex; justify-content: space-between; align-items: center; }
  .header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
  .header h1 span { color: #38bdf8; }
  .header-meta { text-align: right; font-size: 11px; opacity: 0.7; line-height: 1.8; }
  .container { max-width: 1100px; margin: 0 auto; padding: 28px 20px; }
  .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
  .metric-card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; text-align: center; }
  .metric-card .label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
  .metric-card .value { font-size: 28px; font-weight: 700; }
  .match-rate { background: #0f172a; color: white; border-radius: 10px; padding: 16px 24px; margin-bottom: 24px; }
  .match-rate .summary-text { font-size: 15px; line-height: 1.6; }
  .match-rate .rate { font-size: 36px; font-weight: 800; color: #38bdf8; float: right; }
  table { width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; margin-bottom: 24px; }
  th { background: #1e293b; color: white; padding: 10px 14px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
  td { padding: 10px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; font-size: 12px; line-height: 1.5; }
  .status-badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .section-header { font-size: 14px; font-weight: 700; color: #0f172a; background: #f1f5f9; padding: 10px 14px; border-left: 4px solid #0ea5e9; }
  .footer { text-align: center; font-size: 11px; color: #94a3b8; padding: 20px; margin-top: 16px; border-top: 1px solid #e2e8f0; }
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>⚓ Trade<span>Proof</span></h1>
    <div style="font-size:12px;margin-top:4px;opacity:0.7;">Intelligent Trade Document Reconciliation</div>
  </div>
  <div class="header-meta">
    Report ID: {{ report.report_id }}<br>
    BL No.: {{ report.bl_number }}<br>
    SBs Reconciled: {{ report.sb_count }}<br>
    Generated: {{ report.generated_at }}
  </div>
</div>

<div class="container">
  <div class="match-rate">
    <div class="rate">{{ report.match_rate_pct }}%</div>
    <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;">Match Rate</div>
    <div class="summary-text">{{ report.summary }}</div>
  </div>

  <div class="summary-grid">
    <div class="metric-card"><div class="label">Total Checks</div><div class="value" style="color:#1e293b">{{ report.total_checks }}</div></div>
    <div class="metric-card"><div class="label">✅ Matches</div><div class="value" style="color:#16a34a">{{ report.match_count }}</div></div>
    <div class="metric-card"><div class="label">❌ Mismatches</div><div class="value" style="color:#dc2626">{{ report.mismatch_count }}</div></div>
    <div class="metric-card"><div class="label">⚠️ Warnings / Missing</div><div class="value" style="color:#d97706">{{ report.warning_count + report.missing_count }}</div></div>
  </div>

  {% set categories = checks | groupby('category') %}
  {% for category, items in categories %}
  <div class="section-header">{{ category }}</div>
  <table>
    <tr>
      <th style="width:5%">#</th>
      <th style="width:20%">Check</th>
      <th style="width:10%">Status</th>
      <th style="width:8%">Severity</th>
      <th style="width:24%">BL Value</th>
      <th style="width:24%">SB Value</th>
      <th style="width:9%">Details</th>
    </tr>
    {% for c in items %}
    <tr style="background: {{ status_bg[c.status] }}">
      <td>{{ loop.index }}</td>
      <td><strong>{{ c.check_name }}</strong></td>
      <td>
        <span class="status-badge" style="background:{{ status_badge_bg[c.status] }};color:{{ status_badge_text[c.status] }}">
          {{ status_emoji[c.status] }} {{ c.status }}
        </span>
      </td>
      <td style="font-size:11px;font-weight:600">{{ c.severity }}</td>
      <td style="font-family:monospace;word-break:break-all">{{ c.bl_value or '—' }}</td>
      <td style="font-family:monospace;word-break:break-all">{{ c.sb_value or '—' }}</td>
      <td style="font-size:11px;color:#475569">{{ c.details }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endfor %}

  <div class="footer">
    Generated by <strong>TradeProof {{ version }}</strong> — Powered by Google Gemini AI<br>
    This report is auto-generated and intended for internal reconciliation use only.
  </div>
</div>
</body>
</html>
"""

def generate_html_report(report: ReconciliationReport) -> str:
    template = Template(REPORT_HTML)
    return template.render(
        report=report,
        checks=report.checks,
        status_emoji=STATUS_EMOJI,
        status_bg=STATUS_COLOR,
        status_badge_bg={
            "MATCH": "#dcfce7", "MISMATCH": "#fee2e2",
            "MISSING": "#e2e8f0", "WARNING": "#fef3c7"
        },
        status_badge_text=STATUS_TEXT_COLOR,
        version=APP_VERSION
    )

def generate_json_report(report: ReconciliationReport) -> str:
    return report.model_dump_json(indent=2)

def generate_excel_report(report: ReconciliationReport) -> bytes:
    """Generate a formatted Excel report from the reconciliation results."""
    # Convert checks to a DataFrame
    check_dicts = []
    for c in report.checks:
        check_dicts.append({
            "Category": c.category,
            "Check": c.check_name,
            "Status": c.status,
            "Severity": c.severity,
            "BL Value": str(c.bl_value) if c.bl_value is not None else "-",
            "SB Value": str(c.sb_value) if c.sb_value is not None else "-",
            "Details": c.details
        })
    df = pd.DataFrame(check_dicts)
    
    # Write to BytesIO
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Audit Report', index=False)
        
        # Get workbook and worksheet objects
        workbook  = writer.book
        worksheet = writer.sheets['Audit Report']
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': False,
            'valign': 'top',
            'fg_color': '#0B2447',
            'font_color': 'white',
            'border': 1
        })
        
        match_format = workbook.add_format({'bg_color': '#dcfce7', 'font_color': '#166534'})
        mismatch_format = workbook.add_format({'bg_color': '#fee2e2', 'font_color': '#991b1b'})
        warning_format = workbook.add_format({'bg_color': '#fef3c7', 'font_color': '#92400e'})
        missing_format = workbook.add_format({'bg_color': '#e2e8f0', 'font_color': '#475569'})
        
        # Write column headers with formatting
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        # Set column widths
        worksheet.set_column('A:B', 25)
        worksheet.set_column('C:D', 15)
        worksheet.set_column('E:F', 30)
        worksheet.set_column('G:G', 45)
        
        # Apply conditional formatting to the "Status" column (Column C)
        worksheet.conditional_format('C2:C1000', {'type': 'cell', 'criteria': '==', 'value': '"MATCH"', 'format': match_format})
        worksheet.conditional_format('C2:C1000', {'type': 'cell', 'criteria': '==', 'value': '"MISMATCH"', 'format': mismatch_format})
        worksheet.conditional_format('C2:C1000', {'type': 'cell', 'criteria': '==', 'value': '"WARNING"', 'format': warning_format})
        worksheet.conditional_format('C2:C1000', {'type': 'cell', 'criteria': '==', 'value': '"MISSING"', 'format': missing_format})
        
    return output.getvalue()
