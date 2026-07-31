import shutil
import stat
import zipfile
from pathlib import Path

import pytest

from release.release_zip import PLUGIN_NAME, REQUIRED_FILES, build_release


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def copy_release_sources(destination: Path) -> Path:
    plugin_dir = destination / "source"
    for relative in REQUIRED_FILES:
        source = REPOSITORY_ROOT / relative
        target = plugin_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return plugin_dir


def archive_files(archive_path: Path) -> set[str]:
    with zipfile.ZipFile(archive_path) as archive:
        return {name for name in archive.namelist() if not name.endswith("/")}


def test_release_contains_exact_runtime_manifest(tmp_path):
    plugin_dir = copy_release_sources(tmp_path)
    archive_path, staging_root = build_release(plugin_dir, tmp_path / "custom-output")

    expected = {f"{PLUGIN_NAME}/{relative}" for relative in REQUIRED_FILES}
    assert archive_files(archive_path) == expected
    assert staging_root == tmp_path / "custom-output" / PLUGIN_NAME


def test_release_includes_only_compiled_translations(tmp_path):
    plugin_dir = copy_release_sources(tmp_path)
    translations = plugin_dir / "i18n"
    translations.mkdir()
    (translations / "sidewalkreator_pt_BR.qm").write_bytes(b"compiled")
    (translations / "sidewalkreator_pt_BR.ts").write_text("source")

    archive_path, _ = build_release(plugin_dir, tmp_path / "output")
    names = archive_files(archive_path)

    assert f"{PLUGIN_NAME}/i18n/sidewalkreator_pt_BR.qm" in names
    assert f"{PLUGIN_NAME}/i18n/sidewalkreator_pt_BR.ts" not in names


def test_release_omits_repository_only_and_executable_files(tmp_path):
    plugin_dir = copy_release_sources(tmp_path)
    unwanted = (
        "scripts/example.sh",
        "docker/run.bat",
        "test/test_example.py",
        "scratch/security_report.json",
        "release/release_zip.py",
        "assets/test_data/sample.json",
        "assets/test_outputs/result.geojson",
        "__pycache__/module.pyc",
    )
    for relative in unwanted:
        path = plugin_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("development only")

    archive_path, _ = build_release(plugin_dir, tmp_path / "output")
    names = archive_files(archive_path)

    assert all(f"{PLUGIN_NAME}/{relative}" not in names for relative in unwanted)
    assert not any(name.endswith((".sh", ".bat")) for name in names)


def test_release_normalizes_file_permissions(tmp_path):
    plugin_dir = copy_release_sources(tmp_path)
    for filename in ("generic_functions.py", "osm_sidewalkreator.py"):
        (plugin_dir / filename).chmod(0o755)

    archive_path, staging_root = build_release(plugin_dir, tmp_path / "output")

    with zipfile.ZipFile(archive_path) as archive:
        for filename in ("generic_functions.py", "osm_sidewalkreator.py"):
            info = archive.getinfo(f"{PLUGIN_NAME}/{filename}")
            assert stat.S_IMODE(info.external_attr >> 16) == 0o644
            assert stat.S_IMODE((staging_root / filename).stat().st_mode) == 0o644


def test_release_reports_all_missing_required_files(tmp_path):
    plugin_dir = copy_release_sources(tmp_path)
    (plugin_dir / "metadata.txt").unlink()
    (plugin_dir / "icon.png").unlink()

    with pytest.raises(FileNotFoundError) as error:
        build_release(plugin_dir, tmp_path / "output")

    assert "metadata.txt" in str(error.value)
    assert "icon.png" in str(error.value)


def test_release_replaces_stale_output(tmp_path):
    plugin_dir = copy_release_sources(tmp_path)
    output_dir = tmp_path / "output"
    stale_staged = output_dir / PLUGIN_NAME / "stale.sh"
    stale_staged.parent.mkdir(parents=True)
    stale_staged.write_text("stale")
    stale_archive = output_dir / f"{PLUGIN_NAME}.zip"
    stale_archive.write_bytes(b"stale")

    archive_path, staging_root = build_release(plugin_dir, output_dir)

    assert not (staging_root / "stale.sh").exists()
    assert f"{PLUGIN_NAME}/stale.sh" not in archive_files(archive_path)
