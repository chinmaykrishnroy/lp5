import os
import shutil
import time
from datetime import datetime
import logging
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
)

# =========================
# CONFIG
# =========================
EXCEL_FILE = "Despegar SPRK users Creation.xlsx"
PASSWORD = "Despegar@321"
START_URL = "https://platform.prd.farelogix.com/fpm/PCCs/Details/BV5Q"

TESTING = False
USER_DATA_DIR = None
PROFILE_DIR = "Default"
HEADLESS = False

WORKING_SUFFIX = "_working"  # appended to EXCEL_FILE stem to create working copy
LOG_SUFFIX = "_run.log"

# =========================
# XPaths / IDs
# =========================
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

# =========================
# HELPERS
# =========================

def pause(msg: str = "Press ENTER to continue..."):
    if TESTING:
        input(f"⏸ {msg}")
    else:
        print(f"➡ {msg}")

# Force a pause regardless of TESTING
def pause_always(msg: str = "Press ENTER to continue..."):
    input(f"⏸ {msg}")


def make_driver():
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    if USER_DATA_DIR:
        options.add_argument(f"user-data-dir={USER_DATA_DIR}")
        options.add_argument(f"profile-directory={PROFILE_DIR}")
    driver_path = os.path.join(os.getcwd(), "msedgedriver.exe")
    service = EdgeService(executable_path=driver_path)
    return webdriver.Edge(service=service, options=options)


def wait_click(driver, by, locator, timeout=WAIT_TIME):
    """Wait until clickable, scroll, JS click fallback."""
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


def normalize_role(role_text: str) -> str:
    r = (role_text or "").strip().lower()
    mapping = {
        "sub agent": "sub agent",
        "agent": "agent",
        "ticket agent": "ticketing agent",
        "ticketing agent": "ticketing agent",
        "agency admin": "agency admin",
        "enterprise admin": "enterprise admin",
    }
    return mapping.get(r, r)


def role_to_index(normalized_role: str) -> int:
    order = {
        "sub agent": 1,
        "agent": 2,
        "ticketing agent": 3,
        "agency admin": 4,
        "enterprise admin": 5,
    }
    return order.get(normalized_role, 0)


# -------------------------
# New helper: working copy + logging + table builder
# -------------------------

def make_working_copy(src_path: str) -> str:
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f"Source Excel not found: {src}")
    working = src.with_name(f"{src.stem}{WORKING_SUFFIX}{src.suffix}")
    if working.exists():
        logging.info(f"Using existing working copy: {working}")
    else:
        shutil.copy2(src, working)
        logging.info(f"Created working copy: {working}")
    return str(working)


def setup_logging(working_file: str) -> str:
    p = Path(working_file)
    log_file = p.with_name(p.stem + LOG_SUFFIX)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8", mode="a"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    logging.info(f"Logging started. Log file: {log_file}")
    return str(log_file)


def make_md_table(headers, values) -> str:
    headers = [str(h) for h in headers]
    values = [str(v) for v in values]
    widths = [max(len(h), len(v)) for h, v in zip(headers, values)]
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    sep_line = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    row_line = "| " + " | ".join(v.ljust(w) for v, w in zip(values, widths)) + " |"
    return "\n".join([header_line, sep_line, row_line])


# =========================
# MAIN
# =========================

def main():
    working_file = make_working_copy(EXCEL_FILE)
    log_file = setup_logging(working_file)

    df_all = pd.read_excel(working_file)

    for col in ("Status", "DoneAt"):
        if col not in df_all.columns:
            df_all[col] = ""

    mask = df_all["Creator"].astype(str).str.strip().str.lower() == "chinmay"
    df_to_process = df_all[mask]

    if df_to_process.empty:
        logging.info("No rows found where Creator == 'Chinmay'. Nothing to do.")
        return

    driver = make_driver()

    try:
        driver.get(START_URL)
        logging.info("Opened start URL. Please log in manually in the Edge window.")
        pause_always("After logging in completely, press ENTER to proceed to the Users tab...")

        try:
            wait_click(driver, By.XPATH, XPATH_TAB_TO_CLICK)
            WebDriverWait(driver, WAIT_TIME).until(
                EC.presence_of_element_located((By.XPATH, XPATH_ADD_USER_BUTTON))
            )
            pause("Users tab clicked. Press ENTER to continue to Add User loop...")
        except TimeoutException:
            logging.error("Users tab not found or not clickable. Check XPath or page load.")
            driver.quit()
            return

        for idx in df_to_process.index:
            row = df_all.loc[idx]

            if str(row.get("Status", "")).strip().lower() == "done":
                logging.info(f"Skipping row {idx}: already marked Done")
                continue

            name = str(row.get("Name", "")).strip()
            last_name = str(row.get("Last Name", "")).strip()
            email = str(row.get("Email", "")).strip()
            role = str(row.get("Role", "")).strip()
            agent_user = str(row.get("Agent User Name", "")).strip()

            if not agent_user or not name or not last_name or not email:
                msg = f"Skipping row {idx}: missing required fields. agent_user='{agent_user}', name='{name}', last_name='{last_name}', email='{email}'"
                logging.warning(msg)
                df_all.at[idx, "Status"] = "Skipped - missing fields"
                df_all.at[idx, "DoneAt"] = datetime.now().isoformat()
                df_all.to_excel(working_file, index=False)
                continue

            full_name = f"{name} {last_name}"
            normalized_role = normalize_role(role)
            role_index = role_to_index(normalized_role)
            if role_index == 0:
                logging.warning(f"Skipping row {idx}: Unknown role '{role}'.")
                df_all.at[idx, "Status"] = f"Skipped - unknown role: {role}"
                df_all.to_excel(working_file, index=False)
                continue

            try:
                wait_click(driver, By.XPATH, XPATH_ADD_USER_BUTTON)
                pause(f"Opened Add User modal for row {idx}. Press ENTER to fill details...")

                wait_present(driver, By.ID, ID_AGENT_ID)
                clear_and_type(driver, By.ID, ID_AGENT_ID, agent_user)
                clear_and_type(driver, By.ID, ID_NEW_PWD, PASSWORD)
                clear_and_type(driver, By.ID, ID_CONF_PWD, PASSWORD)
                clear_and_type(driver, By.ID, ID_NAME, full_name)
                clear_and_type(driver, By.ID, ID_EMAIL, email)

                role_xpath = XPATH_ROLE_BASE.format(index=role_index)
                wait_click(driver, By.XPATH, role_xpath)
                pause(f"Role '{normalized_role}' selected. Press ENTER to Save...")

                headers = ["Agent User", "Full Name", "Email", "Password", "Role"]
                values = [agent_user, full_name, email, PASSWORD, normalized_role]
                filled_table = make_md_table(headers, values)
                logging.info(f"Filled inputs for row {idx}:\n{filled_table}")

                wait_click(driver, By.XPATH, XPATH_SAVE_BUTTON)

                try:
                    WebDriverWait(driver, WAIT_TIME).until(
                        EC.invisibility_of_element_located((By.ID, ID_AGENT_ID))
                    )
                except TimeoutException:
                    logging.warning("Modal did not disappear after save within wait time; continuing anyway.")
                    time.sleep(1.0)

                df_all.at[idx, "Status"] = "Done"
                df_all.at[idx, "DoneAt"] = datetime.now().isoformat()
                df_all.to_excel(working_file, index=False)

                logging.info(f"✓ Row {idx}: Created user '{agent_user}' ({full_name}) as {normalized_role}")
                pause(f"Row {idx} done. Press ENTER to continue to next row...")

            except TimeoutException as e:
                logging.exception(f"Row {idx}: Timeout while creating '{agent_user}'. Error: {e}")
                df_all.at[idx, "Status"] = f"Error - Timeout: {e}"
                df_all.to_excel(working_file, index=False)
            except Exception as e:
                logging.exception(f"Row {idx}: Unexpected error for '{agent_user}': {e}")
                df_all.at[idx, "Status"] = f"Error - {e}"
                df_all.to_excel(working_file, index=False)

            time.sleep(SLEEP_BETWEEN_ROWS)

        logging.info("✅ Done processing all rows.")

    finally:
        pause("All rows done. Press ENTER to close the browser.")
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
