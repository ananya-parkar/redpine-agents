# agent-1/src/enrichment/attom_basicprofile.py
import requests
from src.core.config import ATTOM_API_KEY
import re


def get_basic_profile(address):

    try:
        parts = [x.strip() for x in address.replace(", USA", "").split(",")]

        street = ""
        for part in parts:
            if re.match(r"^\d+", part.strip()):
                street = part.strip()
                break

        if not street:
            return {}

        city = parts[-2]
        state_zip = parts[-1]
        address2 = f"{city}, {state_zip}"

        url = (
            "https://api.gateway.attomdata.com/"
            "propertyapi/v1.0.0/property/basicprofile"
        )

        headers = {
            "apikey": ATTOM_API_KEY,
            "accept": "application/json"
        }

        params = {
            "address1": street,
            "address2": address2
        }

        print(
            f"[BASICPROFILE REQUEST] address1={street} | address2={address2}",
            flush=True
        )

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20
        )

        response.raise_for_status()
        properties = response.json().get("property", [])
        print(
            f"[BASICPROFILE PROPERTY COUNT] {len(properties)}",
            flush=True
        )

        if not properties:
            return {}

        sale = properties[0].get("sale", {})

        print(
            "[BASICPROFILE SALE]",
            sale,
            flush=True
        )
        return {
            "sale_trans_date": sale.get("saleTransDate"),
            "sale_search_date": sale.get("saleSearchDate"),
            "sale_amount":
                sale.get("saleAmountData", {})
                    .get("saleAmt")
        }

    except Exception as e:
        print(
            f"[ATTOM BASICPROFILE ERROR] {e}",
            flush=True
        )
        return {}