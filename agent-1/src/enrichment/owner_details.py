# agent-1/src/enrichment/owner_details.py
import requests
import re
from datetime import datetime
from typing import Dict
from src.core.config import ATTOM_API_KEY

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

        if len(parts) < 3:
            return {
                **default_response,
                "owner_evidence": f"Invalid address format: {address}"
            }

        street = ""

        for part in parts:
            if re.match(r"^\d+", part.strip()):
                street = part.strip()
                break

        if not street:
            return {
                **default_response,
                "owner_evidence": f"No street address found: {address}"
            }
        
        if not re.match(r"^\d+", street):
            return {
                **default_response,
                "owner_evidence": f"Could not identify street address: {address}"
            }

        city = parts[-2]
        state_zip = parts[-1]

        address2 = f"{city}, {state_zip}"

        print(
            f"[ATTOM REQUEST] address1={street} | address2={address2}",
            flush=True
        )

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
        sale = property_data.get("sale", {})
        sale_date = (sale.get("saleTransDate") or sale.get("saleSearchDate") or "")
        sale_search_date = sale.get("saleSearchDate", "")
        print(
            "[ATTOM SALE DATE]",
            sale_date,
            flush=True
        )

        owner_data = property_data.get("owner", {})
        print(
            "[ATTOM OWNER SECTION]",
            owner_data,
            flush=True
        )
        print(
            "[ATTOM PROPERTY RAW]",
            property_data,
            flush=True
        )
        owner1_data = owner_data.get("owner1", {})
        print(
            "[ATTOM OWNER1 SECTION]",
            owner1_data,
            flush=True
        )

        if isinstance(owner1_data, dict):
            owner_name = owner1_data.get("fullname", "")
        else:
            owner_name = str(owner1_data) if owner1_data else ""

        mailing = owner_data.get("mailingaddressoneline", "")
        summary = property_data.get("summary", {})

        year_built = (
            summary.get("yearBuilt")
            or summary.get("yearbuilt")
            or ""
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

        building_summary = (
            property_data
                .get("building", {})
                .get("summary", {})
        )
        
        room_count = (
            building_summary.get("unitsCount")
            or building_summary.get("unitscount")
            or ""
        )

        print(
            "[ATTOM ROOM COUNT]",
            room_count
        )

        return {
            "owner_name": owner_name,
            "owner_company": owner_company,
            "mailing_address": mailing,
            "owner_phone": "",
            "sale_trans_date": sale_date,
            "sale_search_date": sale_search_date,
            "year_built": year_built,
            "is_older_than_20_years": is_older_than_20_years,
            "owner_confidence": "High" if owner_name else "Low",
            "room_count": room_count,
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