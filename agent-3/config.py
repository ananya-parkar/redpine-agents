# agent-3/ config.py
from pathlib import Path
BASE_DIR = Path(__file__).parent
DATA_FOLDER = BASE_DIR / "data"
OUTPUT_FOLDER = BASE_DIR / "outputs"
INPUT_FOLDER = BASE_DIR / "inputs"

US_STATE_MAP = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY"
}

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
    "family owned companies in {location}",
    "founder led companies in {location}",
    "privately held companies in {location}",
    "private businesses in {location}",
    "middle market companies in {location}",
    "companies in {location} founded more than {min_years} years ago"
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