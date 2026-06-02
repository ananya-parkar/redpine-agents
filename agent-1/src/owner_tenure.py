# agent-1/src/owner_tenure.py
from datetime import datetime
from typing import Dict

def get_owner_tenure(property_data: Dict) -> Dict:
    try:
        sale_date = ""

        sale_history = property_data.get(
            "salehistory",
            []
        )

        if sale_history:
            latest_sale = sale_history[0]

            sale_date = (
                latest_sale.get("saleTransDate", "")
                or latest_sale.get("saleTransdate", "")
            )

        if not sale_date:
            sale_obj = property_data.get(
                "sale",
                {}
            )

            if isinstance(sale_obj, dict):
                sale_date = (
                    sale_obj.get("saleTransDate", "")
                    or sale_obj.get("saleTransdate", "")
                )

        ownership_years = ""

        if sale_date:
            sale_year = int(sale_date[:4])

            ownership_years = str(
                datetime.now().year - sale_year
            )

        return {
            "ownership_since": sale_date,
            "ownership_length_years": ownership_years
        }

    except Exception:
        return {
            "ownership_since": "",
            "ownership_length_years": ""
        }