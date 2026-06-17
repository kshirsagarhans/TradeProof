from pydantic import BaseModel
from typing import Any, Literal, Optional

class ReconciliationCheck(BaseModel):
    check_id: str
    check_name: str
    category: Literal[
        "IDENTIFIERS", "DOCUMENTATION", "QUANTITATIVE",
        "LOGISTICS", "CLASSIFICATION", "FINANCIAL", "PHYSICAL VERIFICATION"
    ]
    status: Literal["MATCH", "MISMATCH", "MISSING", "WARNING"]
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    bl_value: Any = None
    sb_value: Any = None
    details: str = ""
    sub_checks: list = []   # for container-level breakdowns
    is_overridden: bool = False
    override_reason: Optional[str] = None

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
    port_of_loading_lat: Optional[float] = None
    port_of_loading_lon: Optional[float] = None
    port_of_discharge_lat: Optional[float] = None
    port_of_discharge_lon: Optional[float] = None
    checks: list[ReconciliationCheck]
    summary: str
    
    def update_metrics(self):
        """Recalculate metrics based on current checks (e.g., after an override)."""
        self.total_checks = len(self.checks)
        self.match_count = sum(1 for c in self.checks if c.status == "MATCH" or c.is_overridden)
        self.mismatch_count = sum(1 for c in self.checks if c.status == "MISMATCH" and not c.is_overridden)
        self.missing_count = sum(1 for c in self.checks if c.status == "MISSING" and not c.is_overridden)
        self.warning_count = sum(1 for c in self.checks if c.status == "WARNING" and not c.is_overridden)
        
        if self.total_checks > 0:
            self.match_rate_pct = round((self.match_count / self.total_checks) * 100, 1)
        else:
            self.match_rate_pct = 0.0
            
        if self.mismatch_count == 0 and self.missing_count == 0:
            self.summary = f"✅ Clean reconciliation: {self.match_count}/{self.total_checks} checks passed with {self.warning_count} warning(s)."
        elif self.mismatch_count > 0:
            self.summary = f"❌ {self.mismatch_count} mismatch(es) found across {self.total_checks} checks. Immediate review required."
        else:
            self.summary = f"⚠️ {self.missing_count} missing field(s) detected. {self.match_count} checks passed."
