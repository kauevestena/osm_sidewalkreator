import json
import os
import sys

import pytest

pytest.importorskip("osgeo")

# Import the fetcher directly from the plugin root, without importing QGIS.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from osm_fetch import get_osm_data, osm_query_string_by_bbox


pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        os.environ.get("OSM_SIDEWALKREATOR_RUN_NETWORK_TESTS") != "1",
        reason="set OSM_SIDEWALKREATOR_RUN_NETWORK_TESTS=1 to run live Overpass tests",
    ),
]


def test_get_osm_data_for_issue_78_bbox_without_qgis():
    minx, miny, maxx, maxy = (
        -49.274644,
        -25.448677,
        -49.260173,
        -25.438781,
    )
    query = osm_query_string_by_bbox(miny, minx, maxy, maxx)

    result = get_osm_data(
        querystring=query,
        tempfilesname="issue_78_roads",
        geomtype="LineString",
        timeout=30,
        return_as_string=True,
    )

    assert result is not None
    geojson = json.loads(result)
    assert geojson["type"] == "FeatureCollection"
    assert geojson["features"]
    assert all(feature["geometry"] is not None for feature in geojson["features"])
