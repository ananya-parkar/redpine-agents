# agent-1/src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "inputs" / "locations.txt"
RUNS_DIR = BASE_DIR / "runs"

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER")  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

GEOCODE_URL = os.getenv("GEOCODE_URL")
NEARBY_URL = os.getenv("NEARBY_URL")
PLACE_DETAILS_URL_TEMPLATE = "https://places.googleapis.com/v1/places/{place_id}"

DISTRESS_KEYWORDS = {
    "negative": [
        "dirty", "filthy", "smell", "mold", "leak", "broken", "worst", "bad service",
        "rude", "unsafe", "cockroach", "bed bug", "refund", "noise", "stained",
        "unhygienic", "poor maintenance", "not maintained", "disappointing"
    ],
    "financial_or_operational": [
        "closed", "shut down", "understaffed", "no staff", "abandoned",
        "renovation needed", "declining", "run down", "maintenance issue"
    ]
}
# ------------------------------------------------------------------------------
# Franchise Detection Settings
# ------------------------------------------------------------------------------
FRANCHISE_BRANDS = [
   "Marriott",
   "Hilton",
   "Hyatt",
   "Holiday Inn",
   "InterContinental",
   "Crowne Plaza",
   "Staybridge Suites",
   "Candlewood Suites",
   "Best Western",
   "Wyndham",
   "Ramada",
   "Days Inn",
   "Super 8",
   "La Quinta",
   "Comfort Inn",
   "Quality Inn",
   "Sleep Inn",
   "Clarion",
   "Econo Lodge",
   "Motel 6",
   "Red Roof Inn",
   "Fairfield Inn",
   "Courtyard",
   "Residence Inn",
   "SpringHill Suites",
   "Hampton Inn",
   "DoubleTree",
   "Embassy Suites",
   "Homewood Suites",
   "Hyatt Place",
   "Hyatt House"
]
SEARCH_TIMEOUT = 30

REVIEW_LOOKBACK_MONTHS = int(os.getenv("REVIEW_LOOKBACK_MONTHS", "24"))
# Add this after DISTRESS_KEYWORDS
RENOVATION_KEYWORDS = [
    "outdated", "old", "worn", "dated", "shabby", "musty", "needs renovation",
    "run down", "needs update", "needs remodel", "tired", "aged", "weathered",
    "faded", "peeling", "cracked", "stained carpet", "old furniture",
    "needs work", "worn out", "past its prime"
]

# Add configuration for age threshold
PROPERTY_AGE_THRESHOLD_YEARS = 20

ATTOM_API_KEY = os.getenv("ATTOM_API_KEY")