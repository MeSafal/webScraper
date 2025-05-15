from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import os

# ——————————————————————————————
# CONFIG
# ——————————————————————————————
SEARCH_URL = (
    "https://study.unimelb.edu.au/find/"
    "?collection=find-a-course&profile=_default"
    "&query=%21showall&num_ranks=12&start_rank=1"
    "&f.Tabs%7CtypeCourse=Courses"
)
MAX_WAIT = 2  # seconds to wait after page load
JSONL_FILE = "melb_courses.jsonl"
CSV_FILE   = "melb_courses.csv"

# ——————————————————————————————
# PREP OUTPUT FILES
# ——————————————————————————————
# If present, back them up or delete
for fn in (JSONL_FILE, CSV_FILE):
    if os.path.exists(fn):
        os.remove(fn)

# Prepare CSV header
pd.DataFrame(columns=[
    "Title",
    "Duration",
    "Mode (Location)",
    "Intake",
    "Key facts—Fees",
    "Indicative total course fee",
    "English requirements",
    "Overview"
]).to_csv(CSV_FILE, index=False, encoding="utf-8-sig")

# ——————————————————————————————
# SETUP SELENIUM
# ——————————————————————————————
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("window-size=1920,1080")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
driver = webdriver.Chrome(options=options)

# ——————————————————————————————
# HELPERS
# ——————————————————————————————
def get_search_results():
    driver.get(SEARCH_URL)
    time.sleep(MAX_WAIT)
    soup = BeautifulSoup(driver.page_source, "lxml")
    out = []
    for li in soup.select("li.search-result-course"):
        a = li.select_one("a.card-header--title")
        title = a.get_text(strip=True)
        href  = a["href"]
        out.append((title, href))
    return out

def parse_course_page(url):
    driver.get(url)
    time.sleep(MAX_WAIT)
    soup = BeautifulSoup(driver.page_source, "lxml")

    facts = {}
    for item in soup.select("div.key-facts-section__main--item"):
        k = item.select_one(".key-facts-section__main--title").get_text(strip=True)
        v = item.select_one(".key-facts-section__main--value").get_text(" ", strip=True)
        facts[k] = v

    # Overview
    ov = soup.select_one("div[data-test='course-overview-content']")
    if ov:
        parts = []
        for tag in ov.find_all(["p","li"], recursive=True):
            parts.append(tag.get_text(strip=True))
        overview = "\n".join(parts)
    else:
        overview = None

    # Indicative total fee
    fee_value = None
    for fee_item in soup.select("li[data-test='fee-item']"):
        title = fee_item.select_one("[data-test='fee-item-title']").get_text(strip=True)
        price = fee_item.select_one("[data-test='fee-item-price']").get_text(strip=True)
        if "Indicative total course fee" in title:
            fee_value = price
            break

    return {
        "Duration": facts.get("Duration"),
        "Mode (Location)": facts.get("Mode (Location)"),
        "Intake": facts.get("Intake"),
        "Key facts—Fees": facts.get("Fees"),
        "Indicative total course fee": fee_value,
        "English requirements": facts.get("English language requirements"),
        "Overview": overview
    }

# ——————————————————————————————
# MAIN LOOP (incremental writes)
# ——————————————————————————————
results = get_search_results()
for idx, (title, detail_url) in enumerate(results, 1):
    print(f"[{idx}/{len(results)}] Scraping {title!r}")
    record = parse_course_page(detail_url)
    record["Title"] = title

    # 1) Append as JSON line
    with open(JSONL_FILE, "a", encoding="utf-8") as jf:
        jf.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 2) Append to CSV
    pd.DataFrame([record])[[
        "Title",
        "Duration",
        "Mode (Location)",
        "Intake",
        "Key facts—Fees",
        "Indicative total course fee",
        "English requirements",
        "Overview"
    ]].to_csv(CSV_FILE, mode="a", header=False, index=False, encoding="utf-8-sig")

driver.quit()
print(f"✅ Done — wrote {len(results)} records to {JSONL_FILE} and {CSV_FILE}")
