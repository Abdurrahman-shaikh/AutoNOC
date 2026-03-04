"""
Loads a downloaded CSV, filters rows to the requested time window,
and builds a typed summary DataFrame ready for Excel output.

Key behaviours:
- Time window is measured back from the LATEST timestamp in the CSV,
  not from system clock — so historical CSVs work correctly.
- Window hours are passed in at runtime (user-chosen, 1–24).
- PLMN-specific column filtering is applied via get_columns_for_plmn().
"""
import logging
import pandas as pd
from datetime import timedelta
from src.report_definitions import get_columns_for_plmn

log = logging.getLogger(__name__)


def _find_numeric(df: pd.DataFrame, fragments: list) -> pd.Series:
    """
    Searches DataFrame columns for the first one whose name contains
    any of the given fragments (case-insensitive).
    Returns a numeric Series, or a zero Series if nothing matches.
    """
    for frag in fragments:
        match = next((c for c in df.columns if frag.lower() in c.lower()), None)
        if match:
            return pd.to_numeric(df[match], errors="coerce").fillna(0)
    log.warning(f"  Column not found for {fragments} — using 0")
    return pd.Series([0.0] * len(df), dtype=float)


def _find_string(df: pd.DataFrame, fragments: list) -> pd.Series:
    """
    Same as _find_numeric but returns raw string values.
    Used for text columns like Node Name, Fault Type, Status.
    """
    for frag in fragments:
        match = next((c for c in df.columns if frag.lower() in c.lower()), None)
        if match:
            return df[match].astype(str).fillna("")
    return pd.Series([""] * len(df))


def load_and_filter(csv_path: str, window_hours: int):
    """
    Reads the CSV and keeps only rows within the last window_hours
    counting back from the most recent timestamp in the file.

    Returns:
        filtered_df : pd.DataFrame  rows within the time window
        dt_col      : str           name of the datetime column
    """
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    # Locate the datetime column by searching for 'date' or 'time' in the name
    dt_col = next(
        (c for c in df.columns if "date" in c.lower() or "time" in c.lower()), None
    )
    if not dt_col:
        raise ValueError("No Date/Time column found in CSV.")

    df[dt_col] = pd.to_datetime(df[dt_col], dayfirst=True, errors="coerce")
    df = df.dropna(subset=[dt_col]).sort_values(dt_col).reset_index(drop=True)

    latest = df[dt_col].max()
    cutoff = latest - timedelta(hours=window_hours)
    kept   = df[df[dt_col] > cutoff].reset_index(drop=True)

    log.info(f"  CSV rows total : {len(df)}")
    log.info(f"  Latest in CSV  : {latest.strftime('%d-%b-%Y %H:%M')}")
    log.info(f"  Window start   : {cutoff.strftime('%d-%b-%Y %H:%M')}")
    log.info(f"  Rows in window : {len(kept)}")
    return kept, dt_col


def build_summary(df: pd.DataFrame, dt_col: str, rdef: dict, plmn: str) -> pd.DataFrame:
    """
    Assembles the final output DataFrame from filtered rows.

    Steps:
      1. Map CSV columns → numeric series using csv_map fragments
      2. Run computed lambdas to derive additional columns
      3. Apply PLMN-specific column filtering (e.g. PLMN 40459 reduced set)
      4. Cast types and return ordered DataFrame
    """
    # Use the PLMN-appropriate column list
    columns   = get_columns_for_plmn(rdef, plmn)
    csv_map   = rdef.get("csv_map",   {})
    computed  = rdef.get("computed",  {})
    rate_cols = set(rdef.get("rate_cols", []))
    int_cols  = set(rdef.get("int_cols",  []))

    # Step 1: Map CSV columns to numeric series
    mapped = {}
    for col, frags in csv_map.items():
        mapped[col] = _find_numeric(df, frags)

    # Step 2: Compute derived columns (e.g. answer rates, totals)
    for col, func in computed.items():
        try:
            mapped[col] = func(mapped)
        except Exception as e:
            log.warning(f"  Computed column '{col}' failed: {e} — using 0")
            mapped[col] = pd.Series([0.0] * len(df))

    # Step 3: Assemble final DataFrame in the correct column order
    result = {"Date Time": df[dt_col].dt.strftime("%d-%b-%Y %H:%M")}
    for col in columns:
        if col == "Date Time":
            continue
        if col in mapped:
            s = mapped[col]
            if col in int_cols:
                result[col] = s.round(0).astype(int)
            elif col in rate_cols:
                result[col] = s.round(2)
            else:
                result[col] = s.round(4)
        else:
            # Try to read as a string column (e.g. Node Name, Status)
            frags = csv_map.get(col, [col.replace("\n", "_")])
            result[col] = _find_string(df, frags)

    return pd.DataFrame(result)


def process(csv_path: str, window_hours: int, rdef: dict, plmn: str) -> pd.DataFrame:
    """
    Full pipeline: load CSV → filter to time window → build summary DataFrame.
    Returns an empty DataFrame if no rows fall within the window.
    """
    df, dt_col = load_and_filter(csv_path, window_hours)
    if df.empty:
        log.warning("  No rows found within the time window.")
        return pd.DataFrame()
    return build_summary(df, dt_col, rdef, plmn)
