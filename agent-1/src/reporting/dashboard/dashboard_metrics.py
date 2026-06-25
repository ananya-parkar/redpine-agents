# agent-1/src/reporting/dashboard/dashboard_metrics.py
def build_metrics(df, search_area=""):
    return {
        "search_area": search_area,
        "total_hotels": len(df),
        "high_opportunity": len(df[df["final_lead_score"] >= 70]),
        "deep_distress": len(df[df["llm_distress_probability"] >= 0.75]),
        "long_term_owners": len(
            df[df["ownership_length_years"] >= 10]
        ),
        "avg_opportunity_score": round(
            df["llm_opportunity_score"].mean(),1
        )
    }

def build_signal_summary(df):
    return {
        "Old Property":
            len(df[df["property_age"] >= 20]),
        "Long-Term Owner":
            len(df[df["ownership_length_years"] >= 10]),
        "High Distress":
            len(df[df["llm_distress_probability"] >= 0.75]),
        "Franchise":
            len(df[df["franchise_affiliated"] == True]),
        "High Opportunity":
            len(df[df["final_lead_score"] >= 70]),
    }
