# agent-3/ config.py
from pathlib import Path
BASE_DIR = Path(__file__).parent
DATA_FOLDER = BASE_DIR / "data"
OUTPUT_FOLDER = BASE_DIR / "outputs"
INPUT_FOLDER = BASE_DIR / "inputs"
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

RUNS_FOLDER = BASE_DIR / "runs"
OUTPUT_COLUMNS = [
    "Company Name",
    "City",
    "State",
    "Industry",
    "Revenue Estimate",
    "Founded Year",
    "Years in Business",
    "Founder Name",
    "Founder Age Estimate",
    "Founder Led",
    "Family Owned",
    "Seller Readiness Score",
    "Reason",
    "Review Status"
]

TAVILY_MAX_RESULTS = 10

UNIVERSE_SEARCH_QUERIES = [
    "family owned manufacturing companies in {location}",
    "founder led companies in {location}",
    "privately held distribution companies in {location}",
    "privately held industrial companies in {location}",
    "private services companies in {location} founded more than {min_years} years ago",
    "middle market private companies in {location}"
]

SCORED_OUTPUT_COLUMNS = [
    "Company Name",
    "Industry",
    "State",
    "Company Type",
    "Founded Year",
    "Years in Business",
    "Founder Name",
    "Founder Led",
    "Family Owned",
    "Founder Age Estimate",
    "Seller Readiness Score"
]