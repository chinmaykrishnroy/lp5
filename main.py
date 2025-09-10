#!/usr/bin/env python3
import os
import shutil
import time
import re
import argparse
import logging
import traceback
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

# =========================
# DEFAULT CONFIG (can be overridden by CLI args)
# =========================
DEFAULT_EXCEL_FILE = "Despegar SPRK users Creation.xlsx"
DEFAULT_PASSWORD = "Despegar@321"
DEFAULT_START_URL = "https://platform.prd.farelogix.com/fpm/PCCs/Details/BV5Q"
DEFAULT_TESTING = False
DEFAULT_USER_DATA_DIR = None
DEFAULT_PROFILE_DIR = "Default"
DEFAULT_HEADLESS = False
DEFAULT_CREATOR = None  # set to e.g. "Rushikesh" to filter, or None to process all

WORKING_SUFFIX = "_working"
LOG_SUFFIX = "_run.log"

# XPaths / IDs
XPATH_TAB_TO_CLICK = "(//a[@ng-click='select($event)'])[2]"
XPATH_ADD_USER_BUTTON = "//button[@ng-click=\"vm.addAclUser(vm.AclAgents,'lg')\"]"
XPATH_SAVE_BUTTON = "//button[@type='submit' and contains(@class,'btn-primary')]"

ID_AGENT_ID = "acl-user-id"
ID_NEW_PWD = "acl-user-newpwd"
ID_CONF_PWD = "acl-user-confnewpwd"
ID_NAME = "acl-user-name"
ID_EMAIL = "acl-user-email"
XPATH_ROLE_BASE = "//*[@id='acl-user-roles']/label[{index}]"

WAIT_TIME = 20
SLEEP_BETWEEN_ROWS = 1.0

# Validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
INVALID_USER_CHARS = set(" :;/'\"\\|,<>?*")


# -------------------------
# Helpers
# -------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Automated user creation with resume and robust pausing")
    p.add_argument("--excel", default=DEFAULT_EXCEL_FILE, help="Path to source Excel file")
    p.add_argument("--password", default=DEFAULT_PASSWORD, help="Password to set for new users")
    p.add_argument("--start-url", default=DEFAULT_START_URL, help="Start URL to open")
    p.add_argument("--testing", action="store_true", help="If set, script will pause at interactive prompts")
    p.add_argument("--creator", default=DEFAULT_CREATOR, help="Creator name to filter rows (case-insensitive). Omit to process all")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--user-data-dir", default=DEFAULT_USER_DATA_DIR, help="Edge user-data-dir (optional)")
    p.add_argument("--profile-dir", default=DEFAULT_PROFILE_DIR, help="Edge profile directory name (optional)")
    return p.parse_args()


def setup_logging(working_file: Path) -> str:
    log_file = working_file.with_name(working_file.stem + LOG_SUFFIX)
    # configure logging
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
    """Pause for user input.
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
        raise FileNotFoundError(f"Source Excel not found: {src}")
    working = src.with_name(f"{src.stem}{WORKING_SUFFIX}{src.suffix}")
    if working.exists():
        logging.info("Using existing working copy: %s", working)
    else:
        shutil.copy2(src, working)
        logging.info("Created working copy: %s", working)
    return working


def make_md_table(headers, values) -> str:
    headers = [str(h) for h in headers]
    values = [str(v) for v in values]
    widths = [max(len(h), len(v)) for h, v in zip(headers, values)]
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    sep_line = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    row_line = "| " + " | ".join(v.ljust(w) for v, w in zip(values, widths)) + " |"
    return "\n".join([header_line, sep_line, row_line])


# Selenium helper wrappers

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


# Validation routines

def validate_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match((email or "").strip()))


def validate_username(username: str) -> bool:
    u = (username or "").strip()
    if u == "":
        return False
    return not any(ch in INVALID_USER_CHARS for ch in u)


# -------------------------
# Main flow
# -------------------------

def main():
    args = parse_args()
    excel_file = args.excel
    password = args.password
    start_url = args.start_url
    testing = args.testing
    creator_filter = args.creator
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

    # Build list of row ids to consider (we'll always refresh the row data from disk before each attempt)
    if creator_filter:
        mask = df_all["Creator"].astype(str).str.strip().str.lower() == creator_filter.lower()
        row_ids = df_all[mask]["RowID"].tolist()
    else:
        row_ids = df_all["RowID"].tolist()

    if not row_ids:
        logging.info("No rows to process (creator filter=%s). Exiting.", creator_filter)
        return

    # start browser
    driver = make_driver(headless=headless, user_data_dir=user_data_dir, profile_dir=profile_dir)

    try:
        driver.get(start_url)
        logging.info("Opened start URL: %s", start_url)
        user_pause("After logging in completely in the browser, press ENTER to continue...", testing, mandatory=True)

        # Ensure Users tab is clickable — loop until user fixes or it becomes clickable
        while True:
            try:
                wait_click(driver, By.XPATH, XPATH_TAB_TO_CLICK)
                WebDriverWait(driver, WAIT_TIME).until(
                    EC.presence_of_element_located((By.XPATH, XPATH_ADD_USER_BUTTON))
                )
                logging.info("Users tab available and Add User button present")
                break
            except Exception as e:
                logging.exception("Users tab click/presence failed: %s", e)
                user_pause("⚠ Users tab not available. Fix and press ENTER to retry (or Ctrl+C to abort).", testing, mandatory=True)

        # Process each RowID — keep retrying the same row until it's marked Done
        for rid in row_ids:
            logging.info("==== Processing RowID=%s ====" , rid)
            flush_logs()

            while True:  # retry loop for this row
                # reload latest data from disk so user can edit during pauses
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

                name = str(row.get("Name", "")).strip()
                last_name = str(row.get("Last Name", "")).strip()
                email = str(row.get("Email", "")).strip()
                role = str(row.get("Role", "")).strip()
                agent_user = str(row.get("Agent User Name", "")).strip()

                # Basic validations — if invalid, log + pause (allow user to fix) and then retry same row
                if not validate_username(agent_user):
                    logging.error("Invalid username for RowID %s: '%s' — contains illegal chars or is empty", rid, agent_user)
                    # mark pending state so we can see it in the sheet
                    df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - invalid username"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Invalid username detected. Fix the Excel and press ENTER to retry this row.", testing, mandatory=True)
                    continue

                if not validate_email(email):
                    logging.error("Invalid email for RowID %s: '%s'", rid, email)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - invalid email"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Invalid email detected. Fix the Excel and press ENTER to retry this row.", testing, mandatory=True)
                    continue

                if not agent_user or not name or not last_name or not email:
                    logging.warning("Missing required fields for RowID %s. agent_user='%s', name='%s', last_name='%s', email='%s'", rid, agent_user, name, last_name, email)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = "Pending - missing fields"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Missing fields. Fix the Excel and press ENTER to retry this row.", testing, mandatory=True)
                    continue

                normalized_role = normalize_role(role)
                role_index = role_to_index(normalized_role)
                if role_index == 0:
                    logging.warning("Unknown role for RowID %s: '%s'", rid, role)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = f"Pending - unknown role: {role}"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Unknown role. Fix the Excel and press ENTER to retry this row.", testing, mandatory=True)
                    continue

                # At this point, we attempt to open/fill modal and save.
                try:
                    # If modal already present, don't click Add User again — just try filling
                    modal_elements = driver.find_elements(By.ID, ID_AGENT_ID)
                    if modal_elements:
                        logging.info("Modal seems already open — will try to fill it")
                    else:
                        try:
                            wait_click(driver, By.XPATH, XPATH_ADD_USER_BUTTON)
                        except Exception as e:
                            logging.exception("Failed to click Add User button: %s", e)
                            user_pause("⚠ Could not open Add User modal. Fix UI/state and press ENTER to retry this row.", testing, mandatory=True)
                            continue

                    # Fill inputs
                    try:
                        wait_present(driver, By.ID, ID_AGENT_ID, timeout=WAIT_TIME)
                        clear_and_type(driver, By.ID, ID_AGENT_ID, agent_user)
                        clear_and_type(driver, By.ID, ID_NEW_PWD, password)
                        clear_and_type(driver, By.ID, ID_CONF_PWD, password)
                        clear_and_type(driver, By.ID, ID_NAME, f"{name} {last_name}")
                        clear_and_type(driver, By.ID, ID_EMAIL, email)
                    except Exception as e:
                        logging.exception("Error while filling inputs for RowID %s: %s", rid, e)
                        user_pause("⚠ Error filling modal inputs. Fix browser state and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    # Select role
                    try:
                        role_xpath = XPATH_ROLE_BASE.format(index=role_index)
                        wait_click(driver, By.XPATH, role_xpath)
                    except Exception as e:
                        logging.exception("Error selecting role for RowID %s: %s", rid, e)
                        user_pause("⚠ Error selecting role. Fix browser UI and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    # Log what we filled
                    headers = ["Agent User", "Full Name", "Email", "Password", "Role"]
                    values = [agent_user, f"{name} {last_name}", email, password, normalized_role]
                    filled_table = make_md_table(headers, values)
                    logging.info("Filled inputs for RowID %s:\n%s", rid, filled_table)
                    flush_logs()

                    # Click Save and wait for modal to disappear — if it doesn't, pause and retry same row
                    try:
                        wait_click(driver, By.XPATH, XPATH_SAVE_BUTTON)
                    except Exception as e:
                        logging.exception("Failed to click Save for RowID %s: %s", rid, e)
                        user_pause("⚠ Could not click Save. Fix browser state and press ENTER to retry this row.", testing, mandatory=True)
                        continue

                    try:
                        WebDriverWait(driver, WAIT_TIME).until(
                            EC.invisibility_of_element_located((By.ID, ID_AGENT_ID))
                        )
                        # success
                        df_all = pd.read_excel(working_path)
                        df_all.loc[df_all["RowID"] == rid, "Status"] = "Done"
                        df_all.loc[df_all["RowID"] == rid, "DoneAt"] = datetime.now().isoformat()
                        df_all.to_excel(working_path, index=False)
                        logging.info("✓ RowID %s: Created user '%s' as %s — marked Done", rid, agent_user, normalized_role)
                        flush_logs()
                        # interactive pause for manual review if testing mode enabled
                        user_pause("Row done. Press ENTER to continue to next row...", testing, mandatory=False)
                        break  # exit retry loop; go to next row
                    except TimeoutException:
                        logging.warning("Save action did not close modal for RowID %s within %s seconds", rid, WAIT_TIME)
                        # keep status as pending; allow user to inspect/fix
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
                    logging.exception("Unexpected error while processing RowID %s: %s", rid, e)
                    df_all = pd.read_excel(working_path)
                    df_all.loc[df_all["RowID"] == rid, "Status"] = f"Error - {type(e).__name__}"
                    df_all.to_excel(working_path, index=False)
                    flush_logs()
                    user_pause("⚠ Unexpected error occurred. Fix and press ENTER to retry this row.", testing, mandatory=True)
                    continue

            # end retry loop for this row

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


"""
Usage examples:

# ─────────────────────────────
# Basic run with defaults
# (Excel: 'Despegar SPRK users Creation.xlsx',
#  Password: 'Despegar@321',
#  URL: default START_URL,
#  Creator: Chinmay by default)
python script.py

# ─────────────────────────────
# Choose a different Creator
# ─────────────────────────────
python script.py --creator Rushikesh
python script.py --creator "Some Other Name"

# ─────────────────────────────
# Process all creators (ignore filtering)
# ─────────────────────────────
python script.py --creator ""     # empty string → no filtering

# ─────────────────────────────
# Use a different Excel file
# ─────────────────────────────
python script.py --excel "TeamUsers.xlsx"

# ─────────────────────────────
# Use a different password
# ─────────────────────────────
python script.py --password "MySecurePass@123"

# ─────────────────────────────
# Change the start URL
# ─────────────────────────────
python script.py --start-url "https://example.com/login"

# ─────────────────────────────
# Run in TESTING mode (pauses at every prompt)
# ─────────────────────────────
python script.py --testing

# ─────────────────────────────
# Run browser in headless mode
# ─────────────────────────────
python script.py --headless

# ─────────────────────────────
# Use custom Edge profile
# ─────────────────────────────
python script.py --user-data-dir "C:/Users/you/AppData/Local/Microsoft/Edge/User Data" \
                 --profile-dir "Profile 2"

# ─────────────────────────────
# Combine multiple options
# ─────────────────────────────
python script.py --excel "RushikeshUsers.xlsx" --creator Rushikesh --password "Abc@123" --headless
python script.py --all --start-url "https://another.url" --testing
"""
