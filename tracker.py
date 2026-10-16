import csv
import os
import re
import requests
from datetime import datetime

API_KEY = os.environ.get("SCRAPER_API_KEY")
API_URL = "https://www.holidaycheck.de/api/vacancies;currency=EUR;offerIds=%5B%22501f1bd5-bcf8-47bc-a26f-8ba0aafd4b73%22%2C%2250192648-1a42-486f-a8d2-98ae68ec2af0%22%2C%22501fc602-280b-4c49-b23f-b1304c00d98c%22%2C%22161e82c5-a8af-47bc-b9da-b929ff2dc95f%22%5D"

def hole_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt in den GitHub Secrets!")
        return

    print("Frage HolidayCheck-API über ScraperAPI ab...")

    payload = {
        'api_key': API_KEY,
        'url': API_URL,
        'country_code': 'de',
        'premium': 'true'
    }

    try:
        response = requests.get('https://api.scraperapi.com/', params=payload, timeout=60)
        print(f"API Antwort-Status: {response.status_code}")

        if response.status_code == 200:
            text_antwort = response.text
            print(f"Antwort-Länge: {len(text_antwort)} Zeichen")
            
            # Sucht nach allen Beträgen / Preisen im gesamten JSON-Text
            alle_zahlen = re.findall(r'"(?:price|amount|total|totalPrice)"\s*:\s*([0-9.]+)', text_antwort)
            if not alle_zahlen:
                alle_zahlen = re.findall(r'\b([4-9]\d{2}|[1-9]\d{3})\b', text_antwort)

            preise = [int(float(p)) for p in alle_zahlen if 300 < int(float(p)) < 8000]

            if preise:
                bester_preis = min(preise)
                details = f"Gefundene Preise: {sorted(list(set(preise)))[:5]}"
                print(f"Erfolg! Günstigster Preis: {bester_preis} EUR")
            else:
                bester_preis = "Keine Preise erkannt"
                details = text_antwort[:200]
                print("Keine passenden Preise im JSON-Text gefunden.")
        else:
            bester_preis = f"HTTP {response.status_code}"
            details = "-"
            print(f"Fehler: {response.status_code}")

        # Schreibt direkt in die echte preishistorie.csv
        eintrag = [zeitstempel, "Dream World Palace", str(bester_preis), details]
        
        with open("preishistorie.csv", mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(eintrag)
        print("Erfolgreich in preishistorie.csv geschrieben.")

    except Exception as e:
        print(f"Fehler beim Abruf: {e}")

if __name__ == "__main__":
    hole_preise()
