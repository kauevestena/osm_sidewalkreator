"""Build a minimal, runtime-only QGIS plugin release archive."""

import argparse
import shutil
import stat
import zipfile
from pathlib import Path
from typing import Iterable


PLUGIN_NAME = "osm_sidewalkreator"

# Keep this list explicit: adding a repository file must not silently add it to a
# published plugin. All entries here are required for the plugin to run.
REQUIRED_FILES = (
    "__init__.py",
    "generic_functions.py",
    "icon.png",
    "LICENSE",
    "metadata.txt",
    "osm_fetch.py",
    "osm_sidewalkreator.py",
    "osm_sidewalkreator_dialog.py",
    "osm_sidewalkreator_dialog_base.ui",
    "parameters.py",
    "resources.py",
    "resources.qrc",
    "symbology-style.db",
    "processing/__init__.py",
    "processing/full_sidewalkreator_bbox_algorithm.py",
    "processing/full_sidewalkreator_polygon_algorithm.py",
    "processing/protoblock_algorithm.py",
    "processing/protoblock_bbox_algorithm.py",
    "processing/protoblock_provider.py",
    "processing/sidewalk_generation_logic.py",
    "assets/addrs_centroids.qml",
    "assets/addrs_centroids2.qml",
    "assets/buildings.qml",
    "assets/crossings.qml",
    "assets/exclusion_zones.qml",
    "assets/kerbs.qml",
    "assets/polygonstyles.qml",
    "assets/road_intersections.qml",
    "assets/roads_p1.qml",
    "assets/roads_p2_main.qml",
    "assets/roads_p3.qml",
    "assets/sidewalkstyles.qml",
    "assets/sure_zones.qml",
    "assets/logos/logos.png",
    "assets/logos/sidewalkreator_logo.png",
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for release generation."""

    default_plugin_dir = Path(__file__).resolve().parent.parent
    default_output_dir = Path.home() / "sidewalkreator_release"

    parser = argparse.ArgumentParser(description="Package plugin into a zip archive")
    parser.add_argument(
        "--plugin-dir",
        default=default_plugin_dir,
        type=Path,
        help="Path to the plugin directory (default: repository root)",
    )
    parser.add_argument(
        "--output-dir",
        default=default_output_dir,
        type=Path,
        help="Directory where the release zip will be written",
    )
    return parser.parse_args()


def release_files(plugin_dir: Path) -> Iterable[Path]:
    """Return validated runtime files that belong in a release."""

    missing = [relative for relative in REQUIRED_FILES if not (plugin_dir / relative).is_file()]
    if missing:
        formatted = "\n  - ".join(missing)
        raise FileNotFoundError(f"Required release files are missing:\n  - {formatted}")

    yield from (plugin_dir / relative for relative in REQUIRED_FILES)

    i18n_dir = plugin_dir / "i18n"
    if i18n_dir.is_dir():
        # QGIS loads compiled catalogs at runtime. Translation source files and
        # every other development artifact remain outside the release.
        yield from sorted(path for path in i18n_dir.glob("*.qm") if path.is_file())


def _write_archive(staging_root: Path, archive_path: Path) -> None:
    """Write an archive with predictable, non-executable file permissions."""

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        directories = [staging_root, *sorted(p for p in staging_root.rglob("*") if p.is_dir())]
        for directory in directories:
            relative = directory.relative_to(staging_root.parent).as_posix().rstrip("/") + "/"
            info = zipfile.ZipInfo(relative)
            info.create_system = 3
            info.external_attr = (stat.S_IFDIR | 0o755) << 16
            archive.writestr(info, b"")

        for path in sorted(p for p in staging_root.rglob("*") if p.is_file()):
            relative = path.relative_to(staging_root.parent).as_posix()
            info = zipfile.ZipInfo.from_file(path, relative)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes())


def build_release(plugin_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    """Stage allowed runtime files and create the plugin release archive."""

    plugin_dir = plugin_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    staging_root = output_dir / PLUGIN_NAME
    archive_path = output_dir / f"{PLUGIN_NAME}.zip"

    files = list(release_files(plugin_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    if staging_root.exists():
        shutil.rmtree(staging_root)
    if archive_path.exists():
        archive_path.unlink()

    for source in files:
        relative = source.relative_to(plugin_dir)
        destination = staging_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o644)

    _write_archive(staging_root, archive_path)
    return archive_path, staging_root


def main() -> None:
    args = parse_args()
    archive_path, staging_root = build_release(args.plugin_dir, args.output_dir)
    print(archive_path)
    print(staging_root)


if __name__ == "__main__":
    main()
