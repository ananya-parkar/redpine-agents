# agent-3/collection/signal_models.py
from dataclasses import dataclass, field

@dataclass
class CompanySignals:
    company_name: str
    website_url: str = ""
    website_content: str = ""
    about_content: str = ""
    leadership_content: str = ""
    news_content: str = ""
    source_urls: list = field(default_factory=list)