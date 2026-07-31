import ast
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _main_module_tree():
    source_path = PLUGIN_ROOT / "osm_sidewalkreator.py"
    return source_path, ast.parse(
        source_path.read_text(encoding="utf-8"), filename=str(source_path)
    )


def test_dialog_button_box_uses_scoped_enum_compatibility():
    _, tree = _main_module_tree()
    legacy_members = {"Reset", "Cancel", "Ok"}

    direct_legacy_accesses = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "QDialogButtonBox"
        and node.attr in legacy_members
    ]

    assert direct_legacy_accesses == []


def test_dialog_exec_supports_qt5_and_qt6_method_names():
    source_path, tree = _main_module_tree()
    helper = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_exec_dialog"
    )
    namespace = {}
    helper_module = ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[]))
    exec(compile(helper_module, str(source_path), "exec"), namespace)
    exec_dialog = namespace["_exec_dialog"]

    class Qt6Dialog:
        def exec(self):
            return "qt6"

    class Qt5Dialog:
        def exec_(self):
            return "qt5"

    assert exec_dialog(Qt6Dialog()) == "qt6"
    assert exec_dialog(Qt5Dialog()) == "qt5"
