"""
AutoNOC — Automated Network Operations Centre Report Generator

Generates formatted Excel reports from portal traffic data.

Usage:
  python main.py              → production mode (opens browser for login)
  python main.py --test       → test mode (uses local dummy CSV, no browser)
  python main.py --test --all → test mode, generate all 4 report types
  python main.py --csv <path> → use a specific CSV file directly
"""

import os
import sys
import json
import logging
import argparse
import shutil
from datetime import datetime
from pathlib import Path

# Resolve base directory — works both as a .py file and as a PyInstaller .exe
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))

from src.logger_setup       import setup as setup_logging
from src.report_definitions import ALL_REPORTS
from src.processor          import process
from src.excel_writer       import append_report


# ── Config loading ────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Reads config/config.json and returns it as a dict."""
    path = BASE_DIR / "config" / "config.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_paths(cfg: dict) -> dict:
    """
    Converts relative output paths in config to absolute paths
    anchored at the project BASE_DIR. Ensures portability across machines.
    """
    for key in ("folder", "download_folder", "log_folder"):
        cfg["output"][key] = str(BASE_DIR / cfg["output"][key])
    return cfg


# ── User input helpers ────────────────────────────────────────────────────────

def ask_plmn(cfg: dict) -> dict:
    """
    Shows a numbered menu of circles loaded from config.json → circles.
    User picks a number. Returns the chosen circle dict: {name, plmn}.

    The circles list in config is the single source of truth —
    add/remove circles there without touching any code.
    """
    circles = cfg.get("circles", [])
    if not circles:
        print("  [ERROR] No circles defined in config.json → circles")
        sys.exit(1)

    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║              AutoNOC — Select Circle / PLMN                ║")
    print("╠════════════════════════════════════════════════════════════╣")
    for i, c in enumerate(circles, 1):
        line = f"  [{i}]  {c['name']}   (PLMN: {c['plmn']})"
        print(f"║  {line:<56}║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    while True:
        raw = input(f"  Select circle [1–{len(circles)}]: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(circles):
                chosen = circles[idx]
                print(f"\n  ✓  Selected: {chosen['name']}  (PLMN {chosen['plmn']})")
                return chosen
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(circles)}.")


def ask_window_hours() -> int:
    """
    Asks the user how many hours of data to include in the report.
    Accepts 1–24. Defaults to 4 if the user presses Enter without a value.
    Repeats the prompt if the input is invalid.
    """
    print()
    while True:
        raw = input("  How many hours of data to include? [1-24, default=4]: ").strip()
        if raw == "":
            return 4
        try:
            h = int(raw)
            if 1 <= h <= 24:
                return h
            print("  Please enter a number between 1 and 24.")
        except ValueError:
            print("  Invalid input — please enter a whole number.")


def show_menu() -> list:
    """
    Displays the report selection menu and returns a list of selected report keys.
    Loops until a valid choice is made.
    """
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║              AutoNOC — Report Generation System            ║")
    print("╠════════════════════════════════════════════════════════════╣")
    for key, rdef in ALL_REPORTS.items():
        print(f"║  [{key}]  {rdef['label']:<52}║")
    print("║  [A]  Generate ALL report types                            ║")
    print("║  [Q]  Quit                                                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    choice = input("  Select [1/2/3/4/A/Q]: ").strip().upper()

    if choice == "Q":
        print("  Exiting AutoNOC.")
        sys.exit(0)
    elif choice == "A":
        return list(ALL_REPORTS.keys())
    elif choice in ALL_REPORTS:
        return [choice]
    else:
        print(f"  Invalid choice '{choice}'. Please try again.\n")
        return show_menu()


# ── Report execution ──────────────────────────────────────────────────────────

def run_report(key: str, csv_path: str, window_hours: int, cfg: dict, plmn: str):
    """
    Processes one report type:
      1. Runs processor.process() to filter CSV and build a summary DataFrame
      2. Calls excel_writer.append_report() to write it to the master workbook

    plmn is passed in from the circle the user selected at the menu —
    it drives which column set is used (via plmn_columns in config.json).
    """
    log  = logging.getLogger(__name__)
    rdef = ALL_REPORTS[key]

    log.info(f"── {rdef['label']} ──")
    log.info(f"   CSV    : {csv_path}")
    log.info(f"   Window : last {window_hours} hours")
    log.info(f"   PLMN   : {plmn}")

    summary = process(csv_path, window_hours, rdef, plmn, cfg)
    if summary.empty:
        log.warning("  No data found in window — skipping this report.")
        return

    xlsx, sheet, r1, r2 = append_report(summary, rdef, cfg, plmn)
    log.info(f"  ✓  {xlsx}")
    log.info(f"     Sheet '{sheet}'  rows {r1}–{r2}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AutoNOC Report Generator")
    parser.add_argument("--test", action="store_true",
                        help="Use local dummy CSV (no browser required)")
    parser.add_argument("--all",  action="store_true",
                        help="Generate all report types without the menu")
    parser.add_argument("--csv",  default=None,
                        help="Path to a specific CSV file to process")
    args = parser.parse_args()

    cfg = resolve_paths(load_config())
    setup_logging(cfg["output"]["log_folder"])
    log = logging.getLogger(__name__)

    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║           AutoNOC v1.0               ║")
    print("  ╚══════════════════════════════════════╝")
    print(f"  Output : {cfg['output']['folder']}/{cfg['output']['master_filename']}")
    print(f"  Time   : {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")

    # ── Select which reports to run ───────────────────────────────────────────
    selected = list(ALL_REPORTS.keys()) if args.all else show_menu()
    log.info(f"Selected reports: {[ALL_REPORTS[k]['label'] for k in selected]}")

    # ── Select PLMN / Circle (production only — test uses dummy CSV) ──────────
    # In test/csv mode we still ask so the correct plmn_columns config is applied
    if args.all and args.test:
        # Non-interactive CI mode — use first circle in config as default
        circle = cfg["circles"][0]
        plmn   = circle["plmn"]
        log.info(f"Non-interactive mode — defaulting to: {circle['name']} (PLMN {plmn})")
    else:
        circle = ask_plmn(cfg)
        plmn   = circle["plmn"]
        log.info(f"Circle selected: {circle['name']}  PLMN: {plmn}")

    # ── Ask time window ───────────────────────────────────────────────────────
    if args.all and args.test:
        window_hours = 4
        log.info(f"Window: {window_hours} hours (default, non-interactive mode)")
    else:
        window_hours = ask_window_hours()
        log.info(f"Window: {window_hours} hours")

    # ── Resolve CSV source ────────────────────────────────────────────────────
    if args.csv:
        csv_path = args.csv
        log.info(f"Using provided CSV: {csv_path}")

    elif args.test:
        csv_path = str(BASE_DIR / "downloads" / "dummy_traffic_report.csv")
        if not os.path.exists(csv_path):
            log.info("Dummy CSV not found — generating now...")
            import subprocess
            subprocess.run(
                [sys.executable, str(BASE_DIR / "generate_dummy_csv.py")],
                check=True
            )
        log.info(f"Test CSV: {csv_path}")

    else:
        # Production: pass the chosen PLMN into the downloader so it selects
        # the correct circle in the portal dropdown automatically
        log.info(f"Launching browser — will select PLMN {plmn} ({circle['name']}) in portal...")
        try:
            from src.downloader import download_csv
            dl_dir = cfg["output"]["download_folder"]
            os.makedirs(dl_dir, exist_ok=True)
            # Inject chosen plmn into the portal config for the downloader
            cfg["portal"]["plmn"] = plmn
            csv_path = download_csv(cfg, dl_dir)
        except Exception as e:
            log.error(f"Download failed: {e}")
            sys.exit(1)

    # ── Archive raw CSV for audit trail ──────────────────────────────────────
    def archive_csv(path: str):
        arch = os.path.join(cfg["output"]["download_folder"], "archive")
        os.makedirs(arch, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.copy(path, os.path.join(arch, f"raw_{plmn}_{ts}.csv"))
        except Exception:
            pass

    # ── Run each selected report ──────────────────────────────────────────────
    print()
    for key in selected:
        try:
            run_report(key, csv_path, window_hours, cfg, plmn)
        except Exception as e:
            log.error(f"Report '{ALL_REPORTS[key]['label']}' failed: {e}", exc_info=True)

    archive_csv(csv_path)

    print()
    log.info("=" * 60)
    log.info(f"  AutoNOC — All reports completed ✓  [{circle['name']} / PLMN {plmn}]")
    log.info(f"  File: {cfg['output']['folder']}/{cfg['output']['master_filename']}")
    log.info("=" * 60)
    log.info("  Run again to append the next block.")
    log.info("  A new sheet tab is created automatically at midnight.")


if __name__ == "__main__":
    main()
