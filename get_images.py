import csv
import io
import os
import requests
from playwright.sync_api import sync_playwright

SHEET_ID = os.getenv("SHEET_ID")

def main():
    print("Lade Hotelliste aus Google Sheets...")
    r = requests.get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=hotels")
    recs = list(csv.DictReader(io.StringIO(r.content.decode("utf-8"))))
    
    results = [["name", "image"]]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for i, row in enumerate(recs):
            name = row.get("name", "").strip()
            url = row.get("url", "").strip()
            if not name or not url.startswith("http"): continue
            
            print(f"[{i+1}/{len(recs)}] Hole Bild für: {name}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                
                img_url = page.evaluate("""() => {
                    const img = document.querySelector('img[data-no-translate="true"]');
                    return img ? img.src : '';
                }""")
                
                results.append([name, img_url])
                print(f" -> {img_url}")
            except Exception:
                results.append([name, "FEHLER"])
                print(" -> FEHLER")
                
        browser.close()
        
    with open("hotel_bilder.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerows(results)
    print("Fertig! Datei wurde erstellt.")

if __name__ == "__main__":
    main()
