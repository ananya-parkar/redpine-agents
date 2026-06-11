# agent-1/src/enrichment/brand_matcher.py
KNOWN_BRANDS = {
    "wyndham": "Wyndham",
    "hyatt": "Hyatt",
    "hilton": "Hilton",
    "marriott": "Marriott",
    "ritz-carlton": "Ritz-Carlton",
    "holiday inn": "Holiday Inn",
    "ihg": "IHG",
    "best western": "Best Western",
    "comfort": "Choice Hotels",
    "quality inn": "Choice Hotels",
    "days inn": "Wyndham",
    "super 8": "Wyndham",
    "ramada": "Wyndham",
    "curio": "Hilton",
    "hampton": "Hilton",
    "embassy suites": "Hilton",
    "doubletree": "Hilton",
}

def detect_known_brand(hotel_name):
    if not hotel_name:
        return None

    hotel_name = hotel_name.lower()

    for keyword, brand in KNOWN_BRANDS.items():
        if keyword in hotel_name:
            return {
                "franchise_affiliated": True,
                "current_brand": brand,
                "former_brand": "",
                "brand_status": "CURRENT",
                "franchise_confidence": "High",
                "franchise_evidence": f"Brand match: {brand}"
            }

    return None