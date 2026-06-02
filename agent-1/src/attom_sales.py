# agent-1/src/atom_sales.py
import requests
from src.config import ATTOM_API_KEY

def get_sale_data(address: str):
    try:
        url = (
            "https://api.gateway.attomdata.com/"
            "propertyapi/v1.0.0/property/basicprofile"
        )

        headers = {"accept": "application/json", "apikey": ATTOM_API_KEY}

        params = {"address": address}
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()

        data = response.json()
        properties = data.get("property", [])

        if not properties:
            print("[SALE DEBUG] No property data found for address:", address, flush=True)
            return {}

        property_data = properties[0]
        print("[SALE DEBUG] property keys:",list(property_data.keys()), flush=True)

        sale = property_data.get("sale", {})
        print("[SALE DEBUG] sale object:", sale, flush=True)

        sale_date = (sale.get("saleTransDate") or sale.get("saleSearchDate"))

        return {
            "sale_trans_date": sale_date,
            "sale_amount": sale.get("saleAmountData", {}).get("saleAmt"),
        }

    except Exception as e:
        print(f"[ATTOM SALE ERROR] {e}", flush=True)
        return {}