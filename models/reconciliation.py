from pydantic import BaseModel
from typing import Any, Literal, Optional

class ReconciliationCheck(BaseModel):
    check_id: str
    check_name: str
    category: Literal[
        "IDENTIFIERS", "DOCUMENTATION", "QUANTITATIVE",
        "LOGISTICS", "CLASSIFICATION", "FINANCIAL"
    ]
    status: Literal["MATCH", "MISMATCH", "MISSING", "WARNING"]
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    bl_value: Any = None
    sb_value: Any = None
    details: str = ""
    sub_checks: list = []   # for container-level breakdowns

class ReconciliationReport(BaseModel):
    report_id: str
    generated_at: str
    bl_number: str
    sb_count: int
    total_checks: int
    match_count: int
    mismatch_count: int
    missing_count: int
    warning_count: int
    match_rate_pct: float
    checks: list[ReconciliationCheck]
    summary: str
