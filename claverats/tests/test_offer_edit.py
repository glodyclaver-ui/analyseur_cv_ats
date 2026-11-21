import unittest
from _helpers import client, make_cv_pdf, JOB
import io


class OfferEditTest(unittest.TestCase):
    def setUp(self):
        self.c, self.h = client()

    def _analyze(self):
        r = self.c.post("/api/analyze", data={"cv_pdf": (io.BytesIO(make_cv_pdf()), "cv.pdf"), "job_text": JOB}, content_type="multipart/form-data", headers=self.h)
        return r.get_json()

    def test_edit_company_email_link(self):
        rep = self._analyze(); self.assertTrue(rep["success"])
        rep["offer_edit"] = None
        body = {**rep, "offer": {"company_name": "ONG Test", "contact_email": "rh@ong-test.org", "offer_url": "https://ong-test.org/job/1"}}
        r = self.c.post("/api/reanalyze-offer", json=body, headers=self.h).get_json()
        self.assertEqual(r["job_details"]["company_name"], "ONG Test")
        self.assertEqual(r["job_details"]["apply_emails"][0], "rh@ong-test.org")
        self.assertEqual(r["job_details"]["apply_links"][0], "https://ong-test.org/job/1")

    def test_new_description_changes_requirements(self):
        rep = self._analyze()
        body = {**rep, "offer": {"description": "Infirmier diplômé d'État. Soins infirmiers, hygiène hospitalière, pansements, perfusions, 3 ans d'expérience. Kinshasa."}}
        r = self.c.post("/api/reanalyze-offer", json=body, headers=self.h).get_json()
        self.assertTrue(r["success"]); self.assertNotEqual(r["score"], None)
        self.assertIn("infirm", (r["job_details"]["detected_role"].get("label") or "").lower())

    def test_validation(self):
        rep = self._analyze()
        r = self.c.post("/api/reanalyze-offer", json={**rep, "offer": {"contact_email": "pas-un-mail"}}, headers=self.h)
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
