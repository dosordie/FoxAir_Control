"""A display-only activity border for the existing Cloud button."""
from PySide6.QtCore import QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton


class CloudStatusButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._polling_active = False
        self._dash_offset = 0.0
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(75)
        self.animation_timer.timeout.connect(self._advance_border)

    def setPollingActive(self, active: bool) -> None:
        self._polling_active = bool(active)
        if self._polling_active:
            if not self.animation_timer.isActive():
                self.animation_timer.start()
        else:
            self.animation_timer.stop()
            self._dash_offset = 0.0
        self.update()

    def _advance_border(self) -> None:
        self._dash_offset = (self._dash_offset - 0.5) % 12
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._polling_active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        painter.setPen(QPen(QColor("#38965b"), 1.4))
        painter.drawRoundedRect(rect, 3, 3)
        pen = QPen(QColor("#68d98b"), 2)
        pen.setDashPattern([4, 8])
        pen.setDashOffset(self._dash_offset)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 3, 3)
        painter.end()
