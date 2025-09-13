import geopandas as gpd
from shapely.geometry import LineString
from generic_functions_headless import remove_lines_from_no_block_gdf

def test_remove_dead_ends():
    """Test the remove_lines_from_no_block_gdf function."""

    # Create a small street network with a dead-end street
    line1 = LineString([(0, 0), (1, 1)])
    line2 = LineString([(1, 1), (2, 2)])
    line3 = LineString([(1, 1), (1, 0)]) # Dead-end
    line4 = LineString([(2, 2), (3, 3)])
    line5 = LineString([(2, 2), (2, 3)])

    gdf = gpd.GeoDataFrame(geometry=[line1, line2, line3, line4, line5], crs="EPSG:4326")

    cleaned_gdf = remove_lines_from_no_block_gdf(gdf)

    assert len(cleaned_gdf) == 4
