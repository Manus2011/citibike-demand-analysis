# NYC Citibike Demand vs. Supply Analysis (Jan–Jun 2025)

## Business Question
Which Citibike stations have demand consistently exceeding supply during morning rush hours, and what is the estimated cost of the resulting rebalancing operations?

## Key Findings
- Analyzed 20M+ trips across 2,169 stations (Jan–Jun 2025)
- Identified 15 high-outflow stations with 67–74% morning rush drain rates
- Two geographic clusters: Upper West Side (residential commuter drain) and East Village/LES
- W 43 St & 10 Ave: highest volume problem station with 68.9% outflow rate and 46,111 total trips
- Average member concentration at problem stations: 87% — demand is predictable and pre-positioning is viable
- Estimated $28M annualized system-wide rebalancing cost based on NACTO $2.10/bike benchmark

## Recommendation
Pre-position bikes at high-outflow residential stations before 7am on weekdays. Proactive rebalancing is cheaper and more effective than reactive truck dispatch.

## Stack
- Python (Pandas, NumPy) — data pipeline and analysis
- SQL / SQLite — business queries across 20M+ records
- Tableau — dashboard visualization

## Files
- `citibike_analysis.py` — main analysis pipeline
- `run_sql.py` — 5 business queries against SQLite database
- `load_db.py` — loads CSVs into SQLite
- `citibike_station_summary.csv` — 2,169 stations with outflow metrics
- `citibike_problem_stations.csv` — 15 high-priority stations

## Dashboard
[Tableau Public link — add after publishing]

## Methodology
**Outflow rate** = (peak departures − peak arrivals) / peak departures during 7–9am weekdays

**Rebalancing cost** = net outflow volume × $2.10/bike (NACTO Urban Street Design Guide benchmark)

**Revenue opportunity** = casual trips × 15% unfulfilled demand × $4.99 single ride price (casual riders only — annual members pay flat fee)
