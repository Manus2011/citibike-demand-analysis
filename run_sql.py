import sqlite3
import pandas as pd

conn = sqlite3.connect('citibike.db')

queries = {
    "Q1: Top 15 stations by outflow rate": """
        SELECT 
            start_station_name,
            total_trips,
            peak_departures,
            ROUND(peak_outflow_rate * 100, 1) as outflow_pct,
            ROUND(rebalancing_cost, 0) as rebalancing_cost_usd
        FROM station_summary
        WHERE total_trips > 20000 AND peak_outflow_rate > 0
        ORDER BY peak_outflow_rate DESC
        LIMIT 15
    """,
    "Q2: Top 10 stations share of rebalancing cost": """
        SELECT 
            ROUND(SUM(rebalancing_cost), 0) as top10_cost,
            ROUND(SUM(rebalancing_cost) / (SELECT SUM(rebalancing_cost) FROM station_summary) * 100, 1) as pct_of_total
        FROM (
            SELECT rebalancing_cost 
            FROM station_summary 
            ORDER BY rebalancing_cost DESC 
            LIMIT 10
        )
    """,
    "Q3: Member vs casual at high outflow stations": """
        SELECT
            start_station_name,
            total_trips,
            ROUND(member_trips * 100.0 / total_trips, 1) as member_pct,
            ROUND(peak_outflow_rate * 100, 1) as outflow_pct
        FROM station_summary
        WHERE peak_outflow_rate > 0.5 AND total_trips > 20000
        ORDER BY peak_outflow_rate DESC
    """,
    "Q4: Revenue opportunity at top 5 outflow stations (casual riders only)": """
        SELECT
            start_station_name,
            total_trips,
            casual_trips,
            ROUND(peak_outflow_rate * 100, 1) as outflow_pct,
            ROUND(casual_trips * 0.15 * 4.99, 0) as casual_revenue_opportunity_usd
        FROM station_summary
        WHERE peak_outflow_rate > 0 AND total_trips > 20000
        ORDER BY peak_outflow_rate DESC
        LIMIT 5
    """,
    "Q5: Total system rebalancing cost annualized": """
        SELECT
            ROUND(SUM(rebalancing_cost), 0) as sixmonth_cost,
            ROUND(SUM(rebalancing_cost) * 2, 0) as annualized_cost
        FROM station_summary
    """
}

for title, query in queries.items():
    print(f"\n=== {title} ===")
    print(pd.read_sql(query, conn).to_string(index=False))

conn.close()
