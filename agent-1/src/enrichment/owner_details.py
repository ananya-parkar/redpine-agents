# agent-1/src/enrichment/owner_details.py
from datetime import datetime
from typing import Dict
from src.enrichment.regrid_provider import lookup_property
import json

def detect_owner_details(address="", latitude=None, longitude=None):

    default_response = {
        "owner_name": "",
        "owner_company": "",
        "mailing_address": "",
        "owner_phone": "",
        "ownership_since": "",
        "ownership_length_years": "",
        "year_built": "",
        "is_older_than_20_years": "",
        "owner_confidence": "Low",
        "owner_evidence": "",
        "property_data": {}
    }

    if not address:
        return default_response
    
    print("=" * 80)
    print("ADDRESS RECEIVED:", address)

    feature = lookup_property(address=address, latitude=latitude, longitude=longitude)
    print("FEATURE FOUND:", feature is not None)

    if feature:
        print("HEADLINE:", feature.get("properties", {}).get("headline"))

    if not feature:
        return default_response

    props = feature.get("properties", {})
    fields = props.get("fields", {})
    print("\n================ REGRID VALUES ================")
    print("Address      :", fields.get("address"))
    print("Owner        :", fields.get("owner"))
    print("Year Built   :", fields.get("yearbuilt"))
    print("Rooms        :", fields.get("numunits"))
    print("Sale Date    :", fields.get("last_ownership_transfer_date"))
    print("==============================================\n")
    # print("\nFIELDS AVAILABLE:")
    # print(fields.keys())

    owner = fields.get("owner", "")

    mailing = " ".join(filter(None, [
        fields.get("mailadd"),
        fields.get("mail_city"),
        fields.get("mail_state2"),
        fields.get("mail_zip")
    ]))

    year_built = (
        fields.get("yearbuilt")
        or fields.get("year_built")
        or props.get("summary", {}).get("yearBuilt")
        or ""
    )
        

    sale_date = (
        fields.get("last_ownership_transfer_date")
        or fields.get("saledate")
        or fields.get("sale_date")
        or ""
    )

    room_count = (
        fields.get("numunits")
        or fields.get("number_of_units")
        or fields.get("room_count")
        or fields.get("rooms")
        or ""
    )

    owner_company = ""

    if owner and any(
        x in owner.lower()
        for x in [
            "llc",
            "inc",
            "corp",
            "trust"
        ]
    ):
        owner_company = owner

    age_flag = ""
    owner_confidence = "High" if owner else "Low"
   
    if year_built:
        try:
            year_built = int(year_built)
            age = datetime.now().year - year_built
            age_flag = "Yes" if age >= 20 else "No"

        except Exception as e:
            print("Age calculation failed:", e)
    
    print("\n======= RETURNING OWNER DATA =======")
    print("Owner:", owner)
    print("Company:", owner_company)
    print("Mailing:", mailing)
    print("Year Built:", year_built)
    print("Sale Date:", sale_date)
    print("Rooms:", room_count)
    print("===================================\n")

    return {

        "owner_name": owner,
        "owner_company": owner_company,
        "mailing_address": mailing,
        "owner_phone": "",
        "sale_trans_date": sale_date,
        "sale_search_date": sale_date,
        "year_built": year_built,
        "is_older_than_20_years": age_flag,
        "owner_confidence": owner_confidence,
        "owner_evidence": f"Retrieved from Regrid parcel {props.get('headline','')}",
        "room_count": room_count,
        "property_data": feature
    }