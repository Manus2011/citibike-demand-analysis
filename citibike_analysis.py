"""
NYC Citibike: Station Demand vs. Supply Analysis
Business Question: Which stations have demand that consistently exceeds supply,
and what is the estimated rebalancing cost of not fixing it?


HOW TO RUN:
1. Place this script in the same folder as your 4 zip files:
   - 202501-citbike-tripdata.csv.zip
   - 202503-citbike-tripdata.csv.zip
   - 202505-citbike-tripdata.csv.zip
   - 202506-citbike-tripdata.csv.zip
2. pip install pandas numpy matplotlib seaborn
3. python citibike_analysis.py
"""

import glob
import warnings

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
})
CITIBIKE_BLUE = '#003DA5'
ALERT_RED     = '#D62728'

# Domain constants
MEMBER            = 'member'
CASUAL            = 'casual'
MIN_TRIP_MIN      = 1
MAX_TRIP_MIN      = 180
PEAK_AM_HOURS        = [7, 8, 9]
PEAK_PM_HOURS        = [17, 18, 19]
RUSH_HOURS           = set(PEAK_AM_HOURS + PEAK_PM_HOURS)
REBALANCE_COST_PER_BIKE = 2.10   # NACTO Urban Street Design Guide benchmark

# =============================================================================
# 0. LOAD DATA
# =============================================================================
CSV_FOLDERS = [
    '202501-citibike-tripdata',
    '202502-citibike-tripdata',
    '202503-citibike-tripdata',
    '202504-citibike-tripdata',
    '202505-citibike-tripdata',
    '202506-citibike-tripdata',
]
dfs = []
for folder in CSV_FOLDERS:
    files = glob.glob(f'{folder}/*.csv')
    for f in files:
        print(f"Loading {f}...")
        chunk = pd.read_csv(f, parse_dates=['started_at', 'ended_at'],
                            dtype={'start_station_id': str, 'end_station_id': str})
        dfs.append(chunk)
        print(f"  -> {len(chunk):,} rows")

df = pd.concat(dfs, ignore_index=True)
print(f"\nTotal records loaded: {len(df):,}")
print(f"Columns: {list(df.columns)}")

# =============================================================================
# 1. CLEAN & ENRICH
# =============================================================================
# Drop rows missing station info (dockless/electric bike trips parked outside stations)
df = df.dropna(subset=['start_station_name', 'start_station_id',
                        'end_station_name',   'end_station_id'])

df['duration_min'] = (df['ended_at'] - df['started_at']).dt.total_seconds() / 60

# Remove clearly bad trips (under 1 min or over 3 hours)
df = df[(df['duration_min'] >= MIN_TRIP_MIN) & (df['duration_min'] <= MAX_TRIP_MIN)]

df['date']       = df['started_at'].dt.date
df['hour']       = df['started_at'].dt.hour
df['day_of_week']= df['started_at'].dt.dayofweek   # 0=Monday
df['month']      = df['started_at'].dt.month
df['is_weekday'] = df['day_of_week'] < 5
df['month_label']= df['started_at'].dt.strftime('%b')

print(f"\nAfter cleaning: {len(df):,} valid trips")
print(f"Date range: {df['started_at'].min().date()} to {df['started_at'].max().date()}")
print(f"Unique start stations: {df['start_station_name'].nunique():,}")
print(f"Member vs Casual: {df['member_casual'].value_counts().to_dict()}")

# =============================================================================
# 2. STATION-LEVEL DEMAND (DEPARTURES)
# =============================================================================
# Each departure = demand. We use trip counts as a proxy for demand.
# Note: actual demand is higher because some riders arrive and find no bikes —
# we can estimate this from docking patterns (arrivals vs departures imbalance).

departures = df.groupby(['start_station_name', 'start_station_id', 'date', 'hour']).agg(
    departures = ('ride_id', 'count'),
    start_lat  = ('start_lat', 'mean'),
    start_lng  = ('start_lng', 'mean'),
    month      = ('month', 'first'),
    is_weekday = ('is_weekday', 'first'),
).reset_index()

arrivals = df.groupby(['end_station_name', 'end_station_id', 'date', 'hour']).agg(
    arrivals = ('ride_id', 'count'),
).reset_index().rename(columns={
    'end_station_name': 'start_station_name',
    'end_station_id':   'start_station_id',
})

hourly = departures.merge(arrivals, on=['start_station_name','start_station_id','date','hour'], how='left')
hourly['arrivals'] = hourly['arrivals'].fillna(0)

# Net flow: positive = more bikes leaving than arriving (station draining)
hourly['net_outflow'] = hourly['departures'] - hourly['arrivals']

# =============================================================================
# 3. STATION SUMMARY
# =============================================================================
station_summary = df.groupby(['start_station_name', 'start_station_id']).agg(
    total_trips  = ('ride_id',      'count'),
    avg_lat      = ('start_lat',    'mean'),
    avg_lng      = ('start_lng',    'mean'),
    member_trips = ('member_casual', lambda x: (x == MEMBER).sum()),
    casual_trips = ('member_casual', lambda x: (x == CASUAL).sum()),
).reset_index()

# Peak hour stats
peak = hourly[hourly['hour'].isin(PEAK_AM_HOURS) & hourly['is_weekday']]
peak_station = peak.groupby('start_station_name').agg(
    peak_departures    = ('departures', 'sum'),
    peak_arrivals      = ('arrivals',   'sum'),
    peak_net_outflow   = ('net_outflow','sum'),
    peak_hours_counted = ('hour',       'count'),
).reset_index()
peak_station['avg_peak_hourly_departures'] = (
    peak_station['peak_departures'] / peak_station['peak_hours_counted']
)
peak_station['peak_outflow_rate'] = (
    peak_station['peak_net_outflow'] / peak_station['peak_departures'].replace(0, np.nan)
)

station_summary = station_summary.merge(peak_station, on='start_station_name', how='left')

# Rebalancing cost estimate
# Logic: Each net outflow bike requires a rebalancing truck move to restore balance
# Cost: $2.10/bike (NACTO Urban Street Design Guide industry benchmark)
# A positive net_outflow = bikes leaving faster than arriving = station drains = needs rebalancing
REBALANCE_COST_PER_BIKE = 2.10

# Only count POSITIVE net outflow (station draining, not overflow)
hourly['rebalancing_needed'] = hourly['net_outflow'].clip(lower=0)
rebalance_by_station = hourly.groupby('start_station_name')['rebalancing_needed'].sum().reset_index()
rebalance_by_station.columns = ['start_station_name', 'total_rebalancing_needed']
rebalance_by_station['rebalancing_cost'] = rebalance_by_station['total_rebalancing_needed'] * REBALANCE_COST_PER_BIKE

station_summary = station_summary.merge(rebalance_by_station, on='start_station_name', how='left')
station_summary = station_summary.sort_values('total_trips', ascending=False).reset_index(drop=True)

print(f"\n=== TOP 10 BUSIEST STATIONS ===")
print(station_summary[['start_station_name','total_trips','peak_departures','rebalancing_cost']].head(10).to_string(index=False))

# =============================================================================
# 4. KEY FINDINGS
# =============================================================================
top10_stations = station_summary.head(10)
top3_stations  = station_summary.head(3)

total_trips    = station_summary['total_trips'].sum()
top3_trips     = top3_stations['total_trips'].sum()
top10_trips    = top10_stations['total_trips'].sum()

total_rebalancing_cost = station_summary['rebalancing_cost'].sum()
top3_rebalancing_cost  = top3_stations['rebalancing_cost'].sum()

print(f"\n=== KEY FINDINGS ===")
print(f"Total trips analyzed: {total_trips:,}")
print(f"Top 3 stations: {top3_stations['start_station_name'].tolist()}")
print(f"Top 3 share of total trips: {top3_trips/total_trips*100:.1f}%")
print(f"Top 10 share of total trips: {top10_trips/total_trips*100:.1f}%")
print(f"\nEstimated rebalancing cost (all stations): ${total_rebalancing_cost:,.0f}")
print(f"Top 3 stations rebalancing cost: ${top3_rebalancing_cost:,.0f}")
print(f"Top 3 share of rebalancing cost: {top3_rebalancing_cost/total_rebalancing_cost*100:.0f}%")

# Morning rush outflow rate
print(f"\n=== MORNING RUSH (7-9am, weekdays) ===")
top5_peak = station_summary.nlargest(5, 'peak_departures')
print(top5_peak[['start_station_name','peak_departures','peak_net_outflow','peak_outflow_rate']].to_string(index=False))

# =============================================================================
# 5. MONTHLY TREND
# =============================================================================
monthly = df.groupby(['month','month_label']).agg(
    trips = ('ride_id', 'count')
).reset_index().sort_values('month')

top_station_name = station_summary.iloc[0]['start_station_name']
top_station_df   = df[df['start_station_name'] == top_station_name]
monthly_top = top_station_df.groupby(['month','month_label']).agg(
    trips = ('ride_id','count')
).reset_index().sort_values('month')

print(f"\n=== MONTHLY TRIP TREND: {top_station_name} ===")
print(monthly_top.to_string(index=False))

# =============================================================================
# 6. MEMBER VS CASUAL BREAKDOWN (bonus finding)
# =============================================================================
member_pct = df['member_casual'].value_counts(normalize=True) * 100
print(f"\n=== MEMBER VS CASUAL ===")
print(member_pct.round(1))

# At high-demand stations, is it mostly members (commuters) or casuals (tourists)?
top3_member = station_summary.head(3)[['start_station_name','member_trips','casual_trips']].copy()
top3_member['member_pct'] = top3_member['member_trips'] / (top3_member['member_trips'] + top3_member['casual_trips']) * 100
print(f"\nTop 3 stations member %:")
print(top3_member[['start_station_name','member_pct']].to_string(index=False))
print("-> High member % = commuter-driven demand = highly predictable = easier to pre-position")

# =============================================================================
# 7. HOUR-OF-DAY PATTERN (top station)
# =============================================================================
top_hourly = top_station_df.groupby('hour').agg(
    trips=('ride_id','count')
).reset_index()

# =============================================================================
# 8. VISUALIZATIONS
# =============================================================================
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('NYC Citibike: Station Demand vs. Supply Analysis\nJan - Jun 2025',
             fontsize=14, fontweight='bold')

# Chart 1: Top 15 stations by total trips
ax = axes[0, 0]
top15 = station_summary.head(15)
colors = [ALERT_RED if i < 3 else CITIBIKE_BLUE for i in range(len(top15))]
ax.barh(top15['start_station_name'], top15['total_trips'] / 1000,
        color=colors, edgecolor='none')
ax.invert_yaxis()
ax.set_xlabel('Total Trips (thousands)', fontsize=10)
ax.set_title('Top 15 Stations: Total Trip Volume', fontweight='bold')
ax.tick_params(axis='y', labelsize=7)

# Chart 2: Rebalancing cost vs trip volume
ax = axes[0, 1]
plot_data = station_summary.head(30).dropna(subset=['rebalancing_cost','total_trips'])
sc = ax.scatter(plot_data['total_trips'] / 1000,
                plot_data['rebalancing_cost'] / 1000,
                c=plot_data['peak_outflow_rate'].fillna(0),
                cmap='RdYlGn_r', s=60, alpha=0.8)
plt.colorbar(sc, ax=ax, label='Peak Outflow Rate')
ax.set_xlabel('Total Trips (thousands)', fontsize=10)
ax.set_ylabel('Estimated Rebalancing Cost ($K)', fontsize=10)
ax.set_title('Trip Volume vs. Rebalancing Cost\n(color = morning rush outflow rate)', fontweight='bold')
for _, row in top3_stations.iterrows():
    ax.annotate(row['start_station_name'].split('&')[0].strip(),
                (row['total_trips']/1000, row['rebalancing_cost']/1000),
                xytext=(4, 4), textcoords='offset points', fontsize=7, color=ALERT_RED)

# Chart 3: Hour-of-day demand at top station
ax = axes[1, 0]
ax.bar(top_hourly['hour'], top_hourly['trips'],
       color=[ALERT_RED if h in RUSH_HOURS else CITIBIKE_BLUE for h in top_hourly['hour']],
       edgecolor='none')
ax.set_xlabel('Hour of Day', fontsize=10)
ax.set_ylabel('Total Trips', fontsize=10)
ax.set_title(f'Hourly Demand Pattern\n{top_station_name[:40]}', fontweight='bold')
ax.set_xticks(range(0, 24, 3))
ax.annotate('Morning\nRush', xy=(8, top_hourly[top_hourly['hour']==8]['trips'].values[0]),
            xytext=(10, top_hourly[top_hourly['hour']==8]['trips'].values[0]),
            fontsize=8, color=ALERT_RED, arrowprops=dict(arrowstyle='->', color=ALERT_RED))

# Chart 4: Monthly trip volume (system + top station)
ax = axes[1, 1]
month_labels = monthly['month_label'].tolist()
x = range(len(monthly))
ax.bar(x, monthly['trips'] / 1000, color=CITIBIKE_BLUE, alpha=0.7, label='All Stations')
ax2 = ax.twinx()
month_to_x = {m: i for i, m in enumerate(monthly['month'].tolist())}
top_x = [month_to_x[m] for m in monthly_top['month'].tolist()]
ax2.plot(top_x, monthly_top['trips'], color=ALERT_RED, marker='o', linewidth=2.5,
         label=top_station_name[:20]+'...', markersize=6)
ax.set_xticks(x)
ax.set_xticklabels(month_labels)
ax.set_ylabel('System Total Trips (thousands)', fontsize=9, color=CITIBIKE_BLUE)
ax2.set_ylabel(f'Top Station Trips', fontsize=9, color=ALERT_RED)
ax.set_title('Monthly Ridership: System vs. Top Station', fontweight='bold')
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='upper left')

plt.tight_layout()
plt.savefig('citibike_analysis_charts.png', dpi=150, bbox_inches='tight')
plt.close()
print("\nSaved: citibike_analysis_charts.png")

# =============================================================================
# 9. EXPORT
# =============================================================================
export = station_summary[[
    'start_station_name','start_station_id','avg_lat','avg_lng',
    'total_trips','member_trips','casual_trips',
    'peak_departures','peak_net_outflow','peak_outflow_rate',
    'total_rebalancing_needed','rebalancing_cost'
]].copy()
export.to_csv('citibike_station_summary.csv', index=False)
print("Saved: citibike_station_summary.csv")
print("\n=== DONE ===")
print("Next step: load citibike_station_summary.csv into Tableau or Power BI for the dashboard.")
