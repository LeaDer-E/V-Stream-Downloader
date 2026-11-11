import re
from typing import Callable, List, Optional, Tuple
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
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
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app import __app_name__, __version__
from app.domain.manager import DownloadManager
from app.i18n import I18N, force_ltr, t, tl, tp, ui_language_choices
from app.notifier import NotifierEngine
from app.state import AppState
from app.theme import T
from app.ui.about_dialog import AboutOverlay
from app.ui.icons import draw_icon, logo_pixmap, make_qicon
from app.ui.notification import NotificationPopup
from app.ui.onboarding import OnboardingOverlay
from app.ui.pages.downloads_page import DownloadsPage
from app.ui.pages.smart_link_dialog import BlobStreamHelperOverlay, SmartLinkOverlay
from app.ui.pages.subtitle_studio_page import SubtitleStudioPage
from app.ui.settings_page import SettingsPage
from app.ui.themes_page import ThemesPage
from app.ui.widgets import Button, IconButton, SearchCombo, SlideStack, ToastOverlay, app_font, rtl_text_flags

SHADOW_MARGIN = 10
SIDEBAR_COLLAPSED_W = 74
SIDEBAR_EXPANDED_W = 216
TITLEBAR_H = 44

CLIPBOARD_MEDIA_URL_RE = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube\.com/\S+|youtu\.be/\S+|vimeo\.com/\S+|tiktok\.com/\S+|"
    r"facebook\.com/\S+|fb\.watch/\S+|twitch\.tv/\S+|soundcloud\.com/\S+|\S+\.m3u8(?:\?\S*)?)$",
    re.IGNORECASE,
)


class TitleBar(QWidget):
    minimizeClicked = Signal()
    maximizeClicked = Signal()
    closeClicked = Signal()
    themeToggleRequested = Signal()
    langSelected = Signal(str)

    def __init__(self, state: AppState, parent: QWidget) -> None:
        super().__init__(parent)
        self.state = state
        self.setFixedHeight(TITLEBAR_H)
        self.setLayoutDirection(Qt.LeftToRight)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 8, 0)
        lay.setSpacing(6)

        self.logo_lbl = QLabel()
        self.logo_lbl.setPixmap(logo_pixmap(26))
        self.logo_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.logo_lbl)

        self.title_lbl = QLabel(force_ltr(__app_name__))
        self.title_lbl.setFont(app_font(13, QFont.ExtraBold))
        self.title_lbl.setStyleSheet(f"color: {T.token_str('text')};")
        self.title_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.title_lbl)

        short_ver = ".".join(__version__.split(".")[:2])
        self.ver_pill = QLabel(force_ltr(f"PRO {short_ver}"))
        self.ver_pill.setFont(app_font(10, QFont.ExtraBold))
        self.ver_pill.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.ver_pill)

        lay.addStretch(1)

        # Multi-Language Drop Panel Switcher (SearchCombo with all 13 UI languages!)
        self.combo_lang = SearchCombo(
            ui_language_choices(),
            self.state.config.language,
            min_width=138,
            height=30,
            icon_name="globe",
            parent=self,
        )
        self.combo_lang.setToolTip(t("tray_toggle_lang"))
        self.combo_lang.changed.connect(self.langSelected.emit)
        lay.addWidget(self.combo_lang)

        is_dark = T.effective_mode() == "dark"
        self.btn_theme = Button(
            t("mode_light") if is_dark else t("mode_dark"),
            icon_name="sun" if is_dark else "moon",
            variant="glass",
            height=30,
            compact=True,
            parent=self,
        )
        self.btn_theme.setToolTip(t("tray_toggle_theme"))
        self.btn_theme.clicked.connect(self.themeToggleRequested.emit)
        lay.addWidget(self.btn_theme)

        lay.addSpacing(4)

        self.btn_min = IconButton("minimize", size=32, width=38, parent=self)
        self.btn_max = IconButton("maximize", size=32, width=38, parent=self)
        self.btn_close = IconButton("close", size=32, width=38, danger_hover=True, parent=self)

        self.btn_min.clicked.connect(self.minimizeClicked.emit)
        self.btn_max.clicked.connect(self.maximizeClicked.emit)
        self.btn_close.clicked.connect(self.closeClicked.emit)

        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.logo_lbl.setPixmap(logo_pixmap(26))
        self.title_lbl.setStyleSheet(f"color: {T.token_str('text')};")
        self.ver_pill.setStyleSheet(
            f"background: {T.token_str('surface_hi')}; color: {T.token_str('accent_hi')}; "
            f"border: 1px solid {T.token_str('border_hi')}; border-radius: 6px; padding: 2px 7px;"
        )
        self.combo_lang.set_items(ui_language_choices(), self.state.config.language)
        is_dark = T.effective_mode() == "dark"
        self.btn_theme.set_icon("sun" if is_dark else "moon")
        self.btn_theme.setText(t("mode_light") if is_dark else t("mode_dark"))
        self.update()

    def is_in_controls_zone(self, pos: QPoint) -> bool:
        if pos.x() >= self.combo_lang.x() - 10:
            return True
        for btn in (self.combo_lang, self.btn_theme, self.btn_min, self.btn_max, self.btn_close):
            if btn.geometry().adjusted(-4, -6, 4, 6).contains(pos):
                return True
        return False

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if not self.is_in_controls_zone(pos):
                win = self.window().windowHandle()
                if win is not None:
                    win.startSystemMove()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self.is_in_controls_zone(event.position().toPoint()):
            self.maximizeClicked.emit()
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(T.c("border", alpha=110), 1.0))
        p.drawLine(14, self.height() - 1, self.width() - 14, self.height() - 1)
        p.end()


class _BodyHost(QWidget):
    def __init__(self, on_geometry_change: Callable[[], None], parent: QWidget) -> None:
        super().__init__(parent)
        self._on_geometry_change = on_geometry_change

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._on_geometry_change()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._on_geometry_change()


class FloatingSidebar(QWidget):
    navSelected = Signal(int)
    aboutRequested = Signal()
    themeToggleRequested = Signal()
    langToggleRequested = Signal()
    widthChanged = Signal()

    def __init__(self, state: AppState, parent: QWidget) -> None:
        super().__init__(parent)
        self.state = state
        self._anim_w: float = float(SIDEBAR_COLLAPSED_W)
        self._active_idx: int = 0
        self._hover_idx: int = -1
        self.setMouseTracking(True)
        self.setFixedWidth(SIDEBAR_COLLAPSED_W)

        self._nav_items: List[Tuple[str, str]] = []
        self._footer_items: List[Tuple[str, str]] = []
        self.rebuild_items()

        self._anim = QPropertyAnimation(self, b"sidebarWidth", self)
        self._anim.setDuration(190)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def rebuild_items(self) -> None:
        self._nav_items = [
            ("downloads", t("nav_downloads")),
            ("subtitles", t("nav_Subtitles")),
            ("themes", t("nav_themes")),
            ("settings", t("nav_settings")),
        ]
        is_dark = T.effective_mode() == "dark"
        self._footer_items = [
            ("sun" if is_dark else "moon", t("tray_toggle_theme")),
            ("globe", t("tray_toggle_lang")),
            ("about", t("nav_about")),
        ]
        self.update()

    def set_active(self, idx: int) -> None:
        self._active_idx = idx
        self.update()

    def getSidebarWidth(self) -> float:
        return self._anim_w

    def setSidebarWidth(self, w: float) -> None:
        self._anim_w = w
        self.setFixedWidth(int(w))
        self.widthChanged.emit()
        self.update()

    sidebarWidth = Property(float, getSidebarWidth, setSidebarWidth)

    def enterEvent(self, event) -> None:
        self._anim.stop()
        self._anim.setEndValue(float(SIDEBAR_EXPANDED_W))
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_idx = -1
        self._anim.stop()
        self._anim.setEndValue(float(SIDEBAR_COLLAPSED_W))
        self._anim.start()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        y = event.position().y()
        idx = self._hit_index(y)
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.setCursor(Qt.PointingHandCursor if idx >= 0 else Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            event.accept()
            idx = self._hit_index(event.position().y())
            if 0 <= idx < 4:
                self._active_idx = idx
                self.navSelected.emit(idx)
                self.update()
            elif idx == 10:
                self.themeToggleRequested.emit()
            elif idx == 11:
                self.langToggleRequested.emit()
            elif idx == 12:
                self.aboutRequested.emit()
            return
        super().mouseReleaseEvent(event)

    def _hit_index(self, y: float) -> int:
        top_offset = 16.0
        row_h = 48.0
        for i in range(4):
            ry = top_offset + i * row_h
            if ry <= y <= ry + 42:
                return i
        base_y = max(224.0, self.height() - 156.0)
        for j in range(3):
            fy = base_y + j * 46.0
            if fy <= y <= fy + 40:
                return 10 + j
        return -1

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(6, 6, -6, -8)

        p.setBrush(T.c("surface", alpha=246))
        p.setPen(QPen(T.c("border_hi" if self._anim_w > 90 else "border"), 1.15))
        p.drawRoundedRect(r, 18.0, 18.0)

        is_rtl = I18N.is_rtl()
        expanded_ratio = max(
            0.0,
            min(1.0, (self._anim_w - SIDEBAR_COLLAPSED_W) / float(SIDEBAR_EXPANDED_W - SIDEBAR_COLLAPSED_W)),
        )

        total_tasks = len(self.state.tasks)
        total_sub_jobs = len(self.state.sub_jobs)

        for i, (icon_name, label) in enumerate(self._nav_items):
            ry = 16.0 + i * 48.0
            item_rect = QRectF(12, ry, self.width() - 24, 42)

            is_active = i == self._active_idx
            is_hover = i == self._hover_idx

            if is_active:
                grad = QLinearGradient(item_rect.topLeft(), item_rect.bottomRight())
                grad.setColorAt(0.0, T.c("accent"))
                grad.setColorAt(1.0, T.c("accent2"))
                p.setBrush(grad)
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(item_rect, 12.0, 12.0)
                fg = T.c("on_accent")
            elif is_hover:
                p.setBrush(T.c("surface_hi", alpha=195))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(item_rect, 12.0, 12.0)
                fg = T.c("text")
            else:
                fg = T.c("text2")

            icon_x = (self.width() - 12 - 33) if is_rtl else 19
            icon_rect = QRectF(icon_x, ry + 10, 21, 21)
            draw_icon(p, icon_name, icon_rect, color=fg)

            badge_count = total_tasks if i == 0 else (total_sub_jobs if i == 1 else 0)
            if badge_count > 0 and expanded_ratio < 0.3:
                p.setBrush(T.c("ok"))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(icon_rect.right() - 1, icon_rect.top() + 2), 4.5, 4.5)

            if expanded_ratio > 0.15:
                p.save()
                p.setOpacity(expanded_ratio)
                p.setFont(app_font(13, QFont.Bold if is_active else QFont.DemiBold))
                p.setPen(fg)
                if is_rtl:
                    txt_rect = QRectF(18, ry, self.width() - 72, 42)
                else:
                    txt_rect = QRectF(50, ry, self.width() - 68, 42)
                lbl_with_cnt = f"{label} ({badge_count})" if badge_count > 0 else label
                elided = p.fontMetrics().elidedText(lbl_with_cnt, Qt.ElideRight, int(txt_rect.width()))
                p.drawText(txt_rect, rtl_text_flags(True, True), tl(elided))
                p.restore()

        base_y = max(224.0, self.height() - 156.0)
        p.setPen(QPen(T.c("border", alpha=110), 1.0))
        p.drawLine(18, int(base_y - 8), self.width() - 18, int(base_y - 8))

        for j, (icon_name, label) in enumerate(self._footer_items):
            fy = base_y + j * 46.0
            item_rect = QRectF(12, fy, self.width() - 24, 40)
            is_hover = (10 + j) == self._hover_idx
            if is_hover:
                p.setBrush(T.c("surface_hi", alpha=195))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(item_rect, 11.0, 11.0)
                fg = T.c("text")
            else:
                fg = T.c("text2")

            icon_x = (self.width() - 12 - 33) if is_rtl else 19
            icon_rect = QRectF(icon_x, fy + 9.5, 20, 20)
            draw_icon(p, icon_name, icon_rect, color=fg)

            if expanded_ratio > 0.15:
                p.save()
                p.setOpacity(expanded_ratio)
                p.setFont(app_font(12, QFont.DemiBold))
                p.setPen(fg)
                if is_rtl:
                    txt_rect = QRectF(18, fy, self.width() - 72, 40)
                else:
                    txt_rect = QRectF(50, fy, self.width() - 68, 40)
                elided = p.fontMetrics().elidedText(label, Qt.ElideRight, int(txt_rect.width()))
                p.drawText(txt_rect, rtl_text_flags(True, True), tl(elided))
                p.restore()

        p.end()



class PostQueueCountdownOverlay(QWidget):
    """
    60-second cancellable confirmation modal before executing any post-queue power action
    (Shutdown, Sleep, or Quit App). Includes a live countdown progress label,
    an "Execute Now" button, and a prominent "Cancel" button (plus Esc key support).
    """

    def __init__(self, state: AppState, manager: DownloadManager, parent: QWidget) -> None:
        super().__init__(parent)
        self.state = state
        self.manager = manager
        self._action: str = "none"
        self._remaining: int = 60
        self.setFocusPolicy(Qt.StrongFocus)
        self.hide()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        self.card = QWidget(self)
        self.card.setFixedSize(460, 230)
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(28, 22, 28, 22)
        card_lay.setSpacing(12)

        self.lbl_title = QLabel()
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setFont(app_font(16, QFont.ExtraBold))
        card_lay.addWidget(self.lbl_title)

        self.lbl_desc = QLabel()
        self.lbl_desc.setAlignment(Qt.AlignCenter)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setFont(app_font(12, QFont.Bold))
        card_lay.addWidget(self.lbl_desc)

        card_lay.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_cancel = Button("", icon_name="close", variant="primary", height=38)
        self.btn_cancel.clicked.connect(self.cancel_countdown)
        self.btn_now = Button("", icon_name="check", variant="danger", height=38)
        self.btn_now.clicked.connect(self._execute_immediately)
        btn_row.addWidget(self.btn_cancel, 1)
        btn_row.addWidget(self.btn_now, 1)
        card_lay.addLayout(btn_row)

        root.addWidget(self.card)

    def start_countdown(self, action: str) -> None:
        if not action or action == "none":
            return
        self._action = action
        self._remaining = 60
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        self._refresh_labels()
        self.show()
        self.raise_()
        self.setFocus()
        self._timer.start()

    def _on_tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            act = self._action
            self._action = "none"
            self.hide()
            self.manager.execute_power_action_now(act)
            return
        self._refresh_labels()

    def _execute_immediately(self) -> None:
        self._timer.stop()
        act = self._action
        self._action = "none"
        self.hide()
        self.manager.execute_power_action_now(act)

    def cancel_countdown(self) -> None:
        self._timer.stop()
        self._action = "none"
        self.hide()
        self.state.toast_requested.emit(
            tp("تم إلغاء الإجراء التلقائي بنجاح", "Post-queue action canceled"),
            "info",
        )

    def _refresh_labels(self) -> None:
        self.lbl_title.setText(
            tp("اكتملت جميع التحميلات — تأكيد الإجراء التلقائي", "All Downloads Finished — Confirm Action")
        )
        self.lbl_title.setStyleSheet(f"color: {T.token_str('text')};")

        if self._action == "shutdown":
            msg = tp(
                f"سيتم إيقاف تشغيل الكمبيوتر تلقائياً خلال {self._remaining} ثانية...",
                f"Computer will shut down automatically in {self._remaining}s...",
            )
        elif self._action == "sleep":
            msg = tp(
                f"سيتم إدخال الكمبيوتر في وضع السكون خلال {self._remaining} ثانية...",
                f"Computer will enter sleep mode in {self._remaining}s...",
            )
        else:
            msg = tp(
                f"سيتم إغلاق البرنامج تلقائياً خلال {self._remaining} ثانية...",
                f"Application will close automatically in {self._remaining}s...",
            )
        self.lbl_desc.setText(msg)
        self.lbl_desc.setStyleSheet(f"color: {T.token_str('warn')};")

        self.btn_cancel.setText(t("btn_cancel"))
        self.btn_now.setText(tp("تنفيذ الآن", "Execute Now"))
        self.card.setStyleSheet(
            f"background: {T.token_str('surface')}; border: 1.5px solid {T.token_str('border_hi')}; border-radius: 20px;"
        )
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.cancel_countdown()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), T.c("bg0", alpha=210, force_dark=True))
        p.end()


class MainWindow(QWidget):
    def __init__(self, state: AppState, manager: DownloadManager) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(960, 640)
        self.resize(1180, 760)
        self.setMouseTracking(True)

        self.state = state
        self.manager = manager
        self.notifier = NotifierEngine(self.state)
        self._last_clipboard_url: str = ""

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN)
        self._outer_layout.setSpacing(0)

        self.shell = QWidget(self)
        self.shell.setMouseTracking(True)
        self._outer_layout.addWidget(self.shell)

        self.shell_layout = QVBoxLayout(self.shell)
        self.shell_layout.setContentsMargins(0, 0, 0, 0)
        self.shell_layout.setSpacing(0)

        self.title_bar = TitleBar(self.state, self.shell)
        self.title_bar.minimizeClicked.connect(self.showMinimized)
        self.title_bar.maximizeClicked.connect(self._toggle_max_restore)
        self.title_bar.closeClicked.connect(self._on_close_requested)
        self.title_bar.themeToggleRequested.connect(self._toggle_theme_mode)
        self.title_bar.langSelected.connect(self._set_language)
        self.shell_layout.addWidget(self.title_bar)

        self.body_host = _BodyHost(self._position_floating_children, self.shell)
        self.body_layout = QHBoxLayout(self.body_host)
        self.shell_layout.addWidget(self.body_host, 1)

        self.stack = SlideStack(self.body_host)
        self.body_layout.addWidget(self.stack)

        self.sidebar = FloatingSidebar(self.state, self.body_host)
        self.sidebar.navSelected.connect(self.stack.slide_to)
        self.sidebar.aboutRequested.connect(self._show_about)
        self.sidebar.themeToggleRequested.connect(self._toggle_theme_mode)
        self.sidebar.langToggleRequested.connect(lambda: self.title_bar.combo_lang.mouseReleaseEvent(
            type("DummyEvt", (), {"button": lambda: Qt.LeftButton, "accept": lambda: None})()
        ) if False else self._navigate_to_index(3))
        self.sidebar.widthChanged.connect(self._position_floating_children)

        self.smart_dialog = SmartLinkOverlay(self.state, self.manager, self.shell)
        self.blob_dialog = BlobStreamHelperOverlay(self.state, self.manager, self.shell)
        self.about_overlay = AboutOverlay(self.state, self.shell, manager=self.manager)
        self.countdown_overlay = PostQueueCountdownOverlay(self.state, self.manager, self.shell)
        self.toast = ToastOverlay(self.shell)
        self.popup_notification = NotificationPopup()

        self._crossfade_lbl: Optional[QLabel] = None
        self._onboarding: Optional[OnboardingOverlay] = None

        self._build_pages()
        self._apply_body_margins()
        self._setup_tray()
        self._connect_signals()
        self._setup_clipboard_monitor()

        if not self.state.config.first_run_completed:
            self._show_onboarding()

        QTimer.singleShot(0, self._position_floating_children)

    def _setup_clipboard_monitor(self) -> None:
        cb = QGuiApplication.clipboard()
        if cb is not None:
            self._last_clipboard_url = cb.text().strip()
            cb.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self) -> None:
        if not self.state.config.auto_paste_clipboard:
            return
        cb = QGuiApplication.clipboard()
        if cb is None:
            return
        txt = cb.text().strip()
        if not txt or txt == self._last_clipboard_url:
            return
        if CLIPBOARD_MEDIA_URL_RE.match(txt):
            self._last_clipboard_url = txt
            self.page_downloads.url_input.setText(txt)
            self.manager.analyze_link(txt)

    def _toggle_theme_mode(self) -> None:
        new_mode = "light" if T.effective_mode() == "dark" else "dark"
        self.state.config.theme_mode = new_mode
        T.set_theme(self.state.config.palette_id, new_mode, self.state.config.custom_accent)
        self.state.config.save()
        self.state.theme_changed.emit()
        self.state.toast_requested.emit(
            tp(
                "تم التبديل إلى الوضع الفاتح" if new_mode == "light" else "تم التبديل إلى الوضع الداكن",
                "Switched to Light Mode" if new_mode == "light" else "Switched to Dark Mode",
            ),
            "info",
        )

    def _set_language(self, new_lang: str) -> None:
        if not new_lang or new_lang == self.state.config.language:
            return
        self.state.config.language = new_lang
        self.state.config.save()
        self.state.language_changed.emit(new_lang)
        lang_disp = dict(ui_language_choices()).get(new_lang, new_lang)
        self.state.toast_requested.emit(f"✓ {lang_disp}", "info")

    def _toggle_language(self) -> None:
        new_lang = "en" if self.state.config.language == "ar" else "ar"
        self._set_language(new_lang)

    def _build_pages(self) -> None:
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.hide()
            w.setParent(None)
            w.deleteLater()

        self.page_downloads = DownloadsPage(
            self.state,
            self.manager,
            on_open_smart_dialog=self.smart_dialog.open_for_info,
            on_navigate_page=self._navigate_to_index,
            parent=self.stack,
        )
        self.page_subtitles = SubtitleStudioPage(self.state, self.manager, self.stack)
        self.page_themes = ThemesPage(self.state, self.stack)
        self.page_settings = SettingsPage(self.state, self.manager, self.stack)

        self.stack.addWidget(self.page_downloads)
        self.stack.addWidget(self.page_subtitles)
        self.stack.addWidget(self.page_themes)
        self.stack.addWidget(self.page_settings)

    def _navigate_to_index(self, idx: int) -> None:
        if 0 <= idx < self.stack.count():
            self.stack.slide_to(idx)
            self.sidebar.set_active(idx)

    def _apply_body_margins(self) -> None:
        if I18N.is_rtl():
            self.body_layout.setContentsMargins(0, 0, SIDEBAR_COLLAPSED_W, 0)
        else:
            self.body_layout.setContentsMargins(SIDEBAR_COLLAPSED_W, 0, 0, 0)
        self._position_floating_children()

    def _position_floating_children(self) -> None:
        bh = max(420, self.body_host.height())
        bw = max(600, self.body_host.width())
        sw = self.sidebar.width()
        if I18N.is_rtl():
            self.sidebar.setGeometry(bw - sw, 0, sw, bh)
        else:
            self.sidebar.setGeometry(0, 0, sw, bh)
        self.sidebar.raise_()

        if self.smart_dialog.isVisible():
            self.smart_dialog.setGeometry(self.shell.rect())
            self.smart_dialog.raise_()
        if self.blob_dialog.isVisible():
            self.blob_dialog.setGeometry(self.shell.rect())
            self.blob_dialog.raise_()
        if self.about_overlay.isVisible():
            self.about_overlay.setGeometry(self.shell.rect())
            self.about_overlay.raise_()
        if self.countdown_overlay.isVisible():
            self.countdown_overlay.setGeometry(self.shell.rect())
            self.countdown_overlay.raise_()
        if self._onboarding is not None and self._onboarding.isVisible():
            self.onboarding_geometry()
        if self.toast.isVisible():
            self.toast.raise_()

    def onboarding_geometry(self) -> None:
        if self._onboarding is not None:
            self._onboarding.setGeometry(self.shell.rect())
            self._onboarding.raise_()

    def _show_onboarding(self) -> None:
        self._onboarding = OnboardingOverlay(self.state, on_complete=lambda: None, parent=self.shell)
        self._onboarding.setGeometry(self.shell.rect())
        self._onboarding.show()
        self._onboarding.raise_()

    def _show_about(self) -> None:
        self.about_overlay.show_modal()

    def _connect_signals(self) -> None:
        self.state.theme_changed.connect(self._on_theme_or_lang_rebuild)
        self.state.language_changed.connect(self._on_lang_changed)
        self.state.toast_requested.connect(self.toast.show_toast)
        self.notifier.popup_triggered.connect(self.popup_notification.show_notification)
        self.state.queue_changed.connect(self._on_queue_changed)
        self.state.blob_help_requested.connect(self.blob_dialog.open_for_blob)
        self.state.post_queue_countdown_requested.connect(self.countdown_overlay.start_countdown)

    def _on_queue_changed(self) -> None:
        self.sidebar.update()
        self._refresh_tray_menu()

    def _on_lang_changed(self, lang: str) -> None:
        I18N.set_language(lang)
        self._on_theme_or_lang_rebuild()

    def _on_theme_or_lang_rebuild(self) -> None:
        current_idx = self.stack.currentIndex()
        modal_open = any(
            w is not None and w.isVisible()
            for w in (self._onboarding, self.smart_dialog, self.blob_dialog, self.about_overlay, self.countdown_overlay)
        )

        if self._crossfade_lbl is not None:
            self._crossfade_lbl.hide()
            self._crossfade_lbl.deleteLater()
            self._crossfade_lbl = None

        overlay: Optional[QLabel] = None
        if not modal_open:
            snapshot = self.shell.grab()
            overlay = QLabel(self.shell)
            overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            overlay.setPixmap(snapshot)
            overlay.setGeometry(self.shell.rect())
            overlay.show()
            overlay.raise_()
            self._crossfade_lbl = overlay

        self.setWindowIcon(QIcon(logo_pixmap(64)))
        self.title_bar.refresh_theme()
        self.sidebar.rebuild_items()
        self._apply_body_margins()
        self._build_pages()
        self.stack.setCurrentIndex(max(0, current_idx))
        self.sidebar.set_active(max(0, current_idx))
        self.smart_dialog.refresh_theme()
        self.blob_dialog.refresh_theme()
        self.about_overlay.refresh_ui()
        if self._onboarding is not None:
            self._onboarding.refresh_ui()
        if self.countdown_overlay.isVisible():
            self.countdown_overlay._refresh_labels()
        self._refresh_tray_menu()
        self._position_floating_children()
        self.shell.update()
        self.update()
        QTimer.singleShot(0, self._position_floating_children)

        if overlay is not None:
            eff = QGraphicsOpacityEffect(overlay)
            overlay.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(260)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _cleanup() -> None:
                overlay.hide()
                overlay.setParent(None)
                overlay.deleteLater()
                if self._crossfade_lbl is overlay:
                    self._crossfade_lbl = None

            anim.finished.connect(_cleanup)
            self._fade_anim = anim
            anim.start()

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(logo_pixmap(32)))
        self.tray.setToolTip(__app_name__)
        self.tray_menu = QMenu()
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self._refresh_tray_menu()
        self.tray.show()

    def _refresh_tray_menu(self) -> None:
        self.tray.setIcon(QIcon(logo_pixmap(32)))
        self.tray_menu.clear()
        self.tray_menu.setStyleSheet(
            f"QMenu {{ background: {T.token_str('surface')}; color: {T.token_str('text')}; "
            f"border: 1px solid {T.token_str('border_hi')}; border-radius: 12px; padding: 6px; }}"
            f"QMenu::item {{ padding: 7px 16px; border-radius: 8px; }}"
            f"QMenu::item:selected {{ background: {T.token_str('accent')}; color: #FFFFFF; }}"
        )

        active_n = self.state.active_count()
        status_txt = t("tray_status_active", count=active_n) if active_n > 0 else t("tray_status_idle")
        act_status = self.tray_menu.addAction(make_qicon("downloads", color=T.c("accent_hi")), status_txt)
        act_status.setEnabled(False)
        self.tray_menu.addSeparator()

        act_open = self.tray_menu.addAction(make_qicon("play"), t("tray_show_window"))
        act_open.triggered.connect(self._restore_from_tray)

        act_notify = self.tray_menu.addAction(
            make_qicon("bell", color=T.c("ok" if self.state.config.notifications_enabled else "text3")),
            t("tray_toggle_notify"),
        )
        act_notify.triggered.connect(self._tray_toggle_notify)

        act_theme = self.tray_menu.addAction(make_qicon("moon"), t("tray_toggle_theme"))
        act_theme.triggered.connect(self._toggle_theme_mode)

        lang_submenu = self.tray_menu.addMenu(make_qicon("globe"), t("tray_toggle_lang"))
        for l_code, l_label in ui_language_choices():
            act_l = lang_submenu.addAction(l_label)
            act_l.triggered.connect(lambda _checked=False, lc=l_code: self._set_language(lc))

        self.tray_menu.addSeparator()
        act_quit = self.tray_menu.addAction(make_qicon("close", color=T.c("danger")), t("tray_quit"))
        act_quit.triggered.connect(self._quit_app)

    def _tray_toggle_notify(self) -> None:
        self.state.config.notifications_enabled = not self.state.config.notifications_enabled
        self.state.config.save()
        self._refresh_tray_menu()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _toggle_max_restore(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _on_close_requested(self) -> None:
        if self.state.config.minimize_to_tray and self.tray.isVisible():
            self.hide()
        else:
            self._quit_app()

    def _quit_app(self) -> None:
        self.manager.shutdown()
        self.tray.hide()
        QApplication.quit()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.WindowStateChange:
            m = 0 if self.isMaximized() else SHADOW_MARGIN
            self._outer_layout.setContentsMargins(m, m, m, m)
            self.update()
            QTimer.singleShot(0, self._position_floating_children)
        super().changeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._position_floating_children()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_floating_children()

    def _detect_resize_edges(self, pos: QPoint) -> Qt.Edges:
        if self.isMaximized():
            return Qt.Edges()
        if pos.y() <= SHADOW_MARGIN + TITLEBAR_H and pos.x() >= self.width() - 360:
            return Qt.Edges()
        m = SHADOW_MARGIN + 2
        edges = Qt.Edges()
        if pos.x() <= m:
            edges |= Qt.LeftEdge
        elif pos.x() >= self.width() - m:
            edges |= Qt.RightEdge
        if pos.y() <= m:
            edges |= Qt.TopEdge
        elif pos.y() >= self.height() - m:
            edges |= Qt.BottomEdge
        return edges

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            edges = self._detect_resize_edges(event.position().toPoint())
            if edges and self.windowHandle() is not None:
                self.windowHandle().startSystemResize(edges)
                return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        if not self.isMaximized():
            for i in range(SHADOW_MARGIN, 0, -2):
                alpha = int(28 * (1.0 - i / float(SHADOW_MARGIN)))
                sr = QRectF(self.rect()).adjusted(i, i, -i, -i)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(0, 0, 0, alpha), 2.0))
                p.drawRoundedRect(sr, 20.0 + i * 0.4, 20.0 + i * 0.4)

        shell_rect = QRectF(self.shell.geometry())
        radius = 0.0 if self.isMaximized() else 20.0

        bg_grad = QLinearGradient(shell_rect.topLeft(), shell_rect.bottomRight())
        bg_grad.setColorAt(0.0, T.c("bg0"))
        bg_grad.setColorAt(1.0, T.c("bg1"))

        p.setBrush(bg_grad)
        p.setPen(QPen(T.c("border"), 1.1))
        p.drawRoundedRect(shell_rect, radius, radius)
        p.end()
