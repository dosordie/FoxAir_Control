from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from cloud.warmlink_codes import (
    WARMLINK_SERVICE_KNOWLEDGE,
    warmlink_service_rows,
)


class WarmlinkServiceDialog(QDialog):
    """Read-only diagnosis for reverse-engineered Warmlink service registers."""

    HEADERS = ("Register", "Name", "RAW", "Dekodierte Bedeutung", "Typ", "TTL/Persistenz", "Transport", "Schreibstatus")

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Warmlink Service / Engineering")
        self.resize(1320, 560)
        layout = QVBoxLayout(self)
        info = QLabel(WARMLINK_SERVICE_KNOWLEDGE)
        info.setWordWrap(True)
        layout.addWidget(info)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for col in range(len(self.HEADERS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents if col in (0, 2, 4) else QHeaderView.Stretch)
        layout.addWidget(self.table)
        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh, alignment=Qt.AlignRight)
        self.refresh()

    def refresh(self):
        rows = warmlink_service_rows(getattr(self.main_window, "last_values", {}))
        self.table.setRowCount(len(rows))
        for row, data in enumerate(rows):
            for col, key in enumerate(("register", "name", "raw", "meaning", "type", "lifetime", "transport", "write_status")):
                self.table.setItem(row, col, QTableWidgetItem(data[key]))
