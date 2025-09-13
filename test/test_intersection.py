import unittest
import geopandas as gpd
from shapely.geometry import LineString, MultiPoint
from generic_functions_headless import split_lines_at_intersections

class IntersectionTest(unittest.TestCase):
    """Test the intersection logic."""

    def test_split_lines(self):
        """Test the split_lines_at_intersections function."""

        line1 = LineString([(0, 0), (2, 2)])
        line2 = LineString([(0, 2), (2, 0)])

        gdf = gpd.GeoDataFrame(geometry=[line1, line2], crs="EPSG:4326")

        splitted_gdf = split_lines_at_intersections(gdf)

        self.assertEqual(len(splitted_gdf), 4)

if __name__ == "__main__":
    unittest.main()
