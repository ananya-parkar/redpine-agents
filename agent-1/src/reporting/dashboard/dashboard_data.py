# agent-1/src/reporting/dashboard/dashboard_data.py
import ast
import pandas as pd
from datetime import datetime
from src.storage.postgres_storage import get_connection
from src.reporting.dashboard.dashboard_constants import *

# def load_leads():
#     conn = get_connection()
#     query = """ SELECT * FROM hotel_leads ORDER BY final_lead_score DESC """
#     df = pd.read_sql(query, conn)
#     conn.close()
#     return df



def unpack_signals(signal_data):
    if isinstance(signal_data, str):
        try:
            signal_data = ast.literal_eval(signal_data)
        except:
            return {}

    return signal_data if isinstance(signal_data, dict) else {}

def load_leads():
    conn = get_connection()
    query = """
    SELECT *
    FROM hotel_leads
    ORDER BY final_lead_score DESC
    """

    df = pd.read_sql(query, conn)
    print("\n===== DASHBOARD DATA =====")
    print("Rows:", len(df))
    print(df[["hotel_name","address"]].head(20))

    conn.close()
    return df

def extract_city(address):
    if not address:
        return ""

    parts = [p.strip() for p in address.split(",")]

    if len(parts) >= 3:
        return parts[-3]

    return ""

def extract_state(address):
    if not address:
        return ""

    parts = [p.strip() for p in address.split(",")]

    if len(parts) >= 2:
        state_zip = parts[-2]     
        return state_zip.split()[0]

    return ""

def prepare_leads(df):
    required_columns = {
        "lead_status": "New",
        "feedback_reason": "",
        "feedback_notes": "",
        "notes": ""
    }

    for col, default_value in required_columns.items():
        if col not in df.columns:
            df[col] = default_value

    current_year = datetime.now().year
    def calculate_property_age(x):
        try:
            if pd.isna(x) or str(x).strip() == "":
                return None

            return current_year - int(float(x))

        except Exception:
            return None
    df["property_age"] = df["attom_year_built"].apply(calculate_property_age)
    if "lead_status" not in df.columns:
        df["lead_status"] = "New"

    df["lead_status"] = (
        df["lead_status"]
        .fillna("New")
        .astype(str)
        .str.title()
    )
    if "feedback_reason" not in df.columns:
        df["feedback_reason"] = ""

    if "feedback_notes" not in df.columns:
        df["feedback_notes"] = ""

    if "notes" not in df.columns:
        df["notes"] = ""

    df["city"] = df["address"].fillna("").apply(extract_city)
    df["state"] = df["address"].fillna("").apply(extract_state)

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
    
    df["signal_dict"] = df["signals"].apply(unpack_signals)    
    df["signals_fired"] = df.apply(build_signals, axis=1)
    print("\n ====== CITY VALUES =======")
    print(df["city"].value_counts().head(20))
    return df

def build_signals(row):
    signal_data = row.get("signal_dict", {})
    signals = []

    if signal_data.get("complaint_increase"):
        signals.append("Complaint Increase")

    if signal_data.get("review_volume_decline"):
        signals.append("Review Decline")

    if signal_data.get("franchise_loss"):
        signals.append("Franchise Loss")

    if signal_data.get("renovation_needed"):
        signals.append("Renovation Needed")

    if pd.notna(row["ownership_length_years"]):
        if row["ownership_length_years"] >= 10:
            signals.append("Long-Term Owner")

    # if pd.notna(row["cmbs_watchlist"]) and row["cmbs_watchlist"]:
    #     signals.append("CMBS Watchlist")

    # if pd.notna(row["cmbs_delinquent"]) and row["cmbs_delinquent"]:
    #     signals.append("CMBS Delinquent")

    # if pd.notna(row["cmbs_special_servicing"]) and row["cmbs_special_servicing"]:
    #     signals.append("Special Servicing")

    if pd.notna(row["property_age"]):
        if row["property_age"] >= 20:
            signals.append("Old Property")

    return " | ".join(signals)
