"""
Automates the web portal to download a Voice Traffic CSV.

Flow:
  1. Opens Chrome (visible) at the login page
  2. Pauses — user logs in manually then presses Enter
  3. Navigates to the report page, retries if slow to load
  4. Fills all dropdowns via JavaScript (portal uses Select2 widgets)
  5. Opens the date picker and selects yesterday (start) and today (end)
  6. Clicks Show Report, waits for the DataTable to populate
  7. Clicks the CSV button, waits for the file in the download folder
  8. Returns the CSV file path to main.py

ChromeDriver is bundled inside the EXE — no installation needed on target machine.
No internet required at runtime — chromedriver.exe is included in the build.
"""

import os
import sys
import glob
import time
import logging
import platform
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


def _get_chromedriver_path() -> str:
    """
    Resolves the chromedriver.exe path.
    Frozen EXE: sits next to AutoNOC.exe (bundled by PyInstaller).
    Dev mode:   must be placed in the project root folder.
    """
    driver_name = "chromedriver.exe" if platform.system() == "Windows" else "chromedriver"
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    driver_path = base / driver_name
    if not driver_path.exists():
        raise FileNotFoundError(
            f"ChromeDriver not found at: {driver_path}\n"
            f"Download from: https://googlechromelabs.github.io/chrome-for-testing/\n"
            f"Place '{driver_name}' in: {base}"
        )
    log.info(f"ChromeDriver: {driver_path}")
    return str(driver_path)


def _default_download_dir() -> str:
    if platform.system() == "Windows":
        base = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
    else:
        base = Path.home() / "Downloads"
    folder = base / "AutoNOC_Reports"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def _list_options(driver, select_id: str) -> list:
    return driver.execute_script("""
        var s = document.getElementById(arguments[0]);
        if (!s) return ['NOT_FOUND'];
        return Array.from(s.options).map(o => o.text.trim()).filter(Boolean);
    """, select_id) or []


def _select2_set(driver, select_id: str, visible_text: str) -> bool:
    """Sets a Select2 dropdown via JS (primary) or click fallback."""
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
        log.info(f"    #{select_id} -> '{visible_text}'")
        time.sleep(0.8)
        return True

    log.warning(f"    #{select_id} JS failed ({result}) — trying click fallback")
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
            f"//li[contains(@class,'select2-results__option') and normalize-space(.)='{visible_text}']"
        )))
        opt.click()
        log.info(f"    #{select_id} click -> '{visible_text}'")
        time.sleep(0.8)
        return True
    except Exception as e:
        log.error(f"    #{select_id} both strategies failed: {e}")
        return False


def _set_date_range(driver):
    """Opens daterangepicker, clicks yesterday and today, clicks Apply."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    yesterday = (datetime.now() - timedelta(days=1)).day
    today_day = datetime.now().day
    log.info(f"  Setting date: yesterday ({yesterday}) -> today ({today_day})")

    try:
        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "max-date"))
        time.sleep(1)
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.daterangepicker"))
        )

        y_cells = driver.find_elements(By.XPATH,
            f"//div[contains(@class,'drp-calendar left')]"
            f"//td[contains(@class,'available') and not(contains(@class,'disabled')) and normalize-space(text())='{yesterday}']"
        ) or driver.find_elements(By.XPATH,
            f"//td[contains(@class,'available') and not(contains(@class,'disabled')) and normalize-space(text())='{yesterday}']"
        )
        if y_cells:
            driver.execute_script("arguments[0].click();", y_cells[0])
            log.info(f"  Clicked yesterday ({yesterday})")
        else:
            log.warning(f"  Could not find yesterday ({yesterday})")
        time.sleep(0.5)

        t_cells = driver.find_elements(By.CSS_SELECTOR, "td.today.available, td.available.today") or \
                  driver.find_elements(By.XPATH, "//td[contains(@class,'today') and contains(@class,'available')]")
        if t_cells:
            driver.execute_script("arguments[0].click();", t_cells[-1])
            log.info(f"  Clicked today ({today_day})")
        else:
            log.warning(f"  Could not find today ({today_day})")
        time.sleep(0.5)

        apply_btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.drp-buttons .applyBtn, .daterangepicker .applyBtn"))
        )
        driver.execute_script("arguments[0].click();", apply_btn)
        log.info("  Date picker Apply clicked")
        time.sleep(0.8)
    except Exception as e:
        log.warning(f"  Date picker failed: {e} — proceeding without date change")


def _wait_for_table(driver, timeout: int = 90) -> bool:
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
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _get_expected_filename(driver) -> str:
    try:
        title = driver.execute_script("return document.title || '';")
        if title:
            clean = "".join(c for c in title if c.isalnum() or c in " _-")
            return clean.strip() + ".csv" if clean.strip() else None
    except Exception:
        pass
    return None


def _file_size_stable(path: str, wait: float = 1.5) -> bool:
    try:
        s1 = os.path.getsize(path); time.sleep(wait); s2 = os.path.getsize(path)
        return s1 == s2 and s1 > 0
    except OSError:
        return False


def _snapshot_dir(dl_dir: str) -> dict:
    result = {}
    for f in glob.glob(os.path.join(dl_dir, "*.csv")):
        try: result[f] = os.path.getmtime(f)
        except OSError: pass
    return result


def _rename_existing(dl_dir: str, expected_name: str):
    target = os.path.join(dl_dir, expected_name)
    if os.path.exists(target):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = os.path.join(dl_dir, f"_backup_{ts}_{expected_name}")
        try:
            os.rename(target, backup)
            log.info(f"    Renamed existing to backup")
            return backup
        except OSError as e:
            log.warning(f"    Could not rename: {e}")
    return None


def _wait_for_csv(dl_dir, snapshot_before, click_time, timeout=60, expected_name=None) -> str:
    log.info(f"    Watching: {dl_dir}")
    deadline = time.time() + timeout
    candidate = None
    while time.time() < deadline:
        time.sleep(1.5)
        all_csvs = [f for f in glob.glob(os.path.join(dl_dir, "*.csv"))
                    if not f.endswith((".crdownload", ".tmp"))]
        if expected_name:
            exact = os.path.join(dl_dir, expected_name)
            if exact in all_csvs and exact not in snapshot_before:
                candidate = exact
                log.info(f"    Layer 1: {os.path.basename(candidate)}")
        if not candidate:
            truly_new = [f for f in all_csvs
                         if f not in snapshot_before or snapshot_before.get(f, 0) < os.path.getmtime(f) - 0.5]
            if truly_new:
                candidate = max(truly_new, key=os.path.getmtime)
                log.info(f"    Layer 2: {os.path.basename(candidate)}")
        if candidate:
            if _file_size_stable(candidate):
                log.info(f"    Layer 3 confirmed: {candidate}")
                return candidate
            else:
                log.info("    Still growing — waiting...")
                candidate = None
    raise TimeoutError(f"No CSV appeared in '{dl_dir}' within {timeout}s.")


def download_csv(config: dict, download_dir: str = None) -> str:
    """
    Full portal automation: login -> dropdowns -> date -> show report -> download CSV.
    Returns path to downloaded CSV file.
    """
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    portal      = config["portal"]
    dl_dir      = download_dir or _default_download_dir()
    os.makedirs(dl_dir, exist_ok=True)
    dl_abs      = str(Path(dl_dir).resolve())
    driver_path = _get_chromedriver_path()

    opts = webdriver.ChromeOptions()
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--ignore-ssl-errors")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("prefs", {
        "download.default_directory":               dl_abs,
        "download.prompt_for_download":             False,
        "download.directory_upgrade":               True,
        "safebrowsing.enabled":                     True,
        "profile.default_content_settings.popups":  0,
    })

    log.info("Starting browser...")
    driver = webdriver.Chrome(service=Service(driver_path), options=opts)
    driver.set_page_load_timeout(60)

    try:
        login_url = portal.get("login_url", portal["url"].rsplit("/", 1)[0] + "/login")
        log.info(f"Opening: {login_url}")
        driver.get(login_url)
        time.sleep(2)

        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║   AutoNOC — Browser is open. Please log in manually.    ║")
        print(f"║   {login_url:<56}║")
        print("║   Once you see the main dashboard, come back here.      ║")
        print("╚══════════════════════════════════════════════════════════╝")
        input("  >> Press ENTER after login is complete: ")
        print()

        report_url = portal["url"]
        log.info(f"Navigating to: {report_url}")
        driver.get(report_url)

        for attempt in range(1, 4):
            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "report")))
                log.info("  Report page loaded")
                break
            except Exception:
                log.warning(f"  Load attempt {attempt}/3 — refreshing...")
                driver.refresh(); time.sleep(4)
        else:
            raise RuntimeError("Report page did not load after 3 retries.")

        time.sleep(1.5)
        for sid in ("report", "plmn", "period"):
            log.info(f"  #{sid} options: {_list_options(driver, sid)}")

        log.info("Filling dropdowns...")
        _select2_set(driver, "report", portal["report_type"])
        _select2_set(driver, "plmn",   portal["plmn"])
        _select2_set(driver, "period", portal["report_periodicity"])

        template = portal.get("template", "").strip()
        tmpl_result = driver.execute_script("""
            var s = document.getElementById('template');
            if (!s) { var all = document.querySelectorAll('select.select2_single, select.form-control'); s = all[3] || all[all.length-1] || null; }
            if (!s) return 'NOT_FOUND';
            var want = arguments[0];
            if (want) { for (var i=0;i<s.options.length;i++) { if (s.options[i].text.trim()===want) { s.value=s.options[i].value; s.dispatchEvent(new Event('change',{bubbles:true})); return 'OK:'+want; } } }
            if (s.options.length>1) { s.selectedIndex=1; s.dispatchEvent(new Event('change',{bubbles:true})); return 'AUTO:'+s.options[1].text.trim(); }
            return 'EMPTY';
        """, template)
        log.info(f"  Template: {tmpl_result}")
        time.sleep(0.8)

        _set_date_range(driver)

        log.info("Clicking Show Report...")
        try:
            show_btn = driver.find_element(By.ID, "pc")
        except Exception:
            show_btn = driver.find_element(By.XPATH, "//button[normalize-space(text())='Show Report']")
        driver.execute_script("arguments[0].click();", show_btn)
        time.sleep(3)

        log.info("Waiting for report data (up to 90s)...")
        if not _wait_for_table(driver, timeout=90):
            log.warning("Table empty — refreshing and retrying once...")
            driver.refresh(); time.sleep(4)
            _select2_set(driver, "report", portal["report_type"])
            _select2_set(driver, "plmn",   portal["plmn"])
            _select2_set(driver, "period", portal["report_periodicity"])
            driver.execute_script("""
                var s=document.getElementById('template');
                if(!s){var all=document.querySelectorAll('select.select2_single, select.form-control');s=all[3]||null;}
                if(s&&s.options.length>1){s.selectedIndex=1;s.dispatchEvent(new Event('change',{bubbles:true}));}
            """)
            _set_date_range(driver); time.sleep(0.5)
            try: show_btn = driver.find_element(By.ID, "pc")
            except Exception: show_btn = driver.find_element(By.XPATH, "//button[normalize-space(text())='Show Report']")
            driver.execute_script("arguments[0].click();", show_btn); time.sleep(3)
            if not _wait_for_table(driver, timeout=60):
                log.warning("Data still not loaded — downloading whatever is available")

        log.info("Preparing CSV download...")
        expected_name = _get_expected_filename(driver)
        snapshot      = _snapshot_dir(dl_dir)
        backup_path   = _rename_existing(dl_dir, expected_name) if expected_name else None
        click_time    = time.time()

        log.info("Clicking CSV export...")
        try:
            csv_btn = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.buttons-csv")))
            driver.execute_script("arguments[0].scrollIntoView(true);", csv_btn); time.sleep(0.4)
            driver.execute_script("arguments[0].click();", csv_btn)
            log.info("  Clicked a.buttons-csv")
        except Exception as e:
            log.warning(f"  Fallback: {e}")
            csv_btn = driver.find_element(By.XPATH, "//a[normalize-space(text())='CSV']|//button[normalize-space(text())='CSV']")
            driver.execute_script("arguments[0].click();", csv_btn)

        csv_path = _wait_for_csv(dl_dir, snapshot, click_time, 60, expected_name)

        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_no_ext  = os.path.splitext(os.path.basename(csv_path))[0]
        stamped_path = os.path.join(dl_dir, f"{name_no_ext}_{ts}.csv")
        try:
            os.rename(csv_path, stamped_path)
            log.info(f"  Renamed -> {os.path.basename(stamped_path)}")
            csv_path = stamped_path
        except OSError as e:
            log.warning(f"  Rename failed: {e}")

        if backup_path and os.path.exists(backup_path):
            try: os.remove(backup_path)
            except OSError: pass

        return csv_path

    except Exception as e:
        log.error(f"Download failed: {e}", exc_info=True)
        raise
    finally:
        try: driver.quit()
        except Exception: pass
