"""Database operations for TradeProof Audit History."""
import sqlite3
import json
from models.reconciliation import ReconciliationReport

DB_PATH = "tradeproof.db"

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id TEXT PRIMARY KEY,
            generated_at TEXT,
            bl_number TEXT,
            match_rate_pct REAL,
            mismatch_count INTEGER,
            full_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_report(report: ReconciliationReport):
    """Save a reconciliation report to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO reports 
        (report_id, generated_at, bl_number, match_rate_pct, mismatch_count, full_json)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        report.report_id,
        report.generated_at,
        report.bl_number,
        report.match_rate_pct,
        report.mismatch_count,
        report.model_dump_json()
    ))
    conn.commit()
    conn.close()

def get_all_reports() -> list[dict]:
    """Retrieve metadata for all past reports."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT report_id, generated_at, bl_number, match_rate_pct, mismatch_count 
        FROM reports 
        ORDER BY generated_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_report_by_id(report_id: str) -> ReconciliationReport | None:
    """Retrieve a full report by its ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT full_json FROM reports WHERE report_id = ?', (report_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return ReconciliationReport.model_validate_json(row[0])
    return None
