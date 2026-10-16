import csv
import os
import requests
from datetime import datetime

API_KEY = os.environ.get("SCRAPER_API_KEY")

# Deine gefundene direkte API-URL von HolidayCheck
API_URL = "https://www.holidaycheck.de/api/vacancies;currency=EUR;offerIds=%5B%22501f1bd5-bcf8-47bc-a26f-8ba0aafd4b73%22%2C%2250192648-1a42-486f-a8d2-98ae68ec2af0%22%2C%22501fc602-280b-4c49-b23f-b1304c00d98c%22%2C%22161e82c5-a8af-47bc-b9da-b929ff2dc95f%22%5D"

def hole_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt in den GitHub Secrets!")
        return

    print("Frage HolidayCheck-API über ScraperAPI ab...")

    # ScraperAPI leitet den API-Aufruf über eine deutsche IP weiter
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
            data = response.json()
            
            # Versucht die Preise aus der JSON-Antwort zu fischen
            preise = []
            
            # Je nach Struktur der API-Antwort durchsuchen wir die JSON-Daten
            # (Beispielhaft angepasst an typische Veranstalter-APIs)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('vacancies', data.get('offers', [data]))
            else:
                items = []

            for item in items:
                # Holt den Preis (oft als 'price', 'totalPrice' oder 'amount' hinterlegt)
                preis = item.get('price', item.get('totalPrice', item.get('amount')))
                if preis:
                    preise.append(int(float(preis)))

            # Falls direkt keine Liste zurückkommt, suchen wir im rohen JSON nach Zahlenwerten
            if not preise:
                import re
                rohe_zahlen = re.findall(r'"price":\s*([0-9.]+)', response.text)
                preise = [int(float(p)) for p in rohe_zahlen if int(float(p)) > 300]

            if preise:
                bester_preis = min(preise)
                eintrag = [zeitstempel, "Dream World Palace (API)", bester_preis, str(preise)]
                print(f"Erfolg! Günstigster Preis aus API: {bester_preis} EUR")
            else:
                eintrag = [zeitstempel, "Dream World Palace (API)", "Keine Preise in JSON", "-"]
                print("Antwort erhalten, aber keine Preise im JSON gefunden.")
                # Speichert die JSON-Antwort zur Kontrolle
                with open("letzte_antwort.json", "w", encoding="utf-8") as f:
                    f.write(response.text)
        else:
            eintrag = [zeitstempel, "Dream World Palace (API)", f"HTTP {response.status_code}", "-"]
            print(f"Fehler: {response.status_code} - {response.text[:200]}")

        # In CSV schreiben
        with open("preishistorie.csv", mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(eintrag)

    except Exception as e:
        print(f"Fehler beim API-Abruf: {e}")

if __name__ == "__main__":
    hole_preise()
