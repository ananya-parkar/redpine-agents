# agent-1/src/postgres_storage.py
import psycopg2
from src.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD
)

def get_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

def insert_priority_leads(rows):
    if not rows:
        return

    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    for row in rows:
        llm = row.get("llm_analysis", {})

        cur.execute(
        """
        INSERT INTO hotel_leads (
            hotel_name,
            address,
            final_lead_score,
            opportunity_score,
            owner_name,
            franchise_affiliated,
            current_brand,

            distress_probability,
            seller_fatigue_probability,
            review_summary,
            investment_thesis,
            recommended_action,
            distress_summary,
            llm_star_rating,

            ownership_since,
            ownership_length_years,
            attom_year_built,

            cmbs_watchlist,
            cmbs_delinquent,
            cmbs_special_servicing
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,
            %s,%s,%s,%s,%s,%s,
            %s,
            %s,%s,%s,
            %s,%s,%s
        )
        ON CONFLICT(address)
        DO UPDATE SET
            final_lead_score = EXCLUDED.final_lead_score,
            opportunity_score = EXCLUDED.opportunity_score,

            owner_name = EXCLUDED.owner_name,
            ownership_since = EXCLUDED.ownership_since,
            distress_probability = EXCLUDED.distress_probability,
            seller_fatigue_probability = EXCLUDED.seller_fatigue_probability,

            review_summary = EXCLUDED.review_summary,
            investment_thesis = EXCLUDED.investment_thesis,
            recommended_action = EXCLUDED.recommended_action,
            distress_summary = EXCLUDED.distress_summary,
            llm_star_rating = EXCLUDED.llm_star_rating,

            ownership_length_years = EXCLUDED.ownership_length_years,
            attom_year_built = EXCLUDED.attom_year_built,

            cmbs_watchlist = EXCLUDED.cmbs_watchlist,
            cmbs_delinquent = EXCLUDED.cmbs_delinquent,
            cmbs_special_servicing = EXCLUDED.cmbs_special_servicing
        """,
        (
            row.get("hotel_name"),
            row.get("address"),
            row.get("final_lead_score"),
            llm.get("opportunity_score"),
            row.get("owner_name"),
            row.get("franchise_affiliated"),
            row.get("current_brand"),
            llm.get("distress_probability"),
            llm.get("seller_fatigue_probability"),
            llm.get("review_summary"),
            llm.get("investment_thesis"),
            llm.get("recommended_action"),
            llm.get("distress_summary"),
            llm.get("llm_star_rating"),
            row.get("ownership_since"),
            int(row["ownership_length_years"])
            if str(row.get("ownership_length_years", "")).isdigit()
            else None,

            int(row["attom_year_built"])
            if str(row.get("attom_year_built", "")).isdigit()
            else None,
            row.get("cmbs_watchlist_flag"),
            row.get("cmbs_delinquency_flag"),
            row.get("cmbs_special_servicing_flag")
        )
    )
        if cur.rowcount > 0:
            inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f"[POSTGRES] Inserted {inserted} priority leads", flush=True)

def get_existing_addresses():

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT address
        FROM hotel_leads
        """
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return {row[0].lower().strip() for row in rows if row[0]}

if __name__ == "__main__":
    conn = get_connection()
    print("Postgres Connected Successfully")
    conn.close()