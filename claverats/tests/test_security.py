import unittest
from _helpers import client, make_cv_pdf, JOB
from services import document_security_engine as ds, security_manager as sec, audit_trail_manager as audit


class T(unittest.TestCase):
    def test_magic_bytes(self):
        self.assertFalse(ds.validate_pdf_bytes(b"MZ not a pdf")["ok"])
        self.assertTrue(ds.validate_pdf_bytes(make_cv_pdf())["ok"])

    def test_size_limit(self):
        self.assertFalse(ds.validate_pdf_bytes(b"%PDF-" + b"0" * (16 * 1024 * 1024))["ok"])

    def test_js_detection(self):
        r = ds.validate_pdf_bytes(b"%PDF-1.4\n/JavaScript (app.alert(1)) \n%%EOF")
        self.assertTrue(r["ok"] and r["active_content"])

    def test_ssrf(self):
        for u in ("http://127.0.0.1/x", "http://localhost/", "http://10.0.0.5/", "http://169.254.169.254/", "file:///etc/passwd", "http://[::1]/"):
            self.assertFalse(ds.is_safe_url(u, resolve=False), u)

    def test_formula_injection(self):
        self.assertEqual(ds.neutralize_cell("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(ds.neutralize_cell("abc"), "abc")

    def test_punycode(self):
        self.assertTrue(ds.punycode_alert("xn--pple-43d.com"))

    def test_xss_escape(self):
        self.assertNotIn("<script>", ds.escape_html("<script>alert(1)</script>"))

    def test_csrf_enforced_and_headers(self):
        import app as A
        c = A.app.test_client()
        self.assertEqual(c.post("/api/recalculate", json={}).status_code, 403)
        c2, h = client()
        r = c2.post("/api/recalculate", json={"cv_details": {}, "job_details": {}}, headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])

    def test_fake_pdf_rejected_by_api(self):
        import io
        c, h = client()
        r = c.post("/api/analyze", data={"cv_pdf": (io.BytesIO(b"hello"), "x.pdf"), "job_text": JOB}, headers=h, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.assertIn("vrai PDF", r.get_json()["message"])

    def test_pin_and_audit_chain(self):
        sec.set_pin("1234")
        self.assertTrue(sec.check_pin("1234"))
        self.assertFalse(sec.check_pin("0000"))
        self.assertTrue(audit.verify()["ok"])


if __name__ == "__main__":
    unittest.main()
