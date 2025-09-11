# Repository Guidelines

- Always run `scripts/run_qgis_tests.sh` before committing.
- For a quick local check without Docker, run `pytest -m 'not qgis'`.
- Use `release/release_zip.py` to build distribution archives.
- Follow existing formatting and avoid trailing whitespace in commits.
- Update tests and documentation when modifying processing algorithms or release tooling.
- Any `AGENTS.md` files in subdirectories override these root guidelines for files within their scope.
