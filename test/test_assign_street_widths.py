import pytest

pytest.importorskip("qgis")

from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant

from .utilities import get_qgis_app
from generic_functions import assign_street_widths
from parameters import default_widths

pytestmark = pytest.mark.qgis


@pytest.fixture(scope="module", autouse=True)
def qgis_env():
    app, _, _, _ = get_qgis_app()
    assert app is not None
    return app


def _road_layer():
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", "roads", "memory")
    dp = layer.dataProvider()
    dp.addAttributes([QgsField("highway", QVariant.String)])
    layer.updateFields()

    feat = QgsFeature()
    feat.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]))
    feat.setAttribute("highway", "residential")
    dp.addFeature(feat)
    layer.updateExtents()
    return layer


def test_assign_street_widths_adds_default_width(qgis_env):
    source = _road_layer()
    out = assign_street_widths(source, "out")
    assert out is not None
    width_idx = out.fields().lookupField("width")
    assert width_idx != -1
    feat = next(out.getFeatures())
    assert feat["width"] == default_widths["residential"]
