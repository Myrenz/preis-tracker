#!/usr/bin/env python3
"""HolidayCheck-Preistracker: ScraperAPI -> Parser -> Google-Sheet-Webhook."""
import csv, json, os, re, statistics, sys, time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

API_KEY = os.environ["SCRAPER_API_KEY"]
WEBHOOK = os.environ["SHEET_WEBHOOK_URL"]
TOKEN = os.environ["SHEET_TOKEN"]

DEBUG_DIR = Path("debug")
LOCAL_CSV = Path("preishistorie_local.csv")
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d{3,5})\s*(?:€|EUR)")
MIN_PLAUSIBLE, MAX_PLAUSIBLE = 300, 15000
WAITS = [20, 35]  # Sekunden Wartezeit für nachgeladene Angebote (1. und 2. Versuch)


def fetch(url: str, wait: int) -> str:
    last = "unbekannt"
    for i in range(1, 3):
        try:
            r = requests.get(
                "https://api.scraperapi.com/",
                params={
                    "api_key": API_KEY,
                    "url": url,
                    "render": "true",
                    "country_code": "de",
                    "premium": "true",
                },
                headers={
                    "x-sapi-instruction_set": json.dumps([{"type": "wait", "value": wait}])
                },
                timeout=240,
            )
            if r.status_code == 200 and len(r.text) > 20000:
                return r.text
            last = f"HTTP {r.status_code}, {len(r.text)} Bytes: {r.text[:200]}"
        except requests.RequestException as e:
            last = str(e)
        print(f"  Abruf-Versuch {i} fehlgeschlagen: {last}", file=sys.stderr)
        time.sleep(10)
    raise RuntimeError(f"Abruf fehlgeschlagen: {last}")


def parse_prices(html: str, selector: str = "") -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    if selector:
        text = " | ".join(el.get_text(" ", strip=True) for el in soup.select(selector))
    else:
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        text = soup.get_text(" ", strip=True)
    prices = []
    for m in PRICE_RE.finditer(text):
        v = int(m.group(1).replace(".", ""))
        if MIN_PLAUSIBLE <= v <= MAX_PLAUSIBLE:
            prices.append(v)
    return prices


def get_prices(name: str, url: str, selector: str) -> list[int]:
    for wait in WAITS:
        print(f"  Warte {wait}s auf Angebote ...")
        html = fetch(url, wait)
        (DEBUG_DIR / f"{name}.html").write_text(html, encoding="utf-8")
        prices = parse_prices(html, selector)
        if prices:
            return prices
        print("  Noch keine Preise im HTML.", file=sys.stderr)
    raise RuntimeError("Keine Preise gefunden (HTML in debug/ gespeichert)")


def post_row(row: list) -> bool:
    for i in range(1, 4):
        try:
            r = requests.post(WEBHOOK, json={"token": TOKEN, "row": row}, timeout=60)
            if r.ok and r.text.strip() == "ok":
                return True
            print(f"  Webhook-Antwort: {r.status_code} {r.text[:100]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  Webhook-Fehler: {e}", file=sys.stderr)
        time.sleep(5 * i)
    return False


def main() -> int:
    searches = json.loads(Path("searches.json").read_text(encoding="utf-8"))
    DEBUG_DIR.mkdir(exist_ok=True)
    failures = 0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for s in searches:
        name = s["name"]
        print(f"→ {name}", flush=True)
        try:
            prices = get_prices(name, s["url"], s.get("selector", ""))
            row = [ts, name, min(prices), int(statistics.median(prices)), len(prices), s["url"]]
            print(f"  min={row[2]} median={row[3]} n={row[4]}")

            new = not LOCAL_CSV.exists()
            with LOCAL_CSV.open("a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["timestamp_utc", "name", "min_preis", "median_preis", "anzahl", "url"])
                w.writerow(row)

            if not post_row(row):
                raise RuntimeError("Webhook nicht erreichbar")
        except Exception as e:
            failures += 1
            print(f"  FEHLER: {e}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
