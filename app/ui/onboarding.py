from typing import Callable, Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.i18n import I18N, t, tp, ui_language_choices
from app.paths import set_windows_startup
from app.state import AppState
from app.theme import PALETTE_SPECS, T
from app.ui.icons import logo_pixmap
from app.ui.widgets import (
    Button,
    GlassCard,
    SearchCombo,
    SegmentedControl,
    SlideStack,
    ToggleSwitch,
    app_font,
)


class _ProgressDots(QWidget):
    def __init__(self, total: int = 3, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._total = total
        self._current = 0
        self.setFixedSize(120, 20)

    def set_step(self, step: int) -> None:
        self._current = max(0, min(self._total - 1, step))
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx = self.width() / 2.0 - ((self._total - 1) * 22) / 2.0
        cy = self.height() / 2.0
        for i in range(self._total):
            x = cx + i * 22
            if i == self._current:
                p.setBrush(T.c("accent"))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(x - 10, cy - 4, 20, 8), 4, 4)
            else:
                p.setBrush(T.c("text3", alpha=140))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x, cy), 4, 4)
        p.end()


class OnboardingOverlay(QWidget):
    """
    First-run setup wizard that dynamically updates 100% of its labels, controls,
    steps (Step 1, Step 2, Step 3), layout direction (RTL/LTR), and theme colors
    (Light Mode & Dark Mode) the instant the user picks a language or switches appearance mode.
    """

    def __init__(self, state: AppState, on_complete: Callable[[], None], parent: QWidget) -> None:
        super().__init__(parent)
        self.state = state
        self.on_complete = on_complete

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        self.card = GlassCard(radius=28.0, opaque=True, parent=self)
        self.card.setFixedSize(640, 480)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(32, 22, 32, 22)
        lay.setSpacing(10)

        self.logo_lbl = QLabel()
        self.logo_lbl.setPixmap(logo_pixmap(58))
        self.logo_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.logo_lbl)

        self.title_lbl = QLabel()
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setFont(app_font(19, QFont.ExtraBold))
        lay.addWidget(self.title_lbl)

        self.step_sub_lbl = QLabel()
        self.step_sub_lbl.setAlignment(Qt.AlignCenter)
        self.step_sub_lbl.setFont(app_font(12, QFont.Bold))
        lay.addWidget(self.step_sub_lbl)

        lay.addSpacing(4)

        self.stack = SlideStack()
        self.step1_widget = self._build_step1()
        self.step2_widget = self._build_step2()
        self.step3_widget = self._build_step3()
        self.stack.addWidget(self.step1_widget)
        self.stack.addWidget(self.step2_widget)
        self.stack.addWidget(self.step3_widget)
        lay.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        self.btn_prev = Button("", variant="ghost", height=38)
        self.btn_prev.clicked.connect(self._prev_step)
        self.dots = _ProgressDots(3)
        self.btn_next = Button("", variant="primary", height=38)
        self.btn_next.clicked.connect(self._next_step)

        nav.addWidget(self.btn_prev)
        nav.addStretch(1)
        nav.addWidget(self.dots)
        nav.addStretch(1)
        nav.addWidget(self.btn_next)
        lay.addLayout(nav)

        root.addWidget(self.card)

        self.state.theme_changed.connect(self.refresh_ui)
        self.state.language_changed.connect(lambda _lang: self.refresh_ui())
        self.refresh_ui()

    def _build_step1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 6, 4, 6)
        v.setSpacing(16)

        r1 = QHBoxLayout()
        self.lbl_lang = QLabel()
        self.lbl_lang.setFont(app_font(13, QFont.Bold))
        self.combo_lang = SearchCombo(
            ui_language_choices(),
            self.state.config.language,
            min_width=220,
            icon_name="globe",
        )
        self.combo_lang.changed.connect(self._on_lang_picked)
        r1.addWidget(self.lbl_lang)
        r1.addStretch(1)
        r1.addWidget(self.combo_lang)
        v.addLayout(r1)

        r2 = QHBoxLayout()
        self.lbl_mode = QLabel()
        self.lbl_mode.setFont(app_font(13, QFont.Bold))
        self.seg_mode = SegmentedControl(
            [("dark", t("mode_dark")), ("light", t("mode_light")), ("auto", t("mode_auto"))],
            self.state.config.theme_mode,
            compact=True,
        )
        self.seg_mode.changed.connect(self._on_mode_picked)
        r2.addWidget(self.lbl_mode)
        r2.addStretch(1)
        r2.addWidget(self.seg_mode)
        v.addLayout(r2)

        r3 = QHBoxLayout()
        self.lbl_st = QLabel()
        self.lbl_st.setFont(app_font(13, QFont.Bold))
        self.sw_st = ToggleSwitch(self.state.config.run_on_startup)

        def _toggle_st(val: bool) -> None:
            self.state.config.run_on_startup = val
            set_windows_startup(val)
            self.state.config.save()

        self.sw_st.toggled.connect(_toggle_st)
        r3.addWidget(self.lbl_st)
        r3.addStretch(1)
        r3.addWidget(self.sw_st)
        v.addLayout(r3)
        v.addStretch(1)
        return w

    def _build_step2(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 6, 4, 6)
        v.setSpacing(14)

        self.lbl_dir_hdr = QLabel()
        self.lbl_dir_hdr.setFont(app_font(13, QFont.Bold))
        v.addWidget(self.lbl_dir_hdr)

        r_dir = QHBoxLayout()
        self.dir_lbl = QLabel(self.state.config.download_dir)
        self.dir_lbl.setFont(app_font(12, QFont.DemiBold))
        self.btn_browse = Button("", icon_name="folder", variant="glass", height=36, compact=True)
        self.btn_browse.clicked.connect(self._pick_folder)
        r_dir.addWidget(self.dir_lbl, 1)
        r_dir.addWidget(self.btn_browse)
        v.addLayout(r_dir)

        r_num = QHBoxLayout()
        self.lbl_num = QLabel()
        self.lbl_num.setWordWrap(True)
        self.lbl_num.setFont(app_font(12, QFont.DemiBold))
        self.sw_num = ToggleSwitch(self.state.config.smart_numbering)
        self.sw_num.toggled.connect(lambda val: setattr(self.state.config, "smart_numbering", val))
        r_num.addWidget(self.lbl_num, 1)
        r_num.addWidget(self.sw_num)
        v.addLayout(r_num)

        r_bidi = QHBoxLayout()
        self.lbl_bidi = QLabel()
        self.lbl_bidi.setWordWrap(True)
        self.lbl_bidi.setFont(app_font(12, QFont.DemiBold))
        self.sw_bidi = ToggleSwitch(self.state.config.enforce_bidi_rtl_fix)
        self.sw_bidi.toggled.connect(lambda val: setattr(self.state.config, "enforce_bidi_rtl_fix", val))
        r_bidi.addWidget(self.lbl_bidi, 1)
        r_bidi.addWidget(self.sw_bidi)
        v.addLayout(r_bidi)

        v.addStretch(1)
        return w

    def _build_step3(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 6, 4, 6)
        v.setSpacing(14)

        self.lbl_pal = QLabel()
        self.lbl_pal.setFont(app_font(13, QFont.Bold))
        v.addWidget(self.lbl_pal)

        items = [(pid, tp(ar, en)) for pid, ar, en, _ in PALETTE_SPECS]
        self.combo_pal = SearchCombo(items, self.state.config.palette_id, height=38)
        self.combo_pal.changed.connect(self._on_palette_picked)
        v.addWidget(self.combo_pal)

        v.addStretch(1)

        self.lbl_legal_note = QLabel()
        self.lbl_legal_note.setWordWrap(True)
        self.lbl_legal_note.setAlignment(Qt.AlignCenter)
        self.lbl_legal_note.setFont(app_font(10, QFont.Medium))
        v.addWidget(self.lbl_legal_note)
        return w

    def refresh_ui(self) -> None:
        """
        Refreshes all texts, combo items, segmented controls, layout directions (RTL/LTR),
        and high-contrast theme colors across all 3 steps immediately!
        """
        direction = Qt.RightToLeft if I18N.is_rtl() else Qt.LeftToRight
        self.setLayoutDirection(direction)
        self.card.setLayoutDirection(direction)
        self.step1_widget.setLayoutDirection(direction)
        self.step2_widget.setLayoutDirection(direction)
        self.step3_widget.setLayoutDirection(direction)

        self.logo_lbl.setPixmap(logo_pixmap(58))

        self.title_lbl.setText(t("onboarding_welcome"))
        self.title_lbl.setStyleSheet(f"color: {T.token_str('text')};")

        # Step 1 texts & colors
        self.lbl_lang.setText(tp("لغة الواجهة:", "Interface Language:"))
        self.lbl_lang.setStyleSheet(f"color: {T.token_str('text')};")
        self.combo_lang.set_items(ui_language_choices(), self.state.config.language)

        self.lbl_mode.setText(tp("نمط المظهر:", "Appearance Mode:"))
        self.lbl_mode.setStyleSheet(f"color: {T.token_str('text')};")
        self.seg_mode.set_items(
            [("dark", t("mode_dark")), ("light", t("mode_light")), ("auto", t("mode_auto"))],
            self.state.config.theme_mode,
        )

        self.lbl_st.setText(tp("التشغيل التلقائي مع بدء الويندوز:", "Launch on Windows Startup:"))
        self.lbl_st.setStyleSheet(f"color: {T.token_str('text')};")

        # Step 2 texts & colors
        self.lbl_dir_hdr.setText(tp("مجلد الحفظ الافتراضي", "Default Download Folder"))
        self.lbl_dir_hdr.setStyleSheet(f"color: {T.token_str('text')};")
        self.dir_lbl.setText(self.state.config.download_dir)
        self.dir_lbl.setStyleSheet(
            f"color: {T.token_str('text')}; background: {T.token_str('bg1')}; "
            f"border: 1px solid {T.token_str('border')}; border-radius: 10px; padding: 6px 12px;"
        )
        self.btn_browse.setText(t("btn_browse"))

        self.lbl_num.setText(t("smart_numbering_toggle"))
        self.lbl_num.setStyleSheet(f"color: {T.token_str('text')};")

        self.lbl_bidi.setText(t("sub_bidi_fix"))
        self.lbl_bidi.setStyleSheet(f"color: {T.token_str('text')};")

        # Step 3 texts & colors
        self.lbl_pal.setText(tp("اختر اللوحة اللونية المفضلة:", "Select your signature color palette:"))
        self.lbl_pal.setStyleSheet(f"color: {T.token_str('text')};")
        pal_items = [(pid, tp(ar, en)) for pid, ar, en, _ in PALETTE_SPECS]
        self.combo_pal.set_items(pal_items, self.state.config.palette_id)

        self.lbl_legal_note.setText(
            tp(
                "تنويه قانوني: الأداة مخصصة للأرشفة والاستخدام الشخصي المشروع فقط مع احترام حقوق الملكية الفكرية وشروط المواقع.",
                "Legal Notice: Intended strictly for personal archiving & lawful use. Please respect copyright and platform Terms of Service.",
            )
        )
        self.lbl_legal_note.setStyleSheet(f"color: {T.token_str('text2')};")

        self.btn_prev.setText(t("onboarding_prev"))
        self._sync_nav()
        self.dots.update()
        self.card.update()
        self.update()

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("btn_browse"), self.state.config.download_dir)
        if folder:
            self.state.config.download_dir = folder
            self.dir_lbl.setText(folder)

    def _on_lang_picked(self, lang: str) -> None:
        I18N.set_language(lang)
        self.state.config.language = lang
        self.state.config.save()
        self.refresh_ui()
        self.state.language_changed.emit(lang)

    def _on_mode_picked(self, mode: str) -> None:
        self.state.config.theme_mode = mode
        T.set_theme(self.state.config.palette_id, mode, self.state.config.custom_accent)
        self.state.config.save()
        self.refresh_ui()
        self.state.theme_changed.emit()

    def _on_palette_picked(self, pid: str) -> None:
        self.state.config.palette_id = pid
        T.set_theme(pid, self.state.config.theme_mode, self.state.config.custom_accent)
        self.state.config.save()
        self.refresh_ui()
        self.state.theme_changed.emit()

    def _prev_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.slide_to(idx - 1)
            self._sync_nav()

    def _next_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx < 2:
            self.stack.slide_to(idx + 1)
            self._sync_nav()
        else:
            self.state.config.first_run_completed = True
            self.state.config.save()
            self.hide()
            self.on_complete()

    def _sync_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.dots.set_step(idx)
        step_keys = ("onboarding_step1", "onboarding_step2", "onboarding_step3")
        step_title = t(step_keys[min(2, max(0, idx))])
        self.step_sub_lbl.setText(f"{idx + 1} / 3  •  {step_title}")
        self.step_sub_lbl.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        self.btn_prev.setVisible(idx > 0)
        self.btn_next.setText(t("onboarding_finish") if idx == 2 else t("onboarding_next"))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), T.c("bg0", alpha=228, force_dark=True))
        p.end()
