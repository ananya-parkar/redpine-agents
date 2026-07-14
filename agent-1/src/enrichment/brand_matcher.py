# agent-1/src/enrichment/brand_matcher.py

KNOWN_BRANDS = {
    # Marriott
    "marriott": "Marriott",
    "courtyard": "Marriott",
    "fairfield": "Marriott",
    "residence inn": "Marriott",
    "towneplace": "Marriott",
    "aloft": "Marriott",
    "westin": "Marriott",
    "jw marriott": "Marriott",
    "renaissance": "Marriott",
    "delta hotels": "Marriott",
    "moxy": "Marriott",
    "springhill": "Marriott",
    "element": "Marriott",
    "ritz-carlton": "Marriott",
    "st. regis": "Marriott",
    "sheraton": "Marriott",
    "le meridien": "Marriott",
    "tribute portfolio": "Marriott",
    "autograph collection": "Marriott",

    # Hilton
    "hilton": "Hilton",
    "hampton": "Hilton",
    "doubletree": "Hilton",
    "embassy suites": "Hilton",
    "homewood": "Hilton",
    "home2": "Hilton",
    "curio": "Hilton",
    "tru": "Hilton",
    "tapestry": "Hilton",
    "canopy": "Hilton",
    "waldorf": "Hilton",
    "conrad": "Hilton",

    # IHG
    "holiday inn": "IHG",
    "avid": "IHG",
    "candlewood": "IHG",
    "staybridge": "IHG",
    "crowne plaza": "IHG",
    "hotel indigo": "IHG",
    "intercontinental": "IHG",
    "voco": "IHG",
    "kimpton": "IHG",

    # Wyndham
    "wyndham": "Wyndham",
    "days inn": "Wyndham",
    "super 8": "Wyndham",
    "ramada": "Wyndham",
    "travelodge": "Wyndham",
    "baymont": "Wyndham",
    "microtel": "Wyndham",
    "la quinta": "Wyndham",
    "americinn": "Wyndham",
    "hawthorn": "Wyndham",
    "howard johnson": "Wyndham",
    "motel 6": "Motel 6",

    # Choice
    "comfort": "Choice Hotels",
    "comfort suites": "Choice Hotels",
    "comfort inn": "Choice Hotels",
    "quality inn": "Choice Hotels",
    "sleep inn": "Choice Hotels",
    "econo lodge": "Choice Hotels",
    "rodeway": "Choice Hotels",
    "clarion": "Choice Hotels",
    "mainstay": "Choice Hotels",
    "suburban": "Choice Hotels",
    "woodspring": "Choice Hotels",

    # Best Western
    "best western": "Best Western",
    "glo": "Best Western",
    "glō": "Best Western",
    "surestay": "Best Western",
}

def detect_known_brand(hotel_name):
    if not hotel_name:
        return None

    hotel_name = hotel_name.lower()

    for keyword, brand in sorted(KNOWN_BRANDS.items(), key=lambda x: len(x[0]), reverse=True):
        if keyword in hotel_name:
            return {
                "franchise_affiliated": True,
                "current_brand": brand,
                "former_brand": "",
                "brand_status": "CURRENT",
                "franchise_loss_date": "",
                "franchise_confidence": "High",
                "franchise_evidence": f"Brand match: {brand}",
            }

    return None