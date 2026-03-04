════════════════════════════════════════════════════════════════
  AutoNOC v1.0
  Automated Network Operations Centre Report Generator
════════════════════════════════════════════════════════════════

OVERVIEW
--------
AutoNOC downloads data from a web portal, processes
it through a configurable time window, and appends formatted report
blocks to a master Excel workbook.

Each hourly run adds one block below the previous on today's sheet.
At midnight a new sheet tab is created automatically.

KPI cells are highlighted automatically:
  🔴 RED    = Answer Rate fell below the floor threshold (default 40%)
  🟠 ORANGE = Answer Rate dropped more than the alert threshold (default 4%)
              compared to the previous 15-minute interval

All other cells keep clean alternating white/blue row colours.


PROJECT STRUCTURE
-----------------
autonoc/
├── main.py                    ← Entry point — always run this
├── generate_dummy_csv.py      ← Generates test data without the portal
├── requirements.txt           ← Python package dependencies
├── README.txt                 ← This file
│
├── config/
│   └── config.json            ← All settings — edit this before first run
│
├── src/
│   ├── logger_setup.py        ← Rotating log file + console output
│   ├── downloader.py          ← Browser automation (Selenium)
│   ├── report_definitions.py  ← Column mappings for each report type
│   ├── processor.py           ← CSV → filtered DataFrame
│   └── excel_writer.py        ← DataFrame → formatted Excel block
│
├── downloads/                 ← Portal CSVs land here
│   └── archive/               ← Archived copies of raw CSVs
├── output/                    ← AutoNOC_Report.xlsx lives here
└── logs/                      ← autonoc.log (rotating, 5 MB × 7 backups)


QUICK START
-----------
1. Install dependencies (run once):
     pip install -r requirements.txt

2. Edit config/config.json:
     Set "plmn", "report_type", "report_periodicity", "template"".
3. Test without the portal:
     python generate_dummy_csv.py
     python main.py --test

4. Production run:
     python main.py
     → Browser opens → log in → press Enter → everything else is automated


CONFIGURATION  (config/config.json)
------------------------------------
portal:
  login_url           URL of the login page
  url                 URL of the traffic report page
  report_type         Exact text of the Report Type dropdown option
  plmn                Exact text of the PLMN dropdown option
  report_periodicity  Exact text of the Report Periodicity option
  template            Exact text of the Template option (leave "" to auto-select)

kpi_thresholds:
  drop_pct            % drop vs previous row that triggers ORANGE highlight
  floor_pct           Absolute % floor that triggers RED highlight

colors:
  All hex colours used in the Excel output — edit to match your style guide


PLMN-SPECIFIC COLUMNS
----------------------
When PLMN is set to 40459, the Traffic report shows only 4 columns:
  Total Recovery Timer_Expiry_102
  Total Interworking Unspecified
  MO Recovery Timer_Expiry_102
  MT CAUSE ACK TIMEOUT

All other PLMNs show the full 14-column Traffic report.
This is controlled in src/report_definitions.py → get_columns_for_plmn().


REPORT TYPES
------------
  [1] Voice Traffic Report (MO+MT)
      MO/MT call volumes, answer rates, recovery and timeout counters.

  [2] CPU / RAM Utilization Report
      Per-node processor and memory usage.

  [3] Registered Subscriber Count Report
      Total, active, idle, and deregistered subscriber counts.

  [4] System Crash / Fault Report
      Crash events per node with severity and recovery time.


TIME WINDOW
-----------
On each run, AutoNOC asks:
  "How many hours of data to include? [1-24, default=4]:"

The window is counted back from the LATEST timestamp in the CSV,
not from the system clock. This means historical CSVs work correctly.

For a 15-minute periodicity, 4 hours = 16 rows, 24 hours = 96 rows.


EXCEL OUTPUT
------------
File:  output/AutoNOC_Report.xlsx

Sheet naming:  Traffic_26-Feb-2026, CPU_RAM_26-Feb-2026, etc.
  - One sheet per report type per calendar day
  - New sheet created automatically at midnight
  - Previous sheets are never deleted

Block structure (appended on each run):
  Row 1  — Separator bar: report name, PLMN, time window, timestamp
  Row 2  — Column headers
  Rows   — 15-minute data rows (16 rows for 4h, up to 96 rows for 24h)
  TOTAL  — SUM for count columns, AVERAGE for rate columns


RUNNING ON WINDOWS
------------------
All paths are handled via Python's pathlib — fully Windows compatible.
Chrome is managed automatically by webdriver-manager.
No manual ChromeDriver download needed.

To run on Windows:
    run_autonoc.bat
        or
  1. Open Command Prompt or PowerShell
  2. cd into the autonoc folder
  3. pip install -r requirements.txt
  4. python main.py


LOG FILE
--------
logs/autonoc.log
  - Rotating: max 5 MB per file, keeps 7 backups
  - Contains: timestamps, selected options, row counts, file paths, errors
  - Also printed to the terminal during each run


ADDING A NEW REPORT TYPE
-------------------------
1. Open src/report_definitions.py
2. Copy one of the existing report dicts (e.g. CPU_RAM_REPORT)
3. Update: label, sheet_prefix, columns, csv_map, computed, sum/avg/kpi cols
4. Add to ALL_REPORTS: "5": MY_NEW_REPORT
5. No changes needed in any other file

════════════════════════════════════════════════════════════════
# AutoNOC
# AutoNOC
# AutoNOC
