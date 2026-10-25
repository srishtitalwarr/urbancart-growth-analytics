"""Project-wide settings. Change these here, not in the SQL or the scripts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "outputs"
DELIVERABLES_DIR = ROOT / "deliverables"
CHARTS_DIR = DELIVERABLES_DIR / "charts"
DB_PATH = OUTPUT_DIR / "warehouse.duckdb"

CONTRIBUTION_MARGIN = 0.30
TEST_EMAIL_DOMAIN = "@urbancart.in"
UNKNOWN_CHANNEL = "Unknown"

PAID_CHANNELS = ["Google Ads", "Meta Ads", "Affiliate", "Influencer"]
ALL_CHANNELS = PAID_CHANNELS + ["Organic"]

PERIOD_START = "2026-01-01"
PERIOD_END = "2026-06-30"
VALID_STATUSES = ("delivered", "cancelled", "returned")

SPEND_CUT_TARGET = 0.20
# Part 2 recommendation: quarterly cuts against the Q2 2026 run-rate (₹8.68L).
RECOMMENDED_CUTS_INR = {"Meta Ads": 131_000, "Affiliate": 43_000}
