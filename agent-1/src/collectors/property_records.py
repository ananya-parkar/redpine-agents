# agent-1/src/collectors/property_records.py
import re
from difflib import SequenceMatcher
from typing import Dict

ADDRESS_ABBREVIATIONS = {
    "street": "st",
    "st.": "st",
    "avenue": "ave",
    "ave.": "ave",
    "road": "rd",
    "rd.": "rd",
    "boulevard": "blvd",
    "blvd.": "blvd",
    "drive": "dr",
    "dr.": "dr",
    "lane": "ln",
    "ln.": "ln",
    "court": "ct",
    "ct.": "ct",
    "circle": "cir",
    "cir.": "cir",
    "highway": "hwy",
    "parkway": "pkwy",
    "suite": "ste",
    "ste.": "ste",
}

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[,#]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_street(address: str) -> str:
    if not address:
        return ""

    # Google address format:
    # Street, City, State ZIP, USA
    street = address.split(",")[0]

    return normalize_address(street)

def normalize_address(address: str) -> str:
    text = normalize_text(address)
    parts = text.split()
    normalized_parts = [ADDRESS_ABBREVIATIONS.get(part, part) for part in parts]
    normalized = " ".join(normalized_parts)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()

def address_similarity(a: str, b: str) -> int:
    if not a or not b:
        return 0
    
    street_a = extract_street(a)
    street_b = extract_street(b)

    if street_a == street_b:
        return 100

    return int(
        SequenceMatcher(
            None,
            street_a,
            street_b
        ).ratio() * 100
    )

def default_property_record_result() -> Dict:
    return {
        "property_match_found": False,
        "property_match_confidence": "Not Checked",
        "property_record_source": "",
        "property_record_address": "",
        "property_record_owner_hint": "",
        "property_record_match_score": 0,
        "property_record_evidence": "",
    }

def match_property_record(hotel_name: str, address: str = "") -> Dict:
    result = default_property_record_result()

    if not hotel_name and not address:
        result["property_record_evidence"] = "Missing hotel name and address"
        return result

    normalized_hotel = normalize_text(hotel_name)
    normalized_address = normalize_address(address)

    if not normalized_address:
        result["property_match_confidence"] = "Low"
        result["property_record_evidence"] = "No address available for property-record matching"
        return result

    result.update({
        "property_match_found": True,
        "property_match_confidence": "Prototype",
        "property_record_source": "Address normalization prototype",
        "property_record_address": normalized_address,
        "property_record_owner_hint": "",
        "property_record_match_score": 100,
        "property_record_evidence": (
            f"Prototype property match generated from normalized address for "
            f"'{normalized_hotel or hotel_name}'"
        ),
    })
    return result