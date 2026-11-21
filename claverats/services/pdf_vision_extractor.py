"""Extraction visuelle PDF 100 % locale, en memoire : photo (cascade + heuristiques), logos exclus,
QR codes, liens reels (/Annots -> /URI), nom strict. Degrade proprement sans OpenCV."""
import base64
import io
import re

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except Exception:  # pragma: no cover
    cv2 = np = None
    HAS_CV2 = False
from PIL import Image

Image.MAX_IMAGE_PIXELS = 40_000_000
from .contact_extractor import classify_link


def _cascades():
    out = []
    if HAS_CV2:
        try:
            import os
            base = cv2.data.haarcascades
            for n in ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml", "haarcascade_profileface.xml"):
                p = os.path.join(base, n)
                if os.path.exists(p):
                    out.append(cv2.CascadeClassifier(p))
        except Exception:
            pass
    return out


_CASC = None


def _skin_ratio(arr):
    """Part de pixels « peau » : plusieurs plages (YCrCb + HSV) pour couvrir TOUTES les carnations, y compris les peaux foncées ou peu éclairées."""
    ycc = cv2.cvtColor(arr, cv2.COLOR_RGB2YCrCb)
    m1 = cv2.inRange(ycc, (0, 133, 77), (255, 180, 135))
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    m2 = cv2.inRange(hsv, (0, 25, 25), (25, 190, 255))          # teintes chaudes (peau claire a foncee)
    m3 = cv2.inRange(hsv, (170, 25, 25), (180, 190, 255))
    m = cv2.bitwise_or(m1, cv2.bitwise_or(m2, m3))
    return float(m.mean() / 255.0)


def score_image(img):
    """Probabilite 0-1 qu'une image soit une photo d'identite (et non un logo/icone/QR)."""
    global _CASC
    w, h = img.size
    if w < 60 or h < 60:
        return 0.0
    ar = w / h
    if ar < 0.45 or ar > 1.7:
        return 0.0
    small = img.convert("RGB").resize((64, 64))
    colors = len(small.getcolors(5000) or [])
    if colors < 60:  # aplat de couleurs : logo / icone / pictogramme
        return 0.02
    # un logo/pictogramme est domine par quelques aplats ; une photo repartit ses pixels sur de nombreuses nuances
    q = (np.array(small).reshape(-1, 3) // 32) if HAS_CV2 else None
    if q is not None:
        _, counts = np.unique(q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2], return_counts=True)
        if np.sort(counts)[::-1][:2].sum() / counts.sum() > 0.9:
            return 0.02
    if not HAS_CV2:
        return 0.4 if 0.7 <= ar <= 1.2 else 0.2
    arr = np.array(img.convert("RGB"))
    sc = 0.0
    skin = _skin_ratio(cv2.resize(arr, (96, 96)))
    sc += min(0.45, skin * 1.2)
    if _CASC is None:
        _CASC = _cascades()
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    for c in _CASC:
        try:
            if len(c.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))):
                sc += 0.5
                break
        except Exception:
            continue
    sc += 0.1 if 0.7 <= ar <= 1.2 else 0.0
    # sans modele de visage : un portrait est riche en couleurs/nuances, centre-clair, sans trop de contours
    if not _CASC:
        sc += 0.15 if colors >= 400 else 0.05
        cx = gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
        if cx.size and cx.std() > 25:
            sc += 0.1
    edges = cv2.Canny(gray, 80, 160).mean() / 255
    if edges > 0.25:  # trop de contours : QR code / schema
        sc -= 0.3
    return max(0.0, min(1.0, sc))


def detect_qr(img):
    if not HAS_CV2:
        return None
    try:
        data, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(img.convert("RGB")))
        return data or None
    except Exception:
        return None


def extract_photo(reader, threshold=0.35):
    """Retourne {photo_base64, score, qr_links} depuis le PDF (PdfReader) ; photo=None si aucune."""
    best, best_s, qrs, cands = None, 0.0, [], []
    for pi, page in enumerate(list(reader.pages)[:2]):
        try:
            imgs = list(page.images)
        except Exception:
            imgs = []
        for im in imgs[:12]:
            try:
                pil = Image.open(io.BytesIO(im.data))
                pil.load()
            except Exception:
                continue
            q = detect_qr(pil) if min(pil.size) >= 60 else None
            if q:
                qrs.append(q)
                continue
            s = score_image(pil) * (1.1 if pi == 0 else 0.9)
            if s >= 0.15:
                cands.append(s)
            if s > best_s:
                best, best_s = pil, s
    photo = None
    # image portrait-compatible unique : tres probablement la photo meme si le score est modeste (carnation foncee, pas de modele de visage)
    lone = best is not None and best_s >= 0.2 and len(cands) == 1
    if best is not None and (best_s >= threshold or lone):
        best = best.convert("RGB")
        best.thumbnail((320, 320))
        buf = io.BytesIO()
        best.save(buf, "JPEG", quality=85)
        photo = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"photo_base64": photo, "score": round(best_s, 2), "qr_links": qrs}


def extract_annotation_links(reader):
    """Liens cliquables reels (icones LinkedIn/GitHub incluses) via /Annots -> /A -> /URI."""
    uris = []
    for page in reader.pages:
        try:
            annots = page.get("/Annots") or []
        except Exception:
            continue
        for a in annots:
            try:
                obj = a.get_object()
                act = obj.get("/A")
                if act is not None:
                    uri = act.get_object().get("/URI")
                    if uri:
                        uris.append(str(uri))
            except Exception:
                continue
    out, seen = [], set()
    for u in uris:
        k = u.lower().rstrip("/")
        if k not in seen:
            seen.add(k)
            out.append({"url": u, "type": "email" if u.lower().startswith("mailto:") else "phone" if u.lower().startswith("tel:") else classify_link(u), "source": "pdf-annotation"})
    return out


_BAD_NAME = re.compile(r"(curriculum|vitae|\bcv\b|resume|profil|contact|competence|experience|formation|education|langue|objectif|"
                       r"developpeur|ingenieur|manager|analyste|technicien|@|http|\d)", re.I)


def extract_name_strict(text, email=""):
    """Nom = 2-4 mots alphabetiques, majuscule initiale, hors mots-cles de sections ; sinon derive de l'e-mail."""
    import unicodedata
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()][:12]
    for l in lines:
        ln = "".join(c for c in unicodedata.normalize("NFD", l) if unicodedata.category(c) != "Mn")
        if _BAD_NAME.search(ln):
            continue
        w = l.split()
        if 2 <= len(w) <= 4 and all(re.fullmatch(r"[A-Za-zÀ-ÿ'’-]{2,}", x) for x in w) and sum(x[0].isupper() for x in w) >= 2:
            return " ".join(x.capitalize() if x.isupper() else x for x in w)
    if email:
        loc = email.split("@")[0]
        parts = [p for p in re.split(r"[._-]+", re.sub(r"\d+", "", loc)) if len(p) > 1]
        if len(parts) >= 2:
            return " ".join(p.capitalize() for p in parts[:3])
    return ""


def ocr_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_image(pil):
    """OCR local optionnel (Tesseract) ; chaine vide si indisponible."""
    if not ocr_available():
        return ""
    import pytesseract
    try:
        return pytesseract.image_to_string(pil, lang="fra+eng")
    except Exception:
        try:
            return pytesseract.image_to_string(pil)
        except Exception:
            return ""


def analyze_pdf(data: bytes, password=""):
    """Point d'entree : tout en RAM. Retourne dict (photo, links, qr, encrypted, pages)."""
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(data))
    enc = bool(r.is_encrypted)
    if enc:
        try:
            if r.decrypt(password or "") == 0:
                return {"encrypted": True, "locked": True, "photo_base64": None, "links": [], "qr_links": [], "pages": 0}
        except Exception:
            return {"encrypted": True, "locked": True, "photo_base64": None, "links": [], "qr_links": [], "pages": 0}
    ph = extract_photo(r)
    return {"encrypted": enc, "locked": False, "pages": len(r.pages), "photo_base64": ph["photo_base64"],
            "photo_score": ph["score"], "qr_links": ph["qr_links"], "links": extract_annotation_links(r)}
