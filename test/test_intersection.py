import geopandas as gpd
from shapely.geometry import LineString, MultiPoint
from generic_functions_headless import split_lines_at_intersections, remove_lines_from_no_block_gdf

def test_split_lines():
    """Test the split_lines_at_intersections function."""

    line1 = LineString([(0, 0), (2, 2)])
    line2 = LineString([(0, 2), (2, 0)])

    gdf = gpd.GeoDataFrame(geometry=[line1, line2], crs="EPSG:4326")

    splitted_gdf = split_lines_at_intersections(gdf)

    assert len(splitted_gdf) == 4

def test_remove_dead_ends():
    """Test the remove_lines_from_no_block_gdf function."""

    line1 = LineString([(0, 0), (1, 1)])
    line2 = LineString([(1, 1), (2, 2)])
    line3 = LineString([(1, 1), (1, 0)]) # Dead-end

    gdf = gpd.GeoDataFrame(geometry=[line1, line2, line3], crs="EPSG:4326")

    cleaned_gdf = remove_lines_from_no_block_gdf(gdf)

    assert len(cleaned_gdf) == 2
