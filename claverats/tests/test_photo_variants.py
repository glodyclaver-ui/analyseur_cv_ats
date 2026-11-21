import io, unittest
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from pypdf import PdfReader
from services import pdf_vision_extractor as pv


def portrait(skin=(224, 172, 140), bg=(200, 210, 230), size=(300, 400)):
    im = Image.new("RGB", size, bg); d = ImageDraw.Draw(im); w, h = size
    d.rectangle([w * .1, h * .72, w * .9, h], fill=(40, 60, 110))            # epaules
    d.ellipse([w * .28, h * .18, w * .72, h * .66], fill=skin)               # visage
    d.pieslice([w * .25, h * .12, w * .75, h * .5], 180, 360, fill=(25, 20, 20))  # cheveux
    d.ellipse([w * .38, h * .36, w * .44, h * .41], fill=(20, 20, 20)); d.ellipse([w * .56, h * .36, w * .62, h * .41], fill=(20, 20, 20))
    d.arc([w * .4, h * .5, w * .6, h * .6], 20, 160, fill=(90, 30, 30), width=4)
    rng = np.random.default_rng(1)
    arr = np.clip(np.array(im).astype(int) + rng.integers(-12, 12, (h, w, 3)), 0, 255).astype("uint8")
    return Image.fromarray(arr).filter(ImageFilter.GaussianBlur(0.8))


def pdf_with(imgs, fmt="JPEG"):
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); c.drawString(60, 800, "Jean Mukendi")
    for i, (im, box) in enumerate(imgs):
        b = io.BytesIO(); im.save(b, fmt); b.seek(0); c.drawImage(ImageReader(b), *box, mask="auto")
    c.save(); return PdfReader(io.BytesIO(buf.getvalue()))


def logo():
    im = Image.new("RGB", (200, 200), (255, 255, 255)); d = ImageDraw.Draw(im); d.ellipse([20, 20, 180, 180], fill=(30, 80, 200)); return im


class PhotoTest(unittest.TestCase):
    def test_light_and_dark_skin_found(self):
        for skin in [(224, 172, 140), (141, 85, 60), (92, 56, 40), (60, 38, 28)]:
            r = pdf_with([(portrait(skin), (400, 650, 120, 160))])
            self.assertTrue(pv.extract_photo(r)["photo_base64"], f"photo non reconnue pour la carnation {skin}")

    def test_png_with_alpha_and_cropped_portrait(self):
        im = portrait((120, 74, 50)).convert("RGBA")
        r = pdf_with([(im, (400, 650, 120, 160))], fmt="PNG")
        self.assertTrue(pv.extract_photo(r)["photo_base64"])

    def test_logo_and_banner_are_not_photos(self):
        banner = Image.new("RGB", (900, 120), (30, 30, 90))
        r = pdf_with([(logo(), (40, 700, 80, 80)), (banner, (0, 760, 595, 80))])
        self.assertIsNone(pv.extract_photo(r)["photo_base64"])

    def test_photo_chosen_among_logo(self):
        r = pdf_with([(logo(), (40, 700, 80, 80)), (portrait((100, 60, 45)), (420, 640, 120, 160))])
        self.assertTrue(pv.extract_photo(r)["photo_base64"])


if __name__ == "__main__":
    unittest.main()
