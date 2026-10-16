import csv
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

API_KEY = os.environ.get("SCRAPER_API_KEY")

# Korrigierte URL (mit korrekter Hotel-ID 5f99a171-6caa-4aff-aa4b-d7dbf273672d)
DEFAULT_URL = (
    "https://www.holidaycheck.de/ho/angebote-dream-world-palace-hotel/"
    "5f99a171-6caa-4aff-aa4b-d7dbf273672d/package"
    "?_offer=airport:~BRE~FMO,deal:1,departureDate:2027-06-14,"
    "duration:7,returnDate:2027-06-30,rooms:a-a"
)

def lade_ziel_url():
    """Liest falls vorhanden die URL aus searches.json, sonst DEFAULT_URL."""
    if os.path.exists("searches.json"):
        try:
            with open("searches.json", "r", encoding="utf-8") as f:
                daten = json.load(f)
            # Kopie in debug speichern zur Transparenz
            os.makedirs("debug", exist_ok=True)
            with open("debug/searches_kopie.json", "w", encoding="utf-8") as out:
                json.dump(daten, out, indent=2, ensure_ascii=False)
            if isinstance(daten, list) and len(daten) > 0 and isinstance(daten[0], dict):
                url = daten[0].get("url") or daten[0].get("target_url")
                if url and "a4db" not in url:
                    return url
            elif isinstance(daten, dict):
                for val in daten.values():
                    if isinstance(val, dict) and val.get("url"):
                        return val["url"]
                    elif isinstance(val, str) and val.startswith("http"):
                        return val
        except Exception as e:
            print(f"Hinweis beim Lesen von searches.json: {e}")
    return DEFAULT_URL

def extrahiere_preise_aus_text(roh_text):
    """Sucht gezielt nach echten Pauschalreise-Preisen (1.000 € bis 5.000 €)."""
    gefundene_preise = []

    # 1. Suche nach deutschen Euro-Preisformaten im sichtbaren Text, z. B. "1.682,00 €" oder "1.592 €"
    soup = BeautifulSoup(roh_text, "html.parser")
    sichtbarer_text = soup.get_text(separator=" ")
    euro_matches = re.findall(r'(\d{1}\.\d{3})(?:,\d{2})?\s*€', sichtbarer_text)
    for m in euro_matches:
        wert = int(m.replace(".", ""))
        if 1000 <= wert <= 5000:
            gefundene_preise.append(wert)

    # 2. Suche nach expliziten JSON-Preisfeldern (falls API-JSON oder eingebettetes State-JSON vorliegt)
    json_matches = re.findall(
        r'"(?:totalPrice|price|amount|total)"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        roh_text
    )
    for m in json_matches:
        wert = int(float(m))
        if 1000 <= wert <= 5000:
            gefundene_preise.append(wert)

    return sorted(list(set(gefundene_preise)))

def hole_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs("debug", exist_ok=True)

    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt in den GitHub Secrets!")
        return

    ziel_url = lade_ziel_url()
    ist_api_endpunkt = "/api/" in ziel_url or "json" in ziel_url.lower()
    print(f"Starte Abruf für URL: {ziel_url}")

    # Basis-Payload für ScraperAPI (ohne die fehlerhafte 'wait_for_selector': 'body' Falle)
    payload = {
        "api_key": API_KEY,
        "url": ziel_url,
        "country_code": "de",
        "premium": "true"
    }

    # Nur bei normalen HTML-Webseiten Browser-Rendering aktivieren
    if not ist_api_endpunkt:
        payload["render"] = "true"

    bester_preis = "Fehler"
    details = "-"

    try:
        response = requests.get("https://api.scraperapi.com/", params=payload, timeout=120)
        status = response.status_code
        text_antwort = response.text
        print(f"API Antwort-Status: {status} | Länge: {len(text_antwort)} Zeichen")

        # Speichert die komplette Roh-Antwort im debug-Ordner für das GitHub-Artifact
        with open("debug/letzte_antwort.txt", "w", encoding="utf-8") as f:
            f.write(f"URL: {ziel_url}\nStatus: {status}\nLänge: {len(text_antwort)}\n\n")
            f.write(text_antwort)

        if status == 200:
            preise = extrahiere_preise_aus_text(text_antwort)

            if preise:
                bester_preis = min(preise)
                details = f"Gefundene Preise (EUR): {preise[:8]}"
                print(f"ERFOLG! Günstigster Preis: {bester_preis} EUR | Alle: {preise[:8]}")
            else:
                # Prüfen, ob nur das leere Lade-Gerüst (isLoading:true) ausgeliefert wurde
                if '"isLoading":true' in text_antwort or '"offers":[]' in text_antwort:
                    bester_preis = "Lade-Geruest (isLoading=true)"
                    details = "HTML-Geruest ohne nachgeladene XHR-Preise"
                    print("WARNUNG: Seite lieferte nur das leere Lade-Gerüst (isLoading:true).")
                elif '"status":410' in text_antwort or "410" in text_antwort:
                    bester_preis = "OfferIDs abgelaufen (410)"
                    details = text_antwort[:150].replace("\n", " ")
                    print("WARNUNG: Die abgefragten Offer-IDs sind abgelaufen (Status 410).")
                else:
                    bester_preis = "Keine Preise (1000-5000 EUR)"
                    details = f"Antwort-Laenge: {len(text_antwort)} Zeichen"
                    print("Keine Preise im Bereich 1.000 - 5.000 EUR gefunden.")
        else:
            bester_preis = f"HTTP {status}"
            details = text_antwort[:150].replace("\n", " ")
            print(f"HTTP-Fehler: {status}")

    except Exception as e:
        bester_preis = "Ausnahmefehler"
        details = str(e)[:150]
        print(f"Fehler beim Abruf: {e}")

    # Sicherstellen, dass preishistorie.csv mit Kopfzeile existiert und Zeile anhängen
    datei_existiert = os.path.exists("preishistorie.csv") and os.path.getsize("preishistorie.csv") > 0
    with open("preishistorie.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not datei_existiert:
            writer.writerow(["Zeitstempel", "Hotel", "Günstigster_Preis_EUR", "Details"])
        writer.writerow([zeitstempel, "Dream World Palace", str(bester_preis), details])

    print("Ergebnis erfolgreich in preishistorie.csv und debug/letzte_antwort.txt gespeichert.")

if __name__ == "__main__":
    hole_preise()
