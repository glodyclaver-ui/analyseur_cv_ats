import io, unittest
from PIL import Image, ImageDraw, ImageFont
from _helpers import client
from services import ocr_engine

LINES = ["Jean MUKENDI", "Infirmier diplome", "jean.mukendi@example.com", "Bunia, RDC", "Soins infirmiers, injections, hygiene hospitaliere", "Experience: 5 ans"]


def make_img(fmt="PNG"):
    im = Image.new("RGB", (1000, 520), "white"); d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    except Exception:
        f = ImageFont.load_default()
    for i, l in enumerate(LINES):
        d.text((40, 30 + i * 70), l, fill="black", font=f)
    b = io.BytesIO(); im.save(b, fmt); return b.getvalue()


class OcrTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(ocr_engine.detect_kind(make_img("PNG")), "png")
        self.assertEqual(ocr_engine.detect_kind(make_img("JPEG")), "jpg")
        self.assertIsNone(ocr_engine.detect_kind(b"MZ\x90 not an image"))

    def test_fake_image_rejected(self):
        self.assertFalse(ocr_engine.validate_image_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage")["ok"])
        self.assertFalse(ocr_engine.validate_image_bytes(b"hello")["ok"])

    @unittest.skipUnless(ocr_engine.available(), "Tesseract absent")
    def test_ocr_text(self):
        t = ocr_engine.ocr_image(make_img("PNG")).lower()
        self.assertIn("mukendi", t); self.assertIn("example.com", t)

    @unittest.skipUnless(ocr_engine.available(), "Tesseract absent")
    def test_analyze_with_image_cv(self):
        c, h = client()
        job = "Offre Infirmier a Bunia, RDC.\n- Soins infirmiers\n- Injections\n- Hygiene hospitaliere"
        r = c.post("/api/analyze", data={"cv_pdf": (io.BytesIO(make_img("JPEG")), "cv.jpg"), "job_text": job}, content_type="multipart/form-data", headers=h).get_json()
        self.assertTrue(r["success"], r)
        self.assertIn("mukendi", r["cv_details"]["full_name"].lower())
        self.assertTrue(r["matched_skills"])

    def test_text_file_renamed_jpg_rejected(self):
        c, h = client()
        r = c.post("/api/analyze", data={"cv_pdf": (io.BytesIO(b"just text"), "cv.jpg"), "job_text": "Offre Infirmier soins"}, content_type="multipart/form-data", headers=h)
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
