"""
Creates 24 hours of synthetic traffic data (96 rows, 15-minute intervals)
for testing AutoNOC without connecting to the live portal.

Intentional anomalies are injected into the last 4 hours so that
KPI highlighting can be verified in the output Excel file:
  row 84 → MO Answer Rate drops sharply (ORANGE expected)
  row 88 → MT Answer Rate falls below 40% floor (RED expected)
  row 92 → Both MO and MT below floor (RED on both)
  row 94 → Recovery to normal levels

Run:  python generate_dummy_csv.py
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

# Build 96 timestamps ending at the most recent 15-minute boundary
now   = datetime.now().replace(second=0, microsecond=0)
now  -= timedelta(minutes=now.minute % 15)
start = now - timedelta(hours=24)
times = [start + timedelta(minutes=15 * i) for i in range(96)]

rows = []
for i, t in enumerate(times):
    mo_att = max(1000, int(np.random.normal(15000, 2000)))
    mt_att = max(1000, int(np.random.normal(40000, 5000)))
    mo_r   = np.random.uniform(0.47, 0.52)
    mt_r   = np.random.uniform(0.42, 0.48)

    # Inject anomalies in the last 4 hours only
    if i == 83: mo_r = 0.41                      # MO drop >4% — ORANGE
    if i == 87: mt_r = 0.355                     # MT below 40% — RED
    if i == 91: mo_r = 0.38; mt_r = 0.33        # Both below floor — RED
    if i == 93: mo_r = 0.49; mt_r = 0.43        # Recovery

    rows.append({
        "PLMN":                               40434,
        "Date Time":                          t.strftime("%d-%b-%Y %H:%M:%S"),
        "Report Periodicity(s)":              900,
        "MO_Attempts":                        mo_att,
        "MO_Answered_Calls":                  int(mo_att * mo_r),
        "MT_Attempts":                        mt_att,
        "MT_Answered":                        int(mt_att * mt_r),
        "MO_Recovery_on_Timer_Expiry_102":    int(np.random.uniform(100, 200)),
        "Total_Recovery_on_Timer_Expiry_102": int(np.random.uniform(500, 800)),
        "Total_Interworking_Unspecified":     int(np.random.uniform(40, 90)),
        "MT_CAUSE_ACK_TIMEOUT":               int(np.random.uniform(5, 15)),
    })

os.makedirs("downloads", exist_ok=True)
out = "downloads/dummy_traffic_report.csv"
pd.DataFrame(rows).to_csv(out, index=False)

print(f"Generated : {out}")
print(f"Rows      : 96  ({times[0].strftime('%d-%b %H:%M')} → {times[-1].strftime('%d-%b %H:%M')})")
print(f"Anomalies :")
print(f"  row 84  {times[83].strftime('%H:%M')}  🟠 MO drop >4%")
print(f"  row 88  {times[87].strftime('%H:%M')}  🔴 MT below 40%")
print(f"  row 92  {times[91].strftime('%H:%M')}  🔴 Both below floor")
print(f"  row 94  {times[93].strftime('%H:%M')}  ✅ Recovery")
