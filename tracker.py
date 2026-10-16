import csv
import json
import os
import re
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

# Exakte Such-Nutzlast (POST Body) aus deinen Browser-Entwicklertools
SEARCH_PAYLOAD = {
    "body": {
        "facets": {
            "hotelIds": ["5f99a171-6caa-4aff-aa4b-d7dbf273672d"]
        },
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
                "list": [
                    {"age": 25, "travellerRefId": 1},
                    {"age": 25, "travellerRefId": 2}
                ]
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
            "specials": [
                {
                    "specialType": "LOGGED_IN_ONLY_DEAL",
                    "code": "LOGGED_IN_ONLY_DEAL",
                    "scope": "SHOULD_HAVE"
                },
                {
                    "specialType": "LOGGED_IN_ONLY_DEAL_AVAILABLE",
                    "code": "LOGGED_IN_ONLY_DEAL_AVAILABLE",
                    "scope": "MUST_NOT_HAVE"
                }
            ],
            "deal": True
        },
        "resultSpec": {"pageSize": 200},
        "withPromotedOffer": True,
        "withSponsoredOffers": True,
        "sponsoredOffersModelThreshold": 0.2,
        "allowIgnoreFilters": True,
        "addVacancyCheckFlag": True,
        "shouldAddFlexOffer": True,
        "withAirportOffers": True,
        "hotelLocations": ["colakli", "tuerkische_riviera", "tuerkei", "europa"],
        "withAccoTrio": False,
        "withOfferGroups": True,
        "isPackageBundle": True,
        "withRoomEnrichment": True
    },
    "context": {},
    "operation": "create",
    "params": {},
    "resource": "all-offers-service"
}

HEADERS = {
    "accept": "*/*",
    "accept-language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.holidaycheck.de",
    "referer": REFERER_URL,
    "x-client-version": "master.eaa127c648",
    "x-requested-with": "XMLHttpRequest",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


def finde_angebote_rekursiv(obj, gefundene=None):
    """Durchsucht die JSON-Antwort rekursiv nach allen echten Angebots-Objekten."""
    if gefundene is None:
        gefundene = []
    if isinstance(obj, dict):
        tp = obj.get("totalPrice")
        preis = None
        if isinstance(tp, dict) and "amount" in tp:
            try:
                preis = float(tp["amount"])
            except (ValueError, TypeError):
                preis = None
        elif isinstance(tp, (int, float)):
            preis = float(tp)

        if preis is not None and 1000 <= preis <= 6000:
            gefundene.append(obj)

        for v in obj.values():
            finde_angebote_rekursiv(v, gefundene)
    elif isinstance(obj, list):
        for item in obj:
            finde_angebote_rekursiv(item, gefundene)
    return gefundene


def berechne_angebots_infos(angebot):
    """Extrahiert Preis, Cashback, Flugdaten, Veranstalter und Transfer aus einem Angebot."""
    tp = angebot.get("totalPrice")
    brutto = int(round(float(tp["amount"]))) if isinstance(tp, dict) else int(round(float(tp)))

    cashback = 0
    for item in angebot.get("priceBreakdown", []) or []:
        if isinstance(item, dict) and item.get("type") == "CASH_BACK_VOUCHER":
            preis_obj = item.get("price") or {}
            if isinstance(preis_obj, dict) and "amount" in preis_obj:
                cashback += int(round(float(preis_obj["amount"])))

    netto = brutto - cashback
    flughafen = (angebot.get("flight") or {}).get("departureAirport", "?")
    hin = (angebot.get("departureDate") or {}).get("formatted", "?")
    rueck = (angebot.get("returnDate") or {}).get("formatted", "?")
    veranstalter = (angebot.get("tourOperator") or {}).get("name", "?")
    transfer = angebot.get("transferName") or (
        "inkl. Transfer" if angebot.get("transfer") == "GT14-TR" else "ohne Transfer"
    )
    zimmer = (angebot.get("room") or {}).get("name", "Zimmer")

    return {
        "brutto": brutto,
        "cashback": cashback,
        "netto": netto,
        "flughafen": flughafen,
        "zeitraum": f"{hin}-{rueck}",
        "veranstalter": veranstalter,
        "transfer": transfer,
        "zimmer": zimmer
    }


def sende_post_anfrage():
    """Probiert den POST-Abruf über verschiedene ScraperAPI-Modi bis Status 200 erreicht wird."""
     body_json = json.dumps(SEARCH_PAYLOAD)

    versuche = [
        (
            "ScraperAPI (DE Standard + keep_headers)",
            {
                "api_key": API_KEY,
                "url": API_URL,
                "country_code": "de",
                "keep_headers": "true"
            }
        ),
        (
            "ScraperAPI (DE Premium + keep_headers)",
            {
                "api_key": API_KEY,
                "url": API_URL,
                "country_code": "de",
                "premium": "true",
                "keep_headers": "true"
            }
        ),
        (
            "ScraperAPI (DE Ultra-Premium + keep_headers)",
            {
                "api_key": API_KEY,
                "url": API_URL,
                "country_code": "de",
                "ultra_premium": "true",
                "keep_headers": "true"
            }
        )
    ]

    letzte_response = None
    for name, params in versuche:
        print(f"Starte Versuch: {name} ...")
        try:
            resp = requests.post(
                "https://api.scraperapi.com/",
                params=params,
                headers=HEADERS,
                data=body_json,
                timeout=90
            )
            letzte_response = resp
            print(f"-> Status: {resp.status_code} | Länge: {len(resp.text)} Zeichen")
            if resp.status_code == 200 and len(resp.text) > 300:
                return resp, name
        except Exception as e:
            print(f"-> Fehler bei {name}: {e}")

    # Letzter Fallback: Direkter Abruf ohne Proxy
    print("Starte Fallback: Direkter POST-Abruf an HolidayCheck-API ...")
    resp = requests.post(API_URL, headers=HEADERS, data=body_json, timeout=60)
    print(f"-> Direkt-Status: {resp.status_code} | Länge: {len(resp.text)} Zeichen")
    return resp, "Direkt-Abruf"


def hole_preise():
    zeitstempel = datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs("debug", exist_ok=True)

    if not API_KEY:
        print("FEHLER: SCRAPER_API_KEY fehlt in den GitHub Secrets!")
        return

    bester_preis = "Fehler"
    details = "-"

    try:
        response, verwendete_methode = sende_post_anfrage()
        status = response.status_code
        text_antwort = response.text

        # Komplette Antwort zur Kontrolle im debug-Ordner sichern
        with open("debug/letzte_antwort.txt", "w", encoding="utf-8") as f:
            f.write(
                f"Methode: {verwendete_methode}\nURL: {API_URL}\n"
                f"Status: {status}\nLänge: {len(text_antwort)}\n\n{text_antwort}"
            )

        if status == 200:
            angebote_roh = []
            try:
                json_daten = response.json()
                angebote_roh = finde_angebote_rekursiv(json_daten)
            except Exception as json_err:
                print(f"Hinweis beim JSON-Parsing: {json_err}")

            if angebote_roh:
                ausgewertet = [berechne_angebots_infos(a) for a in angebote_roh]
                # Sortieren nach Brutto-Gesamtpreis (aufsteigend)
                ausgewertet.sort(key=lambda x: x["brutto"])

                top = ausgewertet[0]
                bester_preis = top["brutto"]

                # Bestes Angebot inklusive Hoteltransfer separat suchen
                mit_transfer = [
                    a for a in ausgewertet
                    if "inkl" in a["transfer"].lower()
                ]

                transfer_info = ""
                if mit_transfer:
                    t_top = mit_transfer[0]
                    transfer_info = (
                        f" | Bestes inkl. Transfer: {t_top['brutto']} EUR "
                        f"({t_top['netto']} EUR nach Cashback, {t_top['flughafen']}, {t_top['zeitraum']})"
                    )

                alle_brutto = sorted(list(set(a["brutto"] for a in ausgewertet)))[:6]
                details = (
                    f"Netto nach Cashback: {top['netto']} EUR (-{top['cashback']} EUR) | "
                    f"{top['flughafen']} {top['zeitraum']} | {top['veranstalter']} | "
                    f"{top['transfer']}{transfer_info} | Top-Preise: {alle_brutto}"
                )
                print(f"ERFOLG! Günstigster Gesamtpreis: {bester_preis} EUR | {details}")
            else:
                # Fallback per Regex auf totalPrice
                matches = re.findall(r'"totalPrice"\s*:\s*\{\s*"amount"\s*:\s*([0-9.]+)', text_antwort)
                preise = sorted(list(set(int(round(float(m))) for m in matches if 1000 <= float(m) <= 6000)))
                if preise:
                    bester_preis = preise[0]
                    details = f"Gefundene Gesamtpreise (EUR): {preise[:8]}"
                    print(f"ERFOLG (Regex)! Günstigster Gesamtpreis: {bester_preis} EUR")
                else:
                    bester_preis = "Keine Angebote im JSON"
                    details = text_antwort[:180].replace("\n", " ")
                    print("Keine Angebote im Bereich 1000-6000 EUR gefunden.")
        else:
            bester_preis = f"HTTP {status}"
            details = text_antwort[:180].replace("\n", " ")
            print(f"Fehler-Status: {status}")

    except Exception as e:
        bester_preis = "Ausnahmefehler"
        details = str(e)[:180]
        print(f"Fehler beim Abruf: {e}")

    # In preishistorie.csv speichern
    datei_existiert = os.path.exists("preishistorie.csv") and os.path.getsize("preishistorie.csv") > 0
    with open("preishistorie.csv", mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not datei_existiert:
            writer.writerow(["Zeitstempel", "Hotel", "Günstigster_Preis_EUR", "Details"])
        writer.writerow([zeitstempel, "Dream World Palace", str(bester_preis), details])

    print("Ergebnis erfolgreich in preishistorie.csv gespeichert.")


if __name__ == "__main__":
    hole_preise()
