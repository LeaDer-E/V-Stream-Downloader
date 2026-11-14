from typing import List, Optional
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.i18n import I18N, t, tl, tp
from app.state import AppState
from app.theme import PALETTE_SPECS, PALETTES, T
from app.ui.widgets import Button, SegmentedControl, app_font, rtl_text_flags


class PalettePreviewCard(QWidget):
    clicked = Signal(str)

    def __init__(self, palette_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.palette_id = palette_id
        self._hover = False
        self.setMinimumWidth(185)
        self.setFixedHeight(124)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            event.accept()
            self.clicked.emit(self.palette_id)
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        pal = PALETTES.get(self.palette_id, PALETTES["cyber_violet"])
        mode = T.effective_mode()
        sub = pal[mode]
        is_selected = T.palette_id == self.palette_id

        bg0 = QColor(sub["bg0"])
        surface = QColor(sub["surface"])
        acc = QColor(sub["accent"])
        acc2 = QColor(sub["accent2"])
        txt = QColor(sub["text"])

        p.setBrush(surface)
        pen_col = acc if is_selected else (QColor(sub["border_hi"]) if self._hover else QColor(sub["border"]))
        p.setPen(QPen(pen_col, 2.2 if is_selected else 1.1))
        p.drawRoundedRect(r, 16.0, 16.0)

        mini = QRectF(r.left() + 10, r.top() + 10, r.width() - 20, 64)
        p.setBrush(bg0)
        p.setPen(QPen(QColor(sub["border"]), 1.0))
        p.drawRoundedRect(mini, 10.0, 10.0)

        grad = QLinearGradient(mini.topLeft(), mini.topRight())
        grad.setColorAt(0.0, acc)
        grad.setColorAt(1.0, acc2)
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(mini.left() + 10, mini.top() + 11, 64, 11), 5.5, 5.5)

        swatches = [acc, acc2, QColor(sub["cat_single"]), QColor(sub["cat_channel"])]
        for idx, sw in enumerate(swatches):
            p.setBrush(sw)
            p.drawEllipse(QPointF(mini.left() + 15 + idx * 17, mini.bottom() - 15), 5.0, 5.0)

        label = tp(str(pal["ar_name"]), str(pal["en_name"]))
        p.setFont(app_font(12, QFont.Bold))
        p.setPen(txt)
        is_rtl = I18N.is_rtl()
        lbl_rect = QRectF(
            r.left() + (28 if is_rtl and is_selected else 12),
            r.bottom() - 36,
            r.width() - (40 if is_selected else 24),
            26,
        )
        elided = p.fontMetrics().elidedText(label, Qt.ElideRight, int(lbl_rect.width()))
        p.drawText(lbl_rect, rtl_text_flags(True, True), tl(elided))

        if is_selected:
            p.setBrush(acc)
            p.setPen(Qt.NoPen)
            dot_x = (r.left() + 16) if is_rtl else (r.right() - 16)
            p.drawEllipse(QPointF(dot_x, r.bottom() - 23), 5.0, 5.0)
        p.end()


class ThemesPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self._cols = 4

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_lbl = QLabel(t("themes_title"))
        self.title_lbl.setFont(app_font(20, QFont.ExtraBold))
        self.title_lbl.setStyleSheet(f"color: {T.token_str('text')};")
        self.sub_lbl = QLabel(t("themes_subtitle"))
        self.sub_lbl.setFont(app_font(12, QFont.Medium))
        self.sub_lbl.setStyleSheet(f"color: {T.token_str('text2')};")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.sub_lbl)
        header.addLayout(title_box, 1)

        self.mode_seg = SegmentedControl(
            [
                ("dark", t("mode_dark")),
                ("light", t("mode_light")),
                ("auto", t("mode_auto")),
            ],
            self.state.config.theme_mode,
            compact=True,
        )
        self.mode_seg.changed.connect(self._on_mode_changed)
        header.addWidget(self.mode_seg)

        self.btn_custom = Button(t("custom_color_btn"), icon_name="themes", variant="glass", height=34, compact=True)
        self.btn_custom.clicked.connect(self._pick_custom_color)
        header.addWidget(self.btn_custom)

        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(T.scrollbar_qss())

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 4, 4, 16)
        self.grid.setSpacing(12)

        self.cards: List[PalettePreviewCard] = []
        spec_ids = [pid for pid, _, _, _ in PALETTE_SPECS]
        if "custom" in PALETTES:
            spec_ids.insert(0, "custom")

        for pid in spec_ids:
            card = PalettePreviewCard(pid)
            card.clicked.connect(self._on_palette_selected)
            self.cards.append(card)

        self._relayout_grid(4)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

    def _relayout_grid(self, cols: int) -> None:
        self._cols = max(2, cols)
        while self.grid.count():
            self.grid.takeAt(0)
        for idx, card in enumerate(self.cards):
            self.grid.addWidget(card, idx // self._cols, idx % self._cols)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        avail_w = self.width() - 56
        cols = max(2, min(5, avail_w // 205))
        if cols != self._cols:
            self._relayout_grid(cols)

    def _on_mode_changed(self, mode: str) -> None:
        self.state.config.theme_mode = mode
        T.set_theme(self.state.config.palette_id, mode, self.state.config.custom_accent)
        self.state.config.save()
        self.state.theme_changed.emit()

    def _on_palette_selected(self, pid: str) -> None:
        if pid == self.state.config.palette_id:
            return
        self.state.config.palette_id = pid
        T.set_theme(pid, self.state.config.theme_mode, self.state.config.custom_accent)
        self.state.config.save()
        self.state.theme_changed.emit()

    def _pick_custom_color(self) -> None:
        col = QColorDialog.getColor(QColor(self.state.config.custom_accent), self, t("custom_color_btn"))
        if col.isValid():
            hx = col.name(QColor.HexRgb)
            self.state.config.custom_accent = hx
            self.state.config.palette_id = "custom"
            T.set_theme("custom", self.state.config.theme_mode, hx)
            self.state.config.save()
            self.state.theme_changed.emit()
