import io, unittest
from _helpers import client, make_cv_pdf, JOB
from services import ats_scoring


class T(unittest.TestCase):
    def setUp(self):
        self.c, self.h = client()

    def test_analyze_full_pipeline(self):
        r = self.c.post("/api/analyze", data={"cv_pdf": (io.BytesIO(make_cv_pdf()), "cv.pdf"), "job_text": JOB}, headers=self.h,
                        content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])
        j = r.get_json()
        cv = j["cv_details"]
        self.assertEqual(cv["full_name"], "Jean Mukendi")
        self.assertTrue(any(l["type"] == "linkedin" for l in cv["links_detail"]))
        self.assertTrue(cv["structured_experiences"])
        self.assertIn("duration_label", cv["structured_experiences"][0])
        self.assertEqual(j["initial_score"], j["score"])
        self.assertIn("org_check", j)
        self.__class__.report = j

    def test_recalc_keeps_data_and_compares(self):
        self.test_analyze_full_pipeline()
        rep = dict(self.report)
        rep["matched_skills"] = rep["matched_skills"] + rep["missing_skills"]
        rep["missing_skills"] = []
        o = self.c.post("/api/recalculate", json=rep, headers=self.h).get_json()
        self.assertGreater(o["score"], o["initial_score"])
        self.assertEqual(o["score_comparison"]["delta"], o["score"] - o["initial_score"])
        self.assertTrue(o["cv_details"]["structured_experiences"])

    def test_compare(self):
        self.assertEqual(ats_scoring.compare_scores(50, 60)["delta"], 10)

    def test_readability(self):
        self.assertGreater(ats_scoring.ats_readability("experience formation competences a@b.c " + "mot " * 300)["score"], 50)


if __name__ == "__main__":
    unittest.main()


class GeoCountryOnly(unittest.TestCase):
    def test_country_only_levels(self):
        import app as A
        self.assertEqual(A.resolve_city_geo("RDC")["level"], "country")
        self.assertEqual(A.resolve_city_geo("Bénin")["label"], "Bénin (pays seulement)")  # plus pris pour la ville de Beni
        self.assertEqual(A.resolve_city_geo("Paris, France")["level"], "city")

    def test_same_country_no_fake_distance(self):
        import app as A
        e = A.evaluate_geo("RDC", "Kinshasa, RDC", "")
        self.assertEqual(e["chance_pct"], 75)
        self.assertIsNone(e["intel"]["distance_km"])
        self.assertEqual(A.evaluate_geo("France", "Kinshasa, RDC", "")["chance_pct"], 35)

    def test_phone_hint_when_no_location(self):
        import app as A
        cv = A.extract_cv_details("Jean Mukendi\nDeveloppeur\n+243 812 345 678 jean@x.cd\nCompetences Python")
        self.assertEqual(cv["country_hint"], "RDC")
