# agent-1/src/franchise_detection.py
import re
import requests
from typing import Dict, List
from src.config import FRANCHISE_BRANDS, SEARCH_TIMEOUT

# ------------------------------------------------------------------------------
# Helper: Normalize text
# ------------------------------------------------------------------------------
def normalize_text(text: str) -> str:
   if not text:
       return ""
   return re.sub(r"\s+", " ", text).strip().lower()

# ------------------------------------------------------------------------------
# Helper: Search the web using Google search URL
# ------------------------------------------------------------------------------
def search_web(query: str) -> str:
   """
   Performs a lightweight web search by fetching Google search results page HTML.
   This does not require an additional API key, but may be rate-limited if used
   heavily. Suitable for prototype/POC usage.
   """
   url = "https://www.google.com/search"
   headers = {
       "User-Agent": (
           "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/124.0 Safari/537.36"
       )
   }
   response = requests.get(
       url,
       params={"q": query},
       headers=headers,
       timeout=SEARCH_TIMEOUT
   )
   response.raise_for_status()
   # Remove HTML tags to get searchable plain text
   html = response.text
   text = re.sub(r"<[^>]+>", " ", html)
   text = re.sub(r"\s+", " ", text)
   return text

# ------------------------------------------------------------------------------
# Helper: Detect franchise brand from text
# ------------------------------------------------------------------------------
def detect_brand(text: str) -> List[str]:
   """
   Returns a list of matching franchise brands found in the search text.
   """
   normalized = normalize_text(text)
   matches = []
   for brand in FRANCHISE_BRANDS:
       if brand.lower() in normalized:
           matches.append(brand)
   return matches

# ------------------------------------------------------------------------------
# Main function: Detect if hotel was previously franchised
# ------------------------------------------------------------------------------
def detect_franchise_history(hotel_name: str, address: str = "") -> Dict:
   """
   Determines whether a hotel was previously affiliated with a known franchise.
   """
   queries = [
       f'"{hotel_name}" formerly hotel',
       f'"{hotel_name}" previous brand',
       f'"{hotel_name}" rebranded from',
       f'"{hotel_name}" was a Marriott',
       f'"{hotel_name}" was a Hilton',
       f'"{hotel_name}" former franchise'
   ]
   if address:
       queries.insert(0, f'"{hotel_name}" "{address}" former brand')
   evidence = []
   detected_brands = []
   for query in queries:
       try:
           search_text = search_web(query)
           brands = detect_brand(search_text)
           if brands:
               detected_brands.extend(brands)
               evidence.append(f"Query matched: {query}")
       except Exception as e:
           evidence.append(f"Search failed for '{query}': {e}")
   # Remove duplicates while preserving order
   unique_brands = []
   for brand in detected_brands:
       if brand not in unique_brands:
           unique_brands.append(brand)
   if unique_brands:
       confidence = "High" if len(unique_brands) >= 2 else "Medium"
       return {
           "was_franchise": True,
           "former_brand": unique_brands[0],
           "franchise_confidence": confidence,
           "franchise_evidence": " | ".join(evidence[:5])
       }
   return {
       "was_franchise": False,
       "former_brand": "",
       "franchise_confidence": "Low",
       "franchise_evidence": "No franchise affiliation detected"
   }