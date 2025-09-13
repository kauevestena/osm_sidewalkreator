import os
import shutil
import geopandas as gpd
import pytest
from headless_prototype import run_headless

@pytest.fixture
def setup_test_dir():
    """Create a temporary directory for test output."""
    test_dir = os.path.join(os.path.dirname(__file__), 'temp_test_output')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    yield test_dir
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

def test_run_headless(setup_test_dir):
    """Test the main run_headless function."""
    test_dir = setup_test_dir
    input_polygon = os.path.join(os.path.dirname(__file__), 'extra_tests', 'polygon01.geojson')

    run_headless(input_polygon, test_dir)

    # Check if output files were created and have content
    protoblocks_file = os.path.join(test_dir, 'protoblocks_output.geojson')
    assert os.path.exists(protoblocks_file)
    protoblocks_gdf = gpd.read_file(protoblocks_file)
    assert not protoblocks_gdf.empty
    assert protoblocks_gdf.crs.to_string() == "EPSG:4326"
    assert len(protoblocks_gdf) > 0

    sidewalks_file = os.path.join(test_dir, 'sidewalks_output.geojson')
    assert os.path.exists(sidewalks_file)
    sidewalks_gdf = gpd.read_file(sidewalks_file)
    assert not sidewalks_gdf.empty
    assert sidewalks_gdf.crs.to_string() == "EPSG:4326"
    assert len(sidewalks_gdf) > 0

    crossings_file = os.path.join(test_dir, 'crossings_output.geojson')
    assert os.path.exists(crossings_file)
    crossings_gdf = gpd.read_file(crossings_file)
    assert not crossings_gdf.empty
    assert crossings_gdf.crs.to_string() == "EPSG:4326"
    assert len(crossings_gdf) > 0
