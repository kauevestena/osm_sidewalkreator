import os
import pytest

pytest.importorskip("qgis")
from osm_sidewalkreator import _build_plugin_paths

pytestmark = pytest.mark.qgis


def test_build_plugin_paths_windows():
    profile_path = "C:/Users/User/AppData/Roaming/QGIS/QGIS3/profiles/default"
    basepath, temps_path, reports_path, assets_path = _build_plugin_paths(profile_path)
    expected_base = os.path.normpath(
        profile_path + "/python/plugins/osm_sidewalkreator"
    )
    assert basepath == expected_base
    assert temps_path == os.path.join(expected_base, "temporary")
    assert reports_path == os.path.join(expected_base, "reports")
    assert assets_path == os.path.join(expected_base, "assets")
