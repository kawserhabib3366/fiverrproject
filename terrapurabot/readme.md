# Herb Information Scraper with AI Extraction

This project scrapes herbal medicine data from **WebMD**, **Herbpathy**, and **PFAF (Plants For A Future)** using `undetected-chromedriver` (Selenium) and `BeautifulSoup`. It then optionally extracts structured information using a GPT-based extractor and stores the results in JSON files.

---

##  Features

- Headless or visible browser scraping
- Herb detail extraction from:
  - WebMD
  - Herbpathy
  - PFAF (Plants For A Future)
- GPT-based AI extraction via `extract_herb_info_with_gpt`
- Intermediate and final data stored in JSON
- Resumable scraping based on previously saved progress

---

##  File Structure
terrapurabot/
│
├── ai_extractor.py              # Contains extract_herb_info_with_gpt function
├── scraper.py                   # Main scraper script
├── get_all_link.json            #intially get all link from pfaf
├── plant_all_link.json          # Input list of herbs (with PFAF URLs)
├── scraped_data_combined.json   # Combined scraped data with all sources
├── ai_extracted.json            # Final GPT-extracted structured data
├── README.md                    # This file
├── requirements.txt





---

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt


```




## HOW TO RUN

* **First time:**
  Run the script to gather all plant links:

  ```bash
  python get_all_link.py
  ```

* **For scraping data (each time):**
  Run the scraper to extract herb information:

  ```bash
  python scrapper.py
  ```






HEADLESS_MODE = True  # or False





[
  {
    "url": "https://pfaf.org/user/Plant.aspx?LatinName=Plantago+major"
  },
  {
    "url": "https://pfaf.org/user/Plant.aspx?LatinName=Urtica+dioica"
  }
]
Each entry must include a valid PFAF link with a LatinName query parameter.





Output Files
scraped_data_combined.json: Stores all raw scraped text for each herb from 3 sources.



ai_extracted.json: Stores structured herb information extracted by GPT. This will be the final data




✨ Author
Made with 💚 by Kawser

If you have any question ,Ask the developer kawserhabib3366@gmail.com