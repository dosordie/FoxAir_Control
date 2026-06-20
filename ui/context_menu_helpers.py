"""Context-menu helpers for the FoxAir Qt UI.

This module intentionally contains only UI/menu construction code. Actions returned
from these helpers are interpreted by ``MainWindow`` so that write/read logic stays
in the main window implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from cloud.cloud_write_helpers import cloud_code_for_register


class RegisterContextAction(str, Enum):
    """Actions that can be selected from the register-table context menu."""

    QUICK_WRITE = "quick_write"
    CLOUD_WRITE = "cloud_write"
    READ_ONE = "read_one"
    READ_TEN = "read_ten"
    USE_WRITE_ADDRESS = "use_write_address"


@dataclass(frozen=True)
class RegisterContextMenuResult:
    """Selection result for the register-table context menu."""

    action: RegisterContextAction
    cloud_code: str | None = None


def _add_action(menu: QMenu, text: str) -> QAction:
    """Create a QAction with the same defaults as QMenu.addAction()."""

    action = QAction(text, menu)
    menu.addAction(action)
    return action


def _register_cloud_write_code(reg_no: int) -> str | None:
    """Return the writable cloud code for a register, if a menu entry is allowed."""

    return cloud_code_for_register(reg_no, require_write_allowed=True)


def build_register_context_menu(parent: QWidget, reg_no: int) -> tuple[QMenu, dict[QAction, RegisterContextMenuResult]]:
    """Build the register-table context menu and map actions to MainWindow callbacks.

    The visual order and labels are kept identical to the previous inline menu in
    ``MainWindow.open_register_context_menu``.
    """

    menu = QMenu(parent)
    action_map: dict[QAction, RegisterContextMenuResult] = {}

    act_quick_write = _add_action(menu, f"Register {reg_no} schnell schreiben ...")
    action_map[act_quick_write] = RegisterContextMenuResult(RegisterContextAction.QUICK_WRITE)

    cloud_code = _register_cloud_write_code(reg_no)
    if cloud_code:
        act_cloud_write = _add_action(menu, f"Wert per Cloud schreiben ... ({cloud_code})")
        action_map[act_cloud_write] = RegisterContextMenuResult(RegisterContextAction.CLOUD_WRITE, cloud_code)

    menu.addSeparator()

    act_read_one = _add_action(menu, f"Register {reg_no} lesen")
    action_map[act_read_one] = RegisterContextMenuResult(RegisterContextAction.READ_ONE)

    act_read_ten = _add_action(menu, f"10 Register ab {reg_no} lesen")
    action_map[act_read_ten] = RegisterContextMenuResult(RegisterContextAction.READ_TEN)

    act_use_write = _add_action(menu, "Adresse ins Schreib-/Lesefeld übernehmen")
    action_map[act_use_write] = RegisterContextMenuResult(RegisterContextAction.USE_WRITE_ADDRESS)

    return menu, action_map


def exec_register_context_menu(parent: QWidget, reg_no: int, global_pos) -> RegisterContextMenuResult | None:
    """Show the register-table context menu and return the selected action."""

    menu, action_map = build_register_context_menu(parent, reg_no)
    selected_action = menu.exec(global_pos)
    if selected_action is None:
        return None
    return action_map.get(selected_action)
