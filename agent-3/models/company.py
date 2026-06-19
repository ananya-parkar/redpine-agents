# agent-3/models/company.py
from dataclasses import dataclass
@dataclass
class Company:
    company_name: str
    city: str = ""
    state: str = ""
    website: str = ""
    source: str = ""