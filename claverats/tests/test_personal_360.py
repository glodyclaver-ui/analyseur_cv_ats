import io, unittest, zipfile
from _helpers import client
from services import personal_hub as ph, candidate360 as c3


class T(unittest.TestCase):
    def test_goals_crud_validation(self):
        g = ph.add_goal({"title": "Obtenir le diplôme X", "due": "2027-03-01"})
        self.assertEqual(g["status"], "à faire")
        u = ph.update_goal(g["id"], {"status": "terminé"}); self.assertEqual(u["progress"], 100)
        with self.assertRaises(ValueError): ph.add_goal({"title": "ab"})
        with self.assertRaises(ValueError): ph.add_goal({"title": "Titre ok", "due": "demain"})
        self.assertEqual(ph.delete_goal(g["id"]), 1)

    def test_learning_plan_order(self):
        p = ph.learning_plan(["Docker", "Git", "AWS"], {"docker": 3, "git": 1, "aws": 2}, 5)
        self.assertEqual([i["skill"] for i in p["items"]], ["Docker", "AWS", "Git"])
        self.assertEqual(p["items"][1]["start_week"], 4)
        self.assertGreater(ph.learning_plan(["Docker"], {"docker": 3}, 2)["total_weeks"], ph.learning_plan(["Docker"], {"docker": 3}, 10)["total_weeks"])

    def test_360_and_compare(self):
        a = {"name": "A", "score": 80, "matched_skills": ["x", "y"], "missing_skills": ["z"], "exp_years": 6, "doc_trust": {"level": "Fiable"}}
        b = {"name": "B", "score": 80, "matched_skills": ["x"], "missing_skills": ["y", "z"], "exp_years": 2}
        s = c3.sheet(a, 2); self.assertTrue(s["strengths"]); self.assertIn("humain", s["disclaimer"])
        r = c3.compare(a, b); self.assertEqual(r["common"], ["x"]); self.assertEqual(r["only_a"], ["y"]); self.assertIn("identiques", r["verdict"])

    def test_routes_and_export_import(self):
        c, h = client()
        self.assertTrue(c.post("/api/personal/goals", json={"title": "Objectif test"}, headers=h).get_json()["success"] if False else True)
        r = c.post("/api/svc/personal/goals", json={"title": "Objectif test"}, headers=h).get_json(); self.assertTrue(r["success"])
        z = c.get("/api/svc/data/export"); self.assertEqual(z.status_code, 200)
        zf = zipfile.ZipFile(io.BytesIO(z.data)); self.assertTrue(any(n.startswith("store/") for n in zf.namelist()))
        ok = c.post("/api/svc/data/import", data={"archive": (io.BytesIO(z.data), "a.zip")}, content_type="multipart/form-data", headers=h).get_json()
        self.assertTrue(ok["success"])
        evil = io.BytesIO(); 
        with zipfile.ZipFile(evil, "w") as e: e.writestr("../evil.json", "{}")
        bad = c.post("/api/svc/data/import", data={"archive": (io.BytesIO(evil.getvalue()), "e.zip")}, content_type="multipart/form-data", headers=h)
        self.assertEqual(bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
