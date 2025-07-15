import unittest
import json
import sys
import os

# Add the parent directory (project root) to the Python path
# to allow importing osm_fetch from the root of the repository
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

try:
    from osm_fetch import get_osm_data

    GDAL_AVAILABLE = True
except ImportError as e:
    print(f"Failed to import osm_fetch or GDAL: {e}. Some tests may be skipped.")
    # This can happen if GDAL is not installed or not found in the PYTHONPATH
    # In a CI environment, GDAL should be installed.
    # For local testing, ensure GDAL Python bindings are available.
    get_osm_data = None  # Make it None to skip tests if import fails
    GDAL_AVAILABLE = False


# Sample OSM XML data
# Contains one way that should become a LineString, and one node that should become a Point
# The way has tags that might go into 'other_tags' depending on GDAL driver config,
# but usually for direct XML->GeoJSON, they are flattened.
SAMPLE_OSM_XML_COMPLEX = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test_suite">
  <node id="-1" lat="50.0" lon="10.0" />
  <node id="-2" lat="50.1" lon="10.1" />
  <node id="-3" lat="50.2" lon="10.2" />
  <way id="-10">
    <nd ref="-1" />
    <nd ref="-2" />
    <nd ref="-3" />
    <tag k="highway" v="residential" />
    <tag k="name" v="Test Street" />
    <tag k="oneway" v="yes" />
    <tag k="custom:tag" v="custom_value" />
    <tag k="another:tag:with:colons" v="value:with:colon" />
  </way>
  <node id="-4" lat="52.0" lon="12.0">
    <tag k="amenity" v="cafe" />
    <tag k="name" v="Test Cafe" />
    <tag k="cuisine" v="coffee_shop" />
  </node>
  <node id="-5" lat="52.1" lon="12.1">
    <tag k="shop" v="bakery" />
  </node>
</osm>
"""

# Simpler LineString only XML
SAMPLE_OSM_XML_LINESTRING_ONLY = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test_suite">
  <node id="-1" lat="50.0" lon="10.0" />
  <node id="-2" lat="50.1" lon="10.1" />
  <way id="-10">
    <nd ref="-1" />
    <nd ref="-2" />
    <tag k="highway" v="residential" />
    <tag k="name" v="Test Street" />
  </way>
</osm>
"""

SAMPLE_OSM_XML_POINT_ONLY = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="test_suite">
  <node id="-4" lat="52.0" lon="12.0">
    <tag k="amenity" v="cafe" />
    <tag k="name" v="Test Cafe" />
  </node>
</osm>
"""


@unittest.skipIf(not GDAL_AVAILABLE, "GDAL not available, skipping osm_fetch tests")
class TestOsmFetch(unittest.TestCase):

    def test_get_osm_data_linestring(self):
        """Test fetching LineString data using GDAL."""
        geojson_str = get_osm_data(
            querystring=SAMPLE_OSM_XML_LINESTRING_ONLY,
            tempfilesname="test_linestring_output",
            geomtype="LineString",
            return_as_string=True,
            timeout=30,
        )

        self.assertIsInstance(geojson_str, str, "Should return a string.")

        try:
            geojson_output = json.loads(geojson_str)
        except json.JSONDecodeError as e:
            self.fail(
                f"Returned string is not valid JSON: {e}\nString was: {geojson_str}"
            )

        self.assertEqual(geojson_output.get("type"), "FeatureCollection")

        features = geojson_output.get("features", [])
        self.assertEqual(len(features), 1, "Expected 1 LineString feature.")

        if not features:
            return  # Avoid index error if no features

        feature = features[0]
        self.assertEqual(feature.get("type"), "Feature")

        geometry = feature.get("geometry", {})
        self.assertEqual(geometry.get("type"), "LineString")
        self.assertTrue(
            len(geometry.get("coordinates", [])) > 0,
            "LineString should have coordinates.",
        )

        properties = feature.get("properties", {})
        self.assertEqual(properties.get("highway"), "residential")
        self.assertEqual(properties.get("name"), "Test Street")
        # Check if 'other_tags' field itself is present or if tags are flattened
        self.assertNotIn(
            "other_tags",
            properties,
            "'other_tags' field should not be present if tags are flattened.",
        )

    def test_get_osm_data_point(self):
        """Test fetching Point data using GDAL."""
        geojson_str = get_osm_data(
            querystring=SAMPLE_OSM_XML_POINT_ONLY,
            tempfilesname="test_point_output",
            geomtype="Point",
            return_as_string=True,
            timeout=30,
        )

        self.assertIsInstance(geojson_str, str)

        try:
            geojson_output = json.loads(geojson_str)
        except json.JSONDecodeError as e:
            self.fail(
                f"Returned string is not valid JSON: {e}\nString was: {geojson_str}"
            )

        self.assertEqual(geojson_output.get("type"), "FeatureCollection")

        features = geojson_output.get("features", [])
        self.assertEqual(len(features), 1, "Expected 1 Point feature.")

        if not features:
            return

        feature = features[0]
        self.assertEqual(feature.get("type"), "Feature")

        geometry = feature.get("geometry", {})
        self.assertEqual(geometry.get("type"), "Point")
        self.assertEqual(
            len(geometry.get("coordinates", [])), 2, "Point should have 2 coordinates."
        )

        properties = feature.get("properties", {})
        self.assertEqual(properties.get("amenity"), "cafe")
        self.assertEqual(properties.get("name"), "Test Cafe")
        self.assertNotIn("other_tags", properties)

    def test_get_osm_data_complex_tags_and_types(self):
        """Test with mixed types and potentially complex tags using SAMPLE_OSM_XML_COMPLEX."""

        # Test for LineString part of the complex XML
        geojson_str_lines = get_osm_data(
            querystring=SAMPLE_OSM_XML_COMPLEX,
            tempfilesname="test_complex_lines",
            geomtype="LineString",
            return_as_string=True,
        )
        self.assertIsInstance(geojson_str_lines, str)
        geojson_lines = json.loads(geojson_str_lines)
        self.assertEqual(geojson_lines.get("type"), "FeatureCollection")
        line_features = geojson_lines.get("features", [])
        self.assertEqual(
            len(line_features), 1
        )  # Only one way in SAMPLE_OSM_XML_COMPLEX

        line_feature = line_features[0]
        self.assertEqual(line_feature["geometry"]["type"], "LineString")
        line_props = line_feature["properties"]
        self.assertEqual(line_props.get("highway"), "residential")
        self.assertEqual(line_props.get("name"), "Test Street")
        self.assertEqual(line_props.get("oneway"), "yes")
        # Check how GDAL handles tags with colons / custom tags.
        # The current osm_fetch.py includes logic to parse 'other_tags' if GDAL produces it.
        # However, GDAL's default OSM driver behavior often flattens all tags directly.
        self.assertEqual(
            line_props.get("custom:tag"),
            "custom_value",
            "Custom tag not found or not matching.",
        )
        self.assertEqual(
            line_props.get("another:tag:with:colons"),
            "value:with:colon",
            "Tag with colons not found or not matching.",
        )
        self.assertNotIn(
            "other_tags",
            line_props,
            "Tags should be flattened, 'other_tags' field should not be present unless it's an actual OSM tag named 'other_tags'.",
        )

        # Test for Point part of the complex XML
        geojson_str_points = get_osm_data(
            querystring=SAMPLE_OSM_XML_COMPLEX,  # Using the same complex XML
            tempfilesname="test_complex_points",
            geomtype="Point",
            return_as_string=True,
        )
        self.assertIsInstance(geojson_str_points, str)
        geojson_points = json.loads(geojson_str_points)
        self.assertEqual(geojson_points.get("type"), "FeatureCollection")
        point_features = geojson_points.get("features", [])
        # There are 5 nodes in SAMPLE_OSM_XML_COMPLEX.
        # 3 are part of a way, 2 are independent POIs.
        # GDAL's "points" layer usually extracts nodes that are POIs (have tags) or are unreferenced.
        # Nodes that are only part of ways might not appear in the "points" layer unless they also have defining tags.
        # In our sample, node -4 and -5 have tags. Nodes -1, -2, -3 do not, and are part of a way.
        # So, we expect 2 point features.
        self.assertEqual(
            len(point_features),
            2,
            f"Expected 2 point features, got {len(point_features)}",
        )

        # Check properties of the first point (Test Cafe)
        # Ordering might not be guaranteed, so find it by name or a distinctive tag.
        cafe_feature = None
        for pf in point_features:
            if pf["properties"].get("name") == "Test Cafe":
                cafe_feature = pf
                break

        self.assertIsNotNone(cafe_feature, "Test Cafe point feature not found.")
        if cafe_feature:
            self.assertEqual(cafe_feature["geometry"]["type"], "Point")
            cafe_props = cafe_feature["properties"]
            self.assertEqual(cafe_props.get("amenity"), "cafe")
            self.assertEqual(cafe_props.get("cuisine"), "coffee_shop")
            self.assertNotIn("other_tags", cafe_props)

    def test_get_osm_data_empty_input(self):
        """Test with empty OSM XML input."""
        empty_osm_xml = (
            """<?xml version='1.0' encoding='UTF-8'?><osm version="0.6"></osm>"""
        )
        geojson_str = get_osm_data(
            querystring=empty_osm_xml,
            tempfilesname="test_empty_output",
            geomtype="LineString",  # geomtype doesn't matter much if input is empty
            return_as_string=True,
        )
        self.assertIsInstance(geojson_str, str)
        geojson_output = json.loads(geojson_str)
        self.assertEqual(geojson_output.get("type"), "FeatureCollection")
        self.assertEqual(len(geojson_output.get("features", [])), 0)

    def test_get_osm_data_unsupported_geomtype(self):
        """Test with an unsupported geometry type."""
        # Assuming 'UnsupportedType' is not one of 'Point', 'LineString', 'Polygon', 'MultiPolygon'
        result = get_osm_data(
            querystring=SAMPLE_OSM_XML_LINESTRING_ONLY,
            tempfilesname="test_unsupported_geom",
            geomtype="UnsupportedType",
            return_as_string=True,
        )
        # The function currently prints an error and returns None for unsupported types.
        self.assertIsNone(
            result, "Function should return None for unsupported geomtype."
        )


if __name__ == "__main__":
    unittest.main()
