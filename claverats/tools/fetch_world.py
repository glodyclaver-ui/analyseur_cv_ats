#!/usr/bin/env python3
"""
Télécharge UNE SEULE FOIS les frontières réelles des pays (Natural Earth 1:110m, domaine public)
et écrit static/data/world.geojson (~150 Ko). Ensuite l'application reste 100 % hors-ligne :
GeoMap détecte le fichier et remplace automatiquement les contours simplifiés par les vrais pays
(survol, clic et zoom par pays).

Usage (avec une connexion Internet, une seule fois) :
    python tools/fetch_world.py
Option : python tools/fetch_world.py chemin/vers/ne_110m_admin_0_countries.geojson   (fichier déjà téléchargé)
"""
import json, os, sys, urllib.request

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "data", "world.geojson")


def rnd(c):
    return [round(c[0], 2), round(c[1], 2)] if isinstance(c[0], (int, float)) else [rnd(x) for x in c]


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            data = json.load(f)
    else:
        print("Téléchargement de", URL)
        with urllib.request.urlopen(URL, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
    feats = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        g = f.get("geometry")
        if not g or p.get("ISO_A3") == "ATA" and False:
            continue
        feats.append({
            "type": "Feature",
            "properties": {
                "NAME": p.get("NAME") or p.get("ADMIN") or "",
                "NAME_FR": p.get("NAME_FR") or p.get("NAME") or "",
                "CONTINENT": p.get("CONTINENT") or "",
                "ISO_A3": p.get("ISO_A3") or p.get("ADM0_A3") or "",
            },
            "geometry": {"type": g["type"], "coordinates": rnd(g["coordinates"])},
        })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"OK : {len(feats)} pays écrits dans {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
