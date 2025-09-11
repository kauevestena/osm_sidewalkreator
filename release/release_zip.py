"""Utility script to generate a release zip of the plugin."""

import argparse
import os
import shutil
from pathlib import Path


exclude_patternslist = [
    ".git",
    ".github",
    "__pycache__",
    "notes",
    "i18n",
    "release",
    "*.pyc",
    "temporary",
    "plugin_upload.py",
    "trash",
    "paper_publication",
    "extra_tests",
]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for release generation."""

    default_plugin_dir = Path(__file__).resolve().parent.parent
    default_output_dir = Path.home() / "sidewalkreator_release"

    parser = argparse.ArgumentParser(description="Package plugin into a zip archive")
    parser.add_argument(
        "--plugin-dir",
        default=str(default_plugin_dir),
        help="Path to the plugin directory (default: repository root)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output_dir),
        help="Directory where the release zip will be written",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        nargs="*",
        default=[],
        help="Additional patterns to exclude from the archive",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    plugin_path = os.path.abspath(os.path.expanduser(args.plugin_dir))
    output_dir = os.path.abspath(os.path.expanduser(args.output_dir))

    additional_excludes = [p for patterns in args.exclude for p in patterns]
    exclude_patterns = exclude_patternslist + additional_excludes

    destfolderpath = str(
        Path(output_dir) / "osm_sidewalkreator" / "osm_sidewalkreator"
    )
    release_folderpath = str(Path(destfolderpath).parent)
    outpath = os.path.join(output_dir, "osm_sidewalkreator.zip")

    if os.path.exists(release_folderpath):
        shutil.rmtree(release_folderpath)

    shutil.copytree(
        plugin_path, destfolderpath, ignore=shutil.ignore_patterns(*exclude_patterns)
    )

    if os.path.exists(outpath):
        os.remove(outpath)

    shutil.make_archive(outpath.replace(".zip", ""), "zip", release_folderpath)

    print(outpath)
    print(release_folderpath)
    print(destfolderpath)


if __name__ == "__main__":
    main()

