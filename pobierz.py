"""Pobiera oferty Meta Quest 3 z OLX (publiczne API) i zapisuje je do data/oferty.json.

Filtry twarde: Quest 3 (nie 3S/2/Pro), cena 600–1800 zł, Przesyłka OLX aktywna.
Ocenę jakości (rysy, oszustwa, ranking) robi potem Claude na podstawie tego pliku.
"""
import json, re, sys, time, datetime, urllib.request, urllib.parse

API = "https://www.olx.pl/api/v1/offers/"
HEAD = {
    "User-Agent": "quest3-monitor/1.0 (prywatny monitoring ofert, 1 zapytanie dziennie)",
    "Accept": "application/json",
    "Accept-Language": "pl-PL,pl;q=0.9",
}
FRAZY = ["meta quest 3", "oculus quest 3", "quest 3 512", "quest 3 128"]
OK_TYTUL = re.compile(r"quest\s*3(?!\s*s)", re.I)
ZLE_TYTUL = re.compile(r"quest\s*3\s*s|\b3s\b|quest\s*2|quest\s*pro|rift|"
                       r"^(pasek|bateria|akumulator|kabel|etui|podstawka|nak[łl]adka|torba)", re.I)


def get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEAD)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cena(a):
    for p in a.get("params", []):
        if p.get("key") == "price":
            return (p.get("value") or {}).get("value")
    return None


def main():
    zebrane = {}
    for fraza in FRAZY:
        for off in range(0, 250, 50):
            try:
                j = get({"offset": off, "limit": 50, "query": fraza,
                         "filter_float_price:from": 600, "filter_float_price:to": 1800,
                         "sort_by": "created_at:desc"})
            except Exception as e:
                print(f"BŁĄD {fraza} offset {off}: {e}", file=sys.stderr)
                break
            dane = j.get("data") or []
            for a in dane:
                zebrane[a["id"]] = a
            if len(dane) < 50:
                break
            time.sleep(1)

    if not zebrane:
        print("Brak danych z OLX — prawdopodobnie blokada.", file=sys.stderr)
        sys.exit(1)

    wynik, licznik_sprzedawcy = [], {}
    for a in zebrane.values():
        t = a.get("title", "")
        if not OK_TYTUL.search(t) or ZLE_TYTUL.search(t):
            continue
        if not ((a.get("delivery") or {}).get("rock") or {}).get("active"):
            continue  # tylko Przesyłka OLX
        uid = (a.get("user") or {}).get("id")
        if uid and uid not in licznik_sprzedawcy:
            try:
                licznik_sprzedawcy[uid] = len(get({"user_id": uid, "limit": 50}).get("data") or [])
            except Exception:
                licznik_sprzedawcy[uid] = None
            time.sleep(0.5)
        u = a.get("user") or {}
        opis = re.sub(r"<[^>]+>", " ", a.get("description", ""))
        wynik.append({
            "id": a["id"],
            "url": a["url"],
            "tytul": t,
            "cena": cena(a),
            "stan": next((p["value"].get("label") for p in a.get("params", [])
                          if p.get("key") == "state"), None),
            "opis": re.sub(r"\s+", " ", opis).strip()[:1500],
            "miasto": (a.get("location") or {}).get("city", {}).get("name"),
            "region": (a.get("location") or {}).get("region", {}).get("name"),
            "sprzedawca": u.get("name"),
            "sprzedawca_id": uid,
            "konto_od": (u.get("created") or "")[:10],
            "firma": a.get("business"),
            "ogloszen_sprzedawcy": licznik_sprzedawcy.get(uid),
            "dodane": a.get("created_time"),
            "odswiezone": a.get("last_refresh_time"),
        })

    wynik.sort(key=lambda x: x["dodane"] or "", reverse=True)
    out = {"pobrano": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "przejrzano": len(zebrane), "ofert": len(wynik), "oferty": wynik}
    with open("data/oferty.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"OK: przejrzano {len(zebrane)}, z Przesyłką OLX i Quest 3: {len(wynik)}")


if __name__ == "__main__":
    main()
