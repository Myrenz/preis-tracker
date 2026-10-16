import csv
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

API_KEY = os.environ.get("SCRAPER_API_KEY")

# Die saubere Hauptseite des Dream World Palace Hotels bei HolidayCheck
TARGET_URL = "https://www.holidaycheck.de/ho/angebote-dream-world-palace-hotel/5f99a171-6caa-4aff-a4db-d7dbf273672d"

def hole_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt in den GitHub Secrets!")
        return

    print("Frage HolidayCheck-Hotelübersicht über ScraperAPI ab...")

    payload = {
        'api_key': API_KEY,
        'url': TARGET_URL,
        'render': 'true',
        'wait_for_selector': 'body',
        'wait': '6000',
        'country_code': 'de',
        'premium': 'true'
    }

    try:
        response = requests.get('https://api.scraperapi.com/', params=payload, timeout=120)
        print(f"API Antwort-Status: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            text_seite = soup.get_text(separator=" ")

            # Sucht nach Preisen auf der Seite (z.B. Beträge im realistischen Pauschalreise-Bereich)
            rohe_preise = re.findall(r'\b([1-5]\d{3})\b', text_seite)

            alle_preise = [int(p) for p in rohe_preise]
            
            # Filtert realistische Gesamtpreise zwischen 1.000 € und 5.000 €
            gueltige_preise = [pr for pr in alle_preise if 1000 <= pr <= 5000]

            if gueltige_preise:
                bester_preis = min(gueltige_preise)
                details = f"Gefundene Preise: {sorted(list(set(gueltige_preise)))[:5]}"
                print(f"Erfolg! Günstigster Gesamtpreis: {bester_preis} EUR")
            else:
                bester_preis = "Keine passenden Gesamtpreise"
                details = text_seite[:200]
                print("Keine Gesamtpreise im Bereich 1000€ - 5000€ gefunden.")
        else:
            bester_preis = f"HTTP {response.status_code}"
            details = "-"
            print(f"Fehler: {response.status_code}")

        # Schreibt das Ergebnis in die preishistorie.csv
        eintrag = [zeitstempel, "Dream World Palace", str(bester_preis), details]
        
        with open("preishistorie.csv", mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(eintrag)
        print("Erfolgreich in preishistorie.csv geschrieben.")

    except Exception as e:
        print(f"Fehler beim Abruf: {e}")

if __name__ == "__main__":
    hole_preise()
