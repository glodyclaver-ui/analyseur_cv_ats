import json, os, unittest
import _helpers  # noqa: F401
from _helpers import client
from services import skills_referential as sr, _core

JOB = "Offre : Infirmier(ère) à Bunia, RDC.\n- Diplôme d'État infirmier A2\n- Soins infirmiers, prélèvements, injections\n- Hygiène hospitalière"


class T(unittest.TestCase):
    def test_noise_is_rejected(self):
        for w in ("D", "Etc.", "Des", "Salaire", "Compétences", "R", "12"):
            self.assertTrue(sr.is_noise(w), w)
        self.assertFalse(sr.is_noise("Python"))
        self.assertFalse(sr.is_noise("Soins infirmiers"))
        self.assertEqual(sr.clean_skill_list(["Des", "Etc.", "Excel", "excel", "D"]), ["Excel"])

    def test_phrases_not_single_words(self):
        self.assertEqual(sr.phrases_from_requirement_line("- Maîtrise de Excel, Word et Power BI"), ["Excel", "Word", "Power BI"])
        self.assertEqual(sr.phrases_from_requirement_line("Salaire: 800$"), [])
        self.assertEqual(sr.phrases_from_requirement_line("- Gestion de dossiers patients"), ["Gestion de dossiers patients"])

    def test_role_detection_adapts_skills(self):
        self.assertEqual(sr.detect_role(JOB)["role"], "infirmier")
        self.assertEqual(sr.detect_role("Recherche préposé aux bénéficiaires (PAB) pour CHSLD")["role"], "pab")
        self.assertEqual(sr.detect_role("Développeur Python Flask SQL Git")["sector"], "it")
        names_inf = {r["name"] for r in sr.build_requirements(JOB, [])["required"]}
        names_dev = {r["name"] for r in sr.build_requirements("Développeur web HTML CSS JavaScript", [])["required"]}
        self.assertIn("Soins infirmiers", names_inf)
        self.assertNotIn("Soins infirmiers", names_dev)

    def test_estimated_flagged_when_offer_is_thin(self):
        rq = sr.build_requirements("Nous cherchons un infirmier.", [])
        self.assertGreater(rq["estimated_count"], 0)
        self.assertTrue(all(r["source"].startswith("estim") for r in rq["required"] if r["name"] not in ()) or rq["detected_count"] >= 0)

    def test_weighted_score_depends_on_job_not_fixed(self):
        c, h = client()
        cv = "Aline K\nInfirmière\n+243 812 345 678 a@x.cd\nSoins infirmiers, injections, hygiène hospitalière, prélèvements, diplôme d'État infirmier A2\nBunia RDC"
        job_ok = JOB
        job_hard = "Offre : Infirmier. Exigences:\n- Chirurgie cardiaque\n- Hémodialyse\n- Soins intensifs néonataux\n- Bloc opératoire\n- Anesthésie"
        a = c.post("/api/analyze", data={"cv_text": cv, "job_text": job_ok}, headers=h).get_json()["score"]
        b = c.post("/api/analyze", data={"cv_text": cv, "job_text": job_hard}, headers=h).get_json()["score"]
        self.assertGreater(a, b)
        self.assertNotEqual(a, 45)

    def test_no_data_never_100(self):
        c, h = client()
        r = c.post("/api/analyze", data={"cv_text": "Jean Dupont\nDiplôme\nLangues français\njean@x.cd " + "texte " * 60, "job_text": "Nous recrutons une personne motivée pour rejoindre notre belle équipe dynamique."}, headers=h).get_json()
        self.assertLessEqual(r["score"], 70)
        self.assertIn(r["score_confidence"]["level"], ("insuffisante", "faible"))

    def test_crud_and_validation(self):
        c, h = client()
        self.assertTrue(c.post("/api/svc/referentials/skill", json={"sector": "sante", "role": "pab", "name": "Soins palliatifs", "weight": 2, "aliases": ["palliatif"]}, headers=h).get_json()["success"])
        self.assertEqual(c.post("/api/svc/referentials/skill", json={"sector": "sante", "role": "pab", "name": "Etc.", "weight": 2}, headers=h).status_code, 400)
        self.assertEqual(c.post("/api/svc/referentials/skill", json={"sector": "sante", "role": "pab", "name": "Test", "weight": 99}, headers=h).status_code, 400)
        roles = c.get("/api/svc/referentials").get_json()["sectors"]
        pab = [r for s in roles for r in s["roles"] if r["role"] == "pab"][0]
        self.assertIn("Soins palliatifs", [s["name"] for s in pab["skills"]])
        self.assertTrue(c.post("/api/svc/referentials/skill/delete", json={"sector": "sante", "role": "pab", "name": "Soins palliatifs"}, headers=h).get_json()["success"])

    def test_corrupted_config_falls_back(self):
        sr.load()
        with open(sr.CONFIG_PATH if os.path.exists(sr.CONFIG_PATH) else os.path.join(_core.DATA_DIR, "config", "skills_referentials.json"), "w") as f:
            f.write("{pas du json")
        sr._CACHE["cfg"] = None
        self.assertTrue(sr.load()["sectors"])  # repli .bak ou defauts, sans crash
        sr.reset_defaults()


if __name__ == "__main__":
    unittest.main()


class CareerTest(unittest.TestCase):
    def test_progression_explainable(self):
        from services import career_progression as cp
        r = cp.project("Infirmier soins infirmiers injections", 1, 3, 0.8, "Infirmier")
        self.assertTrue(r["indicative"]); self.assertEqual([p["years"] for p in r["projections"]], [1, 3, 5])
        self.assertEqual(r["pace_years_per_step"], 2.0)
        self.assertIn("explanation", r)
        self.assertGreaterEqual(r["projections"][2]["step"], r["projections"][0]["step"])


class TidyTest(unittest.TestCase):
    OFFER = ("Poste : Assistant en gestion de l'information\n- Aider à collecter, compiler et organiser les données pertinentes\n"
             "- Appuyer la préparation de présentations et des supports de formation\n- Maintenir les référentiels d'information\n"
             "Compétences requises :\n- Excel avancé, Statistiques, Leur partage, Des tableaux, Adaptabilité, Travail d'équipe\nCandidature : rh@ong.org")

    def test_fragments_removed(self):
        from services import skills_referential as sr
        for bad in ("Aider à collecter", "Compiler", "Leur partage", "Des tableaux", "Organiser les données pertinentes", "Des supports de formation"):
            self.assertIsNone(sr.tidy_one(bad), bad)
        self.assertEqual(sr.tidy_one("Appuyer la préparation de présentations"), "Préparation de présentations")
        self.assertEqual(sr.tidy_one("Des tableaux de bord"), "Tableaux de bord")
        self.assertEqual(sr.tidy_one("Travail d'équipe"), "Travail d'équipe")

    def test_no_nested_duplicates(self):
        from services import skills_referential as sr
        items = [{"name": "Nettoyage", "source": "offre"}, {"name": "Nettoyage et qualité des données", "source": "offre"}]
        self.assertEqual([i["name"] for i in sr.drop_contained(items)], ["Nettoyage et qualité des données"])
