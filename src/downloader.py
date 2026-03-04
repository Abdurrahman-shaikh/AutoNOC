"""
Automates the web portal to download a Voice Traffic CSV.

Flow:
  1. Opens Chrome (visible) at the login page
  2. Pauses — user logs in manually then presses Enter
  3. Navigates to the report page, retries if slow to load
  4. Fills all dropdowns via JavaScript (portal uses Select2 widgets
     which cannot be driven by standard Selenium Select())
  5. Opens the date picker calendar and selects:
       Start date = yesterday
       End date   = today
     Then clicks Apply
  6. Clicks Show Report, waits for the DataTable to populate
     Auto-retries once with a page refresh if the table stays empty
  7. Clicks the CSV button, waits for the file in the download folder
  8. Returns the CSV file path to main.py

HTML elements confirmed from DevTools inspection:
  select#report       Report Type       (Select2)
  select#plmn         PLMN              (Select2)
  select#period       Report Periodicity (Select2)
  select#template     Select Template   (Select2)
  input#max-date      Date range text input (triggers a date-range picker)
  button#pc           Show Report
  a.buttons-csv       CSV download link
  td.active.start-date  Calendar start-date cell
  td.today            Calendar today cell (end date)
  div.drp-buttons .applyBtn  Apply button in date picker

Cross-platform: works on Windows and Linux.
"""

import os
import glob
import time
import logging
import platform
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


# ── OS-aware download directory ───────────────────────────────────────────────

def _default_download_dir() -> str:
    """
    Returns ~/Downloads/AutoNOC_Reports on both Windows and Linux.
    Creates the directory if it does not exist.
    """
    if platform.system() == "Windows":
        base = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
    else:
        base = Path.home() / "Downloads"
    folder = base / "AutoNOC_Reports"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


# ── Select2 dropdown helpers ──────────────────────────────────────────────────

def _list_options(driver, select_id: str) -> list:
    """
    Returns all visible option texts for a <select> element.
    Logged on first run so you can verify config values match exactly.
    """
    return driver.execute_script("""
        var s = document.getElementById(arguments[0]);
        if (!s) return ['NOT_FOUND'];
        return Array.from(s.options).map(o => o.text.trim()).filter(Boolean);
    """, select_id) or []


def _select2_set(driver, select_id: str, visible_text: str) -> bool:
    """
    Sets a Select2 dropdown to the option matching visible_text.

    Select2 widgets replace the native <select> with a styled span.
    Standard Selenium Select() only works on native selects, so we:
      Strategy 1: Set .value on the underlying <select> via JS and fire 'change'
      Strategy 2 (fallback): Click the Select2 span to open it, then click the option
    """
    # Strategy 1 — direct JavaScript value assignment
    result = driver.execute_script("""
        var s = document.getElementById(arguments[0]);
        if (!s) return 'NOT_FOUND';
        for (var i = 0; i < s.options.length; i++) {
            if (s.options[i].text.trim() === arguments[1]) {
                s.value = s.options[i].value;
                s.dispatchEvent(new Event('change', {bubbles: true}));
                return 'OK:' + s.options[i].value;
            }
        }
        return 'NO_MATCH';
    """, select_id, visible_text)

    if isinstance(result, str) and result.startswith("OK"):
        log.info(f"    #{select_id} → '{visible_text}'")
        time.sleep(0.8)
        return True

    log.warning(f"    #{select_id} JS failed ({result}) — trying click fallback")

    # Strategy 2 — click the rendered Select2 container, then click the option
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        span = driver.find_element(
            By.XPATH,
            f"(//select[@id='{select_id}']/following-sibling::span[contains(@class,'select2')]"
            f"|//select[@id='{select_id}']/parent::*/span[contains(@class,'select2')])[1]"
        )
        span.click()
        time.sleep(0.8)
        opt = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((
            By.XPATH,
            f"//li[contains(@class,'select2-results__option')"
            f" and normalize-space(.)='{visible_text}']"
        )))
        opt.click()
        log.info(f"    #{select_id} click → '{visible_text}'")
        time.sleep(0.8)
        return True
    except Exception as e:
        log.error(f"    #{select_id} both strategies failed: {e}")
        return False


# ── Date picker ───────────────────────────────────────────────────────────────

def _set_date_range(driver):
    """
    Opens the date range picker by clicking input#max-date, then
    selects yesterday as the start date and today as the end date
    using calendar cell clicks, and finally clicks Apply.

    The portal uses a daterangepicker widget. Calendar cells are
    identified by their CSS classes:
      td.available            = any selectable date
      td.active.start-date    = currently selected start
      td.today                = today's calendar cell
      div.drp-buttons .applyBtn = the Apply button
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    yesterday = (datetime.now() - timedelta(days=1)).day
    today_day = datetime.now().day
    log.info(f"  Setting date: yesterday ({yesterday}) → today ({today_day})")

    try:
        # Open the date picker by clicking the date input field
        date_input = driver.find_element(By.ID, "max-date")
        driver.execute_script("arguments[0].click();", date_input)
        time.sleep(1)

        # Wait for the calendar widget to appear
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.daterangepicker"))
        )

        # Click yesterday in the left calendar panel.
        # We look for a td that is 'available', not 'disabled', and has the correct date number.
        # data-title attributes follow the pattern "r{row}c{col}" — we match by visible text.
        yesterday_cells = driver.find_elements(
            By.XPATH,
            f"//div[contains(@class,'drp-calendar left')]"
            f"//td[contains(@class,'available') and not(contains(@class,'disabled'))"
            f" and normalize-space(text())='{yesterday}']"
        )
        if not yesterday_cells:
            # Fallback: search both calendars
            yesterday_cells = driver.find_elements(
                By.XPATH,
                f"//td[contains(@class,'available') and not(contains(@class,'disabled'))"
                f" and normalize-space(text())='{yesterday}']"
            )
        if yesterday_cells:
            driver.execute_script("arguments[0].click();", yesterday_cells[0])
            log.info(f"  Clicked yesterday ({yesterday})")
        else:
            log.warning(f"  Could not find yesterday ({yesterday}) in calendar")
        time.sleep(0.5)

        # Click today as the end date.
        # The td.today class marks the current day reliably.
        today_cells = driver.find_elements(
            By.CSS_SELECTOR,
            "td.today.available, td.available.today"
        )
        if not today_cells:
            today_cells = driver.find_elements(
                By.XPATH,
                f"//td[contains(@class,'today') and contains(@class,'available')]"
            )
        if today_cells:
            driver.execute_script("arguments[0].click();", today_cells[-1])
            log.info(f"  Clicked today ({today_day})")
        else:
            log.warning(f"  Could not find today ({today_day}) in calendar")
        time.sleep(0.5)

        # Click the Apply button to confirm the selection
        apply_btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "div.drp-buttons .applyBtn, .daterangepicker .applyBtn"
            ))
        )
        driver.execute_script("arguments[0].click();", apply_btn)
        log.info("  Date picker Apply clicked")
        time.sleep(0.8)

    except Exception as e:
        log.warning(f"  Date picker failed: {e} — proceeding without date change")


# ── Table load detection ──────────────────────────────────────────────────────

def _wait_for_table(driver, timeout: int = 90) -> bool:
    """
    Polls until the DataTable (id='traffic1') contains real data rows.
    Returns True when data is present, False on timeout.
    """
    from selenium.webdriver.common.by import By
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "table#traffic1 tbody tr td")
            info = driver.find_elements(By.CSS_SELECTOR, "[id*='traffic1_info']")
            if rows:
                if info and "0 entries" not in info[0].text and "entries" in info[0].text:
                    log.info(f"    Table ready: {info[0].text.strip()}")
                    return True
                elif not info:
                    log.info(f"    Table cells visible: {len(rows)}")
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


# ── CSV download detection — 3-layer approach ─────────────────────────────────
#
# Problem with naive "new file appeared" detection:
#   - Portal always downloads a file with the SAME generic filename every time.
#     So on the second run, the file already exists — there is no "new" file.
#   - If two runs happen quickly, the before/after snapshot comparison fails.
#   - Stale .csv files from other tools can be mistaken for the download.
#
# Solution — 3 layers in priority order:
#
#   Layer 1 — RENAME TRAP (most reliable)
#     Before clicking CSV, rename any existing file with the same expected
#     filename to a backup name. After the click, wait for the original
#     filename to reappear. Because Chrome always saves to the same name,
#     this is unambiguous.
#
#   Layer 2 — TIMESTAMP COMPARISON (fallback)
#     Record the exact time just before the click. After downloading,
#     accept only files whose mtime is AFTER that timestamp.
#     This correctly ignores all pre-existing files regardless of name.
#
#   Layer 3 — SIZE STABILITY CHECK (anti-partial-download)
#     Once a candidate file is found, confirm it is complete by checking
#     that its file size stops growing. Chrome writes .crdownload while
#     downloading; the final .csv only appears when fully written.
#     But even without .crdownload, a file can still be growing — so we
#     poll size twice with a 1-second gap and only accept if size is stable.

def _get_expected_filename(driver) -> str:
    """
    Reads the portal page title or a known pattern to predict the
    filename Chrome will use. Falls back to None if it can't be determined.

    The portal typically names the file after the report title, e.g.:
      'Voice Traffic Report for IMS.csv'  or  'traffic1.csv'
    We try to read it from the DataTables export button's aria-label,
    or from the page <title>, as a best guess.
    """
    try:
        # DataTables CSV button often carries the filename in its aria-controls
        # attribute, which matches the table id — the download name mirrors it.
        title = driver.execute_script("return document.title || '';")
        if title:
            # Sanitise to a valid filename fragment
            clean = "".join(c for c in title if c.isalnum() or c in " _-")
            return clean.strip() + ".csv" if clean.strip() else None
    except Exception:
        pass
    return None


def _file_size_stable(path: str, wait: float = 1.5) -> bool:
    """
    Returns True if the file size has not changed over `wait` seconds.
    This guards against reading a file that Chrome is still writing.
    """
    try:
        size1 = os.path.getsize(path)
        time.sleep(wait)
        size2 = os.path.getsize(path)
        return size1 == size2 and size1 > 0
    except OSError:
        return False


def _snapshot_dir(dl_dir: str) -> dict:
    """
    Returns a dict of {filepath: mtime} for all .csv files in dl_dir.
    Used as a before-snapshot so we can detect exactly which file is new.
    """
    result = {}
    for f in glob.glob(os.path.join(dl_dir, "*.csv")):
        try:
            result[f] = os.path.getmtime(f)
        except OSError:
            pass
    return result


def _rename_existing(dl_dir: str, expected_name: str) -> str | None:
    """
    Layer 1: If a file with expected_name already exists, rename it to
    a timestamped backup so Chrome can recreate it fresh.
    Returns the backup path (so we can restore it on error), or None.
    """
    target = os.path.join(dl_dir, expected_name)
    if os.path.exists(target):
        ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(dl_dir, f"_backup_{ts}_{expected_name}")
        try:
            os.rename(target, backup)
            log.info(f"    Renamed existing '{expected_name}' → backup to clear path")
            return backup
        except OSError as e:
            log.warning(f"    Could not rename existing file: {e}")
    return None


def _wait_for_csv(dl_dir: str, snapshot_before: dict,
                  click_time: float, timeout: int = 60,
                  expected_name: str = None) -> str:
    """
    Waits for the portal CSV download to complete and returns its path.

    Uses all 3 detection layers in order:

      Layer 1 — If expected_name is known, wait for that exact file to appear.
      Layer 2 — Accept any .csv whose mtime > click_time AND is not in snapshot.
      Layer 3 — Confirm the winning file is stable (not still being written).

    Parameters:
      dl_dir         : directory Chrome downloads to
      snapshot_before: {filepath: mtime} taken just before clicking CSV
      click_time     : time.time() value recorded just before the click
      timeout        : seconds to wait before giving up
      expected_name  : predicted filename (optional, from _get_expected_filename)
    """
    log.info(f"    Watching for CSV in: {dl_dir}")
    log.info(f"    Files before click : {len(snapshot_before)}")
    if expected_name:
        log.info(f"    Expected filename  : {expected_name}")

    deadline = time.time() + timeout
    candidate = None

    while time.time() < deadline:
        time.sleep(1.5)

        # Ignore .crdownload and .tmp — Chrome's partial download markers
        all_csvs = [
            f for f in glob.glob(os.path.join(dl_dir, "*.csv"))
            if not f.endswith((".crdownload", ".tmp"))
        ]

        # ── Layer 1: exact filename match ──────────────────────────────
        if expected_name:
            exact = os.path.join(dl_dir, expected_name)
            if exact in all_csvs and exact not in snapshot_before:
                candidate = exact
                log.info(f"    Layer 1 match (exact name): {os.path.basename(candidate)}")

        # ── Layer 2: new file with mtime after the click ───────────────
        if not candidate:
            newer = [
                f for f in all_csvs
                if f not in snapshot_before              # not there before
                or os.path.getmtime(f) > click_time + 0.5  # or updated after click
            ]
            # Filter out files that existed before and haven't changed
            truly_new = [
                f for f in newer
                if f not in snapshot_before
                or snapshot_before.get(f, 0) < os.path.getmtime(f) - 0.5
            ]
            if truly_new:
                # Pick the one most recently modified
                candidate = max(truly_new, key=os.path.getmtime)
                log.info(f"    Layer 2 match (new/updated): {os.path.basename(candidate)}")

        # ── Layer 3: size-stability check ──────────────────────────────
        if candidate:
            if _file_size_stable(candidate, wait=1.5):
                size_kb = os.path.getsize(candidate) / 1024
                log.info(f"    Layer 3 confirmed (stable, {size_kb:.1f} KB): {candidate}")
                return candidate
            else:
                log.info(f"    File found but still growing — waiting...")
                candidate = None  # reset and keep polling

    raise TimeoutError(
        f"No valid CSV appeared in '{dl_dir}' within {timeout}s.\n"
        f"Check that the portal actually generated data and the CSV button worked."
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def download_csv(config: dict, download_dir: str = None) -> str:
    """
    Runs the full portal automation sequence.
    Called by main.py when running in production mode.

    Returns the absolute path of the downloaded CSV file.
    """
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    portal = config["portal"]
    dl_dir = download_dir or _default_download_dir()
    os.makedirs(dl_dir, exist_ok=True)
    # Chrome requires an absolute path for the download directory
    dl_abs = str(Path(dl_dir).resolve())

    # Configure Chrome to download silently to dl_abs
    opts = webdriver.ChromeOptions()
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("prefs", {
        "download.default_directory":              dl_abs,
        "download.prompt_for_download":            False,
        "download.directory_upgrade":              True,
        "safebrowsing.enabled":                    True,
        "profile.default_content_settings.popups": 0,
    })

    log.info("Starting browser...")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts,
    )
    driver.set_page_load_timeout(60)

    try:
        # ── Step 1: Open login page, wait for manual login ────────────────
        login_url = portal.get(
            "login_url",
            portal["url"].rsplit("/", 1)[0] + "/login"
        )
        log.info(f"Opening: {login_url}")
        driver.get(login_url)
        time.sleep(2)

        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║   AutoNOC — Browser is open. Please log in manually.    ║")
        print(f"║   {login_url:<56}║")
        print("║                                                          ║")
        print("║   Once you see the main dashboard, come back here.      ║")
        print("╚══════════════════════════════════════════════════════════╝")
        input("  >> Press ENTER after login is complete: ")
        print()

        # ── Step 2: Navigate to report page ──────────────────────────────
        report_url = portal["url"]
        log.info(f"Navigating to: {report_url}")
        driver.get(report_url)

        # Retry up to 3 times if the page is slow to load
        for attempt in range(1, 4):
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.ID, "report"))
                )
                log.info("  Report page loaded")
                break
            except Exception:
                log.warning(f"  Load attempt {attempt}/3 — refreshing...")
                driver.refresh()
                time.sleep(4)
        else:
            raise RuntimeError("Report page did not load after 3 retries.")

        time.sleep(1.5)   # wait for Select2 widgets to initialise

        # Log available options to help verify config values on first run
        for sid in ("report", "plmn", "period"):
            log.info(f"  #{sid} options: {_list_options(driver, sid)}")

        # ── Step 3: Fill Report Type, PLMN, Periodicity dropdowns ────────
        log.info("Filling dropdowns...")
        _select2_set(driver, "report", portal["report_type"])
        _select2_set(driver, "plmn",   portal["plmn"])
        _select2_set(driver, "period", portal["report_periodicity"])

        # Template dropdown — may have id="template" or be the 4th select on the form
        template = portal.get("template", "").strip()
        tmpl_result = driver.execute_script("""
            var s = document.getElementById('template');
            if (!s) {
                var all = document.querySelectorAll(
                    'select.select2_single, select.form-control'
                );
                s = all[3] || all[all.length - 1] || null;
            }
            if (!s) return 'NOT_FOUND';
            var want = arguments[0];
            if (want) {
                for (var i = 0; i < s.options.length; i++) {
                    if (s.options[i].text.trim() === want) {
                        s.value = s.options[i].value;
                        s.dispatchEvent(new Event('change', {bubbles: true}));
                        return 'OK:' + want;
                    }
                }
            }
            // Auto-select first non-empty option if no specific value needed
            if (s.options.length > 1) {
                s.selectedIndex = 1;
                s.dispatchEvent(new Event('change', {bubbles: true}));
                return 'AUTO:' + s.options[1].text.trim();
            }
            return 'EMPTY';
        """, template)
        log.info(f"  Template: {tmpl_result}")
        time.sleep(0.8)

        # ── Step 4: Set date range via calendar picker ────────────────────
        # Selects yesterday (start) and today (end), then clicks Apply
        _set_date_range(driver)

        # ── Step 5: Click Show Report ─────────────────────────────────────
        log.info("Clicking Show Report...")
        try:
            show_btn = driver.find_element(By.ID, "pc")
        except Exception:
            show_btn = driver.find_element(
                By.XPATH, "//button[normalize-space(text())='Show Report']"
            )
        driver.execute_script("arguments[0].click();", show_btn)
        time.sleep(3)

        # ── Step 6: Wait for table data (with one auto-retry) ─────────────
        log.info("Waiting for report data (up to 90s)...")
        if not _wait_for_table(driver, timeout=90):
            log.warning("Table empty — refreshing and retrying once...")
            driver.refresh()
            time.sleep(4)

            # Re-fill everything after the refresh
            _select2_set(driver, "report", portal["report_type"])
            _select2_set(driver, "plmn",   portal["plmn"])
            _select2_set(driver, "period", portal["report_periodicity"])
            driver.execute_script("""
                var s = document.getElementById('template');
                if (!s) {
                    var all = document.querySelectorAll(
                        'select.select2_single, select.form-control'
                    );
                    s = all[3] || null;
                }
                if (s && s.options.length > 1) {
                    s.selectedIndex = 1;
                    s.dispatchEvent(new Event('change', {bubbles: true}));
                }
            """)
            _set_date_range(driver)
            time.sleep(0.5)

            try:
                show_btn = driver.find_element(By.ID, "pc")
            except Exception:
                show_btn = driver.find_element(
                    By.XPATH, "//button[normalize-space(text())='Show Report']"
                )
            driver.execute_script("arguments[0].click();", show_btn)
            time.sleep(3)

            if not _wait_for_table(driver, timeout=60):
                log.warning("Data still not loaded — downloading whatever is available")

        # ── Step 7: Prepare download detection BEFORE clicking CSV ───────
        # Take a directory snapshot and record the click time NOW —
        # before the click — so Layer 2 mtime comparison is accurate.
        # Also predict the expected filename and rename any existing copy
        # so Chrome can write a fresh file (Layer 1).
        log.info("Preparing to capture CSV download...")
        expected_name = _get_expected_filename(driver)
        snapshot      = _snapshot_dir(dl_dir)
        backup_path   = _rename_existing(dl_dir, expected_name) if expected_name else None
        click_time    = time.time()   # record the moment just before the click

        log.info(f"  Pre-click snapshot : {len(snapshot)} existing CSV(s)")
        log.info(f"  Expected filename  : {expected_name or 'unknown'}")

        # ── Step 8: Click the CSV export button ───────────────────────────
        log.info("Clicking CSV export...")
        try:
            csv_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.buttons-csv"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", csv_btn)
            time.sleep(0.4)
            driver.execute_script("arguments[0].click();", csv_btn)
            log.info("  Clicked a.buttons-csv")
        except Exception as e:
            log.warning(f"  a.buttons-csv not found ({e}) — trying text fallback")
            csv_btn = driver.find_element(
                By.XPATH,
                "//a[normalize-space(text())='CSV'] | //button[normalize-space(text())='CSV']"
            )
            driver.execute_script("arguments[0].click();", csv_btn)
            log.info("  Clicked CSV (text fallback)")

        # ── Step 9: Wait for the correct file using 3-layer detection ────
        # Layer 1 — exact filename match (most reliable)
        # Layer 2 — any new/updated CSV with mtime after click_time
        # Layer 3 — size-stability check (confirms file fully written)
        csv_path = _wait_for_csv(
            dl_dir         = dl_dir,
            snapshot_before= snapshot,
            click_time     = click_time,
            timeout        = 60,
            expected_name  = expected_name,
        )

        # Rename the file with a timestamp so the next run starts clean
        # and the archive is easy to audit.
        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        base         = os.path.basename(csv_path)
        name_no_ext  = os.path.splitext(base)[0]
        stamped_name = f"{name_no_ext}_{ts}.csv"
        stamped_path = os.path.join(dl_dir, stamped_name)
        try:
            os.rename(csv_path, stamped_path)
            log.info(f"  Renamed → {stamped_name}  (timestamped for audit)")
            csv_path = stamped_path
        except OSError as e:
            log.warning(f"  Could not rename downloaded file: {e} — using as-is")

        # Clean up the backup we made for Layer 1 (we no longer need it)
        if backup_path and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                log.info("  Removed pre-existing backup file")
            except OSError:
                pass

        return csv_path

    except Exception as e:
        log.error(f"Download failed: {e}", exc_info=True)
        raise
    finally:
        try:
            driver.quit()
        except Exception:
            pass
