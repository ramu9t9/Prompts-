import sqlite3

# Connect to SQLite DB
conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

# Create table for strike-wise data snapshots
cursor.execute("""
CREATE TABLE IF NOT EXISTS option_snapshots (
    timestamp TEXT,
    index_name TEXT,
    expiry TEXT,
    strike INTEGER,

    ce_oi REAL,
    ce_ltp REAL,
    ce_iv REAL,
    ce_volume INTEGER,
    ce_delta REAL,
    ce_theta REAL,
    ce_vega REAL,
    ce_gamma REAL,

    pe_oi REAL,
    pe_ltp REAL,
    pe_iv REAL,
    pe_volume INTEGER,
    pe_delta REAL,
    pe_theta REAL,
    pe_vega REAL,
    pe_gamma REAL
);
""")

conn.commit()
conn.close()
print("✅ option_snapshots table created successfully!")
