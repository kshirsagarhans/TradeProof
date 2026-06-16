import os
from dotenv import load_dotenv
load_dotenv()

# ── App Identity ──────────────────────────────────────────────────
APP_NAME = "TradeProof"
APP_VERSION = "1.0.0-MVP"
APP_TAGLINE = "Intelligent Trade Document Reconciliation"
APP_EMOJI = "⚓"

# ── Gemini Settings ───────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-2.0-flash"
FALLBACK_MODEL = "gemini-1.5-pro"
MAX_RETRIES = 2

# ── Reconciliation Thresholds ─────────────────────────────────────
FUZZY_MATCH_THRESHOLD = 0.85       # 85% string similarity for identifiers
HS_DESCRIPTION_THRESHOLD = 0.90   # 90% for HS code descriptions
WEIGHT_TOLERANCE_PCT = 0.005       # 0.5% tolerance for gross weight
PKG_TOLERANCE = 0                  # Exact match for package counts

# ── File Constraints ──────────────────────────────────────────────
MAX_SB_FILES = 10
MAX_FILE_SIZE_MB = 20
SUPPORTED_TYPES = ["pdf"]

# ── Status Labels ─────────────────────────────────────────────────
STATUS_MATCH = "MATCH"
STATUS_MISMATCH = "MISMATCH"
STATUS_MISSING = "MISSING"
STATUS_WARNING = "WARNING"

# ── UI Colors ─────────────────────────────────────────────────────
COLOR_MATCH = "#22c55e"
COLOR_MISMATCH = "#ef4444"
COLOR_WARNING = "#f59e0b"
COLOR_MISSING = "#94a3b8"
