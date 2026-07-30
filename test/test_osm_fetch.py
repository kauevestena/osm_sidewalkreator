import json
import os
import sys
import unittest
from unittest.mock import Mock, call, patch

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

    def _mock_overpass(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = self.osm_xml

    def test_get_osm_data_linestring(self):
        with patch("osm_fetch.requests.post") as mock_post:
            self._mock_overpass(mock_post)
            geojson_str = get_osm_data(
                querystring="test query",
                tempfilesname="test_linestring_output",
                geomtype="LineString",
                timeout=17,
                return_as_string=True,
            )

        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"], {"data": "test query"})
        self.assertEqual(kwargs["timeout"], 17)
        self.assertIn("OSM-Sidewalkreator", kwargs["headers"]["User-Agent"])
        geojson_output = json.loads(geojson_str)
        self.assertEqual(geojson_output.get("type"), "FeatureCollection")
        self.assertGreater(len(geojson_output.get("features", [])), 0)
        names = [f["properties"].get("name") for f in geojson_output["features"]]
        self.assertIn("Rua Hipólito da Costa", names)

    def test_get_osm_data_point(self):
        with patch("osm_fetch.requests.post") as mock_post:
            self._mock_overpass(mock_post)
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

    @patch("osm_fetch.time.sleep")
    @patch("osm_fetch.requests.post")
    def test_failed_server_advances_to_next_server(self, mock_post, mock_sleep):
        failed_response = Mock(status_code=503, text="server busy")
        successful_response = Mock(status_code=200, text=self.osm_xml)
        mock_post.side_effect = [failed_response, successful_response]

        result = get_osm_data(
            querystring="test query",
            tempfilesname="test_retry_output",
            return_as_string=True,
        )

        self.assertIsNotNone(result)
        self.assertEqual(mock_post.call_count, 2)
        first_url = mock_post.call_args_list[0].args[0]
        second_url = mock_post.call_args_list[1].args[0]
        self.assertNotEqual(first_url, second_url)
        mock_sleep.assert_called_once()

    @patch("osm_fetch.time.sleep")
    @patch("osm_fetch.requests.post")
    def test_all_servers_are_attempted_once_then_failure_is_returned(
        self, mock_post, mock_sleep
    ):
        from osm_fetch import OVERPASS_RETRY_DELAY_SECONDS, OVERPASS_URLS

        mock_post.return_value = Mock(status_code=503, text="server busy")

        result = get_osm_data(
            querystring="test query",
            tempfilesname="test_failure_output",
            return_as_string=True,
        )

        self.assertIsNone(result)
        self.assertEqual(
            [request.args[0] for request in mock_post.call_args_list],
            list(OVERPASS_URLS),
        )
        self.assertEqual(
            mock_sleep.call_args_list,
            [call(OVERPASS_RETRY_DELAY_SECONDS)] * (len(OVERPASS_URLS) - 1),
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
