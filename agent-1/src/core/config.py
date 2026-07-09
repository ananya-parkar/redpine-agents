# agent-1/src/core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_FOLDER = BASE_DIR / "inputs"
INPUT_FILE = INPUT_FOLDER / "agent1_search_request.xlsx"
RUNS_DIR = BASE_DIR / "runs"

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER")  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEOCODE_URL = os.getenv("GEOCODE_URL")
NEARBY_URL = os.getenv("NEARBY_URL")
PLACE_DETAILS_URL_TEMPLATE = "https://places.googleapis.com/v1/places/{place_id}"

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB_AGENT1")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

DISTRESS_SCORE_THRESHOLD = 7  

DISTRESS_KEYWORDS = {
    "negative": [
        "dirty", "filthy", "smell", "mold", "leak", "broken", "worst", "bad service",
        "rude", "unsafe", "cockroach", "bed bug", "refund", "noise", "stained",
        "unhygienic", "poor maintenance", "not maintained", "disappointing"
    ],
    "financial_or_operational": [
        "shut down",
        "abandoned",
        "renovation needed",
        "run down",
        "maintenance issue"
    ]
}
# ------------------------------------------------------------------------------
# Franchise Detection Settings
# ------------------------------------------------------------------------------

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
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM_AGENT1")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD_AGENT1")
EMAIL_TO = os.getenv("EMAIL_TO")

PRICE_TIER_MAPPING = {

    "Wyndham": "Economy",
    "G6": "Economy",
    "Choice": "Economy",
    "Red Roof": "Economy",

    "Best Western": "Midscale",
    "IHG": "Midscale",

    "Marriott": "Upscale",
    "Hilton": "Upscale",
    "Hyatt": "Upscale"
}