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
LOCAL_CSV = Path("preishistorie_local.csv")  # nur Fallback/Backup, wird NICHT committet
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d{3,5})\s*(?:€|EUR)")
MIN_PLAUSIBLE, MAX_PLAUSIBLE = 300, 15000  # filtert Müll-Treffer


def fetch(url: str, attempts: int = 3) -> str:
    last = "unbekannt"
    for i in range(1, attempts + 1):
        try:
            r = requests.get(
                "https://api.scraperapi.com/",
                params={
                    "api_key": API_KEY,
                    "url": url,
                    "render": "true",       # JS rendern (nachgeladene Preise)
                    "country_code": "de",
                    "premium": "true",      # Residential-IPs
                },
                timeout=180,
            )
            # sehr kurze Antworten sind meist Block-/Fehlerseiten
            if r.status_code == 200 and len(r.text) > 20000:
                return r.text
            last = f"HTTP {r.status_code}, {len(r.text)} Bytes"
        except requests.RequestException as e:
            last = str(e)
        print(f"  Versuch {i}/{attempts} fehlgeschlagen: {last}", file=sys.stderr)
        time.sleep(10 * i)
    raise RuntimeError(f"Abruf fehlgeschlagen: {last}")


def parse_prices(html: str, selector: str = "") -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    if selector:
        text_parts = [el.get_text(" ", strip=True) for el in soup.select(selector)]
        text = " | ".join(text_parts)
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
        print(f"→ {name}")
        try:
            html = fetch(s["url"])
            prices = parse_prices(html, s.get("selector", ""))
            if not prices:
                (DEBUG_DIR / f"{name}.html").write_text(html, encoding="utf-8")
                raise RuntimeError("Keine Preise gefunden (HTML in debug/ gespeichert)")
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
