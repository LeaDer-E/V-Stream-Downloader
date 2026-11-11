from typing import Callable, List, Optional, Tuple
from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QLineEdit,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import I18N, normalize_search_query, t, tl
from app.theme import T
from app.ui.icons import draw_icon, make_qicon


def app_font(size_px: int = 13, weight: QFont.Weight = QFont.Medium) -> QFont:
    f = QFont()
    f.setFamilies(
        [
            "Tajawal",
            "Noto Kufi Arabic",
            "Noto Sans Arabic",
            "Noto Nastaliq Urdu",
            "Vazirmatn",
            "Segoe UI",
            "Nirmala UI",
            "Noto Sans Bengali",
            "Vrinda",
            "Urdu Typesetting",
            "Noto Sans",
            "Calibri",
            "Arial",
        ]
    )
    f.setPixelSize(size_px)
    f.setWeight(weight)
    return f


def rtl_text_flags(align_left_in_ltr: bool = True, vcenter: bool = True) -> int:
    is_rtl = I18N.is_rtl()
    if align_left_in_ltr:
        horiz = Qt.AlignRight if is_rtl else Qt.AlignLeft
    else:
        horiz = Qt.AlignLeft if is_rtl else Qt.AlignRight
    vert = Qt.AlignVCenter if vcenter else Qt.AlignTop
    return int(Qt.AlignAbsolute | horiz | vert)


class StyledLineEdit(QLineEdit):
    """
    Custom QLineEdit with:
    1. Built-in high-contrast theme stylesheet (so it is always clearly visible and editable inside any container or ScrollArea).
    2. Optional `ltr_mode=True` for technical inputs (Proxy URLs, HH:MM times, Stream URLs) so typing works naturally even in RTL mode.
    3. Localized (Arabic / English), theme-styled right-click QMenu.
    """

    def __init__(
        self,
        placeholder: str = "",
        on_paste_and_go: Optional[Callable[[], None]] = None,
        ltr_mode: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._on_paste_and_go = on_paste_and_go
        self._ltr_mode = ltr_mode
        self.setEnabled(True)
        self.setReadOnly(False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.setFont(app_font(12, QFont.Medium))
        if ltr_mode:
            self.setLayoutDirection(Qt.LeftToRight)
            self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_localized_menu)
        self.apply_theme_style()

    def apply_theme_style(self, radius: int = 10, pad_h: int = 12) -> None:
        self.setStyleSheet(
            f"QLineEdit {{ background: {T.token_str('bg0')}; color: {T.token_str('text')}; "
            f"selection-background-color: {T.token_str('accent')}; selection-color: #FFFFFF; "
            f"border: 1.5px solid {T.token_str('border_hi')}; border-radius: {radius}px; padding: 0 {pad_h}px; }}"
            f"QLineEdit:focus {{ border: 1.5px solid {T.token_str('accent_hi')}; background: {T.token_str('bg1')}; }}"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
        super().mousePressEvent(event)

    def _show_localized_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setLayoutDirection(Qt.RightToLeft if I18N.is_rtl() else Qt.LeftToRight)
        menu.setStyleSheet(
            f"QMenu {{ background: {T.token_str('surface')}; color: {T.token_str('text')}; "
            f"border: 1px solid {T.token_str('border_hi')}; border-radius: 12px; padding: 6px; }}"
            f"QMenu::item {{ padding: 7px 18px; border-radius: 8px; font-size: 13px; }}"
            f"QMenu::item:selected {{ background: {T.token_str('accent')}; color: #FFFFFF; }}"
            f"QMenu::item:disabled {{ color: {T.token_str('text3')}; }}"
        )

        cb = QGuiApplication.clipboard()
        has_clip = bool(cb is not None and cb.text().strip())
        has_text = bool(self.text())
        has_sel = bool(self.hasSelectedText())

        act_paste = menu.addAction(make_qicon("paste"), t("edit_paste"))
        act_paste.setEnabled(has_clip)
        act_paste.triggered.connect(self.paste)

        if self._on_paste_and_go is not None:
            act_paste_go = menu.addAction(make_qicon("bolt", color=T.c("ok")), t("edit_paste_analyze"))
            act_paste_go.setEnabled(has_clip or has_text)
            act_paste_go.triggered.connect(self._on_paste_and_go)

        menu.addSeparator()

        act_copy = menu.addAction(make_qicon("copy"), t("edit_copy"))
        act_copy.setEnabled(has_sel)
        act_copy.triggered.connect(self.copy)

        act_cut = menu.addAction(make_qicon("copy"), t("edit_cut"))
        act_cut.setEnabled(has_sel)
        act_cut.triggered.connect(self.cut)

        act_all = menu.addAction(make_qicon("check"), t("edit_select_all"))
        act_all.setEnabled(has_text)
        act_all.triggered.connect(self.selectAll)

        menu.addSeparator()

        act_clear = menu.addAction(make_qicon("trash", color=T.c("danger")), t("edit_clear"))
        act_clear.setEnabled(has_text)
        act_clear.triggered.connect(self.clear)

        menu.exec(self.mapToGlobal(pos))


class Button(QWidget):
    clicked = Signal()

    def __init__(
        self,
        text: str = "",
        icon_name: str = "",
        variant: str = "primary",  # "primary", "emerald", "ghost", "glass", "danger"
        height: int = 38,
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._icon = icon_name
        self._variant = variant
        self._compact = compact
        self._hover_p: float = 0.0
        self._press_p: float = 0.0
        self._busy: bool = False
        self._spin_angle: int = 0

        self.setFixedHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._hover_anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(24)
        self._spin_timer.timeout.connect(self._tick_spin)
        self._recalc_width()

    def _recalc_width(self) -> None:
        f = app_font(
            12 if self._compact else 13,
            QFont.Bold if self._variant in ("primary", "emerald") else QFont.DemiBold,
        )
        fm = QFontMetrics(f)
        tw = fm.horizontalAdvance(self._text) if self._text else 0
        iw = (16 if self._compact else 18) if self._icon else 0
        gap = (6 if self._compact else 8) if (self._text and self._icon) else 0
        pad = 22 if self._compact else 30
        self.setMinimumWidth(max(36 if self._compact else 44, tw + iw + gap + pad))

    def setText(self, text: str) -> None:
        self._text = text
        self._recalc_width()
        self.update()

    def set_icon(self, icon_name: str) -> None:
        self._icon = icon_name
        self._recalc_width()
        self.update()

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._recalc_width()
        self.update()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self._spin_timer.start()
        else:
            self._spin_timer.stop()
        self.update()

    def _tick_spin(self) -> None:
        self._spin_angle = (self._spin_angle + 18) % 360
        self.update()

    def getHoverProgress(self) -> float:
        return self._hover_p

    def setHoverProgress(self, val: float) -> None:
        self._hover_p = val
        self.update()

    hoverProgress = Property(float, getHoverProgress, setHoverProgress)

    def enterEvent(self, event) -> None:
        self._hover_anim.stop()
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_anim.stop()
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        self._press_p = 0.0
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._busy:
            self._press_p = 1.0
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._busy:
            was_pressed = self._press_p > 0.0
            self._press_p = 0.0
            self.update()
            if was_pressed and self.rect().adjusted(-6, -6, 6, 6).contains(event.position().toPoint()):
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        inset = 1.5 + self._press_p * 1.0
        r = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        rad = min(12.0, r.height() / 2.0)

        if self._variant == "primary":
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            c1 = T.c("accent").lighter(int(100 + 14 * self._hover_p))
            c2 = T.c("accent2").lighter(int(100 + 14 * self._hover_p))
            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)
            p.setBrush(grad)
            p.setPen(QPen(T.c("accent_hi", alpha=160), 1.0))
            fg = T.c("on_accent")
        elif self._variant == "emerald":
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            base_ok = QColor("#10B981").lighter(int(100 + 14 * self._hover_p))
            end_ok = QColor("#059669").lighter(int(100 + 14 * self._hover_p))
            grad.setColorAt(0.0, base_ok)
            grad.setColorAt(1.0, end_ok)
            p.setBrush(grad)
            p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
            fg = QColor("#FFFFFF")
        elif self._variant == "danger":
            bg = T.c("danger", alpha=int(35 + 45 * self._hover_p))
            p.setBrush(bg)
            p.setPen(QPen(T.c("danger"), 1.2))
            fg = T.c("danger")
        elif self._variant == "glass":
            bg = T.c("surface_hi", alpha=int(155 + 75 * self._hover_p))
            p.setBrush(bg)
            p.setPen(QPen(T.c("border_hi" if self._hover_p > 0.2 else "border"), 1.1))
            fg = T.c("text")
        else:
            bg = T.c("surface_hi", alpha=int(185 * self._hover_p))
            p.setBrush(bg)
            p.setPen(
                QPen(T.c("border", alpha=int(160 * self._hover_p)), 1.0)
                if self._hover_p > 0.05
                else Qt.NoPen
            )
            fg = T.c("text") if self._hover_p > 0.2 else T.c("text2")

        p.drawRoundedRect(r, rad, rad)

        f = app_font(
            12 if self._compact else 13,
            QFont.Bold if self._variant in ("primary", "emerald") else QFont.DemiBold,
        )
        p.setFont(f)
        fm = p.fontMetrics()

        iw = (16.0 if self._compact else 18.0) if (self._icon or self._busy) else 0.0
        tw = float(fm.horizontalAdvance(self._text)) if self._text else 0.0
        gap = (6.0 if self._compact else 8.0) if (iw > 0 and tw > 0) else 0.0
        total_w = iw + gap + tw
        start_x = r.center().x() - total_w / 2.0
        cy = r.center().y()

        is_rtl = I18N.is_rtl()
        if is_rtl:
            icon_x = start_x + tw + gap
            text_x = start_x
        else:
            icon_x = start_x
            text_x = start_x + iw + gap

        if self._busy:
            p.save()
            p.translate(icon_x + iw / 2.0, cy)
            p.rotate(self._spin_angle)
            pen = QPen(fg, 2.2)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            sr = QRectF(-iw / 2.0 + 2, -iw / 2.0 + 2, iw - 4, iw - 4)
            p.drawArc(sr, 0, 270 * 16)
            p.restore()
        elif self._icon:
            draw_icon(p, self._icon, QRectF(icon_x, cy - iw / 2.0, iw, iw), color=fg)

        if self._text:
            p.setPen(fg)
            t_rect = QRectF(text_x - 2, r.top(), tw + 4, r.height())
            p.drawText(t_rect, int(Qt.AlignCenter), tl(self._text))

        p.end()


class IconButton(QWidget):
    clicked = Signal()

    def __init__(
        self,
        icon_name: str,
        size: int = 34,
        width: Optional[int] = None,
        tooltip: str = "",
        danger_hover: bool = False,
        subtle_bg: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._icon = icon_name
        self._danger = danger_hover
        self._subtle_bg = subtle_bg
        self._hover = False
        self._pressed = False
        w = width if width is not None else size
        self.setFixedSize(w, size)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def set_icon(self, icon_name: str) -> None:
        self._icon = icon_name
        self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            was_pressed = self._pressed
            self._pressed = False
            self.update()
            if was_pressed and self.rect().adjusted(-8, -8, 8, 8).contains(event.position().toPoint()):
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        if self._hover:
            bg = T.c("danger", alpha=215) if self._danger else T.c("surface_hi", alpha=220)
            p.setBrush(bg)
            p.setPen(QPen(T.c("danger" if self._danger else "border_hi"), 1.0))
            p.drawRoundedRect(r, 9.0, 9.0)
        elif self._subtle_bg:
            p.setBrush(T.c("bg1", alpha=160))
            p.setPen(QPen(T.c("border", alpha=110), 1.0))
            p.drawRoundedRect(r, 9.0, 9.0)

        fg = (
            QColor("#FFFFFF")
            if (self._hover and self._danger)
            else (T.c("text") if self._hover else T.c("text2"))
        )
        side = min(r.width(), r.height()) * 0.56
        ic_rect = QRectF(r.center().x() - side / 2.0, r.center().y() - side / 2.0, side, side)
        draw_icon(p, self._icon, ic_rect, color=fg)
        p.end()


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self._pos: float = 1.0 if checked else 0.0
        self.setFixedSize(48, 26)
        self.setCursor(Qt.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool, emit_signal: bool = False) -> None:
        if self._checked == val:
            return
        self._checked = val
        self._anim.stop()
        self._anim.setEndValue(1.0 if val else 0.0)
        self._anim.start()
        if emit_signal:
            self.toggled.emit(val)

    def getKnobPos(self) -> float:
        return self._pos

    def setKnobPos(self, val: float) -> None:
        self._pos = val
        self.update()

    knobPos = Property(float, getKnobPos, setKnobPos)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().adjusted(-6, -6, 6, 6).contains(event.position().toPoint()):
            event.accept()
            self.setChecked(not self._checked, emit_signal=True)
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)

        if self._pos > 0.5:
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            grad.setColorAt(0.0, T.c("accent"))
            grad.setColorAt(1.0, T.c("accent2"))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(T.c("bg2"))
            p.setPen(QPen(T.c("border_hi"), 1.1))

        p.drawRoundedRect(r, r.height() / 2.0, r.height() / 2.0)

        d = r.height() - 6.0
        travel = r.width() - d - 6.0
        vis_p = (1.0 - self._pos) if I18N.is_rtl() else self._pos
        kx = r.left() + 3.0 + travel * vis_p
        ky = r.top() + 3.0

        p.setBrush(QColor("#FFFFFF"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(kx, ky, d, d))
        p.end()


class SegmentedControl(QWidget):
    changed = Signal(str)

    def __init__(
        self,
        items: List[Tuple[str, str]],
        active_key: str = "",
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._compact = compact
        self._active_idx = 0
        for i, (k, _) in enumerate(items):
            if k == active_key:
                self._active_idx = i
                break
        self._thumb_x: float = float(self._active_idx)
        self.setFixedHeight(34 if compact else 38)
        self.setCursor(Qt.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"thumbIndex", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._recalc_min_width()

    def _recalc_min_width(self) -> None:
        if not self._items:
            self.setMinimumWidth(120)
            return
        fm = QFontMetrics(app_font(12, QFont.DemiBold))
        max_lbl_w = max(fm.horizontalAdvance(lbl) for _, lbl in self._items)
        seg_w = max(54 if self._compact else 70, min(140, max_lbl_w + (18 if self._compact else 24)))
        self.setMinimumWidth(len(self._items) * seg_w + 8)

    def set_items(self, items: List[Tuple[str, str]], active_key: str = "") -> None:
        self._items = items
        self._active_idx = 0
        for i, (k, _) in enumerate(items):
            if k == active_key:
                self._active_idx = i
                break
        self._thumb_x = float(self._active_idx)
        self._recalc_min_width()
        self.update()

    def current_key(self) -> str:
        if not self._items:
            return ""
        return self._items[self._active_idx][0]

    def getThumbIndex(self) -> float:
        return self._thumb_x

    def setThumbIndex(self, val: float) -> None:
        self._thumb_x = val
        self.update()

    thumbIndex = Property(float, getThumbIndex, setThumbIndex)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._items:
            event.accept()
            n = len(self._items)
            seg_w = self.width() / float(n)
            clicked = int(event.position().x() // seg_w)
            clicked = max(0, min(n - 1, clicked))
            if I18N.is_rtl():
                clicked = (n - 1) - clicked
            if clicked != self._active_idx:
                self._active_idx = clicked
                self._anim.stop()
                self._anim.setEndValue(float(clicked))
                self._anim.start()
                self.changed.emit(self._items[clicked][0])
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        if not self._items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(T.c("bg1"))
        p.setPen(QPen(T.c("border"), 1.0))
        p.drawRoundedRect(r, 11.0, 11.0)

        n = len(self._items)
        seg_w = r.width() / float(n)
        vis_idx = (n - 1 - self._thumb_x) if I18N.is_rtl() else self._thumb_x
        thumb_rect = QRectF(r.left() + vis_idx * seg_w + 3, r.top() + 3, seg_w - 6, r.height() - 6)

        grad = QLinearGradient(thumb_rect.topLeft(), thumb_rect.bottomRight())
        grad.setColorAt(0.0, T.c("accent"))
        grad.setColorAt(1.0, T.c("accent2"))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(thumb_rect, 8.5, 8.5)

        p.setFont(app_font(12, QFont.DemiBold))
        fm = p.fontMetrics()
        for i, (_, label) in enumerate(self._items):
            slot = (n - 1 - i) if I18N.is_rtl() else i
            sr = QRectF(r.left() + slot * seg_w + 4, r.top(), seg_w - 8, r.height())
            p.setPen(T.c("on_accent") if i == self._active_idx else T.c("text2"))
            elided = fm.elidedText(label, Qt.ElideRight, int(sr.width()))
            p.drawText(sr, int(Qt.AlignCenter), tl(elided))
        p.end()


class ScopeChoiceCard(QWidget):
    clicked = Signal(str)

    def __init__(
        self,
        key: str,
        icon_name: str,
        title: str,
        subtitle: str,
        selected: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self._icon = icon_name
        self._title = title
        self._subtitle = subtitle
        self._selected = selected
        self._hover = False
        self.setFixedHeight(68)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

    def set_selected(self, sel: bool) -> None:
        self._selected = sel
        self.update()

    def set_content(self, title: str, subtitle: str) -> None:
        self._title = title
        self._subtitle = subtitle
        self.update()

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
        if event.button() == Qt.LeftButton and self.rect().adjusted(-6, -6, 6, 6).contains(event.position().toPoint()):
            event.accept()
            self.clicked.emit(self.key)
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)

        if self._selected:
            bg = T.c("accent", alpha=42)
            border_c = T.c("accent_hi")
            pen_w = 1.8
        elif self._hover:
            bg = T.c("surface_hi", alpha=195)
            border_c = T.c("border_hi")
            pen_w = 1.2
        else:
            bg = T.c("bg1", alpha=215)
            border_c = T.c("border")
            pen_w = 1.0

        p.setBrush(bg)
        p.setPen(QPen(border_c, pen_w))
        p.drawRoundedRect(r, 14.0, 14.0)

        is_rtl = I18N.is_rtl()
        icon_x = (r.right() - 36) if is_rtl else (r.left() + 14)
        icon_col = T.c("accent_hi") if self._selected else T.c("text2")
        draw_icon(p, self._icon, QRectF(icon_x, r.top() + 12, 20, 20), color=icon_col)

        txt_left = r.left() + 12 if is_rtl else (r.left() + 42)
        txt_right = (r.right() - 42) if is_rtl else (r.right() - 12)
        txt_w = max(60.0, txt_right - txt_left)

        p.setFont(app_font(13, QFont.Bold))
        p.setPen(T.c("text"))
        t_elided = p.fontMetrics().elidedText(self._title, Qt.ElideRight, int(txt_w))
        p.drawText(QRectF(txt_left, r.top() + 10, txt_w, 22), rtl_text_flags(True, True), tl(t_elided))

        p.setFont(app_font(11, QFont.Medium))
        p.setPen(T.c("accent_hi") if self._selected else T.c("text2"))
        s_elided = p.fontMetrics().elidedText(self._subtitle, Qt.ElideRight, int(txt_w))
        p.drawText(QRectF(txt_left, r.top() + 34, txt_w, 20), rtl_text_flags(True, True), tl(s_elided))
        p.end()


class _SearchComboPopup(QWidget):
    selected = Signal(str, str)

    def __init__(self, items: List[Tuple[str, str]], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._all_items = items
        self._filtered = list(items)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        self.search_edit = StyledLineEdit(placeholder=t("search_placeholder"))
        self.search_edit.setFixedHeight(32)
        self.search_edit.textChanged.connect(self._on_filter)
        self._style_search()
        lay.addWidget(self.search_edit)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(T.scrollbar_qss())
        self.list_host = QWidget()
        self.list_host.setObjectName("comboPopupHost")
        self.list_host.setStyleSheet("QWidget#comboPopupHost { background: transparent; }")
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 2, 0)
        self.list_lay.setSpacing(4)
        self.scroll.setWidget(self.list_host)
        lay.addWidget(self.scroll)
        self._rebuild_rows()

    def _style_search(self) -> None:
        self.search_edit.setFont(app_font(12))
        self.search_edit.apply_theme_style(radius=8, pad_h=10)

    def _on_filter(self, q: str) -> None:
        q_norm = normalize_search_query(q)
        if not q_norm:
            self._filtered = list(self._all_items)
        else:
            self._filtered = [
                it
                for it in self._all_items
                if q_norm in normalize_search_query(it[1]) or q_norm in normalize_search_query(it[0])
            ]
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        while self.list_lay.count():
            it = self.list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for key, label in self._filtered:
            btn = Button(label, variant="ghost", height=32, compact=True)
            btn.clicked.connect(lambda k=key, lbl=label: self._pick(k, lbl))
            self.list_lay.addWidget(btn)
        self.list_lay.addStretch(1)

    def _pick(self, key: str, label: str) -> None:
        self.selected.emit(key, label)
        self.close()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        p.setBrush(T.c("surface"))
        p.setPen(QPen(T.c("border_hi"), 1.3))
        p.drawRoundedRect(r, 14.0, 14.0)
        p.end()


class SearchCombo(QWidget):
    changed = Signal(str)

    def __init__(
        self,
        items: List[Tuple[str, str]],
        active_key: str = "",
        min_width: int = 165,
        height: int = 36,
        icon_name: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._active_key = active_key if any(k == active_key for k, _ in items) else (items[0][0] if items else "")
        self._icon = icon_name
        self._hover = False
        self.setFixedHeight(height)
        self.setMinimumWidth(min_width)
        self.setCursor(Qt.PointingHandCursor)

    def set_items(self, items: List[Tuple[str, str]], active_key: str = "") -> None:
        self._items = items
        if active_key and any(k == active_key for k, _ in items):
            self._active_key = active_key
        elif items and self._active_key not in [k for k, _ in items]:
            self._active_key = items[0][0]
        self.update()

    def current_key(self) -> str:
        return self._active_key

    def current_label(self) -> str:
        for k, lbl in self._items:
            if k == self._active_key:
                return lbl
        return self._active_key

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
        if event.button() == Qt.LeftButton and self._items:
            event.accept()
            pop = _SearchComboPopup(self._items, self)
            pop_w = max(230, self.width())
            pop_h = min(280, 62 + len(self._items) * 36)
            pop.setFixedSize(pop_w, pop_h)
            pop.selected.connect(self._on_selected)
            gp = self.mapToGlobal(QPoint(0, self.height() + 4))
            pop.move(gp)
            pop.show()
            pop.search_edit.setFocus()
            return
        super().mouseReleaseEvent(event)

    def _on_selected(self, key: str, _label: str) -> None:
        if key != self._active_key:
            self._active_key = key
            self.update()
            self.changed.emit(key)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(T.c("surface_hi", alpha=165) if self._hover else T.c("bg1"))
        p.setPen(QPen(T.c("border_hi" if self._hover else "border"), 1.0))
        p.drawRoundedRect(r, 11.0, 11.0)

        is_rtl = I18N.is_rtl()
        lead_pad = 12
        if self._icon:
            ic_x = (r.right() - 26) if is_rtl else (r.left() + 10)
            draw_icon(p, self._icon, QRectF(ic_x, r.center().y() - 7.5, 15, 15), color=T.c("accent_hi"))
            lead_pad = 30

        p.setFont(app_font(12, QFont.DemiBold))
        p.setPen(T.c("text"))
        text_rect = r.adjusted(28 if is_rtl else lead_pad, 0, -lead_pad if is_rtl else -28, 0)
        elided = p.fontMetrics().elidedText(self.current_label(), Qt.ElideRight, int(text_rect.width()))
        p.drawText(text_rect, rtl_text_flags(True, True), tl(elided))

        chev_x = r.left() + 9 if is_rtl else r.right() - 24
        draw_icon(p, "chevron_down", QRectF(chev_x, r.center().y() - 7.0, 14, 14), color=T.c("text2"))
        p.end()


class NumberInput(QWidget):
    valueChanged = Signal(int)

    def __init__(self, value: int = 3, min_val: int = 1, max_val: int = 16, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._val = value
        self._min = min_val
        self._max = max_val
        self._hover_zone: int = 0
        self.setFixedSize(112, 36)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def value(self) -> int:
        return self._val

    def set_value(self, v: int, emit_sig: bool = False) -> None:
        nv = max(self._min, min(self._max, v))
        if nv != self._val:
            self._val = nv
            self.update()
            if emit_sig:
                self.valueChanged.emit(nv)

    def mouseMoveEvent(self, event) -> None:
        x = event.position().x()
        if x < 34:
            z = -1
        elif x > self.width() - 34:
            z = 1
        else:
            z = 0
        if z != self._hover_zone:
            self._hover_zone = z
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_zone = 0
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()
            x = event.position().x()
            if x < 34:
                self.set_value(self._val - 1, True)
            elif x > self.width() - 34:
                self.set_value(self._val + 1, True)
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(T.c("bg1"))
        p.setPen(QPen(T.c("border"), 1.0))
        p.drawRoundedRect(r, 11.0, 11.0)

        left_btn = QRectF(r.left() + 3, r.top() + 3, 28, r.height() - 6)
        right_btn = QRectF(r.right() - 31, r.top() + 3, 28, r.height() - 6)

        if self._hover_zone == -1:
            p.setBrush(T.c("surface_hi"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(left_btn, 8.0, 8.0)
        elif self._hover_zone == 1:
            p.setBrush(T.c("surface_hi"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(right_btn, 8.0, 8.0)

        p.setFont(app_font(15, QFont.Bold))
        p.setPen(T.c("text2") if self._val <= self._min else T.c("text"))
        p.drawText(left_btn, int(Qt.AlignCenter), "−")

        p.setPen(T.c("text2") if self._val >= self._max else T.c("text"))
        p.drawText(right_btn, int(Qt.AlignCenter), "+")

        p.setFont(app_font(13, QFont.ExtraBold))
        p.setPen(T.c("accent_hi"))
        p.drawText(r, int(Qt.AlignCenter), str(self._val))
        p.end()


class GlassCard(QWidget):
    def __init__(self, radius: float = 20.0, opaque: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self._opaque = opaque
        self._accent_bar_color: Optional[QColor] = None

    def set_accent_bar(self, color: Optional[QColor]) -> None:
        self._accent_bar_color = color
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.2, 1.2, -1.2, -1.2)

        is_dark = T.effective_mode() == "dark"
        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        if self._opaque:
            c_top = T.c("surface", alpha=255)
            c_bot = T.c("bg1", alpha=255) if is_dark else T.c("surface", alpha=255)
            border_pen = QPen(T.c("border_hi"), 1.35)
        else:
            c_top = T.c("surface_hi", alpha=205) if is_dark else T.c("surface", alpha=255)
            c_bot = T.c("glass", alpha=215) if is_dark else T.c("glass", alpha=252)
            border_pen = QPen(T.c("border"), 1.1)

        grad.setColorAt(0.0, c_top)
        grad.setColorAt(1.0, c_bot)

        p.setBrush(grad)
        p.setPen(border_pen)
        p.drawRoundedRect(r, self._radius, self._radius)

        if self._accent_bar_color is not None:
            is_rtl = I18N.is_rtl()
            bar_w = 5.0
            bar_rect = QRectF(
                r.right() - bar_w if is_rtl else r.left(),
                r.top() + 12,
                bar_w,
                r.height() - 24,
            )
            p.setBrush(self._accent_bar_color)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(bar_rect, 2.5, 2.5)
        p.end()


class ToastOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._msg: str = ""
        self._kind: str = "info"
        self.setFixedSize(480, 46)
        self.hide()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_toast(self, message: str, kind: str = "info", duration_ms: int = 2800) -> None:
        self._msg = message
        self._kind = kind
        if self.parentWidget():
            pw = self.parentWidget().width()
            ph = self.parentWidget().height()
            self.move((pw - self.width()) // 2, ph - self.height() - 24)
        self.show()
        self.raise_()
        self.update()
        self._timer.start(duration_ms)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        border_col = T.c("accent")
        if self._kind == "ok":
            border_col = T.c("ok")
        elif self._kind == "danger":
            border_col = T.c("danger")
        elif self._kind == "warn":
            border_col = T.c("warn")

        p.setBrush(T.c("surface_hi", alpha=248))
        p.setPen(QPen(border_col, 1.5))
        p.drawRoundedRect(r, 14.0, 14.0)

        p.setFont(app_font(12, QFont.DemiBold))
        p.setPen(T.c("text"))
        elided = p.fontMetrics().elidedText(self._msg, Qt.ElideRight, int(r.width() - 28))
        p.drawText(r.adjusted(14, 0, -14, 0), int(Qt.AlignCenter), tl(elided))
        p.end()


class SlideStack(QStackedWidget):
    """
    Page container that switches pages cleanly without attaching `QGraphicsOpacityEffect`
    to the live page widget (avoiding Qt6's QScrollArea + QGraphicsOpacityEffect bug that
    can block keyboard focus or cursor rendering inside child QLineEdit widgets).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def slide_to(self, index: int) -> None:
        if index == self.currentIndex() or index < 0 or index >= self.count():
            return
        self.setCurrentIndex(index)
        w = self.currentWidget()
        if w is not None:
            w.setGraphicsEffect(None)
            w.update()
