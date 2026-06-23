# ---------------------------------------------------
# CONTACT ENRICHER
# Tries to find public contact emails for stakeholders
# Sources (in order):
#   1. Regex extract from article text
#   2. Hunter.io domain search (free 25/month)
#   3. Web search fallback
#
# PII POLICY (per client doc):
#   - Only collect publicly available info
#   - Retain max 12 months unless lead marked "pursuing"
#   - Stored in leads.contact_email + contact_found_at
# ---------------------------------------------------

import re
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

HUNTER_KEY = os.getenv("HUNTER_API_KEY", "")

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

def extract_emails_from_text(text: str) -> list[str]:
    """Pull any email addresses directly mentioned in article text."""
    if not text:
        return []
    found = EMAIL_RE.findall(text)
    # Filter out junk / auto-generated emails
    return [e for e in found
            if not any(skip in e.lower()
                       for skip in ["noreply", "no-reply", "example",
                                    "test@", "info@", "news@", "press@"])]


def hunter_lookup(domain: str) -> list[dict]:
    """
    Hunter.io: given a firm's domain, find named contacts.
    Returns list of {email, first_name, last_name, position}
    Free tier: 25 requests/month.
    """
    if not HUNTER_KEY or not domain:
        return []
    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": HUNTER_KEY, "limit": 3},
            timeout=8
        )
        if r.status_code == 200:
            emails = r.json().get("data", {}).get("emails", [])
            return [
                {
                    "email":    e.get("value", ""),
                    "name":     f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
                    "position": e.get("position", ""),
                    "source":   "hunter.io"
                }
                for e in emails if e.get("value")
            ]
    except Exception:
        pass
    return []


def enrich_contacts(enriched_stakeholders: list[dict],
                    article_text: str = "") -> list[dict]:
    """
    For each stakeholder, try to find a contact email.
    Modifies in-place and returns the list.
    """
    # 1. Pull any emails from article text
    article_emails = extract_emails_from_text(article_text)

    for s in enriched_stakeholders:
        if s.get("contact_email"):
            continue  # already have it

        firm_website = s.get("firm_website", "")
        firm_name    = (s.get("firm_full_name") or s.get("name") or "").lower()

        # Step 1: article text contains email matching firm name?
        for email in article_emails:
            domain_part = email.split("@")[-1].lower()
            # rough match: if email domain words appear in firm name
            domain_core = domain_part.split(".")[0]
            if domain_core and domain_core in firm_name:
                s["contact_email"]    = email
                s["contact_source"]   = "article_text"
                s["contact_found_at"] = datetime.now(timezone.utc).isoformat()
                break

        # Step 2: Hunter.io using firm website domain
        if not s.get("contact_email") and firm_website and HUNTER_KEY:
            domain = firm_website.replace("https://","").replace("http://","").split("/")[0]
            contacts = hunter_lookup(domain)
            if contacts:
                best = contacts[0]
                s["contact_email"]    = best["email"]
                s["contact_name"]     = best["name"]
                s["contact_position"] = best["position"]
                s["contact_source"]   = "hunter.io"
                s["contact_found_at"] = datetime.now(timezone.utc).isoformat()

    return enriched_stakeholders


# ── PII retention helper ───────────────────────────────────────
def should_purge_pii(first_detected_at: str, retain_pii: bool = False) -> bool:
    """
    Returns True if PII should be purged.
    Policy: purge if older than 12 months AND not marked retain_pii.
    """
    if retain_pii:
        return False
    if not first_detected_at:
        return False
    try:
        from datetime import timedelta
        detected = datetime.fromisoformat(str(first_detected_at).replace("Z", "+00:00"))
        if detected.tzinfo is None:
            detected = detected.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - detected
        return age.days > 365
    except Exception:
        return False