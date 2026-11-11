import math
from typing import Callable, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app import __app_name__, __version__
from app.domain.downloader import collect_diagnostics_report, detect_js_runtime, get_ytdlp_version
from app.domain.manager import DownloadManager
from app.i18n import force_ltr, t, tl, tp
from app.state import AppState
from app.theme import T
from app.ui.icons import draw_icon, logo_pixmap
from app.ui.widgets import Button, IconButton, app_font


class _DiamondDivider(QWidget):
    """Paints a sleek horizontal gradient rule with a centered diamond gem (`─── ◆ ───`)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(16)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w = float(self.width())
        cy = float(self.height()) / 2.0
        cx = w / 2.0

        acc = T.c("accent_hi")
        line_c = QColor(acc)
        line_c.setAlpha(95)
        edge_c = QColor(acc)
        edge_c.setAlpha(0)

        grad_l = QLinearGradient(QPointF(26.0, cy), QPointF(cx - 14.0, cy))
        grad_l.setColorAt(0.0, edge_c)
        grad_l.setColorAt(1.0, line_c)
        p.setPen(QPen(grad_l, 1.15))
        p.drawLine(QPointF(26.0, cy), QPointF(cx - 14.0, cy))

        grad_r = QLinearGradient(QPointF(cx + 14.0, cy), QPointF(w - 26.0, cy))
        grad_r.setColorAt(0.0, line_c)
        grad_r.setColorAt(1.0, edge_c)
        p.setPen(QPen(grad_r, 1.15))
        p.drawLine(QPointF(cx + 14.0, cy), QPointF(w - 26.0, cy))

        d = 4.2
        diamond = QPolygonF(
            [
                QPointF(cx, cy - d),
                QPointF(cx + d, cy),
                QPointF(cx, cy + d),
                QPointF(cx - d, cy),
            ]
        )
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawPolygon(diamond)
        p.end()


class _FeatureChip(QWidget):
    """Compact pill chip highlighting a core V-Stream Downloader capability."""

    def __init__(self, icon_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self.setFixedHeight(32)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(32, 0, 10, 0)
        lay.setSpacing(4)
        self.lbl = QLabel()
        self.lbl.setFont(app_font(11, QFont.Bold))
        lay.addWidget(self.lbl, 1)

    def set_text_and_refresh(self, text: str) -> None:
        self.lbl.setText(tl(text))
        self.lbl.setStyleSheet(f"color: {T.token_str('text')};")
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        p.setBrush(T.c("surface_hi", alpha=140))
        p.setPen(QPen(T.c("border_hi", alpha=130), 1.0))
        p.drawRoundedRect(r, 10.0, 10.0)

        ic_r = QRectF(r.left() + 8.0, r.center().y() - 8.0, 16.0, 16.0)
        draw_icon(p, self._icon_name, ic_r, color=T.c("accent_hi"), stroke_width=1.9)
        p.end()


class _DeveloperContactRow(QWidget):
    """
    Interactive rounded contact pill row:
    - Left gradient squircle icon badge (`mail` or `phone`)
    - Bold LTR contact value (`eslaam.mustafa@gmail.com` or `+20 128 344 7065`)
    - Clicking anywhere on the row triggers `on_primary_click` (opens mailto: or WhatsApp wa.me)
      with smooth hover highlighting, without duplicating the left icon!
    - Right side has an optional secondary action pill (e.g. "WhatsApp") + Copy icon button.
    """

    def __init__(
        self,
        icon_name: str,
        contact_text: str,
        on_copy: Callable[[], None],
        on_primary_click: Callable[[], None],
        action_badge_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._on_primary_click = on_primary_click
        self._hover = False
        self.setFixedHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        self.setLayoutDirection(Qt.LeftToRight)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(52, 0, 10, 0)
        lay.setSpacing(8)

        self.lbl_text = QLabel(force_ltr(contact_text))
        self.lbl_text.setFont(app_font(12, QFont.Bold))
        self.lbl_text.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(self.lbl_text)
        lay.addStretch(1)

        self.lbl_action_pill: Optional[QLabel] = None
        if action_badge_text:
            self.lbl_action_pill = QLabel(action_badge_text)
            self.lbl_action_pill.setFont(app_font(10, QFont.ExtraBold))
            self.lbl_action_pill.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lay.addWidget(self.lbl_action_pill)

        self.btn_copy = IconButton("copy", size=30, parent=self)
        self.btn_copy.clicked.connect(on_copy)
        lay.addWidget(self.btn_copy)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            if not self.btn_copy.geometry().contains(event.position().toPoint()):
                event.accept()
                self._on_primary_click()
                return
        super().mouseReleaseEvent(event)

    def refresh_style(self, copy_tooltip: str, row_tooltip: str, pill_text: str = "") -> None:
        self.lbl_text.setStyleSheet(f"color: {T.token_str('text')};")
        self.setToolTip(row_tooltip)
        self.btn_copy.setToolTip(copy_tooltip)
        if self.lbl_action_pill is not None:
            if pill_text:
                self.lbl_action_pill.setText(pill_text)
            self.lbl_action_pill.setStyleSheet(
                f"color: {T.token_str('accent_hi')}; background: {T.token_str('bg1')}; "
                f"border: 1px solid {T.token_str('border_hi')}; border-radius: 8px; padding: 2px 8px;"
            )
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)

        bg_alpha = 200 if self._hover else 140
        border_col = T.c("accent_hi") if self._hover else T.c("border_hi", alpha=165)
        p.setBrush(T.c("surface_hi", alpha=bg_alpha))
        p.setPen(QPen(border_col, 1.35 if self._hover else 1.05))
        p.drawRoundedRect(r, 13.0, 13.0)

        badge_r = QRectF(r.left() + 8.0, r.center().y() - 16.0, 32.0, 32.0)
        grad = QLinearGradient(badge_r.topLeft(), badge_r.bottomRight())
        grad.setColorAt(0.0, T.c("accent_hi").lighter(115))
        grad.setColorAt(1.0, T.c("accent"))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(badge_r, 10.0, 10.0)

        draw_icon(
            p,
            self._icon_name,
            badge_r.adjusted(7.0, 7.0, -7.0, -7.0),
            color=QColor("#FFFFFF"),
            stroke_width=2.0,
        )
        p.end()


class _AboutCardContainer(QWidget):
    # Shared geometry constants so the V-Logo badge and title label NEVER collide under any DPI or font
    BANNER_H = 88.0
    LOGO_SIZE = 66
    LOGO_OVERHANG = 30.0  # How many px the logo extends below BANNER_H
    TOP_BAR_BOTTOM = 42.0  # Top margin (10) + Close button height (32)
    LOGO_TO_TITLE_GAP = 15.0  # Guaranteed clear breathing room below logo halo

    @classmethod
    def required_top_spacer(cls) -> int:
        logo_bottom_y = cls.BANNER_H + cls.LOGO_OVERHANG + 4.0  # +4 for halo border
        return max(48, int(logo_bottom_y - cls.TOP_BAR_BOTTOM + cls.LOGO_TO_TITLE_GAP))

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        rad = 24.0

        card_path = QPainterPath()
        card_path.addRoundedRect(r, rad, rad)

        p.save()
        p.setClipPath(card_path)

        bg_grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        c_top = T.c("bg1", force_dark=True) if T.effective_mode() == "dark" else T.c("surface")
        c_bot = T.c("bg0", force_dark=True) if T.effective_mode() == "dark" else T.c("bg1")
        bg_grad.setColorAt(0.0, c_top)
        bg_grad.setColorAt(1.0, c_bot)
        p.fillPath(card_path, bg_grad)

        banner_rect = QRectF(r.left(), r.top(), r.width(), self.BANNER_H)
        ban_grad = QLinearGradient(banner_rect.topLeft(), banner_rect.bottomRight())
        acc = T.c("accent")
        acc2 = T.c("accent2")
        acc_hi = T.c("accent_hi")
        ban_grad.setColorAt(0.0, acc2.darker(190))
        ban_grad.setColorAt(0.5, acc.darker(155))
        ban_grad.setColorAt(1.0, acc_hi.darker(175))
        p.fillRect(banner_rect, ban_grad)

        cx = r.center().x()
        glow = QRadialGradient(QPointF(cx, r.top() + self.BANNER_H), r.width() * 0.45)
        glow_c1 = QColor(acc_hi)
        glow_c1.setAlpha(110)
        glow_c2 = QColor(acc)
        glow_c2.setAlpha(0)
        glow.setColorAt(0.0, glow_c1)
        glow.setColorAt(1.0, glow_c2)
        p.fillRect(banner_rect, glow)

        bar_col = QColor(255, 255, 255, 34)
        p.setBrush(bar_col)
        p.setPen(Qt.NoPen)
        num_bars = 38
        step = r.width() / float(num_bars)
        for i in range(num_bars):
            bx = r.left() + i * step + step * 0.25
            wave = abs(math.sin(i * 0.45)) * 22.0 + 5.0
            dist_center = abs((bx - cx) / (r.width() * 0.5))
            bh = wave * (0.35 + 0.65 * dist_center)
            by = r.top() + self.BANNER_H - bh
            p.drawRoundedRect(QRectF(bx, by, step * 0.48, bh), 2.0, 2.0)

        p.setPen(QPen(T.c("border_hi", alpha=130), 1.1))
        p.drawLine(QPointF(r.left(), r.top() + self.BANNER_H), QPointF(r.right(), r.top() + self.BANNER_H))

        logo_y = int(r.top() + self.BANNER_H - (self.LOGO_SIZE - self.LOGO_OVERHANG))
        logo_x = int(cx - self.LOGO_SIZE / 2.0)

        p.setBrush(T.c("bg0", alpha=225))
        p.setPen(QPen(T.c("border_hi", alpha=175), 1.4))
        halo_r = QRectF(logo_x - 3, logo_y - 3, self.LOGO_SIZE + 6, self.LOGO_SIZE + 6)
        p.drawRoundedRect(halo_r, 19.0, 19.0)

        pix = logo_pixmap(self.LOGO_SIZE)
        p.drawPixmap(logo_x, logo_y, pix)

        p.restore()

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(T.c("border_hi"), 1.35))
        p.drawRoundedRect(r, rad, rad)
        p.end()


class AboutOverlay(QWidget):
    """
    Redesigned About & Diagnostics Modal featuring:
    - Synchronized Banner & 3D V-Logo constants with a guaranteed 15px gap above the title
    - 4 scannable Feature Chips (4K/8K & Multi-Audio, Smart Playlists, BiDi Subtitles, Live HLS/m3u8)
    - Live Engine Status bar (`yt-dlp` version, `FFmpeg` status, `Copy Diagnostics`, `Check Updates`)
    - Localized Developer section (`Eslam Mustafa`, clickable email & WhatsApp `wa.me/201283447065`)
    - Argon & Claude attribution + `yt-dlp` / `FFmpeg` / `Qt PySide6 (LGPLv3)` credits + Legal Notice
    - Full `Esc` key support to close
    """

    DEV_NAME = "Eslam Mustafa"
    DEV_EMAIL = "eslaam.mustafa@gmail.com"
    DEV_PHONE = "+20 128 344 7065"
    DEV_WHATSAPP_URL = "https://wa.me/201283447065"

    def __init__(self, state: AppState, parent: QWidget, manager: Optional[DownloadManager] = None) -> None:
        super().__init__(parent)
        self.state = state
        self.manager = manager
        self.setFocusPolicy(Qt.StrongFocus)
        self.hide()

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        self.card = _AboutCardContainer(self)
        self.card.setFixedSize(560, 610)

        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(28, 10, 28, 16)
        card_lay.setSpacing(6)

        # Top-right close '×' button over the banner
        top_bar = QHBoxLayout()
        top_bar.setDirection(QHBoxLayout.LeftToRight)
        top_bar.addStretch(1)
        self.btn_close = IconButton("close", size=32, danger_hover=True, subtle_bg=True, parent=self.card)
        self.btn_close.clicked.connect(self.hide)
        top_bar.addWidget(self.btn_close)
        card_lay.addLayout(top_bar)

        # Synchronized spacer calculated directly from _AboutCardContainer constants
        card_lay.addSpacing(_AboutCardContainer.required_top_spacer())

        # Application Name
        self.title_lbl = QLabel(force_ltr(__app_name__))
        self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setFont(app_font(21, QFont.ExtraBold))
        card_lay.addWidget(self.title_lbl)

        # ABOUT THE APPLICATION • Version 5.1.0
        self.sub_lbl = QLabel()
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        self.sub_lbl.setFont(app_font(11, QFont.ExtraBold))
        card_lay.addWidget(self.sub_lbl)

        card_lay.addSpacing(2)

        # 4 Feature Chips Grid (2x2) instead of a dense wall of text
        chips_grid = QGridLayout()
        chips_grid.setContentsMargins(6, 0, 6, 0)
        chips_grid.setHorizontalSpacing(8)
        chips_grid.setVerticalSpacing(6)
        self._chip_specs: List[Tuple[str, str, str]] = [
            ("video", "جودات حتى 8K وتعدد صوتي", "4K/8K & Multi-Audio Tracks"),
            ("playlist", "قوائم تشغيل وقنوات ذكية", "Smart Playlists & Channels"),
            ("translate", "ترجمة ذكية بدون تراكب BiDi", "BiDi Non-Overlap Subtitles"),
            ("m3u8", "بثوث HLS / m3u8 مباشرة", "Live HLS / m3u8 Engine"),
        ]
        self._chips: List[_FeatureChip] = []
        for idx, (ic_name, _ar_t, _en_t) in enumerate(self._chip_specs):
            chip = _FeatureChip(ic_name, self.card)
            self._chips.append(chip)
            chips_grid.addWidget(chip, idx // 2, idx % 2)
        card_lay.addLayout(chips_grid)

        # Live Engine Status + Diagnostics & Update Buttons Row
        eng_bar = QHBoxLayout()
        eng_bar.setContentsMargins(6, 2, 6, 0)
        eng_bar.setSpacing(6)
        self.lbl_engine_status = QLabel()
        self.lbl_engine_status.setFont(app_font(10, QFont.Bold))
        self.btn_diag = Button("", icon_name="copy", variant="glass", height=28, compact=True)
        self.btn_diag.clicked.connect(self._copy_diagnostics)
        self.btn_check_upd = Button("", icon_name="refresh", variant="primary", height=28, compact=True)
        self.btn_check_upd.clicked.connect(self._trigger_update_check)
        eng_bar.addWidget(self.lbl_engine_status, 1)
        eng_bar.addWidget(self.btn_diag)
        eng_bar.addWidget(self.btn_check_upd)
        card_lay.addLayout(eng_bar)

        self.div1 = _DiamondDivider(self.card)
        card_lay.addWidget(self.div1)

        # DEVELOPER header (localized in all 13 languages!)
        self.dev_hdr_lbl = QLabel()
        self.dev_hdr_lbl.setAlignment(Qt.AlignCenter)
        self.dev_hdr_lbl.setFont(app_font(11, QFont.ExtraBold))
        card_lay.addWidget(self.dev_hdr_lbl)

        # Eslam Mustafa
        self.dev_name_lbl = QLabel(force_ltr(self.DEV_NAME))
        self.dev_name_lbl.setAlignment(Qt.AlignCenter)
        self.dev_name_lbl.setFont(app_font(17, QFont.ExtraBold))
        card_lay.addWidget(self.dev_name_lbl)

        # Email Row: clicking row opens mail client; right button copies email (no duplicate mail icon)
        self.row_email = _DeveloperContactRow(
            icon_name="mail",
            contact_text=self.DEV_EMAIL,
            on_copy=lambda: self._copy_text(self.DEV_EMAIL),
            on_primary_click=self._open_email,
            action_badge_text="",
            parent=self.card,
        )
        card_lay.addWidget(self.row_email)

        # Phone / WhatsApp Row: clicking row opens WhatsApp (wa.me); right button copies number
        self.row_phone = _DeveloperContactRow(
            icon_name="phone",
            contact_text=self.DEV_PHONE,
            on_copy=lambda: self._copy_text(self.DEV_PHONE),
            on_primary_click=self._open_whatsapp,
            action_badge_text="WhatsApp ↗",
            parent=self.card,
        )
        card_lay.addWidget(self.row_phone)

        card_lay.addStretch(1)

        # Credit 1: Argon & Claude collaboration credit
        self.lbl_argon_claude = QLabel()
        self.lbl_argon_claude.setAlignment(Qt.AlignCenter)
        self.lbl_argon_claude.setFont(app_font(11, QFont.Bold))
        card_lay.addWidget(self.lbl_argon_claude)

        # Credit 2: Open-source engines & LGPLv3 compliance notice
        self.lbl_oss_credits = QLabel()
        self.lbl_oss_credits.setAlignment(Qt.AlignCenter)
        self.lbl_oss_credits.setWordWrap(True)
        self.lbl_oss_credits.setFont(app_font(10, QFont.Medium))
        card_lay.addWidget(self.lbl_oss_credits)

        # Legal disclaimer (Personal use & copyright respect)
        self.lbl_legal = QLabel()
        self.lbl_legal.setAlignment(Qt.AlignCenter)
        self.lbl_legal.setWordWrap(True)
        self.lbl_legal.setFont(app_font(9, QFont.Medium))
        card_lay.addWidget(self.lbl_legal)

        root.addWidget(self.card)
        self.refresh_ui()

    def _copy_text(self, text: str) -> None:
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setText(text)
        self.state.toast_requested.emit(f"{t('btn_copied')}: {text}", "ok")

    def _copy_diagnostics(self) -> None:
        report = collect_diagnostics_report(self.state.config)
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setText(report)
        self.state.toast_requested.emit(
            tp("✓ تم نسخ تقرير التشخيص الفني إلى الحافظة", "✓ Diagnostics report copied to clipboard"),
            "ok",
        )

    def _trigger_update_check(self) -> None:
        if self.manager is not None:
            self.manager.trigger_ytdlp_update(silent=False)
        else:
            self.state.toast_requested.emit(
                tp("جاري فحص التحديثات...", "Checking for updates..."),
                "info",
            )

    def _open_email(self) -> None:
        QDesktopServices.openUrl(QUrl(f"mailto:{self.DEV_EMAIL}?subject=V-Stream%20Downloader%20Feedback"))

    def _open_whatsapp(self) -> None:
        QDesktopServices.openUrl(QUrl(self.DEV_WHATSAPP_URL))

    def refresh_ui(self) -> None:
        self.title_lbl.setText(force_ltr(__app_name__))
        self.title_lbl.setStyleSheet(f"color: {T.token_str('text')};")

        self.sub_lbl.setText(t("about_subtitle", ver=__version__))
        self.sub_lbl.setStyleSheet(f"color: {T.token_str('accent_hi')}; letter-spacing: 0.5px;")

        for chip, (_ic, ar_t, en_t) in zip(self._chips, self._chip_specs):
            chip.set_text_and_refresh(tp(ar_t, en_t))

        ff_ready = tp("FFmpeg: جاهز ✓", "FFmpeg: Ready ✓") if self.state.ffmpeg_available else tp("FFmpeg: غير مثبت", "FFmpeg: Missing")
        js_rt = detect_js_runtime()
        js_name = js_rt.split(":")[0] if js_rt else "auto"
        self.lbl_engine_status.setText(force_ltr(f"yt-dlp v{get_ytdlp_version()}  •  {ff_ready}  •  JS: {js_name}"))
        self.lbl_engine_status.setStyleSheet(f"color: {T.token_str('text2')};")

        self.btn_diag.setText(tp("نسخ التشخيص", "Copy Diagnostics"))
        self.btn_diag.setToolTip(
            tp(
                "نسخ إصدار البرنامج و yt-dlp و FFmpeg ونظام التشغيل وآخر سطور السجل",
                "Copy app, yt-dlp, FFmpeg, JS runtime, OS version & recent logs",
            )
        )
        self.btn_check_upd.setText(tp("فحص التحديثات", "Check Updates"))

        self.dev_hdr_lbl.setText(tp("المطور", "DEVELOPER"))
        self.dev_hdr_lbl.setStyleSheet(f"color: {T.token_str('text2')}; letter-spacing: 1.0px;")

        self.dev_name_lbl.setText(force_ltr(self.DEV_NAME))
        self.dev_name_lbl.setStyleSheet(f"color: {T.token_str('text')};")

        self.row_email.refresh_style(
            copy_tooltip=t("about_copy_email"),
            row_tooltip=t("about_send_email"),
        )
        self.row_phone.refresh_style(
            copy_tooltip=t("about_copy_phone"),
            row_tooltip=tp("التواصل عبر واتساب (WhatsApp)", "Chat on WhatsApp (wa.me)"),
            pill_text=tp("واتساب ↗", "WhatsApp ↗"),
        )

        self.lbl_argon_claude.setText(
            tp("✦ تم التطوير بمساعدة Argon و Claude ✦", "✦ Developed with the assistance of Argon & Claude ✦")
        )
        self.lbl_argon_claude.setStyleSheet(f"color: {T.token_str('accent_hi')};")

        self.lbl_oss_credits.setText(
            tp(
                "مبني بتقدير على محركات المصادر المفتوحة: yt-dlp (Unlicense) • FFmpeg (GPLv3) • Qt / PySide6 (LGPLv3)",
                "Built on open-source foundations: yt-dlp (Unlicense) • FFmpeg (GPLv3) • Qt / PySide6 (LGPLv3)",
            )
        )
        self.lbl_oss_credits.setStyleSheet(f"color: {T.token_str('text2')};")

        self.lbl_legal.setText(
            tp(
                "تنويه قانوني: الأداة مخصصة للأرشفة والاستخدام الشخصي المشروع فقط مع احترام حقوق الملكية الفكرية وشروط المواقع.",
                "Legal Notice: Intended strictly for personal archiving & lawful use. Please respect copyright and platform Terms of Service.",
            )
        )
        self.lbl_legal.setStyleSheet(f"color: {T.token_str('text3')};")

        self.btn_close.setToolTip(t("btn_close"))
        self.card.update()
        self.update()

    def show_modal(self) -> None:
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        self.refresh_ui()
        self.show()
        self.raise_()
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if not self.card.geometry().contains(event.position().toPoint()):
            self.hide()
        event.accept()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), T.c("bg0", alpha=210, force_dark=True))
        p.end()
