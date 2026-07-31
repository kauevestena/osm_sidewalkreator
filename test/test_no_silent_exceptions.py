import ast
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCANNED_FILES = (
    "generic_functions.py",
    "processing/full_sidewalkreator_bbox_algorithm.py",
    "processing/full_sidewalkreator_polygon_algorithm.py",
    "processing/protoblock_algorithm.py",
    "processing/protoblock_bbox_algorithm.py",
    "processing/protoblock_provider.py",
)


def test_reported_files_do_not_silently_swallow_exceptions():
    silent_handlers = []

    for relative_path in SCANNED_FILES:
        source_path = PLUGIN_ROOT / relative_path
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=relative_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if len(node.body) == 1 and isinstance(node.body[0], (ast.Pass, ast.Continue)):
                silent_handlers.append(f"{relative_path}:{node.lineno}")

    assert silent_handlers == []
