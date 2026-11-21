import io, json, os, tempfile, unittest
from services import world_data as wd


class Resp:
    def __init__(self, b): self.b = b
    def read(self, n=-1): return self.b


def fc(n):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"NAME": f"P{i}", "ISO_A3": f"X{i}"},
         "geometry": {"type": "Polygon", "coordinates": [[[0.123, 1.456], [1, 1], [0, 0]]]}} for i in range(n)]}


class WorldTest(unittest.TestCase):
    def test_ok_and_rounding(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "w.geojson")
            r = wd.fetch(p, opener=lambda u: Resp(json.dumps(fc(200)).encode()))
            self.assertTrue(r["ok"]); self.assertTrue(wd.status(p)["available"])
            self.assertEqual(json.load(open(p))["features"][0]["geometry"]["coordinates"][0][0], [0.12, 1.46])

    def test_invalid_and_offline_keep_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "w.geojson")
            self.assertFalse(wd.fetch(p, opener=lambda u: Resp(json.dumps(fc(5)).encode()))["ok"])
            def boom(u): raise OSError("offline")
            self.assertFalse(wd.fetch(p, opener=boom)["ok"])
            self.assertFalse(os.path.exists(p))


if __name__ == "__main__":
    unittest.main()
