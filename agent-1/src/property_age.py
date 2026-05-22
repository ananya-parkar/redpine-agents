# agent-1/src/property_age.py
from datetime import datetime
from typing import Dict

def get_property_age_flags(property_data: Dict) -> Dict:
   try:
       year_built = (
           property_data.get("summary", {})
           .get("yearbuilt", "")
       )
       is_older_than_20_years = ""
       if year_built:
           current_year = datetime.now().year
           property_age = (
               current_year - int(year_built)
           )
           is_older_than_20_years = (
               "Yes"
               if property_age >= 20
               else "No"
           )
       return {
           "year_built": year_built,
           "is_older_than_20_years":
               is_older_than_20_years
       }
   except Exception:
       return {
           "year_built": "",
           "is_older_than_20_years": ""
       }