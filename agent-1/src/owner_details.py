# agent-1/src/owner_details.py
import requests
from datetime import datetime
from typing import Dict

from src.config import ATTOM_API_KEY


def detect_owner_details(address: str = "") -> Dict:
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
        return {
            **default_response,
            "owner_evidence": "No address available"
        }

    try:
        address = address.replace(", USA", "").strip()

        parts = [x.strip() for x in address.split(",")]
        street = parts[0] if len(parts) > 0 else ""
        city = parts[1] if len(parts) > 1 else ""
        state_zip = parts[2] if len(parts) > 2 else ""
        address2 = f"{city}, {state_zip}".strip(", ")

        url = (
            "https://api.gateway.attomdata.com/"
            "propertyapi/v1.0.0/property/detailowner"
        )
        headers = {
            "apikey": ATTOM_API_KEY,
            "accept": "application/json"
        }
        params = {
            "address1": street,
            "address2": address2
        }

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        property_list = data.get("property", [])

        if not property_list:
            return {
                **default_response,
                "owner_evidence": "No ATTOM property match found"
            }

        property_data = property_list[0]
        print(f"[ATTOM DEBUG] property_data keys: " f"{list(property_data.keys())}", flush=True)

        owner_data = property_data.get("owner", {})
        owner1_data = owner_data.get("owner1", {})

        if isinstance(owner1_data, dict):
            owner_name = owner1_data.get("fullname", "")
        else:
            owner_name = str(owner1_data) if owner1_data else ""

        mailing = owner_data.get("mailingaddressoneline", "")

        year_built = (
            property_data.get("summary", {})
            .get("yearbuilt", "")
        )

        is_older_than_20_years = ""
        if year_built:
            try:
                current_year = datetime.now().year
                property_age = current_year - int(year_built)
                is_older_than_20_years = (
                    "Yes" if property_age >= 20 else "No"
                )
            except Exception:
                is_older_than_20_years = ""

        owner_company = ""
        if owner_name and "llc" in owner_name.lower():
            owner_company = owner_name

        return {
            "owner_name": owner_name,
            "owner_company": owner_company,
            "mailing_address": mailing,
            "owner_phone": "",
            "year_built": year_built,
            "is_older_than_20_years": is_older_than_20_years,
            "owner_confidence": "High" if owner_name else "Low",
            "owner_evidence": (
                "Retrieved from ATTOM property records"
                if owner_name else "Owner data unavailable"
            ),
            "property_data": property_data
        }

    except Exception as e:
        return {
            **default_response,
            "owner_evidence": f"ATTOM lookup failed: {str(e)}"
        }