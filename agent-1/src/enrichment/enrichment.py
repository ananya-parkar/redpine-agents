# agent-1/src/enrichment/enrichment.py
from datetime import datetime
from src.enrichment.franchise_detection import detect_franchise_history
from src.enrichment.owner_details import detect_owner_details
from src.enrichment.property_age import get_property_age_flags
# from src.owner_tenure import get_owner_tenure
from src.enrichment.cmbs_lookup import detect_cmbs_signals, default_cmbs_result
from src.enrichment.attom_basicprofile import get_basic_profile
from src.enrichment.brand_matcher import detect_known_brand


def default_franchise_result():
    return {
        "franchise_affiliated": False,
        "current_brand": "",
        "former_brand": "",
        "brand_status": "NONE",
        "franchise_confidence": "Not Checked",
        "franchise_evidence": ""
    }


def default_owner_result():
    return {
        "owner_name": "",
        "owner_company": "",
        "mailing_address": "",
        "owner_phone": "",
        "owner_confidence": "Not Checked",
        "owner_evidence": "",
        "ownership_since": "",
        "ownership_length_years": "",
        "attom_year_built": "",
        "is_older_than_20_years": "",
    }


def enrich_priority_hotel(hotel_name, address, reviews=None):
    result = {}
    result.update(default_franchise_result())
    result.update(default_owner_result())
    result.update(default_cmbs_result())

    # Franchise detection
    try:
        print("    [FRANCHISE] Checking historical franchise affiliation...", flush=True)
        known_brand = detect_known_brand(hotel_name)
        if known_brand:
            result.update(known_brand)
        else:
            franchise_result = detect_franchise_history(
                hotel_name=hotel_name,
                address=address,
                reviews=reviews
            )
            result.update(franchise_result)
        
        print(
            f"    [FRANCHISE] affiliated={result['franchise_affiliated']} | "
            f"brand_status={result['brand_status']} | "
            f"current_brand={result['current_brand'] or 'N/A'} | "
            f"former_brand={result['former_brand'] or 'N/A'} | "
            f"confidence={result['franchise_confidence']}",
            flush=True
        )
    except Exception as e:
        print(f"    [FRANCHISE] Failed: {e}", flush=True)
        result.update({
            "franchise_affiliated": False,
            "current_brand": "",
            "former_brand": "",
            "brand_status": "NONE",
            "franchise_confidence": "Error",
            "franchise_evidence": str(e)
        })
    
    # Step 2: CMBS lookup (ONLY if franchise was detected)
    if result["franchise_affiliated"]:
        try:
            cmbs_result = detect_cmbs_signals(
                hotel_name=hotel_name,
                address=address
            )
            result.update(cmbs_result)
        except Exception as e:
            print(f"    [CMBS] Failed: {e}", flush=True)
            result.update({
                "cmbs_confidence": "Error",
                "cmbs_evidence": str(e)
            })
    else:
        print("    [CMBS] Skipped (no franchise affiliation detected)", flush=True)
    
    # Owner enrichment via ATTOM
    try:
        print("    [OWNER] Looking up ATTOM property details...", flush=True)
        property_lookup = detect_owner_details(address=address)
        print(
            "[OWNER LOOKUP KEYS]",
            property_lookup.keys(),
            flush=True
        )
        
        # Update with owner details
        result["owner_name"] = property_lookup.get("owner_name", "")
        result["owner_company"] = property_lookup.get("owner_company", "")
        result["mailing_address"] = property_lookup.get("mailing_address", "")
        result["owner_phone"] = property_lookup.get("owner_phone", "")
        result["owner_confidence"] = property_lookup.get("owner_confidence", "Not Checked")
        result["owner_evidence"] = property_lookup.get("owner_evidence", "")
        
        # Get property data for age and tenure calculations
        property_data = property_lookup.get("property_data", {})
        print(address)

        sale_date = (
            property_lookup.get("sale_trans_date")
            or property_lookup.get("sale_search_date")
            or ""
        )
        if not sale_date:
            print(
                "    [SALE] DetailOwner missing sale date. Trying BasicProfile...", flush=True)

            basic_profile = get_basic_profile(address)

            sale_date = (
                basic_profile.get("sale_trans_date")
                or basic_profile.get("sale_search_date")
                or ""
            )
        print(
            "    [SALE FINAL DATE]",
            sale_date,
            flush=True
        )

        ownership_years = 0
        if sale_date:
            try:
                ownership_years = (
                    datetime.now().year -
                    int(str(sale_date)[:4])
                )
            except Exception:
                ownership_years = 0
        
        result["ownership_since"] = sale_date
        result["ownership_length_years"] = ownership_years
        
        print(
            f"    [SALE] date={sale_date} | "
            f"tenure={ownership_years}",
            flush=True
        )

        # Extract year built and age flag
        age_result = get_property_age_flags(property_data)
        result["attom_year_built"] = age_result.get("year_built", "")
        result["is_older_than_20_years"] = age_result.get("is_older_than_20_years", "")
                
        print(
            f"    [OWNER] owner={result['owner_name'] or 'N/A'} | "
            f"built={result['attom_year_built'] or 'N/A'} | "
            f"20+={result['is_older_than_20_years'] or 'N/A'} | "
            f"tenure={result['ownership_length_years'] or 'N/A'}yrs",
            flush=True
        )
    except Exception as e:
        print(f"    [OWNER] Failed: {e}", flush=True)
        result.update({
            "owner_confidence": "Error",
            "owner_evidence": str(e),
            "ownership_length_years": 0,
        })

    return result