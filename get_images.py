import csv
import io
import requests
from playwright.sync_api import sync_playwright

# Deine Sheet-ID ist hier jetzt fest verankert!
SHEET_ID = "1MG0UwMZbmFoSxCdVp8pqspM5wgtgQlJGyoVesRXd5ag"

def main():
    print("Lade Hotelliste aus Google Sheets...")
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=hotels&headers=1"
    r = requests.get(url)
    
    # KUGELSICHERES EINLESEN (ignoriert Groß-/Kleinschreibung)
    reader = csv.DictReader(io.StringIO(r.content.decode("utf-8")))
    recs = [{(k or "").strip().lower(): v for k, v in row.items()} for row in reader]
    
    print(f"Erfolgreich {len(recs)} Zeilen im Sheet gefunden.")
    results = [["name", "image"]]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        hotels_processed = 0
        for i, row in enumerate(recs):
            name = str(row.get("name", "")).strip()
            link = str(row.get("url", "")).strip()
            
            # Überspringt leere Zeilen oder Zeilen ohne gültigen Link
            if not name or not link.startswith("http"): 
                continue
                
            hotels_processed += 1
            print(f"[{hotels_processed}] Hole Bild für: {name}")
            try:
                page.goto(link, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
                
                img_url = page.evaluate("""() => {
                    const img = document.querySelector('img[data-no-translate="true"]');
                    return img ? img.src : '';
                }""")
                
                results.append([name, img_url])
                print(f" -> {img_url}")
            except Exception as e:
                results.append([name, "FEHLER"])
                print(f" -> FEHLER")
                
        browser.close()
        
    with open("hotel_bilder.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerows(results)
    
    print(f"\nFertig! Es wurden {hotels_processed} Hotels verarbeitet.")

if __name__ == "__main__":
    main()
