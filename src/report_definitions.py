"""
Defines all report types used by AutoNOC.

Each report is a dict with:
  label        - display name shown in the menu
  sheet_prefix - prefix for the daily Excel sheet tab name
  columns      - ordered list of output column names (full default set)
  csv_map      - maps output column to CSV column name fragments to search
  computed     - derived columns calculated from already-mapped columns
  sum_cols     - columns that get a SUM formula in the TOTAL row
  avg_cols     - columns that get an AVERAGE formula in the TOTAL row
  rate_cols    - formatted as 0.00 (percentages / rates)
  int_cols     - formatted as #,##0 (whole number counts)
  kpi_cols     - monitored for drop/floor KPI highlighting
  col_widths   - Excel column widths in characters

Column set per PLMN is driven by config.json -> plmn_columns.
get_columns_for_plmn() is the single access point used by processor and writer.
"""


FULL_TRAFFIC_COLUMNS = [
    "Date Time",
    "PLMN",
    "MO Total Calls",
    "MO Answered",
    "MT Total Calls",
    "MT Answered",
    "Total Calls",
    "Total Answered",
    "Total Recovery\nTimer_Expiry_102",
    "Total Interworking\nUnspecified",
    "MO Recovery\nTimer_Expiry_102",
    "MT CAUSE\nACK TIMEOUT",
    "MO Answer\nRate (%)",
    "MT Answer\nRate (%)",
    "Total Answer\nRate (%)",
]


def get_columns_for_plmn(rdef: dict, plmn: str) -> list:
    """
    Returns the report column list for the given PLMN.
    Config-driven plmn_columns takes priority — this is the fallback
    when the caller does not pass config (e.g. excel_writer).
    """
    return rdef.get("columns", FULL_TRAFFIC_COLUMNS)


# ── Report 1: Voice Traffic ───────────────────────────────────────────────────

TRAFFIC_REPORT = {
    "label":        "Voice Traffic Report (MO+MT)",
    "sheet_prefix": "Traffic",
    "columns":      FULL_TRAFFIC_COLUMNS,

    "csv_map": {
        "PLMN":                             ["PLMN", "plmn"],
        "MO Total Calls":                   ["MO_Attempts"],
        "MO Answered":                      ["MO_Answered_Calls", "MO_Answered"],
        "MT Total Calls":                   ["MT_Attempts"],
        "MT Answered":                      ["MT_Answered"],
        "Total Recovery\nTimer_Expiry_102": ["Total_Recovery_on_Timer", "Total_Recovery"],
        "Total Interworking\nUnspecified":  ["Total_Interworking"],
        "MO Recovery\nTimer_Expiry_102":    ["MO_Recovery_on_Timer", "MO_Recovery"],
        "MT CAUSE\nACK TIMEOUT":            ["MT_CAUSE_ACK", "MT_Cause_Ack"],
    },

    "computed": {
        "Total Calls":
            lambda m: m["MO Total Calls"] + m["MT Total Calls"],
        "Total Answered":
            lambda m: m["MO Answered"] + m["MT Answered"],
        "MO Answer\nRate (%)":
            lambda m: (m["MO Answered"] / m["MO Total Calls"]
                       .replace(0, float("nan")) * 100).fillna(0).round(2),
        "MT Answer\nRate (%)":
            lambda m: (m["MT Answered"] / m["MT Total Calls"]
                       .replace(0, float("nan")) * 100).fillna(0).round(2),
        "Total Answer\nRate (%)":
            lambda m: (m["Total Answered"] / m["Total Calls"]
                       .replace(0, float("nan")) * 100).fillna(0).round(2),
    },

    "sum_cols": [
        "MO Total Calls", "MO Answered", "MT Total Calls", "MT Answered",
        "Total Calls", "Total Answered",
        "Total Recovery\nTimer_Expiry_102", "Total Interworking\nUnspecified",
        "MO Recovery\nTimer_Expiry_102",    "MT CAUSE\nACK TIMEOUT",
    ],
    "avg_cols":  ["MO Answer\nRate (%)", "MT Answer\nRate (%)", "Total Answer\nRate (%)"],
    "rate_cols": ["MO Answer\nRate (%)", "MT Answer\nRate (%)", "Total Answer\nRate (%)"],
    "int_cols":  [
        "MO Total Calls", "MO Answered", "MT Total Calls", "MT Answered",
        "Total Calls", "Total Answered",
        "Total Recovery\nTimer_Expiry_102", "Total Interworking\nUnspecified",
        "MO Recovery\nTimer_Expiry_102",    "MT CAUSE\nACK TIMEOUT",
    ],
    "kpi_cols": ["MO Answer\nRate (%)", "MT Answer\nRate (%)", "Total Answer\nRate (%)"],

    "col_widths": {
        "Date Time": 20, "PLMN": 8,
        "MO Total Calls": 12,  "MO Answered": 12,
        "MT Total Calls": 12,  "MT Answered": 12,
        "Total Calls": 12,     "Total Answered": 12,
        "Total Recovery\nTimer_Expiry_102": 17,
        "Total Interworking\nUnspecified":  17,
        "MO Recovery\nTimer_Expiry_102":    17,
        "MT CAUSE\nACK TIMEOUT":            14,
        "MO Answer\nRate (%)":   13,
        "MT Answer\nRate (%)":   13,
        "Total Answer\nRate (%)": 14,
    },
}


# ── Report 2: CPU / RAM Utilization ──────────────────────────────────────────

CPU_RAM_REPORT = {
    "label":        "CPU / RAM Utilization Report",
    "sheet_prefix": "CPU_RAM",
    "columns": [
        "Date Time", "PLMN", "Node Name",
        "CPU Util (%)", "RAM Util (%)",
        "CPU Peak (%)", "RAM Peak (%)",
    ],
    "csv_map": {
        "PLMN":         ["PLMN", "plmn"],
        "Node Name":    ["node_name", "node", "host", "server"],
        "CPU Util (%)": ["cpu_util",  "cpu_usage",  "cpu_percent"],
        "RAM Util (%)": ["ram_util",  "mem_util",   "memory_usage", "ram_usage"],
        "CPU Peak (%)": ["cpu_peak",  "cpu_max"],
        "RAM Peak (%)": ["ram_peak",  "mem_peak",   "memory_peak"],
    },
    "computed":  {},
    "sum_cols":  [],
    "avg_cols":  ["CPU Util (%)", "RAM Util (%)", "CPU Peak (%)", "RAM Peak (%)"],
    "rate_cols": ["CPU Util (%)", "RAM Util (%)", "CPU Peak (%)", "RAM Peak (%)"],
    "int_cols":  [],
    "kpi_cols":  ["CPU Util (%)", "RAM Util (%)"],
    "col_widths": {
        "Date Time": 20, "PLMN": 8, "Node Name": 20,
        "CPU Util (%)": 14, "RAM Util (%)": 14,
        "CPU Peak (%)": 13, "RAM Peak (%)": 13,
    },
}


# ── Report 3: Registered Subscriber Count ────────────────────────────────────

REGISTERED_COUNT_REPORT = {
    "label":        "Registered Subscriber Count Report",
    "sheet_prefix": "RegCount",
    "columns": [
        "Date Time", "PLMN",
        "Total Registered", "Active Registered",
        "Idle Registered",  "Deregistered",
        "Reg Success\nRate (%)",
    ],
    "csv_map": {
        "PLMN":              ["PLMN", "plmn"],
        "Total Registered":  ["total_registered", "total_reg"],
        "Active Registered": ["active_reg",        "active_registered"],
        "Idle Registered":   ["idle_reg",           "idle_registered"],
        "Deregistered":      ["dereg",              "deregistered"],
    },
    "computed": {
        "Reg Success\nRate (%)":
            lambda m: (m["Active Registered"] / m["Total Registered"]
                       .replace(0, float("nan")) * 100).fillna(0).round(2),
    },
    "sum_cols":  ["Total Registered", "Active Registered", "Idle Registered", "Deregistered"],
    "avg_cols":  ["Reg Success\nRate (%)"],
    "rate_cols": ["Reg Success\nRate (%)"],
    "int_cols":  ["Total Registered", "Active Registered", "Idle Registered", "Deregistered"],
    "kpi_cols":  ["Reg Success\nRate (%)"],
    "col_widths": {
        "Date Time": 20, "PLMN": 8,
        "Total Registered": 16, "Active Registered": 18,
        "Idle Registered": 16,  "Deregistered": 14,
        "Reg Success\nRate (%)": 16,
    },
}


# ── Report 4: System Crash / Fault ───────────────────────────────────────────

CRASH_REPORT = {
    "label":        "System Crash / Fault Report",
    "sheet_prefix": "Crash",
    "columns": [
        "Date Time", "PLMN", "Node Name",
        "Crash Count", "Fault Type", "Severity",
        "Recovery Time\n(sec)", "Status",
    ],
    "csv_map": {
        "PLMN":                 ["PLMN", "plmn"],
        "Node Name":            ["node_name",     "node",  "host",   "server"],
        "Crash Count":          ["crash_count",   "crash"],
        "Fault Type":           ["fault_type",    "fault", "type"],
        "Severity":             ["severity",      "level"],
        "Recovery Time\n(sec)": ["recovery_time", "recover_sec", "recover"],
        "Status":               ["status",        "state"],
    },
    "computed":  {},
    "sum_cols":  ["Crash Count"],
    "avg_cols":  ["Recovery Time\n(sec)"],
    "rate_cols": [],
    "int_cols":  ["Crash Count", "Recovery Time\n(sec)"],
    "kpi_cols":  [],
    "col_widths": {
        "Date Time": 20, "PLMN": 8, "Node Name": 18,
        "Crash Count": 12, "Fault Type": 16, "Severity": 12,
        "Recovery Time\n(sec)": 16, "Status": 12,
    },
}


# Maps menu keys to report definitions
ALL_REPORTS = {
    "1": TRAFFIC_REPORT,
    "2": CPU_RAM_REPORT,
    "3": REGISTERED_COUNT_REPORT,
    "4": CRASH_REPORT,
}
