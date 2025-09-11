import json
import tempfile
import pytest

pytest.importorskip("qgis")
from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessingException,
    QgsProject,
    QgsCoordinateReferenceSystem,
)
from qgis import processing
from qgis.core import QgsNotSupportedException

from .utilities import get_qgis_app
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
from osm_sidewalkreator.processing.protoblock_algorithm import ProtoblockAlgorithm
from osm_sidewalkreator.processing.protoblock_bbox_algorithm import ProtoblockBboxAlgorithm
from osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm import (
    FullSidewalkreatorPolygonAlgorithm,
)
from osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm import (
    FullSidewalkreatorBboxAlgorithm,
)

pytestmark = pytest.mark.qgis

"""
Processing initialization is handled by test/conftest.py and the qgis_env
fixture below. Avoid module-level checks which can race Processing bootstrap
in headless CI and cause false-negative skips or partial init states.
"""


@pytest.fixture(scope="module", autouse=True)
def qgis_env():
    """Initialise QGIS and register provider once for tests."""
    app, _, _, _ = get_qgis_app()
    assert app is not None
    # Ensure QGIS Processing framework is initialized in headless tests
    try:
        from processing.core.Processing import Processing
        Processing.initialize()
    except Exception:
        pass
    try:
        from qgis.analysis import QgsNativeAlgorithms
        QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    except Exception:
        pass
    provider = ProtoblockProvider()
    QgsApplication.processingRegistry().addProvider(provider)
    return app


# ---------------------- Protoblock Algorithm Tests ----------------------

def _square_roads_geojson():
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"highway": "residential"},
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                },
                {
                    "type": "Feature",
                    "properties": {"highway": "residential"},
                    "geometry": {"type": "LineString", "coordinates": [[1, 0], [1, 1]]},
                },
                {
                    "type": "Feature",
                    "properties": {"highway": "residential"},
                    "geometry": {"type": "LineString", "coordinates": [[1, 1], [0, 1]]},
                },
                {
                    "type": "Feature",
                    "properties": {"highway": "residential"},
                    "geometry": {"type": "LineString", "coordinates": [[0, 1], [0, 0]]},
                },
            ],
        }
    )


def _simple_polygon_layer():
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "poly", "memory")
    dp = layer.dataProvider()
    feat = QgsFeature()
    feat.setGeometry(
        QgsGeometry.fromPolygonXY(
            [[
                QgsPointXY(-1, -1),
                QgsPointXY(2, -1),
                QgsPointXY(2, 2),
                QgsPointXY(-1, 2),
                QgsPointXY(-1, -1),
            ]]
        )
    )
    dp.addFeatures([feat])
    layer.updateExtents()
    return layer


def test_generateprotoblocks_success(monkeypatch):
    geojson = _square_roads_geojson()
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.protoblock_algorithm.osm_query_string_by_bbox",
        lambda *a, **k: "dummy",
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.protoblock_algorithm.get_osm_data",
        lambda *a, **k: geojson,
    )
    params = {
        "INPUT_POLYGON": _simple_polygon_layer(),
        "TIMEOUT": 30,
        "OUTPUT_PROTOBLOCKS": "memory:protoblocks",
    }
    # Run using an instance to avoid registry createInstance flakiness in CI
    result = processing.run(ProtoblockAlgorithm(), params)
    out_layer = result["OUTPUT_PROTOBLOCKS"]
    assert out_layer.isValid()
    assert out_layer.crs().authid() == "EPSG:4326"
    assert out_layer.featureCount() == 1
    assert out_layer.fields().count() == 0


def test_generateprotoblocks_failure():
    params = {
        "INPUT_POLYGON": QgsVectorLayer("Polygon?crs=EPSG:4326", "empty", "memory"),
        "TIMEOUT": 30,
        "OUTPUT_PROTOBLOCKS": "memory:out",
    }
    with pytest.raises(QgsProcessingException):
        processing.run(ProtoblockAlgorithm(), params)


# ---------------------- Full Sidewalkreator BBOX Algorithm Tests ----------------------

def _patch_full_bbox_alg(monkeypatch, raise_in_generation=False):
    geojson = _square_roads_geojson()

    def fake_get_osm_data(**kwargs):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".geojson")
        tmp.write(geojson.encode("utf-8"))
        tmp.flush()
        tmp.close()
        return tmp.name

    def fake_reproject(layer, outputpath=None, layername=None, lgt_0=None, lat_0=0):
        from qgis.core import QgsCoordinateReferenceSystem

        return layer, QgsCoordinateReferenceSystem("EPSG:4326")

    def fake_clip(inputlayer, overlay_lyr, outputlayer=None):
        return inputlayer

    def fake_polygonize(inputlines, outputlayer="TEMPORARY_OUTPUT", keepfields=True):
        poly = QgsVectorLayer("Polygon?crs=EPSG:4326", "protob", "memory")
        dp = poly.dataProvider()
        f = QgsFeature()
        f.setGeometry(
            QgsGeometry.fromPolygonXY(
                [[
                    QgsPointXY(0, 0),
                    QgsPointXY(1, 0),
                    QgsPointXY(1, 1),
                    QgsPointXY(0, 1),
                    QgsPointXY(0, 0),
                ]]
            )
        )
        dp.addFeatures([f])
        poly.updateExtents()
        return poly

    def fake_clean(osm_layer, poly_layer, crs, name, feedback, context):
        return osm_layer

    def fake_generate(*args, **kwargs):
        if raise_in_generation:
            raise QgsProcessingException("forced failure")
        sidewalks = QgsVectorLayer("LineString?crs=EPSG:4326", "sidewalks", "memory")
        dp = sidewalks.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(
            QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)])
        )
        dp.addFeature(feat)
        sidewalks.updateExtents()
        return {
            "sidewalk_lines": sidewalks,
            "exclusion_zones": QgsVectorLayer(
                "Polygon?crs=EPSG:4326", "excl", "memory"
            ),
            "sure_zones": QgsVectorLayer(
                "Polygon?crs=EPSG:4326", "sure", "memory"
            ),
            "width_adjusted_streets": args[0],
        }

    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.get_osm_data",
        fake_get_osm_data,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.osm_fetch.get_osm_data",
        fake_get_osm_data,
        raising=True,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.osm_query_string_by_bbox",
        lambda **k: "dummy",
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.reproject_layer_localTM",
        fake_reproject,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.cliplayer_v2",
        fake_clip,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.polygonize_lines",
        fake_polygonize,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.clean_street_network_data",
        fake_clean,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.generate_sidewalk_geometries_and_zones",
        fake_generate,
    )


def _patch_full_polygon_alg(monkeypatch, call_recorder, raise_in_generation=False):
    def fake_get_osm_data(**kwargs):
        call_recorder.append(kwargs.get("geomtype"))
        if kwargs.get("geomtype") == "LineString":
            return _square_roads_geojson()
        return json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"addr:housenumber": "1"},
                        "geometry": {"type": "Point", "coordinates": [0, 0]},
                    }
                ],
            }
        )

    def fake_reproject(layer, outputpath=None, layername=None, lgt_0=None, lat_0=0):
        from qgis.core import QgsCoordinateReferenceSystem

        return layer, QgsCoordinateReferenceSystem("EPSG:4326")

    def fake_clip(inputlayer, overlay_lyr, outputlayer=None):
        return inputlayer

    def fake_polygonize(inputlines, outputlayer="TEMPORARY_OUTPUT", keepfields=True):
        poly = QgsVectorLayer("Polygon?crs=EPSG:4326", "protob", "memory")
        dp = poly.dataProvider()
        f = QgsFeature()
        f.setGeometry(
            QgsGeometry.fromPolygonXY(
                [
                    [
                        QgsPointXY(0, 0),
                        QgsPointXY(1, 0),
                        QgsPointXY(1, 1),
                        QgsPointXY(0, 1),
                        QgsPointXY(0, 0),
                    ]
                ]
            )
        )
        dp.addFeature(f)
        poly.updateExtents()
        return poly

    def fake_generate(
        street_network_layer,
        dissolved_protoblocks_layer,
        buildings_layer,
        check_building_overlap,
        min_dist_to_building,
        min_generated_width_near_building,
        added_width_for_sidewalk_axis_total,
        curve_radius,
        feedback,
    ):
        if raise_in_generation:
            raise QgsProcessingException("forced failure")
        sidewalks = QgsVectorLayer("LineString?crs=EPSG:4326", "sidewalks", "memory")
        dp = sidewalks.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(
            QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)])
        )
        dp.addFeature(feat)
        sidewalks.updateExtents()
        return (
            sidewalks,
            QgsVectorLayer("Polygon?crs=EPSG:4326", "excl", "memory"),
            QgsVectorLayer("Polygon?crs=EPSG:4326", "sure", "memory"),
            street_network_layer,
        )

    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.get_osm_data",
        fake_get_osm_data,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.osm_fetch.get_osm_data",
        fake_get_osm_data,
        raising=True,
    )
    def _oqsb(**k):
        interest = k.get("interest_key")
        if interest == "addr:housenumber":
            call_recorder.append("ADDR")
        return "dummy"
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.osm_query_string_by_bbox",
        _oqsb,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.reproject_layer_localTM",
        fake_reproject,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.cliplayer_v2",
        fake_clip,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.remove_unconnected_lines_v2",
        lambda l: None,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.polygonize_lines",
        fake_polygonize,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.dissolve_tosinglegeom",
        lambda layer: layer,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.generate_sidewalk_geometries_and_zones",
        fake_generate,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.processing.run",
        lambda *a, **k: {"OUTPUT": k.get("INPUT")},
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm.QgsProcessingUtils.mapLayerFromString",
        lambda s, c: s,
    )


def test_full_bbox_success(monkeypatch):
    _patch_full_bbox_alg(monkeypatch)
    params = {
        "INPUT_EXTENT": "0,0,1,1 [EPSG:4326]",
        "TIMEOUT": 30,
        "GET_BUILDING_DATA": False,
        "DEFAULT_WIDTH": 2.0,
        "MIN_WIDTH": 1.0,
        "MAX_WIDTH": 5.0,
        "STREET_CLASSES": [10],
        "OUTPUT_SIDEWALKS": "memory:sidewalks",
    }
    result = processing.run(FullSidewalkreatorBboxAlgorithm(), params)
    layer = result["OUTPUT_SIDEWALKS"]
    assert layer.isValid()
    assert layer.crs().authid() == "EPSG:4326"
    assert layer.featureCount() == 1


def test_full_bbox_failure(monkeypatch):
    _patch_full_bbox_alg(monkeypatch, raise_in_generation=True)
    params = {
        "INPUT_EXTENT": "0,0,1,1 [EPSG:4326]",
        "TIMEOUT": 30,
        "GET_BUILDING_DATA": False,
        "DEFAULT_WIDTH": 2.0,
        "MIN_WIDTH": 1.0,
        "MAX_WIDTH": 5.0,
        "STREET_CLASSES": [10],
        "OUTPUT_SIDEWALKS": "memory:sidewalks",
    }
    with pytest.raises(QgsProcessingException):
        processing.run(
            "sidewalkreator_algorithms_provider:osm_sidewalkreator_full_bbox",
            params,
        )


def test_full_bbox_invalid_extent(monkeypatch):
    _patch_full_bbox_alg(monkeypatch)
    project = QgsProject.instance()
    old_crs = project.crs()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
    params = {
        "INPUT_EXTENT": "20037508,0,20037509,1 [EPSG:3857]",
        "TIMEOUT": 30,
        "GET_BUILDING_DATA": False,
        "DEFAULT_WIDTH": 2.0,
        "MIN_WIDTH": 1.0,
        "MAX_WIDTH": 5.0,
        "STREET_CLASSES": [10],
        "OUTPUT_SIDEWALKS": "memory:sidewalks",
    }
    with pytest.raises(QgsProcessingException):
        processing.run(
            "sidewalkreator_algorithms_provider:osm_sidewalkreator_full_bbox",
            params,
        )
    project.setCrs(old_crs)


# ---------------------- Full Sidewalkreator Polygon Algorithm Tests ----------------------


def test_full_polygon_fetches_addresses(monkeypatch):
    calls = []
    _patch_full_polygon_alg(monkeypatch, calls)
    params = {
        "INPUT_POLYGON": _simple_polygon_layer(),
        "TIMEOUT": 30,
        "FETCH_BUILDINGS_DATA": False,
        "FETCH_ADDRESS_DATA": True,
        "DEAD_END_ITERATIONS": 0,
        "OUTPUT_SIDEWALKS": "memory:sw",
        "OUTPUT_CROSSINGS": "memory:cr",
        "OUTPUT_KERBS": "memory:kb",
    }
    processing.run(FullSidewalkreatorPolygonAlgorithm(), params)
    assert ("Point" in calls) or ("ADDR" in calls)


def test_full_polygon_skips_addresses(monkeypatch):
    calls = []
    _patch_full_polygon_alg(monkeypatch, calls)
    params = {
        "INPUT_POLYGON": _simple_polygon_layer(),
        "TIMEOUT": 30,
        "FETCH_BUILDINGS_DATA": False,
        "FETCH_ADDRESS_DATA": False,
        "DEAD_END_ITERATIONS": 0,
        "OUTPUT_SIDEWALKS": "memory:sw",
        "OUTPUT_CROSSINGS": "memory:cr",
        "OUTPUT_KERBS": "memory:kb",
    }
    processing.run(
        "sidewalkreator_algorithms_provider:fullsidewalkreatorfrompolygon", params
    )
    assert ("Point" not in calls) and ("ADDR" not in calls)
