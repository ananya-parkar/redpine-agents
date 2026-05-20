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
REVIEW_LOOKBACK_MONTHS = int(os.getenv("REVIEW_LOOKBACK_MONTHS", "24"))