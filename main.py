"""
AutoNOC - Automated Network Operations Centre Report Generator

Usage:
  AutoNOC.exe              -> production mode (opens browser for login)
  AutoNOC.exe --test       -> test mode (uses local dummy CSV, no browser)
  AutoNOC.exe --test --all -> test mode, all 4 report types
  AutoNOC.exe --csv <path> -> use a specific CSV file directly
"""

import os
import sys
import json
import logging
import argparse
import shutil
from datetime import datetime
from pathlib import Path


# ── Path resolution ───────────────────────────────────────────────────────────
#
# Two different contexts:
#
#  A) Running as AutoNOC.exe (PyInstaller --onefile)
#     sys.frozen  = True
#     sys.executable = C:\Users\you\AutoNOC.exe
#     sys._MEIPASS   = C:\Users\you\AppData\Local\Temp\_MEIxxxxxx\
#                      (PyInstaller extracts bundled files here at startup)
#
#     BASE_DIR   = folder containing AutoNOC.exe  <- all user files live here
#     BUNDLE_DIR = sys._MEIPASS                   <- src/, config/ defaults
#
#  B) Running as python main.py
#     BASE_DIR   = folder containing main.py
#     BUNDLE_DIR = same as BASE_DIR

if getattr(sys, "frozen", False):
    BASE_DIR   = Path(sys.executable).parent
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR   = Path(__file__).parent
    BUNDLE_DIR = BASE_DIR

# Make sure Python can find src/ whether we are frozen or not
for p in [str(BUNDLE_DIR), str(BASE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.logger_setup       import setup as setup_logging
from src.report_definitions import ALL_REPORTS
from src.processor          import process
from src.excel_writer       import append_report


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """
    Always reads config/config.json from BASE_DIR (next to the .exe).
    On very first run, if the file is missing, copies the bundled default
    from inside the EXE so the user has something to edit.
    """
    config_path = BASE_DIR / "config" / "config.json"

    if not config_path.exists():
        bundled = BUNDLE_DIR / "config" / "config.json"
        if bundled.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(str(bundled), str(config_path))
            print(f"  First run: created config at {config_path}")
        else:
            print(f"  [ERROR] config/config.json not found.")
            input("  Press Enter to exit...")
            sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_paths(cfg: dict) -> dict:
    """
    Makes output/, downloads/, logs/ absolute paths anchored at BASE_DIR.
    This ensures they are always created next to the .exe, not in the temp folder.
    """
    for key in ("folder", "download_folder", "log_folder"):
        cfg["output"][key] = str(BASE_DIR / cfg["output"][key])
    return cfg


# ── Menus ─────────────────────────────────────────────────────────────────────

def ask_plmn(cfg: dict) -> dict:
    """
    Numbered circle/PLMN menu built from config.json -> circles list.
    To add a new circle just add it in config.json — no code change needed.
    """
    circles = cfg.get("circles", [])
    if not circles:
        print("  [ERROR] No circles defined in config.json -> circles")
        sys.exit(1)

    print()
    print("+=============================================================+")
    print("|           AutoNOC  --  Select Circle / PLMN                 |")
    print("+=============================================================+")
    for i, c in enumerate(circles, 1):
        print(f"|  [{i}]  {c['name']:<20}  PLMN: {c['plmn']:<10}              |")
    print("+=============================================================+")
    print()

    while True:
        raw = input(f"  Select [1-{len(circles)}]: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(circles):
                chosen = circles[idx]
                print(f"\n  Selected: {chosen['name']}  (PLMN {chosen['plmn']})")
                return chosen
        except ValueError:
            pass
        print(f"  Enter a number between 1 and {len(circles)}.")


def ask_window_hours() -> int:
    """Ask how many hours of data to include (1-24, default 4)."""
    print()
    while True:
        raw = input("  Hours of data to include? [1-24, default=4]: ").strip()
        if raw == "":
            return 4
        try:
            h = int(raw)
            if 1 <= h <= 24:
                return h
            print("  Enter a number between 1 and 24.")
        except ValueError:
            print("  Invalid — enter a whole number.")


def show_menu() -> list:
    """Report type selection menu. Returns list of selected keys."""
    print()
    print("+=============================================================+")
    print("|           AutoNOC  --  Report Selection                     |")
    print("+=============================================================+")
    for key, rdef in ALL_REPORTS.items():
        print(f"|  [{key}]  {rdef['label']:<51}|")
    print("|  [A]  Generate ALL report types                             |")
    print("|  [Q]  Quit                                                  |")
    print("+=============================================================+")
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
        print(f"  Invalid choice '{choice}'. Try again.\n")
        return show_menu()


# ── Report runner ─────────────────────────────────────────────────────────────

def run_report(key: str, csv_path: str, window_hours: int, cfg: dict, plmn: str):
    """Filter CSV -> build DataFrame -> write formatted Excel block."""
    log  = logging.getLogger(__name__)
    rdef = ALL_REPORTS[key]

    log.info(f"-- {rdef['label']} --")
    log.info(f"   CSV    : {csv_path}")
    log.info(f"   Window : {window_hours}h  |  PLMN: {plmn}")

    summary = process(csv_path, window_hours, rdef, plmn, cfg)
    if summary.empty:
        log.warning("  No data in window — skipping.")
        return

    xlsx, sheet, r1, r2 = append_report(summary, rdef, cfg, plmn)
    log.info(f"  OK  sheet='{sheet}'  rows {r1}-{r2}  |  {xlsx}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AutoNOC")
    parser.add_argument("--test", action="store_true",
                        help="Use local dummy CSV, no browser")
    parser.add_argument("--all",  action="store_true",
                        help="Generate all report types")
    parser.add_argument("--csv",  default=None,
                        help="Path to a specific CSV file")
    args = parser.parse_args()

    cfg = resolve_paths(load_config())
    setup_logging(cfg["output"]["log_folder"])
    log = logging.getLogger(__name__)

    print()
    print("  +----------------------------------------+")
    print("  |            AutoNOC  v1.0               |")
    print("  +----------------------------------------+")
    print(f"  Output : {cfg['output']['folder']}")
    print(f"  File   : {cfg['output']['master_filename']}")
    print(f"  Time   : {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")

    # Select reports
    selected = list(ALL_REPORTS.keys()) if args.all else show_menu()
    log.info(f"Reports: {[ALL_REPORTS[k]['label'] for k in selected]}")

    # Select circle / PLMN
    non_interactive = args.all and args.test
    if non_interactive:
        circle = cfg["circles"][0]
        plmn   = circle["plmn"]
        log.info(f"Non-interactive: using {circle['name']} PLMN {plmn}")
    else:
        circle = ask_plmn(cfg)
        plmn   = circle["plmn"]
        log.info(f"Circle: {circle['name']}  PLMN: {plmn}")

    # Time window
    window_hours = 4 if non_interactive else ask_window_hours()
    log.info(f"Window: {window_hours}h")

    # Get CSV
    if args.csv:
        csv_path = args.csv

    elif args.test:
        csv_path = str(BASE_DIR / "downloads" / "dummy_traffic_report.csv")
        if not os.path.exists(csv_path):
            log.info("Generating dummy CSV...")
            import subprocess
            gen = str(BUNDLE_DIR / "generate_dummy_csv.py")
            subprocess.run([sys.executable, gen], check=True,
                           cwd=str(BASE_DIR))
        log.info(f"Test CSV: {csv_path}")

    else:
        log.info(f"Opening browser for {circle['name']} (PLMN {plmn})...")
        try:
            from src.downloader import download_csv
            dl_dir = cfg["output"]["download_folder"]
            os.makedirs(dl_dir, exist_ok=True)
            cfg["portal"]["plmn"] = plmn
            csv_path = download_csv(cfg, dl_dir)
        except Exception as e:
            log.error(f"Download failed: {e}")
            input("\n  Press Enter to exit...")
            sys.exit(1)

    # Archive raw CSV
    def archive_csv(path: str):
        arch = os.path.join(cfg["output"]["download_folder"], "archive")
        os.makedirs(arch, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.copy(path, os.path.join(arch, f"raw_{plmn}_{ts}.csv"))
        except Exception:
            pass

    # Run reports
    print()
    for key in selected:
        try:
            run_report(key, csv_path, window_hours, cfg, plmn)
        except Exception as e:
            log.error(f"'{ALL_REPORTS[key]['label']}' failed: {e}", exc_info=True)

    archive_csv(csv_path)

    print()
    log.info("=" * 60)
    log.info(f"  Done  [{circle['name']} / PLMN {plmn}]")
    log.info(f"  {cfg['output']['folder']}/{cfg['output']['master_filename']}")
    log.info("=" * 60)

    # Keep window open when running as .exe so user can read output
    if getattr(sys, "frozen", False):
        input("\n  Press Enter to close...")


if __name__ == "__main__":
    main()
