import json, os, unittest
import _helpers  # noqa: F401  (chemin du projet)
from services import _core, data_manager as dm, candidate_history_manager as hist


class T(unittest.TestCase):
    def test_roundtrip_and_corruption_recovery(self):
        _core.write_json("t_rt", {"a": 1})
        _core.write_json("t_rt", {"a": 2})  # cree .bak = {"a":1}
        p = _core.store_path("t_rt")
        with open(p, "w") as f:
            f.write("{corrompu")
        self.assertEqual(_core.read_json("t_rt"), {"a": 1})  # restaure depuis .bak

    def test_tamper_detected(self):
        _core.write_json("t_tp", {"x": 1})
        p = _core.store_path("t_tp")
        env = json.load(open(p)); env["data"]["x"] = 999
        json.dump(env, open(p, "w"))
        self.assertIsNone(_core.read_json("t_tp"))

    def test_backup_restore(self):
        _core.write_json("t_bk", {"k": "v"})
        n = dm.backup()
        _core.write_json("t_bk", {"k": "autre"})
        dm.restore(n)
        self.assertEqual(_core.read_json("t_bk"), {"k": "v"})
        with self.assertRaises(ValueError):
            dm.restore("../etc/passwd")

    def test_history(self):
        rep = {"success": True, "score": 40, "cv_details": {"full_name": "Zed Test", "exp_years": 2, "structured_experiences": []},
               "job_details": {"company_name": "X"}, "matched_skills": ["python"], "missing_skills": ["sql"]}
        hist.record(rep)
        rep["score"] = 70; rep["matched_skills"] = ["python", "sql"]
        hist.record(rep, "edition")
        e = hist.evolution("zed test")
        self.assertEqual(e["trend"], 30)
        self.assertEqual(hist.compare_versions("zed test", 0, 1)["skills_added"], ["sql"])
        hist.delete("zed test")


if __name__ == "__main__":
    unittest.main()
