"""String normalization and fuzzy matching utilities."""
import difflib
import re
from config import FUZZY_MATCH_THRESHOLD

def normalize_string(text: str) -> str:
    """Uppercase, strip whitespace, remove extra spaces."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', str(text).upper().strip())

def fuzzy_match(s1: str, s2: str, threshold: float = FUZZY_MATCH_THRESHOLD) -> tuple[bool, float]:
    """Returns (is_match, similarity_ratio)."""
    if not s1 and not s2:
        return True, 1.0
    if not s1 or not s2:
        return False, 0.0
    n1, n2 = normalize_string(s1), normalize_string(s2)
    if n1 == n2:
        return True, 1.0
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold, round(ratio, 3)

def normalize_weight(value: float, unit: str) -> float:
    """Normalize all weights to KG for comparison."""
    if value is None:
        return 0.0
    unit = (unit or "KG").upper().strip()
    conversions = {
        "KG": 1.0, "KGS": 1.0, "KILOGRAM": 1.0, "KILOGRAMS": 1.0,
        "MT": 1000.0, "MTS": 1000.0, "METRIC TON": 1000.0,
        "LB": 0.453592, "LBS": 0.453592, "POUND": 0.453592,
        "G": 0.001, "GM": 0.001, "GRAM": 0.001,
    }
    return value * conversions.get(unit, 1.0)

def parse_date_normalize(date_str: str) -> str:
    """Attempt to normalize date strings to DD/MM/YYYY."""
    if not date_str:
        return ""
    # Try common formats
    import datetime
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%B %d, %Y", "%d %b %Y"]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).strftime("%d/%m/%Y")
        except:
            pass
    return date_str.strip().upper()
