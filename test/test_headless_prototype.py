# coding=utf-8
import unittest
import os
import shutil
import sys
import geopandas as gpd
from headless_prototype import run_headless

class HeadlessPrototypeTest(unittest.TestCase):
    """Test the headless prototype."""

    def setUp(self):
        """Runs before each test."""
        self.test_dir = os.path.join(os.path.dirname(__file__), 'temp_test_output')
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

        self.input_polygon = os.path.join(os.path.dirname(__file__), 'extra_tests', 'polygon01.geojson')

    def tearDown(self):
        """Runs after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_run_headless(self):
        """Test the main run_headless function."""

        run_headless(self.input_polygon, self.test_dir)

        # Check if output files were created and have content
        protoblocks_file = os.path.join(self.test_dir, 'protoblocks_output.geojson')
        self.assertTrue(os.path.exists(protoblocks_file))
        protoblocks_gdf = gpd.read_file(protoblocks_file)
        self.assertFalse(protoblocks_gdf.empty)
        self.assertEqual(protoblocks_gdf.crs, "EPSG:4326")
        self.assertGreater(len(protoblocks_gdf), 0)

        sidewalks_file = os.path.join(self.test_dir, 'sidewalks_output.geojson')
        self.assertTrue(os.path.exists(sidewalks_file))
        sidewalks_gdf = gpd.read_file(sidewalks_file)
        self.assertFalse(sidewalks_gdf.empty)
        self.assertEqual(sidewalks_gdf.crs.to_string(), "EPSG:4326")
        self.assertGreater(len(sidewalks_gdf), 0)

        crossings_file = os.path.join(self.test_dir, 'existing_crossings.geojson')
        self.assertTrue(os.path.exists(crossings_file))
        crossings_gdf = gpd.read_file(crossings_file)
        self.assertFalse(crossings_gdf.empty)
        self.assertEqual(crossings_gdf.crs.to_string(), "EPSG:4326")
        self.assertGreater(len(crossings_gdf), 0)

        # You can add more assertions here, e.g., check the content of the output file

if __name__ == "__main__":
    unittest.main()
