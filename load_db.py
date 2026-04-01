import sqlite3
import pandas as pd

conn = sqlite3.connect('citibike.db')

stations = pd.read_csv('citibike_station_summary.csv')
stations.to_sql('station_summary', conn, if_exists='replace', index=False)

problem = pd.read_csv('citibike_problem_stations.csv')
problem.to_sql('problem_stations', conn, if_exists='replace', index=False)

print("Tables created:")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cursor.fetchall())
conn.close()