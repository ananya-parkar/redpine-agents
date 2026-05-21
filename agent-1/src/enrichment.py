# agent-1/src/enrichment.py
from src.franchise_detection import detect_franchise_history
from src.property_records import match_property_record, default_property_record_result

def default_franchise_result():
    return {
        "was_franchise": False,
        "former_brand": "",
        "franchise_confidence": "Not Checked",
        "franchise_evidence": ""
    }

def enrich_priority_hotel(hotel_name, address):
    result = {}
    result.update(default_franchise_result())
    result.update(default_property_record_result())

    try:
        print("    [FRANCHISE] Checking historical franchise affiliation...", flush=True)
        franchise_result = detect_franchise_history(
            hotel_name=hotel_name,
            address=address
        )
        result.update(franchise_result)
        print(
            f"    [FRANCHISE] was_franchise={result['was_franchise']} | "
            f"former_brand={result['former_brand'] or 'N/A'} | "
            f"confidence={result['franchise_confidence']}",
            flush=True
        )
    except Exception as e:
        print(f"    [FRANCHISE] Failed: {e}", flush=True)
        result.update({
            "was_franchise": False,
            "former_brand": "",
            "franchise_confidence": "Error",
            "franchise_evidence": str(e)
        })
    
    try:
        print("    [PROPERTY] Cross-referencing public property record...", flush=True)
        property_result = match_property_record(
            hotel_name=hotel_name,
            address=address
        )
        result.update(property_result)
        print(
            f"    [PROPERTY] match_found={result['property_match_found']} | "
            f"confidence={result['property_match_confidence']} | "
            f"match_score={result['property_record_match_score']}",
            flush=True
        )
    except Exception as e:
        print(f"    [PROPERTY] Failed: {e}", flush=True)
        result.update({
            "property_match_found": False,
            "property_match_confidence": "Error",
            "property_record_source": "",
            "property_record_address": "",
            "property_record_owner_hint": "",
            "property_record_match_score": 0,
            "property_record_evidence": str(e),
        })

    return result