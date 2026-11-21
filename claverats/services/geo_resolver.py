"""Resolution geographique 100 % locale a deux niveaux : ville (fournie par l'appelant) puis PAYS seul.
Gere les CV/offres qui donnent le pays sans la ville, ou aucun lieu (pays deduit du telephone)."""
import re
import unicodedata

# cle: (label, lat, lon, indicatif, salaire_ref, [alias normalises])
COUNTRIES = {
    "rdc": ("RDC", -2.9, 23.7, "243", 1000, ["rdc", "r d c", "republique democratique du congo", "rd congo", "drc", "dr congo", "congo kinshasa", "congo-kinshasa", "democratic republic of the congo", "congo rdc"]),
    "congo": ("Congo-Brazzaville", -0.7, 15.2, "242", 950, ["congo brazzaville", "congo-brazzaville", "republique du congo", "rep du congo", "republic of the congo"]),
    "angola": ("Angola", -11.2, 17.9, "244", 900, ["angola"]),
    "zambie": ("Zambie", -13.1, 27.8, "260", 850, ["zambie", "zambia"]),
    "rwanda": ("Rwanda", -1.9, 29.9, "250", 850, ["rwanda"]),
    "burundi": ("Burundi", -3.4, 29.9, "257", 700, ["burundi"]),
    "ouganda": ("Ouganda", 1.4, 32.3, "256", 800, ["ouganda", "uganda"]),
    "kenya": ("Kenya", 0.2, 37.9, "254", 950, ["kenya"]),
    "tanzanie": ("Tanzanie", -6.4, 34.9, "255", 800, ["tanzanie", "tanzania"]),
    "ethiopie": ("Éthiopie", 9.1, 40.5, "251", 700, ["ethiopie", "ethiopia"]),
    "cameroun": ("Cameroun", 7.4, 12.4, "237", 950, ["cameroun", "cameroon"]),
    "gabon": ("Gabon", -0.8, 11.6, "241", 1100, ["gabon"]),
    "tchad": ("Tchad", 15.5, 18.7, "235", 750, ["tchad", "chad"]),
    "centrafrique": ("Centrafrique", 6.6, 20.9, "236", 650, ["centrafrique", "republique centrafricaine", "rca"]),
    "cote d'ivoire": ("Côte d'Ivoire", 7.5, -5.5, "225", 1000, ["cote d'ivoire", "cote d ivoire", "cote divoire", "ivory coast"]),
    "senegal": ("Sénégal", 14.5, -14.5, "221", 950, ["senegal"]),
    "mali": ("Mali", 17.6, -4.0, "223", 750, ["mali"]),
    "burkina faso": ("Burkina Faso", 12.2, -1.6, "226", 750, ["burkina faso", "burkina"]),
    "niger": ("Niger", 17.6, 8.1, "227", 700, ["niger"]),
    "togo": ("Togo", 8.6, 0.8, "228", 750, ["togo"]),
    "benin": ("Bénin", 9.3, 2.3, "229", 800, ["benin"]),
    "guinee": ("Guinée", 9.9, -9.7, "224", 700, ["guinee", "guinea"]),
    "nigeria": ("Nigeria", 9.1, 8.7, "234", 1000, ["nigeria"]),
    "ghana": ("Ghana", 7.9, -1.0, "233", 950, ["ghana"]),
    "maroc": ("Maroc", 31.8, -7.1, "212", 1000, ["maroc", "morocco"]),
    "algerie": ("Algérie", 28.0, 1.7, "213", 900, ["algerie", "algeria"]),
    "tunisie": ("Tunisie", 33.9, 9.5, "216", 850, ["tunisie", "tunisia"]),
    "egypte": ("Égypte", 26.8, 30.8, "20", 800, ["egypte", "egypt"]),
    "afrique du sud": ("Afrique du Sud", -30.6, 22.9, "27", 1400, ["afrique du sud", "south africa"]),
    "madagascar": ("Madagascar", -18.8, 46.9, "261", 650, ["madagascar"]),
    "maurice": ("Maurice", -20.3, 57.6, "230", 1200, ["maurice", "ile maurice", "mauritius"]),
    "mozambique": ("Mozambique", -18.7, 35.5, "258", 750, ["mozambique"]),
    "namibie": ("Namibie", -22.6, 17.1, "264", 1000, ["namibie", "namibia"]),
    "france": ("France", 46.6, 2.4, "33", 2400, ["france"]),
    "belgique": ("Belgique", 50.6, 4.7, "32", 2500, ["belgique", "belgium"]),
    "suisse": ("Suisse", 46.8, 8.2, "41", 4500, ["suisse", "switzerland"]),
    "luxembourg": ("Luxembourg", 49.8, 6.1, "352", 3200, ["luxembourg"]),
    "allemagne": ("Allemagne", 51.2, 10.4, "49", 2800, ["allemagne", "germany", "deutschland"]),
    "royaume-uni": ("Royaume-Uni", 54.0, -2.5, "44", 2700, ["royaume-uni", "royaume uni", "united kingdom", "uk", "angleterre", "england"]),
    "espagne": ("Espagne", 40.2, -3.7, "34", 1900, ["espagne", "spain"]),
    "italie": ("Italie", 42.8, 12.6, "39", 1900, ["italie", "italy"]),
    "portugal": ("Portugal", 39.6, -8.0, "351", 1500, ["portugal"]),
    "pays-bas": ("Pays-Bas", 52.2, 5.3, "31", 3000, ["pays-bas", "pays bas", "netherlands", "hollande"]),
    "canada": ("Canada", 56.1, -106.3, "1", 3000, ["canada"]),
    "usa": ("États-Unis", 39.8, -98.6, "1", 4000, ["usa", "u s a", "etats-unis", "etats unis", "united states", "etats-unis d'amerique"]),
    "bresil": ("Brésil", -10.8, -52.9, "55", 1200, ["bresil", "brazil"]),
    "emirats": ("Émirats arabes unis", 24.3, 54.3, "971", 3000, ["emirats arabes unis", "emirats", "uae", "dubai", "dubaï"]),
    "chine": ("Chine", 35.0, 103.8, "86", 1500, ["chine", "china"]),
    "inde": ("Inde", 22.9, 79.6, "91", 900, ["inde", "india"]),
    "turquie": ("Turquie", 39.0, 35.2, "90", 1100, ["turquie", "turkey"]),
}

_PHONE = {}
for _k, _v in COUNTRIES.items():
    _PHONE.setdefault(_v[3], _k)
_PHONE["1"] = "canada"  # +1 : ambigu USA/Canada -> traite comme "Amerique du Nord" via canada/usa


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


_ALIAS = []
for _k, _v in COUNTRIES.items():
    for _a in _v[5] + [_v[0]]:
        _ALIAS.append((_norm(_a), _k))
_ALIAS.sort(key=lambda x: -len(x[0]))  # alias longs d'abord ("congo kinshasa" avant "congo")


def find_country(text):
    """Retourne la cle de pays trouvee dans le texte (mot entier) ou None."""
    n = " " + re.sub(r"[^a-z0-9' -]", " ", _norm(text)) + " "
    for alias, key in _ALIAS:
        if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", n):
            return key
    return None


def country_geo(key, approx_label=True):
    lab, lat, lon, _, sal, _a = COUNTRIES[key]
    return {"key": "country:" + key, "country": key, "lat": lat, "lon": lon,
            "label": lab + (" (pays seulement)" if approx_label else ""), "salary_ref": sal, "tension": "Normale",
            "level": "country", "approx": True}


def resolve_country(text):
    k = find_country(text)
    return country_geo(k) if k else None


def country_of_label(text):
    return find_country(text)


def country_from_phone(phone):
    d = re.sub(r"\D", "", str(phone or ""))
    for L in (3, 2, 1):
        if d[:L] in _PHONE:
            return _PHONE[d[:L]]
    return None


def country_label(key):
    return COUNTRIES[key][0] if key in COUNTRIES else ""
