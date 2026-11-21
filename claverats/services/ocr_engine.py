"""OCR 100 % LOCAL pour CV en image (JPG/PNG) et PDF scannés.

Aucun envoi externe : Pillow + OpenCV (pré-traitement) + Tesseract installé localement (pytesseract).
Dégrade proprement : si Tesseract est absent, on le dit clairement au lieu d'inventer du texte.
"""
import hashlib
import io

from PIL import Image

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except Exception:  # pragma: no cover
    cv2 = np = None
    HAS_CV2 = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    HAS_TESS = True
except Exception:  # pragma: no cover
    pytesseract = None
    HAS_TESS = False

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_PDF_IMAGES = 6
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def available():
    return HAS_TESS


def detect_kind(data: bytes):
    """Type réel d'après les octets magiques (pas l'extension) : 'pdf' | 'png' | 'jpg' | None."""
    head = (data or b"")[:1024].lstrip(b"\x00\r\n\t ")
    if head.startswith(b"%PDF-"):
        return "pdf"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    return None


def validate_image_bytes(data: bytes):
    """Valide une image de CV : signature, taille, décodage réel. Retourne le même format que validate_pdf_bytes."""
    if not data:
        return {"ok": False, "reason": "Fichier vide.", "warnings": []}
    if len(data) > MAX_IMAGE_BYTES:
        return {"ok": False, "reason": "Image trop volumineuse (max 10 Mo).", "warnings": []}
    kind = detect_kind(data)
    if kind not in ("png", "jpg"):
        return {"ok": False, "reason": "Format image non reconnu (JPG ou PNG attendu).", "warnings": []}
    try:
        im = Image.open(io.BytesIO(data)); im.verify()
    except Exception:
        return {"ok": False, "reason": "Image corrompue ou illisible.", "warnings": []}
    warn = [] if HAS_TESS else ["OCR indisponible sur ce poste (Tesseract non installé) : collez le texte du CV."]
    return {"ok": True, "reason": "", "warnings": warn, "kind": "image", "image_type": kind,
            "sha256": hashlib.sha256(data).hexdigest(), "encrypted": False, "active_content": False}


def preprocess(img: Image.Image):
    """Gris -> agrandissement si petit -> débruitage -> binarisation adaptative (OpenCV) ; repli Pillow."""
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) < 1600:
        k = 1600 / max(w, h)
        img = img.resize((int(w * k), int(h * k)), Image.LANCZOS)
    if not HAS_CV2:
        return img.convert("L")
    g = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    g = cv2.fastNlMeansDenoising(g, None, 12, 7, 21)
    g = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    return Image.fromarray(g)


def _lang():
    try:
        have = set(pytesseract.get_languages())
    except Exception:
        have = {"eng"}
    sel = [l for l in ("fra", "eng") if l in have]
    return "+".join(sel) or "eng"


def ocr_image(data: bytes) -> str:
    if not HAS_TESS:
        return ""
    try:
        img = Image.open(io.BytesIO(data))
        txt = pytesseract.image_to_string(preprocess(img), lang=_lang(), config="--psm 6")
    except Exception:
        return ""
    return "\n".join(l.rstrip() for l in txt.splitlines()).strip()


def ocr_pdf(data: bytes) -> str:
    """PDF scanné : OCR des images embarquées de chaque page (jusqu'à MAX_PDF_IMAGES)."""
    if not HAS_TESS:
        return ""
    try:
        from pypdf import PdfReader
        out, n = [], 0
        for page in PdfReader(io.BytesIO(data)).pages:
            for im in getattr(page, "images", []):
                if n >= MAX_PDF_IMAGES:
                    break
                n += 1
                t = ocr_image(im.data)
                if t:
                    out.append(t)
        return "\n".join(out).strip()
    except Exception:
        return ""


def diagnostics():
    """État des composants de lecture d'images (pour l'écran de diagnostic). Aucun accès réseau."""
    import os
    d = {"tesseract": HAS_TESS, "tesseract_version": "", "languages": [], "french": False, "opencv": HAS_CV2, "opencv_version": "",
         "face_models": False, "network_needed": False}
    if HAS_TESS:
        try:
            d["tesseract_version"] = str(pytesseract.get_tesseract_version())
            d["languages"] = sorted(pytesseract.get_languages())
            d["french"] = "fra" in d["languages"]
        except Exception:
            pass
    if HAS_CV2:
        d["opencv_version"] = getattr(cv2, "__version__", "")
        try:
            d["face_models"] = os.path.exists(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
        except Exception:
            pass
    tips = []
    if not HAS_TESS:
        tips.append("Installez Tesseract OCR sur ce poste (Windows : installeur UB Mannheim, cochez la langue « French »), puis redémarrez l'application. Aucune connexion Internet n'est ensuite nécessaire.")
    elif not d["french"]:
        tips.append("Ajoutez la langue française à Tesseract (fichier fra.traineddata dans le dossier tessdata).")
    if not d["face_models"]:
        tips.append("Modèles de détection de visage OpenCV absents : la photo est repérée par une méthode de secours (moins précise).")
    d["tips"] = tips
    d["ok"] = HAS_TESS and d["french"]
    return d
