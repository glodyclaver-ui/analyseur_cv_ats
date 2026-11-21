"""Facade de validation de documents (alias pratique de document_security_engine)."""
from .document_security_engine import validate_pdf_bytes, MAX_PDF_BYTES, sha256_hex


def validate_upload(file_storage):
    """Lit un FileStorage Flask en RAM, valide, retourne (bytes|None, resultat)."""
    data = file_storage.read(MAX_PDF_BYTES + 1)
    file_storage.seek(0)
    res = validate_pdf_bytes(data)
    return (data if res["ok"] else None), res
