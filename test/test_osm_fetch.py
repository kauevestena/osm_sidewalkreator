import json
import os
import sys
import unittest
from unittest.mock import patch

# Ensure the project root is on the Python path so osm_fetch can be imported
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

try:
    from osm_fetch import get_osm_data, join_to_a_outfolder

    GDAL_AVAILABLE = True
except ImportError as e:  # pragma: no cover - executed when GDAL isn't installed
    print(f"Failed to import osm_fetch or GDAL: {e}. Some tests may be skipped.")
    get_osm_data = None
    join_to_a_outfolder = None
    GDAL_AVAILABLE = False

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "curitiba_sample.osm")


@unittest.skipIf(not GDAL_AVAILABLE, "GDAL not available, skipping osm_fetch tests")
class TestOsmFetch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            cls.osm_xml = f.read()

    def _mock_overpass(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = self.osm_xml

    def test_get_osm_data_linestring(self):
        with patch("osm_fetch.requests.get") as mock_get:
            self._mock_overpass(mock_get)
            geojson_str = get_osm_data(
                querystring="",  # content provided by mocked request
                tempfilesname="test_linestring_output",
                geomtype="LineString",
                return_as_string=True,
            )

        geojson_output = json.loads(geojson_str)
        self.assertEqual(geojson_output.get("type"), "FeatureCollection")
        self.assertGreater(len(geojson_output.get("features", [])), 0)
        names = [f["properties"].get("name") for f in geojson_output["features"]]
        self.assertIn("Rua Hipólito da Costa", names)

    def test_get_osm_data_point(self):
        with patch("osm_fetch.requests.get") as mock_get:
            self._mock_overpass(mock_get)
            geojson_str = get_osm_data(
                querystring="",
                tempfilesname="test_point_output",
                geomtype="Point",
                return_as_string=True,
            )

        geojson_output = json.loads(geojson_str)
        self.assertEqual(geojson_output.get("type"), "FeatureCollection")
        self.assertGreater(len(geojson_output.get("features", [])), 0)
        props_list = [f["properties"] for f in geojson_output["features"]]
        self.assertTrue(
            any(p.get("highway") == "traffic_signals" for p in props_list),
            "Expected at least one traffic signal point",
        )


@unittest.skipIf(join_to_a_outfolder is None, "osm_fetch not available")
class TestJoinToAOutfolder(unittest.TestCase):
    def test_join_to_a_outfolder_creates_directory(self):
        original_basepath = os.getcwd()
        try:
            with patch("osm_fetch.basepath", original_basepath):
                foldername = "custom_temp"
                target_path = join_to_a_outfolder("dummy.txt", foldername=foldername)
                expected_dir = os.path.join(original_basepath, foldername)
                self.assertTrue(os.path.isdir(expected_dir))
                self.assertEqual(target_path, os.path.join(expected_dir, "dummy.txt"))
        finally:
            pass


if __name__ == "__main__":  # pragma: no cover - manual execution
    unittest.main()

