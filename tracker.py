import csv
import json
import os
import requests
from datetime import datetime

API_KEY = os.environ.get("SCRAPER_API_KEY")
API_URL = "https://www.holidaycheck.de/api/all-offers-service"

REFERER_URL = (
    "https://www.holidaycheck.de/ho/angebote-dream-world-palace-hotel/"
    "5f99a171-6caa-4aff-aa4b-d7dbf273672d/package"
    "?_offer=airport:~BRE~FMO,deal:1,departureDate:2027-06-14,"
    "duration:7,returnDate:2027-06-30,rooms:a-a"
)

HEADERS = {
    "accept": "*/*",
    "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.holidaycheck.de",
    "referer": REFERER_URL,
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
                    if 1000 <= p <= 6000:
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

def hole_alle_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt!")
        return

    if not os.path.exists("hotels.json"):
        print("FEHLER: hotels.json nicht gefunden!")
        return

    with open("hotels.json", "r", encoding="utf-8") as f:
        hotels = json.load(f)

    einträge = []
    datei_existiert = os.path.exists("preishistorie.csv") and os.path.getsize("preishistorie.csv") > 0

    for hotel in hotels:
        h_id = hotel["id"]
        h_name = hotel["name"]
        print(f"Frage ab: {h_name}...")

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
                    print(f"-> Günstigster Preis für {h_name}: {bester_preis} EUR")
                else:
                    bester_preis = "Keine Preise"
                    print(f"-> Keine gültigen Preise im JSON für {h_name}")
            else:
                bester_preis = f"HTTP {resp.status_code}"
                print(f"-> Fehler bei {h_name}: Status {resp.status_code}")
        except Exception as e:
            bester_preis = "Fehler"
            print(f"-> Ausnahme bei {h_name}: {e}")

        einträge.append([zeitstempel, h-name if 'h-name' in locals() else h_name, str(bester_preis), ""])

    # CSV schreiben
    with open("preishistorie.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not datei_existiert:
            writer.writerow(["Zeitstempel", "Hotel", "Günstigster_Preis_EUR", "Details"])
        writer.writerows(einträge)

    print("Alle Hotelpreise erfolgreich aktualisiert!")

if __name__ == "__main__":
    hole_alle_preise()
