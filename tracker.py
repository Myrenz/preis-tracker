import csv
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

API_KEY = os.environ.get("SCRAPER_API_KEY")

# Deine exakte Such-URL mit allen Filtern (Abflughafen, Datum, Dauer etc.)
TARGET_URL = "https://www.holidaycheck.de/ho/angebote-dream-world-palace-hotel/5f99a171-6caa-4aff-a4db-d7dbf273672d/package?_offer=airport:~BRE~FMO,deal:1,departureDate:2027-06-14,duration:7,returnDate:2027-06-30,rooms:a-o8hcdid=153e2126-7876-4442-b64c-b17a61d0fef5"

def hole_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt in den GitHub Secrets!")
        return

    print("Frage HolidayCheck-Suchseite über ScraperAPI ab...")

    # Konfiguration für ScraperAPI: Lädt die Seite im echten Browser, wartet 8 Sek. auf JavaScript
    payload = {
        'api_key': API_KEY,
        'url': TARGET_URL,
        'render': 'true',
        'wait_for_selector': 'body',
        'wait': '8000',
        'country_code': 'de',
        'premium': 'true'
    }

    try:
        response = requests.get('https://api.scraperapi.com/', params=payload, timeout=120)
        print(f"API Antwort-Status: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            text_seite = soup.get_text(separator=" ")

            # Sucht nach allen Preisangaben mit Euro-Zeichen oder in Zahlenformaten
            rohe_preise = re.findall(r'(\d{1,2}\.\d{3}|\d{3,4})\s*€', text_seite)
            
            # Alternativ: Suche nach reinen Zahlen im Text, die wie Reise-Gesamtpreise aussehen
            if not rohe_preise:
                rohe_preise = re.findall(r'\b([1-5]\d{3})\b', text_seite)

            # Bereinigt und konvertiert die gefundenen Preise
            alle_preise = []
            for p in rohe_preise:
                sauber = int(p.replace('.', '').replace('€', '').strip())
                alle_preise.append(sauber)

            # STRIKTER FILTER: Nur realistische Gesamtpreise für die Pauschalreise (zwischen 1.000 € und 5.000 €)
            gueltige_preise = [pr for pr in alle_preise if 1000 <= pr <= 5000]

            if gueltige_preise:
                bester_preis = min(gueltige_preise)
                details = f"Gefundene echte Preise: {sorted(list(set(gueltige_preise)))[:5]}"
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
