import unittest
from _helpers import client
from services import hr_alerts as h


class T(unittest.TestCase):
    def test_rules(self):
        rep = {"positions_count": 2, "candidates": [
            {"name": "A", "emails": ["a@x.org"], "score": 50, "structured_experiences": [1]},
            {"name": "A bis", "emails": ["a@x.org"], "score": 49, "structured_experiences": [1], "readability": "unreadable"},
            {"name": "B", "score": 20, "score_confidence": {"level": "faible"}}]}
        kinds = {a["kind"] for a in h.build(rep)["alerts"]}
        self.assertTrue({"duplicate", "incomplete_document", "backup_needed", "low_confidence", "close_scores"} <= kinds)

    def test_none_good_and_route(self):
        r = h.build({"candidates": [{"name": "Z", "score": 10}]})
        self.assertIn("offer_without_match", {a["kind"] for a in r["alerts"]})
        c, hd = client()
        self.assertTrue(c.post("/api/svc/hr/alerts", json={"report": {"candidates": []}}, headers=hd).get_json()["success"])


if __name__ == "__main__":
    unittest.main()
