import io, unittest
from _helpers import client, make_cv_pdf, JOB
from services import campaign_manager as cm, candidate_deduplication as dd


class T(unittest.TestCase):
    def test_export_import_and_tamper(self):
        t = cm.export_campaign({"candidates": [{"name": "A"}]})
        self.assertEqual(cm.import_campaign(t)["candidates"][0]["name"], "A")
        with self.assertRaises(ValueError):
            cm.import_campaign(t.replace('"A"', '"B"'))
        with self.assertRaises(ValueError):
            cm.import_campaign("pas du json")

    def test_hr_batch_dedupe_and_reject(self):
        c, h = client()
        pdf = make_cv_pdf()
        r = c.post("/api/hr-batch", data={"hr_job_text": JOB, "hr_cv_files": [(io.BytesIO(pdf), "a.pdf"), (io.BytesIO(pdf), "b.pdf"),
                                                                              (io.BytesIO(b"faux"), "c.pdf")]},
                   headers=h, content_type="multipart/form-data")
        j = r.get_json()
        self.assertTrue(j["success"], j)
        self.assertEqual(j["duplicates_count"], 1)
        self.assertEqual(len(j["rejected_files"]), 1)
        cand = j["candidates"][0]
        self.assertTrue(cand["links_detail"] and cand["experience_analysis"] and cand["initial_score"] is not None)

    def test_hr_recalc_keeps_experiences(self):
        c, h = client()
        j = c.post("/api/hr-batch", data={"hr_job_text": JOB, "hr_cv_files": [(io.BytesIO(make_cv_pdf()), "a.pdf")]}, headers=h,
                   content_type="multipart/form-data").get_json()
        cand = j["candidates"][0]
        cand["matched_skills"] = cand["matched_skills"] + ["Kubernetes"]
        o = c.post("/api/hr-recalculate-candidate", json={"candidate": cand, "job_details": j.get("job_details", {}), "job_skills": ["Python", "Kubernetes"]}, headers=h).get_json()
        nc = o["candidate"]
        self.assertTrue(nc["structured_experiences"] and nc["links"] and nc["score_comparison"])

    def test_dedupe_engine(self):
        r = dd.find_duplicates([{"full_name": "A B", "emails": ["x@y.z"]}, {"full_name": "Autre", "emails": ["X@y.z"]}])
        self.assertEqual(len(r), 1)

    def test_services_endpoints(self):
        c, h = client()
        rep = c.post("/api/analyze", data={"cv_pdf": (io.BytesIO(make_cv_pdf()), "cv.pdf"), "job_text": JOB}, headers=h,
                     content_type="multipart/form-data").get_json()
        i = c.post("/api/svc/intel", json={"report": rep}, headers=h).get_json()
        for k in ("talent", "potential", "decision", "gaps", "careers", "path", "interview", "semantic"):
            self.assertIn(k, i)
        for ep, body in (("/api/svc/analytics", {"reports": [rep]}), ("/api/svc/team", {"reports": [rep]}), ("/api/svc/graph", {"reports": [rep]}),
                         ("/api/svc/search", {"reports": [rep], "query": "python docker"}), ("/api/svc/workforce", {"reports": [rep], "required": ["Python"]}),
                         ("/api/svc/scenario", {"report": rep, "add_skills": rep["missing_skills"][:1]})):
            self.assertTrue(c.post(ep, json=body, headers=h).get_json()["success"], ep)
        self.assertEqual(c.post("/api/svc/report-html", json={"report": rep}, headers=h).status_code, 200)


if __name__ == "__main__":
    unittest.main()
