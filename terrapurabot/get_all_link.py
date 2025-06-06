import requests
from bs4 import BeautifulSoup
import string
import time
import json

def get_links_from_letter(letter):
    base_url = "https://pfaf.org/user/DatabaseSearhResult.aspx?LatinName={}%"  # % is URL encoded
    url = base_url.format(letter)
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch page for letter {letter}")
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.select('td[align="left"] a')

    return [{"url": "https://pfaf.org/user/" + link.get("href")} for link in links if link.get("href")]

def main():
    with open("plant_all_link.json", "w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        for letter in string.ascii_uppercase:
            print(f"Processing: {letter}")
            links = get_links_from_letter(letter)
            for link_obj in links:
                if not first:
                    f.write(",\n")
                f.write(json.dumps(link_obj, ensure_ascii=False))
                first = False
            time.sleep(1)  # polite delay
        f.write("\n]")

    print("Finished writing links to pfaf_links.json")

if __name__ == "__main__":
    main()
