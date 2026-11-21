import unittest
from services import ranking


def c(name, score, m, x, exp=0, trust=90, read="clean"):
    return {"name": name, "score": score, "matched_skills": ["a"] * m, "missing_skills": ["b"] * x, "exp_years": exp,
            "doc_trust": {"score": trust}, "readability": read, "emails": ["e@x.org"], "structured_experiences": [1]}


class RankTest(unittest.TestCase):
    def test_tiebreak_order_and_reason(self):
        L = [c("Zed", 81, 4, 2, 5), c("Ann", 81, 5, 1, 2), c("Bob", 70, 6, 0, 9), c("Cleo", 81, 4, 2, 7)]
        ranking.rank(L)
        self.assertEqual([x["name"] for x in L], ["Ann", "Cleo", "Zed", "Bob"])
        self.assertEqual([x["rank"] for x in L], [1, 2, 3, 4])
        self.assertIn("couverture", L[0]["rank_reason"]); self.assertTrue(L[0]["tie"])
        self.assertIn("expérience", L[1]["rank_reason"])
        self.assertFalse(L[2]["tie"])

    def test_identical_profiles_alphabetical(self):
        L = [c("Zoe", 60, 3, 3), c("Abel", 60, 3, 3)]
        ranking.rank(L)
        self.assertEqual(L[0]["name"], "Abel"); self.assertIn("identique", L[0]["rank_reason"])


if __name__ == "__main__":
    unittest.main()
