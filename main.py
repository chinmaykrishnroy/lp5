import os
import time
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

TESTING = True  # 🔑 Change to False for automatic run
USER_DATA_DIR = None
PROFILE_DIR = "Default"
HEADLESS = False

# =========================
# XPaths / IDs
# =========================
XPATH_TAB_TO_CLICK = "(//a[@ng-click='select($event)'])[2]"  # second tab (AclProd)
XPATH_ADD_USER_BUTTON = "//button[@ng-click=\"vm.addAclUser(vm.AclAgents,'lg')\"]"
# XPATH_SAVE_BUTTON = "//button[text()='Save']" 
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

# =========================
# MAIN
# =========================
def main():
    df = pd.read_excel(EXCEL_FILE)
    df = df[df["Creator"].astype(str).str.strip().str.lower() == "chinmay"]

    if df.empty:
        print("No rows found where Creator == 'Chinmay'. Nothing to do.")
        return

    driver = make_driver()

    try:
        # Step 1: Open login page
        driver.get(START_URL)
        print("👉 Please log in manually in the Edge window.")
        pause("After logging in completely, press ENTER to proceed to the Users tab...")

        # Step 2: Click Users tab
        try:
            wait_click(driver, By.XPATH, XPATH_TAB_TO_CLICK)
            WebDriverWait(driver, WAIT_TIME).until(
                EC.presence_of_element_located((By.XPATH, XPATH_ADD_USER_BUTTON))
            )
            pause("Users tab clicked. Press ENTER to continue to Add User loop...")
        except TimeoutException:
            print("❌ Users tab not found or not clickable. Check XPath or page load.")
            driver.quit()
            return

        # Step 3: Process each row
        for i, row in df.iterrows():
            name = str(row.get("Name", "")).strip()
            last_name = str(row.get("Last Name", "")).strip()
            email = str(row.get("Email", "")).strip()
            role = str(row.get("Role", "")).strip()
            agent_user = str(row.get("Agent User Name", "")).strip()

            if not agent_user or not name or not last_name or not email:
                print(f"Skipping row {i}: missing required fields.")
                continue

            full_name = f"{name} {last_name}"
            normalized_role = normalize_role(role)
            role_index = role_to_index(normalized_role)
            if role_index == 0:
                print(f"Skipping row {i}: Unknown role '{role}'.")
                continue

            try:
                # Add User button
                wait_click(driver, By.XPATH, XPATH_ADD_USER_BUTTON)
                pause(f"Opened Add User modal for row {i}. Press ENTER to fill details...")

                # Fill details
                wait_present(driver, By.ID, ID_AGENT_ID)
                clear_and_type(driver, By.ID, ID_AGENT_ID, agent_user)
                clear_and_type(driver, By.ID, ID_NEW_PWD, PASSWORD)
                clear_and_type(driver, By.ID, ID_CONF_PWD, PASSWORD)
                clear_and_type(driver, By.ID, ID_NAME, full_name)
                clear_and_type(driver, By.ID, ID_EMAIL, email)

                # Role
                role_xpath = XPATH_ROLE_BASE.format(index=role_index)
                wait_click(driver, By.XPATH, role_xpath)
                pause(f"Role '{normalized_role}' selected. Press ENTER to Save...")

                # Save
                wait_click(driver, By.XPATH, XPATH_SAVE_BUTTON)

                # Wait for modal close
                try:
                    WebDriverWait(driver, WAIT_TIME).until(
                        EC.invisibility_of_element_located((By.ID, ID_AGENT_ID))
                    )
                except TimeoutException:
                    time.sleep(1.0)

                print(f"✓ Row {i}: Created user '{agent_user}' ({full_name}) as {normalized_role}")
                pause(f"Row {i} done. Press ENTER to continue to next row...")

            except TimeoutException as e:
                print(f"Row {i}: Timeout while creating '{agent_user}'. Error: {e}")
            except Exception as e:
                print(f"Row {i}: Unexpected error for '{agent_user}': {e}")

            time.sleep(SLEEP_BETWEEN_ROWS)

        print("✅ Done processing all rows.")

    finally:
        pause("All rows done. Press ENTER to close the browser.")
        driver.quit()


if __name__ == "__main__":
    main()
