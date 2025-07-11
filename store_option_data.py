import sqlite3
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def store_option_data(index_name, expiry, data):
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()

    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    for row in data:
        strike = row['strike']

        # Fetch previous snapshot for this strike
        cursor.execute("""
            SELECT * FROM option_snapshots
            WHERE index_name = ? AND expiry = ? AND strike = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (index_name, expiry, strike))
        prev = cursor.fetchone()

        # Compute deltas if previous exists
        def pct_change(current, prev):
            try:
                return round(((current - prev) / prev) * 100, 2) if prev else 0.0
            except:
                return 0.0

        if prev:
            _, _, _, _, prev_ce_oi, prev_ce_ltp, _, _, _, _, _, _, prev_pe_oi, prev_pe_ltp, *_ = prev
            ce_oi_change = round(row['ce_oi'] - prev_ce_oi, 2)
            ce_oi_pct = pct_change(row['ce_oi'], prev_ce_oi)
            ce_ltp_change = round(row['ce_ltp'] - prev_ce_ltp, 2)
            ce_ltp_pct = pct_change(row['ce_ltp'], prev_ce_ltp)

            pe_oi_change = round(row['pe_oi'] - prev_pe_oi, 2)
            pe_oi_pct = pct_change(row['pe_oi'], prev_pe_oi)
            pe_ltp_change = round(row['pe_ltp'] - prev_pe_ltp, 2)
            pe_ltp_pct = pct_change(row['pe_ltp'], prev_pe_ltp)
        else:
            ce_oi_change = ce_ltp_change = ce_oi_pct = ce_ltp_pct = 0.0
            pe_oi_change = pe_ltp_change = pe_oi_pct = pe_ltp_pct = 0.0

        print(f"💾 Saving {index_name} {strike} → CE LTP: {row['ce_ltp']} ({ce_ltp_pct}%), PE LTP: {row['pe_ltp']} ({pe_ltp_pct}%)")

        cursor.execute("""
            INSERT INTO option_snapshots (
                timestamp, index_name, expiry, strike,

                ce_oi, ce_ltp, ce_iv, ce_volume, ce_delta, ce_theta, ce_vega, ce_gamma,
                pe_oi, pe_ltp, pe_iv, pe_volume, pe_delta, pe_theta, pe_vega, pe_gamma
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, index_name, expiry, strike,

            row['ce_oi'], row['ce_ltp'], row['ce_iv'], row['ce_volume'],
            row['ce_delta'], row['ce_theta'], row['ce_vega'], row['ce_gamma'],

            row['pe_oi'], row['pe_ltp'], row['pe_iv'], row['pe_volume'],
            row['pe_delta'], row['pe_theta'], row['pe_vega'], row['pe_gamma']
        ))

    conn.commit()
    conn.close()
