#!/usr/bin/env python3
"""
Update PCC agency contact emails from an Excel file.

Default Excel (in same dir as script):
    MAIL UPDATE IN ADO.xlsx

Usage examples:
    python update_pcc_emails.py
    python update_pcc_emails.py --excel "OtherFile.xlsx" --testing
    python update_pcc_emails.py --headless --user-data-dir "C:/Users/you/AppData/Local/Microsoft/Edge/User Data" --profile-dir "Profile 2"
"""

import os
import shutil
import time
import re
import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException,
)

# -------------------------
# Defaults / constants
# -------------------------
DEFAULT_EXCEL_FILE = "MAIL UPDATE IN ADO.xlsx"   # <-- default file used if --excel not provided
BASE_URL = "https://platform.prd.farelogix.com/fpm/PCCs/Details/"  # append PCC
WORKING_SUFFIX = "_working"
LOG_SUFFIX = "_run.log"

# XPaths / IDs (from you)
XPATH_EDIT_BUTTON = "//button[contains(text(),'Edit') and contains(@class,'btn-primary')]"
XPATH_AGENCY_EMAIL = '//*[@id="pcc-edit"]/div/div/div[1]/form/div[5]/div/input'
XPATH_SAVE_BUTTON = '//*[@id="pcc-edit"]/div/div/div[2]/button[1]'
ID_MODAL = "pcc-edit"

WAIT_TIME = 20
SLEEP_BETWEEN_ROWS = 0.8

# Validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
INVALID_PCC_CHARS = set(" :;/'\"\\|,<>?*")  # basic check

# -------------------------
# Helpers
# -------------------------


def parse_args():
    p = argparse.ArgumentParser(description="Update PCC agency contact emails from Excel")
    p.add_argument("--excel", default=DEFAULT_EXCEL_FILE, help="Path to source Excel file (default uses MAIL UPDATE IN ADO.xlsx)")
    p.add_argument("--testing", action="store_true", help="If set, script will pause at interactive prompts")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--user-data-dir", default=None, help="Edge user-data-dir (optional)")
    p.add_argument("--profile-dir", default="Default", help="Edge profile directory name (optional)")
    return p.parse_args()


def setup_logging(working_file: Path) -> str:
    log_file = working_file.with_name(working_file.stem + LOG_SUFFIX)
    handlers = [
        logging.FileHandler(log_file, encoding="utf-8", mode="a"),
        logging.StreamHandler(),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("\n================ New run started: %s =================", datetime.now().isoformat())
    logging.info("Log file: %s", log_file)
    flush_logs()
    return str(log_file)


def flush_logs():
    for h in logging.getLogger().handlers:
        try:
            if hasattr(h, "flush"):
                h.flush()
        except Exception:
            pass


def user_pause(msg: str, testing: bool, mandatory: bool = False):
    """
    Pause for user input.
      - If mandatory=True -> always block until ENTER
      - Else block only if testing==True
    """
    logging.info("PAUSE: %s", msg)
    flush_logs()
    if mandatory or testing:
        try:
            input(f"⏸ {msg}")
        except (EOFError, KeyboardInterrupt):
            logging.info("User aborted during pause.")
            raise
    else:
        logging.info("Continuing without blocking (testing=False and not mandatory)")


def make_working_copy(src_path: str) -> Path:
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f"Source Excel not found: {src.resolve()}")
    working = src.with_name(f"{src.stem}{WORKING_SUFFIX}{src.suffix}")
    if working.exists():
        logging.info("Using existing working copy: %s", working)
    else:
        shutil.copy2(src, working)
        logging.info("Created working copy: %s", working)
    return working


def normalize_column_name(s: str) -> str:
    if s is None:
        return ""
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def find_required_columns(df: pd.DataFrame):
    """
    Find flexible-matching column names for iata, name, pcc, email.
    Returns mapping canonical -> actual column name in df.
    Throws ValueError if something missing.
    """
    canonical_candidates = {
        "iata": ["iatacode", "iata", "iata_code", "iatacode"],
        "name": ["name", "agencyname", "agency_name", "organizationname"],
        "pcc": ["pcc", "pcccode", "pcc_code", "pccid", "pcccode"],
        "email": [
            "contactemail",
            "contactemailaddress",
            "agencyprimarycontactemail",
            "agencyprimarycontact_email",
            "contactemail",
            "contactemailaddress",
            "contactemail",
            "contact",
            "email",
            "contactemail",
            "contactemail"
        ],
    }

    found = {}
    norm_to_col = {normalize_column_name(col): col for col in df.columns}

    for key, variants in canonical_candidates.items():
        match = None
        for v in variants:
            if v in norm_to_col:
                match = norm_to_col[v]
                break
        if match is None:
            # try partial contains
            for norm, orig in norm_to_col.items():
                for v in variants:
                    if v in norm or norm in v:
                        match = orig
                        break
                if match:
                    break
        if match is None:
            raise ValueError(f"Could not find required column for '{key}' in Excel. Columns present: {list(df.columns)}")
        found[key] = match
    return found


def make_driver(headless: bool, user_data_dir: str = None, profile_dir: str = "Default"):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    if user_data_dir:
        options.add_argument(f"user-data-dir={user_data_dir}")
        options.add_argument(f"profile-directory={profile_dir}")
    driver_path = os.path.join(os.getcwd(), "msedgedriver.exe")
    service = EdgeService(executable_path=driver_path)
    return webdriver.Edge(service=service, options=options)


def wait_click(driver, by, locator, timeout=WAIT_TIME):
    wait = WebDriverWait(driver, timeout)
    el = wait.until(EC.element_to_be_clickable((by, locator)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
    time.sleep(0.3)
    try:
        el.click()
    except (ElementClickInterceptedException, StaleElementReferenceException):
        driver.execute_script("arguments[0].click();", el)


def wait_present(driver, by, locator, timeout=WAIT_TIME):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by, locator))
    )


def clear_and_type(driver, by, locator, text):
    el = wait_present(driver, by, locator)
    try:
        el.clear()
    except Exception:
        pass
    el.send_keys(text)


def validate_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match((email or "").strip()))


def validate_pcc(pcc: str) -> bool:
    p = (pcc or "").strip()
    if not p:
        return False
    return not any(ch in INVALID_PCC_CHARS for ch in p)


# -------------------------
# Main flow
# -------------------------


def main():
    args = parse_args()
    excel_file = args.excel
    testing = args.testing
    headless = args.headless
    user_data_dir = args.user_data_dir
    profile_dir = args.profile_dir

    working_path = make_working_copy(excel_file)
    setup_logging(working_path)

    # load dataframe and ensure helper columns
    df_all = pd.read_excel(working_path)
    if "RowID" not in df_all.columns:
        df_all.insert(0, "RowID", range(0, len(df_all)))
        logging.info("Added RowID column to working excel")
        df_all.to_excel(working_path, index=False)
        flush_logs()

    for col in ("Status", "DoneAt"):
        if col not in df_all.columns:
            df_all[col] = ""
    df_all.to_excel(working_path, index=False)

    # detect columns
    try:
        df_all = pd.read_excel(working_path)
        col_map = find_required_columns(df_all)
        logging.info("Detected columns mapping: %s", col_map)
    except Exception as e:
        logging.exception("Column detection failed: %s", e)
        raise

    # build row list
    row_ids = df_all["RowID"].tolist()
    if not row_ids:
        logging.info("No rows to process. Exiting.")
        return

    driver = make_driver(headless=headless, user_data_dir=user_data_dir, profile_dir=profile_dir)

    try:
        # open base so user can login (mandatory pause after)
        driver.get(BASE_URL)
        logging.info("Opened base URL for login: %s", BASE_URL)
        # MANDATORY: waits until user presses ENTER (preserve original behavior)
        user_pause("After logging in completely in the browser, press ENTER to continue...", testing, mandatory=True)

        # iterate rows
        for rid in row_ids:
            logging.info("==== Processing RowID=%s ====", rid)
            flush_logs()

            while True:
                # refresh sheet
                df_all = pd.read_excel(working_path)
                row_df = df_all[df_all["RowID"] == rid]
                if row_df.empty:
                    logging.warning("RowID %s not found in the sheet (it may have been removed). Skipping.", rid)
                    break
                row = row_df.iloc[0]

                status = str(row.get("Status", "")).strip().lower()
                if status == "done":
                    logging.info("RowID %s already Done; skipping.", rid)
                    break

                iata = str(row.get(col_map["iata"], "")).strip()
                name = str(row.get(col_map["name"], "")).strip()
                pcc = str(row.get(col_map["pcc"], "")).strip()
                contact_email = str(row.get(col_map["email"], "")).strip()

                # validations
                if not validate_pcc(pcc):
                    logging.error("Invalid PCC for RowID %s: '%s'", rid, pcc)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - invalid PCC"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Invalid PCC detected. Fix the Excel and press ENTER to retry this row.", testing, mandatory=True)
                    continue

                if not validate_email(contact_email):
                    logging.error("Invalid email for RowID %s: '%s'", rid, contact_email)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - invalid email"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Invalid email detected. Fix the Excel and press ENTER to retry this row.", testing, mandatory=True)
                    continue

                if not pcc or not contact_email:
                    logging.warning("Missing required fields for RowID %s. pcc='%s', email='%s'", rid, pcc, contact_email)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - missing fields"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Missing fields. Fix the Excel and press ENTER to retry this row.", testing, mandatory=True)
                    continue

                # navigate and try update
                try:
                    target_url = f"{BASE_URL}{pcc}"
                    logging.info("Navigating to PCC URL: %s", target_url)
                    try:
                        driver.get(target_url)
                    except WebDriverException as e:
                        logging.exception("Failed to navigate to %s: %s", target_url, e)
                        user_pause("⚠ Browser navigation failed. Fix and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    # click Edit
                    try:
                        wait_click(driver, By.XPATH, XPATH_EDIT_BUTTON, timeout=WAIT_TIME)
                    except Exception as e:
                        logging.exception("Failed to locate/click Edit button for PCC %s: %s", pcc, e)
                        df_all = pd.read_excel(working_path)
                        df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - edit not available"
                        df_all.to_excel(working_path, index=False)
                        flush_logs()
                        user_pause("⚠ Could not open edit mode. Fix/UI or login state and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    # wait for modal/edit present
                    try:
                        wait_present(driver, By.ID, ID_MODAL, timeout=WAIT_TIME)
                    except Exception as e:
                        logging.exception("Edit modal didn't appear for PCC %s: %s", pcc, e)
                        df_all = pd.read_excel(working_path)
                        df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - edit modal missing"
                        df_all.to_excel(working_path, index=False)
                        flush_logs()
                        user_pause("⚠ Edit modal did not appear. Fix UI and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    # fill agency email input
                    try:
                        clear_and_type(driver, By.XPATH, XPATH_AGENCY_EMAIL, contact_email)
                    except Exception as e:
                        logging.exception("Error while filling email input for PCC %s: %s", pcc, e)
                        df_all = pd.read_excel(working_path)
                        df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - error filling input"
                        df_all.to_excel(working_path, index=False)
                        flush_logs()
                        user_pause("⚠ Error filling email input. Fix browser state and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    logging.info("Filled inputs for RowID %s: PCC=%s, Name=%s, Email=%s", rid, pcc, name, contact_email)
                    flush_logs()

                    # click Save
                    try:
                        wait_click(driver, By.XPATH, XPATH_SAVE_BUTTON)
                    except Exception as e:
                        logging.exception("Failed to click Save for PCC %s: %s", pcc, e)
                        df_all = pd.read_excel(working_path)
                        df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - could not click save"
                        df_all.to_excel(working_path, index=False)
                        flush_logs()
                        user_pause("⚠ Could not click Save. Fix browser state and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    # wait for modal disappearance => success
                    try:
                        WebDriverWait(driver, WAIT_TIME).until(EC.invisibility_of_element_located((By.ID, ID_MODAL)))
                        df_all = pd.read_excel(working_path)
                        df_all.loc[df_all["RowID"] == rid, "Status"] = "Done"
                        df_all.loc[df_all["RowID"] == rid, "DoneAt"] = datetime.now().isoformat()
                        df_all.to_excel(working_path, index=False)
                        logging.info("✓ RowID %s: Updated PCC '%s' email to '%s' — marked Done", rid, pcc, contact_email)
                        flush_logs()
                        user_pause("Row done. Press ENTER to continue to next row...", testing, mandatory=False)
                        time.sleep(SLEEP_BETWEEN_ROWS)
                        break
                    except TimeoutException:
                        logging.warning("Save action did not close modal for PCC %s within %s seconds", pcc, WAIT_TIME)
                        df_all = pd.read_excel(working_path)
                        df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - save modal open"
                        df_all.to_excel(working_path, index=False)
                        flush_logs()
                        user_pause("⚠ Save did not complete (modal still present). Fix and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                except KeyboardInterrupt:
                    logging.info("User requested abort (KeyboardInterrupt). Exiting main loop.")
                    raise
                except Exception as e:
                    logging.exception("Unexpected error while processing RowID %s (PCC %s): %s", rid, pcc, e)
                    df_all = pd.read_excel(working_path)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = f"Error - {type(e).__name__}"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Unexpected error occurred. Fix and press ENTER to retry this row.", testing, mandatory=True)
                    continue

        logging.info("All requested rows processed.")

    finally:
        try:
            user_pause("All rows done. Press ENTER to close the browser.", testing, mandatory=False)
        except Exception:
            pass
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
