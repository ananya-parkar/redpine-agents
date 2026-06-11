# agent-1/src/reporting/dashboard/dashboard_data.py
import pandas as pd
from datetime import datetime
from src.storage.postgres_storage import get_connection
from src.reporting.dashboard.dashboard_constants import *

def load_leads():
    conn = get_connection()
    query = """ SELECT * FROM hotel_leads ORDER BY final_lead_score DESC """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def extract_city(address):
    if not address:
        return ""

    parts = [p.strip() for p in address.split(",")]

    if len(parts) >= 3:
        return parts[-3]

    return ""

def prepare_leads(df):
    current_year = datetime.now().year
    df["property_age"] = df["attom_year_built"].apply(lambda x: current_year - int(x) if pd.notna(x) else None)
    df["lead_status"] = df["lead_status"].str.title()
    df["city"] = df["address"].fillna("").apply(extract_city)
        
    # fallback columns
    if "lead_status" not in df.columns:
        df["lead_status"] = "New"

    if "notes" not in df.columns:
        df["notes"] = ""

    if "city" not in df.columns:
        df["city"] = ""

    if "state" not in df.columns:
        df["state"] = ""
    
    if "feedback_reason" not in df.columns:
        df["feedback_reason"] = ""

    if "feedback_notes" not in df.columns:
        df["feedback_notes"] = ""
        
    df["signals_fired"] = df.apply(build_signals, axis=1)
    print("\n ====== CITY VALUES =======")
    print(df["city"].value_counts().head(20))
    return df

def build_signals(row):
    signals = []
    if pd.notna(row["ownership_length_years"]):
        if row["ownership_length_years"] >= 10:
            signals.append("Long-Term Owner")

    if pd.notna(row["cmbs_watchlist"]) and row["cmbs_watchlist"]:
        signals.append("CMBS Watchlist")

    if pd.notna(row["cmbs_delinquent"]) and row["cmbs_delinquent"]:
        signals.append("CMBS Delinquent")

    if pd.notna(row["cmbs_special_servicing"]) and row["cmbs_special_servicing"]:
        signals.append("Special Servicing")

    if pd.notna(row["property_age"]):
        if row["property_age"] >= 20:
            signals.append("Old Property")

    return " | ".join(signals)
