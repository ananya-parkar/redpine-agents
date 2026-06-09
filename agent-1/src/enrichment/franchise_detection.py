# agent-1/src/enrichment/franchise_detection.py
import re
import requests
from typing import Dict, List
from src.core.config import SEARCH_TIMEOUT, TAVILY_API_KEY, FRANCHISE_KEYWORDS
from tavily import TavilyClient
TAVILY_CLIENT = TavilyClient(api_key=TAVILY_API_KEY)
# ------------------------------------------------------------------------------
# Helper: Normalize text
# ------------------------------------------------------------------------------
def normalize_text(text: str) -> str:
   if not text:
       return ""
   return re.sub(r"\s+", " ", text).strip().lower()

# ------------------------------------------------------------------------------
# Helper: Search the web using Tavily search API
# ------------------------------------------------------------------------------
def search_web(query: str) -> str:
    """
    Search web using Tavily API.
    Returns combined textual evidence.
    """

    response = TAVILY_CLIENT.search(
        query=query,
        search_depth="ADVANCED",
        max_results=8
    )

    results = response.get("results", [])

    combined_text = []

    for result in results:
        title = result.get("title", "")
        content = result.get("content", "")

        combined_text.append(title)
        combined_text.append(content)

    return " ".join(combined_text)
# ------------------------------------------------------------------------------
# Helper: Detect franchise brand from text
# ------------------------------------------------------------------------------
def detect_brand(text: str) -> List[str]:
   """
   Returns a list of matching franchise brands found in the search text.
   """
   normalized = normalize_text(text)
   matches = []

   for parent_brand, keywords in FRANCHISE_KEYWORDS.items():
       for keyword in keywords:
           if keyword.lower() in normalized:
               matches.append(parent_brand)

   return list(set(matches))
# ------------------------------------------------------------------------------
# Main function: Detect if hotel was previously franchised
# ------------------------------------------------------------------------------

def detect_franchise_history(hotel_name: str, address: str = "", reviews=None) -> Dict:
        hotel_lower = hotel_name.lower()
        KNOWN_BRANDS = {
            "ritz-carlton": "Ritz-Carlton",
            "marriott": "Marriott",
            "hilton": "Hilton",
            "curio": "Hilton",
            "hyatt": "Hyatt",
            "wyndham": "Wyndham",
            "holiday inn": "Holiday Inn",
            "ihg": "IHG",
            "hampton": "Hilton",
            "doubletree": "Hilton",
            "embassy suites": "Hilton",
            "homewood suites": "Hilton",
            "courtyard": "Marriott",
            "residence inn": "Marriott",
            "fairfield": "Marriott",
            "westin": "Marriott",
            "sheraton": "Marriott",
            "loews": "Loews",
            "curio collection": "Hilton",
            "canopy": "Hilton",
            "waldorf": "Hilton",
            "conrad": "Hilton",

            "jw marriott": "Marriott",
            "autograph": "Marriott",
            "tribute portfolio": "Marriott",

            "kimpton": "IHG",
            "crowne plaza": "IHG",
            "avid": "IHG",

            "choice": "Choice",
            "comfort inn": "Choice",
            "quality inn": "Choice",

            "best western": "Best Western"

        }

        for keyword, brand in KNOWN_BRANDS.items():
            
            if keyword in hotel_lower:
                return {
                    "franchise_affiliated": True,
                    "current_brand": brand,
                    "former_brand": "",
                    "brand_status": "CURRENT",
                    "franchise_confidence": "High",
                    "franchise_evidence": f"Direct brand match: {keyword}"
                }
            
        review_text = " ".join(
            (
                r.get("text", {}).get("text", "")
                if isinstance(r.get("text"), dict)
                else str(r.get("text", ""))
            )
            for r in (reviews or [])
        ).lower()

        normalized_name = normalize_text(hotel_name)

        for parent_brand, keywords in FRANCHISE_KEYWORDS.items():

            for keyword in keywords:

                if keyword.lower() in normalized_name:

                    return {
                        "franchise_affiliated": True,
                        "current_brand": parent_brand,
                        "former_brand": "",
                        "brand_status": "CURRENT",
                        "franchise_confidence": "High",
                        "franchise_evidence":
                            f"Direct hotel-name franchise match: {keyword}"
                    }

    # ------------------------------------------------------------------
    # FORMER franchise / debranding detection from reviews
    # ------------------------------------------------------------------

        debrand_keywords = [
            "no longer branded",
            "used to be",
            "formerly",
            "rebranded"
        ]
        

        if any(k in review_text for k in debrand_keywords):

            for parent_brand, keywords in FRANCHISE_KEYWORDS.items():

                for keyword in keywords:

                    if keyword.lower() in review_text:

                        

                        return {
                            "franchise_affiliated": True,
                            "current_brand": "",
                            "former_brand": parent_brand,
                            "brand_status": "FORMER",
                            "franchise_confidence": "Medium",
                            "franchise_evidence":
                                f"Detected franchise loss from reviews: {keyword}"
                        }
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
            return {
                "franchise_affiliated": True,
                "current_brand": unique_brands[0],
                "former_brand": "",
                "brand_status": "CURRENT",
                "franchise_confidence": "High",
                "franchise_evidence": " | ".join(evidence[:5])
            }
        return {
            "franchise_affiliated": False,
            "current_brand": "",
            "former_brand": "",
            "brand_status": "NONE",
            "franchise_confidence": "Low",
            "franchise_evidence": "No franchise affiliation detected"
        }