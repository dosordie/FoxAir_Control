import ast
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _settings_snapshot_method():
    """Compile the real method without importing the Qt application module."""
    source = (ROOT / "foxair_phnix_control.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_window = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
    )
    method = next(
        node for node in main_window.body
        if isinstance(node, ast.FunctionDef) and node.name == "_settings_data_snapshot"
    )
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(ROOT / "foxair_phnix_control.py"), "exec"), namespace)
    return namespace["_settings_data_snapshot"]


def test_settings_snapshot_keeps_enabled_engineering_parameters():
    window = SimpleNamespace(
        settings={"show_engineering_parameters": True},
        current_backend_key=lambda: "standard_modbus",
        current_device_model=lambda: "foxair_green_gl9_1",
        autoconnect_cb=SimpleNamespace(isChecked=lambda: False),
    )

    snapshot = _settings_snapshot_method()(window)

    assert snapshot["show_engineering_parameters"] is True
