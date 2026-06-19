# agent-3/ config.py
from pathlib import Path
BASE_DIR = Path(__file__).parent
DATA_FOLDER = BASE_DIR / "data"
OUTPUT_FOLDER = BASE_DIR / "outputs"
INPUT_FOLDER = BASE_DIR / "inputs"
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
    "private companies in {location}",
    "largest private companies in {location}",
    "family owned businesses in {location}",
    "privately held companies in {location}",
    "companies headquartered in {location}",
    "business directory {location}",
    "top private employers in {location}",
    "companies based in {location}"
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