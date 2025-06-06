import os
import json
import time
import logging
from typing import Dict
from urllib.parse import quote_plus, urlparse, parse_qs

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import undetected_chromedriver as uc
from colorama import Fore, Style, init

from ai_extractor import extract_herb_info_with_gpt

# ------------------------- CONFIG -------------------------

init(autoreset=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PLANT_ALL_LINK = "plant_all_link.json"
SCRAPED_COMBINED = "scraped_data_combined.json"
AI_EXTRACTED_FILE = "ai_extracted.json"
HEADLESS_MODE = True
WAIT_TIME = 10

# ------------------------- UTILITIES -------------------------

def load_json(file_path, default=None):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning(f"Failed to load {file_path}, using default.")
        return default if default is not None else []

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)



def save_extracted_herb(data: Dict, output_file: str):
    try:
        existing_data = load_json(output_file, default=[])
        existing_data.append(data)
        save_json(output_file, existing_data)
    except Exception as e:
        logging.error(f"Error saving extracted herb to {output_file}: {e}")

def get_entry(results, latin_name):
    for entry in results:
        if entry.get("latin_name") == latin_name:
            return entry
    entry = {"latin_name": latin_name}
    results.append(entry)
    return entry

def get_driver(headless=True):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--blink-settings=imagesEnabled=false")
    return uc.Chrome(options=options)

# ------------------------- SCRAPERS -------------------------

def extract_detail_text(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    monograph = soup.select_one("#monograph-page")
    if not monograph:
        return ""
    sections = monograph.select(".section-content-holder")
    if sections:
        sections[-1].decompose()
    return monograph.get_text(separator="\n", strip=True)

def get_text_webmd(driver, latin_name, entry):
    search_url = f"https://www.webmd.com/vitamins-supplements/search?type=vitamins&query={quote_plus(latin_name)}"
    logging.info(f"Searching WebMD for {latin_name}")
    try:
        driver.get(search_url)
        WebDriverWait(driver, 6).until(EC.any_of(EC.url_contains("ingredientmono-")))

        if "ingredientmono-" in driver.current_url:
            entry["textwebmd"] = extract_detail_text(driver)
            return

        soup = BeautifulSoup(driver.page_source, "html.parser")
        result = soup.select_one("a.search-results-doc-title")
        if result and result.get("href"):
            driver.get("https://www.webmd.com" + result["href"])
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#monograph-page")))
            entry["textwebmd"] = extract_detail_text(driver)
        else:
            entry["textwebmd"] = "No relevant content found."
    except TimeoutException:
        entry["textwebmd"] = "Timeout or no content found."
    except Exception as e:
        entry["textwebmd"] = " NO DATA FOUND"

def get_text_herbpathy(driver, latin_name, entry):
    logging.info(f"Searching Herbpathy for {latin_name}")
    try:
        driver.get("https://herbpathy.com/")
        WebDriverWait(driver, WAIT_TIME).until(EC.presence_of_element_located((By.ID, "TextTitle")))
        driver.execute_script("ChangeTab(2);")

        search_input = WebDriverWait(driver, WAIT_TIME).until(EC.presence_of_element_located((By.ID, "TextTitle")))
        search_input.clear()
        search_input.send_keys(latin_name)
        WebDriverWait(driver, WAIT_TIME).until(EC.element_to_be_clickable((By.ID, "Button1"))).click()

        content = WebDriverWait(driver, WAIT_TIME).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#div_contnt")))
        entry["textherbpathy"] = content.text
    except Exception as e:
        entry["textherbpathy"] = " NO DATA FOUND"

def get_element_text(driver, xpath):
    return ' '.join(el.text.strip() for el in driver.find_elements(By.XPATH, xpath) if el.text.strip())

def get_text_pfaf(driver, url, entry):
    logging.info(f"Scraping PFAF: {url}")
    try:
        driver.get(url)
        time.sleep(2)
        xpaths = [
            '//*[@id="ContentPlaceHolder1_lbldisplatinname"]',
            '//*[@id="ContentPlaceHolder1_lblCommanName"]',
            '//*[@id="ContentPlaceHolder1_lblFamily"]',
            '//*[@id="ContentPlaceHolder1_lblUSDAhardiness"]',
            '//*[@id="ContentPlaceHolder1_lblKnownHazards"]',
            '//*[@id="ContentPlaceHolder1_txtHabitats"]',
            '//*[@id="ContentPlaceHolder1_lblRange"]',
            '//*[@id="ContentPlaceHolder1_lblWeedPotential"]',
            '//*[@id="ContentPlaceHolder1_lblSynonyms"]',
            '//*[@id="ContentPlaceHolder1_lblhabitats"]',
            '//*[@id="ContentPlaceHolder1_txtEdibleUses"]',
            '//*[@id="ContentPlaceHolder1_txtMediUses"]',
            '//*[@id="ContentPlaceHolder1_txtOtherUses"]',
            '//*[@id="ContentPlaceHolder1_txtSpecialUses"]',
            '//*[@id="ContentPlaceHolder1_txtCultivationDetails"]',
        ]
        entry["textpfaf"] = "\n\n".join(get_element_text(driver, xpath) for xpath in xpaths)
    except Exception as e:
        entry["textpfaf"] = "Error: NO DATA FOUND"

# ------------------------- MAIN -------------------------

def main():
    plants = load_json(PLANT_ALL_LINK, default=[])
    results = load_json(SCRAPED_COMBINED, default=[])

    with get_driver(headless=HEADLESS_MODE) as driver:
        for idx, plant in enumerate(plants, 1):
            query = urlparse(plant.get("url", "")).query
            latin_name = parse_qs(query).get("LatinName", [""])[0]
            if not latin_name:
                logging.warning(f"Skipping entry with no Latin name at index {idx}")
                continue

            logging.info(f"[{idx}/{len(plants)}] Processing: {latin_name}")
            entry = get_entry(results, latin_name)

            if "textwebmd" not in entry:
                get_text_webmd(driver, latin_name, entry)
                save_json(SCRAPED_COMBINED, results)

            if "textherbpathy" not in entry:
                get_text_herbpathy(driver, latin_name, entry)
                save_json(SCRAPED_COMBINED, results)

            if "textpfaf" not in entry and plant.get("url"):
                get_text_pfaf(driver, plant["url"], entry)
                save_json(SCRAPED_COMBINED, results)

            if all(k in entry for k in ["textwebmd", "textherbpathy", "textpfaf"]) and not entry.get("extracted"):
                logging.info("Extracting herb info with GPT...")
                extracted = extract_herb_info_with_gpt(entry)
                if extracted:
                    save_extracted_herb(extracted, AI_EXTRACTED_FILE)
                    entry["extracted"] = True
                    save_json(SCRAPED_COMBINED, results)
                    logging.info("GPT extraction saved.")

    logging.info("✅ All done.")


if __name__ == "__main__":
    main()
