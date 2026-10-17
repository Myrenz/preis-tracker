import csv
import json
import os
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = os.environ.get("SCRAPER_API_KEY")
API_URL = "https://www.holidaycheck.de/api/all-offers-service"

HEADERS = {
    "accept": "*/*",
    "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.holidaycheck.de",
    "referer": "https://www.holidaycheck.de/",
    "x-client-version": "master.eaa127c648",
    "x-requested-with": "XMLHttpRequest",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def erstelle_payload(hotel_id):
    return {
        "body": {
            "facets": {"hotelIds": [hotel_id]},
            "locale": "de_DE",
            "currency": "EUR",
            "package": {
                "transfer": [],
                "flight": {
                    "departureAirports": ["BRE", "FMO"],
                    "directFlight": False,
                    "destinationAirports": []
                },
                "travellers": {
                    "adults": 2,
                    "children": [],
                    "list": [{"age": 25, "travellerRefId": 1}, {"age": 25, "travellerRefId": 2}]
                },
                "rooms": [{"travellerRefIds": [1, 2]}],
                "mealTypes": [],
                "roomTypes": [],
                "attributes": [],
                "numberOfRooms": 1,
                "travelDates": {
                    "departureDate": {"year": 2027, "month": 6, "day": 14},
                    "returnDate": {"year": 2027, "month": 6, "day": 30},
                    "minDuration": 7,
                    "maxDuration": 7
                },
                "tourOperatorIds": [],
                "specials": [],
                "deal": True
            },
            "resultSpec": {"pageSize": 50},
            "withPromotedOffer": True,
            "withSponsoredOffers": True,
            "withOfferGroups": True,
            "isPackageBundle": True
        },
        "context": {},
        "operation": "create",
        "params": {},
        "resource": "all-offers-service"
    }

def finde_günstigsten_preis(json_daten):
    preise = []
    def rekursiv(obj):
        if isinstance(obj, dict):
            tp = obj.get("totalPrice")
            if isinstance(tp, dict) and "amount" in tp:
                try:
                    p = float(tp["amount"])
                    if 900 <= p <= 8000:
                        preise.append(p)
                except:
                    pass
            for v in obj.values():
                rekursiv(v)
        elif isinstance(obj, list):
            for item in obj:
                rekursiv(item)
    rekursiv(json_daten)
    return min(preise) if preise else None

def frage_einzelnes_hotel_ab(hotel, zeitstempel):
    h_id = hotel["id"]
    h_name = hotel["name"]
    payload = erstelle_payload(h_id)

    try:
        resp = requests.post(
            "https://api.scraperapi.com/",
            params={"api_key": API_KEY, "url": API_URL, "country_code": "de", "premium": "true"},
            headers=HEADERS,
            data=json.dumps(payload),
            timeout=60
        )
        if resp.status_code == 200 and '"totalPrice"' in resp.text:
            preis = finde_günstigsten_preis(resp.json())
            if preis:
                bester_preis = int(round(preis))
                print(f"[OK] {h_name}: {bester_preis} EUR")
            else:
                bester_preis = "Keine Preise"
                print(f"[LEER] {h_name}: Keine Angebote")
        else:
            bester_preis = f"HTTP {resp.status_code}"
            print(f"[FEHLER] {h_name}: Status {resp.status_code}")
    except Exception as e:
        bester_preis = "Fehler"
        print(f"[AUSNAHME] {h_name}: {e}")

    return [zeitstempel, h_name, str(bester_preis), ""]

def hole_alle_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt!")
        return

    with open("hotels.json", "r", encoding="utf-8") as f:
        hotels = json.load(f)

    aktive_hotels = [h for h in hotels if h.get("active", True)]
    print(f"Starte Abfrage für {len(aktive_hotels)} aktive Hotels...")

    einträge = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(frage_einzelnes_hotel_ab, h, zeitstempel) for h in aktive_hotels]
        for future in as_completed(futures):
            einträge.append(future.result())

    datei_existiert = os.path.exists("preishistorie.csv") and os.path.getsize("preishistorie.csv") > 0
    with open("preishistorie.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not datei_existiert:
            writer.writerow(["Zeitstempel", "Hotel", "Günstigster_Preis_EUR", "Details"])
        writer.writerows(einträge)

    print("Alle Hotelpreise erfolgreich gespeichert!")

if __name__ == "__main__":
    hole_alle_preise()
