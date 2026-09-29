from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (ROOT / "foxair_phnix_control.py").read_text(encoding="utf-8")
AT_SOURCE = MAIN_SOURCE.split("class ATCompensationDialog", 1)[1].split("class MainWindow", 1)[0]


def _method_source(name: str) -> str:
    return AT_SOURCE.split(f"    def {name}", 1)[1].split("\n    def ", 1)[0]


def test_mode_selection_only_shows_the_matching_input_group():
    handler = _method_source("_mode_changed")

    assert "self.linear_box.setVisible(mode == 1)" in handler
    assert "self.seven_box.setVisible(mode == 2)" in handler
    assert "self.curve_canvas.set_editable(mode == 2)" in handler


def test_curve_drag_updates_the_corresponding_seven_point_input():
    canvas = MAIN_SOURCE.split("class CurveCanvas", 1)[1].split("class ATCompensationDialog", 1)[0]
    handler = _method_source("_curve_point_dragged")

    assert "pointDragged = Signal(int, float)" in canvas
    assert "self.pointDragged.emit(self._dragged_point, value)" in canvas
    assert "0 <= index < len(spins)" in handler
    assert "spins[index].setValue(value)" in handler


def test_curve_dragging_uses_the_active_temperature_limits():
    update = _method_source("update_curve_table")

    assert "self.curve_canvas.set_value_limits(minimum, maximum)" in update
