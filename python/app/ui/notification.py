import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from app.i18n import t, tl
from app.theme import T
from app.ui.icons import logo_pixmap
from app.ui.widgets import Button, IconButton, app_font, rtl_text_flags


def reveal_in_file_manager(file_path: str) -> None:
    if not file_path:
        return
    p = Path(file_path)
    target_dir = p.parent if p.is_file() else p
    if not target_dir.exists():
        return
    try:
        if sys.platform == "win32":
            if p.is_file():
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                os.startfile(str(target_dir))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(target_dir)])
    except Exception:
        pass


class NotificationPopup(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            parent,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(380, 118)

        self._title = ""
        self._message = ""
        self._file_path = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addStretch(1)
        self.btn_close = IconButton("close", size=26, danger_hover=True)
        self.btn_close.clicked.connect(self.hide)
        top_row.addWidget(self.btn_close)
        root.addLayout(top_row)

        root.addStretch(1)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(48, 0, 0, 0)
        actions_row.setSpacing(8)
        self.btn_folder = Button(t("ctx_open_folder"), icon_name="folder", variant="glass", height=28, compact=True)
        self.btn_folder.clicked.connect(self._on_open_folder)
        actions_row.addWidget(self.btn_folder)
        actions_row.addStretch(1)
        root.addLayout(actions_row)

        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(420)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_notification(self, title: str, message: str, file_path: str = "") -> None:
        self._title = title
        self._message = message
        self._file_path = file_path
        self.btn_folder.setText(t("ctx_open_folder"))
        self.btn_folder.setVisible(bool(file_path))

        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            end_x = avail.right() - self.width() - 20
            end_y = avail.bottom() - self.height() - 20
            start_pos = QPoint(end_x, avail.bottom() + 20)
            end_pos = QPoint(end_x, end_y)
            self.move(start_pos)
            self.show()
            self._anim.stop()
            self._anim.setStartValue(start_pos)
            self._anim.setEndValue(end_pos)
            self._anim.start()
        else:
            self.show()

        self.update()
        self._hide_timer.start(5500)

    def _on_open_folder(self) -> None:
        reveal_in_file_manager(self._file_path)
        self.hide()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        p.setBrush(T.c("surface", alpha=245))
        p.setPen(QPen(T.c("border_hi"), 1.3))
        p.drawRoundedRect(r, 22.0, 22.0)

        logo = logo_pixmap(38)
        p.drawPixmap(16, 18, logo)

        title_rect = QRectF(64, 16, r.width() - 104, 24)
        p.setFont(app_font(13, QFont.Bold))
        p.setPen(T.c("text"))
        p.drawText(title_rect, rtl_text_flags(True, True), tl(self._title))

        msg_rect = QRectF(64, 40, r.width() - 84, 34)
        p.setFont(app_font(12, QFont.Medium))
        p.setPen(T.c("text2"))
        elided = p.fontMetrics().elidedText(self._message, Qt.ElideRight, int(msg_rect.width()))
        p.drawText(msg_rect, rtl_text_flags(True, True), tl(elided))
        p.end()
