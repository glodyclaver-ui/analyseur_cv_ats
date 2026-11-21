import unittest
from _helpers import make_cv_pdf
from services import pdf_vision_extractor as pv, contact_extractor as ce, experience_analyzer as ea


class T(unittest.TestCase):
    def test_annotation_links(self):
        r = pv.analyze_pdf(make_cv_pdf())
        self.assertTrue(any(l["type"] == "linkedin" for l in r["links"]))

    def test_no_photo_in_textual_cv(self):
        self.assertIsNone(pv.analyze_pdf(make_cv_pdf())["photo_base64"])

    def test_logo_rejected(self):
        from PIL import Image
        logo = Image.new("RGB", (200, 200), (20, 60, 200))
        self.assertLess(pv.score_image(logo), 0.1)

    def test_strict_name(self):
        self.assertEqual(pv.extract_name_strict("CV\nDeveloppeur Python\nJean Mukendi\n"), "Jean Mukendi")
        self.assertEqual(pv.extract_name_strict("Profil\n", "marie.kabeya@x.cd"), "Marie Kabeya")

    def test_phone_normalization(self):
        self.assertEqual(ce.normalize_phone("0812345678"), "+243 812 345 678")

    def test_exact_duration(self):
        d = ea.duration("Mars 2020 - Juin 2022", (2026, 11))
        self.assertEqual(d["months"], 28)
        self.assertEqual(ea.duration("Janvier 2024 - Present", (2026, 11))["label"], "2 ans 11 mois")

    def test_encrypted_handled(self):
        from pypdf import PdfReader, PdfWriter
        import io
        w = PdfWriter(); w.add_blank_page(100, 100); w.encrypt("secret")
        b = io.BytesIO(); w.write(b)
        self.assertTrue(pv.analyze_pdf(b.getvalue())["locked"])


if __name__ == "__main__":
    unittest.main()
