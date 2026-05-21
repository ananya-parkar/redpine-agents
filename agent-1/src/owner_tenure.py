# agent-1/src/owner_tenure.py
from datetime import datetime
from typing import Dict

def get_owner_tenure(property_data: Dict) -> Dict:
   try:
       sale_history = property_data.get(
           "salehistory",
           []
       )
       sale_date = ""
       if sale_history:
           latest_sale = sale_history[0]
           sale_date = latest_sale.get(
               "saleTransDate",
               ""
           )
       ownership_years = ""
       if sale_date:
           sale_year = int(sale_date[:4])
           current_year = datetime.now().year
           ownership_years = str(
               current_year - sale_year
           )
       return {
           "ownership_since": sale_date,
           "ownership_length_years":
               ownership_years
       }
   except Exception:
       return {
           "ownership_since": "",
           "ownership_length_years": ""
       }