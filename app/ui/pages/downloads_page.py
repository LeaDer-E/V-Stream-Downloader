import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.domain.manager import DownloadManager
from app.i18n import I18N, force_ltr, localized_lang_name, localized_languages, t, tl, tp
from app.state import AnalyzedMediaInfo, AppState
from app.theme import T
from app.ui.icons import draw_icon, logo_pixmap, make_qicon
from app.ui.notification import reveal_in_file_manager
from app.ui.widgets import (
    Button,
    GlassCard,
    IconButton,
    SearchCombo,
    SegmentedControl,
    StyledLineEdit,
    ToggleSwitch,
    app_font,
    rtl_text_flags,
)


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "LIVE / HLS"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _format_bytes(num_bytes: int) -> str:
    if num_bytes <= 0:
        return ""
    mb = num_bytes / (1024.0 * 1024.0)
    if mb >= 1024.0:
        return f"{mb / 1024.0:.2f} GB"
    return f"{mb:.1f} MB"


class ServiceHeroShowcase(QWidget):
    pasteClicked = Signal()
    subtitleStudioClicked = Signal()
    focusUrlRequested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hover_idx: int = -1
        self.setMinimumHeight(340)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self._badges: List[Tuple[str, str, str, str, str, str]] = [
            ("youtube", "يوتيوب 4K / 8K", "YouTube 4K / 8K", "فيديوهات يوتيوب حتى 8K", "Ultra HD Video & Audio", "#EF4444"),
            ("playlist", "قوائم تشغيل ذكية", "Smart Playlists", "قوائم تشغيل بنطاق وحد جودة ذكي", "Range & Quality Ceiling", "#8B5CF6"),
            ("channel", "قنوات كاملة", "Full Channels", "تحميل قنوات كاملة بضغطة", "One-Click Channel Archive", "#3B82F6"),
            ("m3u8", "بثوث HLS / m3u8", "HLS / m3u8 Streams", "بثوث m3u8 المباشرة والمسجلة", "Live & VOD Stream Engine", "#F59E0B"),
            ("audio", "صوت متعدد اللغات", "Multi-Lang Audio", "مسارات صوتية متعددة MP3/FLAC", "MP3 / FLAC / M4A / OPUS", "#10B981"),
            ("translate", "ترجمة ذكية بدون تراكب", "Non-Overlap Sub AI", "ترجمة SRT فقط أو مدمجة بدون تراكب", "SRT-Only or Muxed BiDi", "#06B6D4"),
            ("video", "تيك توك / فيميو / فيسبوك", "TikTok / Vimeo / FB", "دعم منصات التواصل والكوكيز", "Social Platforms & Cookies", "#EC4899"),
            ("globe", "ساوند كلاود / تويتش", "SoundCloud / Twitch", "البثوث والمنصات الصوتية", "Streams & Audio Platforms", "#6366F1"),
        ]
        self._badge_rects: List[QRectF] = []

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        hit = -1
        for i, br in enumerate(self._badge_rects):
            if br.contains(pos):
                hit = i
                break
        if hit != self._hover_idx:
            self._hover_idx = hit
            self.setCursor(Qt.PointingHandCursor if hit >= 0 else Qt.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_idx = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._hover_idx >= 0:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and 0 <= self._hover_idx < len(self._badges):
            event.accept()
            key = self._badges[self._hover_idx][0]
            if key == "translate":
                self.subtitleStudioClicked.emit()
            elif key == "m3u8":
                self.focusUrlRequested.emit("https://example.com/live/master.m3u8")
            else:
                self.pasteClicked.emit()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)

        grad = QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, T.c("surface", alpha=210))
        grad.setColorAt(1.0, T.c("bg1", alpha=185))
        p.setBrush(grad)
        p.setPen(QPen(T.c("border"), 1.0))
        p.drawRoundedRect(r, 22.0, 22.0)

        cx = r.center().x()
        top_y = r.top() + max(18.0, (r.height() - 300.0) / 2.0)

        logo_px = logo_pixmap(54)
        p.drawPixmap(int(cx - 27), int(top_y), logo_px)

        p.setFont(app_font(18, QFont.ExtraBold))
        p.setPen(T.c("text"))
        p.drawText(QRectF(r.left() + 24, top_y + 62, r.width() - 48, 28), int(Qt.AlignCenter), tl(t("empty_title")))

        p.setFont(app_font(12, QFont.Medium))
        p.setPen(T.c("text2"))
        p.drawText(
            QRectF(r.left() + 36, top_y + 90, r.width() - 72, 22),
            int(Qt.AlignCenter),
            tl(t("empty_subtitle")),
        )

        cols = 4
        card_w = min(202.0, max(148.0, (r.width() - 88.0) / cols))
        card_h = 72.0
        gap_x = 13.0
        gap_y = 13.0
        total_grid_w = cols * card_w + (cols - 1) * gap_x
        start_x = cx - total_grid_w / 2.0
        grid_y = top_y + 126.0

        self._badge_rects.clear()
        is_rtl = I18N.is_rtl()

        for idx, (icon_name, ar_title, en_title, ar_sub, en_sub, hex_col) in enumerate(self._badges):
            row = idx // cols
            col = idx % cols
            vis_col = (cols - 1 - col) if is_rtl else col
            bx = start_x + vis_col * (card_w + gap_x)
            by = grid_y + row * (card_h + gap_y)
            brect = QRectF(bx, by, card_w, card_h)
            self._badge_rects.append(brect)

            is_hov = idx == self._hover_idx
            ac = QColor(hex_col)

            bg = T.c("surface_hi", alpha=235) if is_hov else T.c("bg1", alpha=205)
            p.setBrush(bg)
            p.setPen(QPen(ac if is_hov else T.c("border"), 1.6 if is_hov else 1.0))
            p.drawRoundedRect(brect, 14.0, 14.0)

            ic_bg = QColor(ac)
            ic_bg.setAlpha(42 if is_hov else 32)
            ic_x = (brect.right() - 42) if is_rtl else (brect.left() + 10)
            ic_rect = QRectF(ic_x, brect.top() + 12, 32, 32)
            p.setBrush(ic_bg)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(ic_rect, 10.0, 10.0)
            draw_icon(p, icon_name, ic_rect.adjusted(6, 6, -6, -6), color=ac)

            tx_left = brect.left() + 10 if is_rtl else (brect.left() + 48)
            tx_right = (brect.right() - 48) if is_rtl else (brect.right() - 8)
            tx_w = max(50.0, tx_right - tx_left)

            p.setFont(app_font(12, QFont.Bold))
            p.setPen(T.c("text"))
            t1 = p.fontMetrics().elidedText(tp(ar_title, en_title), Qt.ElideRight, int(tx_w))
            p.drawText(QRectF(tx_left, brect.top() + 12, tx_w, 20), rtl_text_flags(True, True), tl(t1))

            p.setFont(app_font(10, QFont.Medium))
            p.setPen(T.c("text2"))
            t2 = p.fontMetrics().elidedText(tp(ar_sub, en_sub), Qt.ElideRight, int(tx_w))
            p.drawText(QRectF(tx_left, brect.top() + 34, tx_w, 18), rtl_text_flags(True, True), tl(t2))

        p.end()


class DownloadItemCard(QWidget):
    ACTION_ZONE_W = 190

    def __init__(self, task_id: str, state: AppState, manager: DownloadManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.state = state
        self.manager = manager
        self._hover = False
        self.setFixedHeight(98)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.btn_pause_resume = IconButton("pause", size=32, tooltip=tp("إيقاف مؤقت / استئناف", "Pause / Resume"), subtle_bg=True, parent=self)
        self.btn_pause_resume.clicked.connect(self._on_toggle_pause)

        self.btn_stop = IconButton("stop", size=32, tooltip=t("btn_cancel"), danger_hover=True, subtle_bg=True, parent=self)
        self.btn_stop.clicked.connect(lambda: self.manager.cancel_task(self.task_id))

        self.btn_play = IconButton("play", size=32, tooltip=t("ctx_open_file"), subtle_bg=True, parent=self)
        self.btn_play.clicked.connect(self._on_play_media)

        self.btn_folder = IconButton("folder", size=32, tooltip=t("ctx_open_folder"), subtle_bg=True, parent=self)
        self.btn_folder.clicked.connect(self._on_open_folder)

        self.btn_copy_url = IconButton("link", size=32, tooltip=t("ctx_copy_url"), subtle_bg=True, parent=self)
        self.btn_copy_url.clicked.connect(self._on_copy_link)

        self.btn_delete = IconButton("trash", size=32, tooltip=t("ctx_remove"), danger_hover=True, subtle_bg=True, parent=self)
        self.btn_delete.clicked.connect(self._remove_self)

        self.refresh_state()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def _layout_action_buttons(self) -> None:
        visible_btns = [
            b
            for b in (
                self.btn_pause_resume,
                self.btn_stop,
                self.btn_play,
                self.btn_folder,
                self.btn_copy_url,
                self.btn_delete,
            )
            if not b.isHidden()
        ]
        if not visible_btns:
            return
        is_rtl = I18N.is_rtl()
        cy = (self.height() - 32) // 2
        gap = 5
        if is_rtl:
            x = 14
            for b in visible_btns:
                b.move(x, cy)
                x += 32 + gap
        else:
            x = self.width() - 14 - 32
            for b in reversed(visible_btns):
                b.move(x, cy)
                x -= 32 + gap

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_action_buttons()

    def refresh_state(self) -> None:
        item = self.state.tasks.get(self.task_id)
        if not item:
            return
        st = item.status
        if st in ("downloading", "fetching", "queued", "translating_sub"):
            self.btn_pause_resume.set_icon("pause")
            self.btn_pause_resume.setToolTip(tp("إيقاف مؤقت", "Pause"))
            self.btn_pause_resume.setVisible(True)
            self.btn_stop.setVisible(True)
            self.btn_play.setVisible(False)
            self.btn_folder.setVisible(True)
            self.btn_delete.setVisible(False)
        elif st == "error":
            self.btn_pause_resume.set_icon("refresh")
            self.btn_pause_resume.setToolTip(t("ctx_retry"))
            self.btn_pause_resume.setVisible(True)
            self.btn_stop.setVisible(False)
            self.btn_play.setVisible(False)
            self.btn_folder.setVisible(True)
            self.btn_delete.setVisible(True)
        elif st in ("paused", "canceled"):
            self.btn_pause_resume.set_icon("play")
            self.btn_pause_resume.setToolTip(tp("استئناف التحميل", "Resume Download"))
            self.btn_pause_resume.setVisible(True)
            self.btn_stop.setVisible(st == "paused")
            self.btn_play.setVisible(False)
            self.btn_folder.setVisible(True)
            self.btn_delete.setVisible(st == "canceled")
        elif st == "completed":
            self.btn_pause_resume.setVisible(False)
            self.btn_stop.setVisible(False)
            self.btn_play.setVisible(True)
            self.btn_folder.setVisible(True)
            self.btn_delete.setVisible(True)
        else:
            self.btn_pause_resume.setVisible(False)
            self.btn_stop.setVisible(True)
            self.btn_play.setVisible(False)
            self.btn_folder.setVisible(True)
            self.btn_delete.setVisible(False)

        if item.status == "error" and item.error_message:
            self.setToolTip(item.error_message)
        elif item.warning_message:
            self.setToolTip(item.warning_message)
        else:
            self.setToolTip("")
        self._layout_action_buttons()
        self.update()

    def _thumb_rect(self) -> QRectF:
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        thumb_w, thumb_h = 132.0, 74.0
        is_rtl = I18N.is_rtl()
        thumb_x = (r.right() - 18 - thumb_w) if is_rtl else (r.left() + 18)
        return QRectF(thumb_x, r.top() + (r.height() - thumb_h) / 2.0, thumb_w, thumb_h)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._thumb_rect().contains(event.position()):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._thumb_rect().contains(event.position()):
            event.accept()
            item = self.state.tasks.get(self.task_id)
            if item:
                if item.status == "completed":
                    self._on_play_media()
                else:
                    self._on_toggle_pause()
            return
        super().mouseReleaseEvent(event)

    def _on_toggle_pause(self) -> None:
        item = self.state.tasks.get(self.task_id)
        if not item:
            return
        if item.status in ("paused", "error", "canceled"):
            self.manager.resume_task(self.task_id)
        else:
            self.manager.pause_task(self.task_id)

    def _on_open_folder(self) -> None:
        item = self.state.tasks.get(self.task_id)
        if item:
            target = item.output_path or self.state.config.download_dir
            reveal_in_file_manager(target)

    def _on_play_media(self) -> None:
        item = self.state.tasks.get(self.task_id)
        if item and item.output_path and Path(item.output_path).exists():
            try:
                if sys.platform == "win32":
                    os.startfile(item.output_path)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", item.output_path])
                else:
                    subprocess.Popen(["xdg-open", item.output_path])
            except Exception:
                pass

    def _on_copy_link(self) -> None:
        item = self.state.tasks.get(self.task_id)
        if item and item.url:
            cb = QGuiApplication.clipboard()
            if cb is not None:
                cb.setText(item.url)
            self.state.toast_requested.emit(t("btn_copied"), "ok")

    def _show_context_menu(self, pos) -> None:
        item = self.state.tasks.get(self.task_id)
        if not item:
            return
        menu = QMenu(self)
        menu.setLayoutDirection(Qt.RightToLeft if I18N.is_rtl() else Qt.LeftToRight)
        menu.setStyleSheet(
            f"QMenu {{ background: {T.token_str('surface')}; color: {T.token_str('text')}; "
            f"border: 1px solid {T.token_str('border_hi')}; border-radius: 12px; padding: 6px; }}"
            f"QMenu::item {{ padding: 7px 16px; border-radius: 8px; }}"
            f"QMenu::item:selected {{ background: {T.token_str('accent')}; color: #FFFFFF; }}"
        )

        act_copy = menu.addAction(make_qicon("link"), t("ctx_copy_url"))
        act_copy.triggered.connect(self._on_copy_link)

        if item.status == "completed":
            act_play = menu.addAction(make_qicon("play"), t("ctx_open_file"))
            act_play.triggered.connect(self._on_play_media)

        act_folder = menu.addAction(make_qicon("folder"), t("ctx_open_folder"))
        act_folder.triggered.connect(self._on_open_folder)

        if item.status in ("paused", "error", "canceled"):
            act_retry = menu.addAction(make_qicon("refresh"), t("ctx_retry"))
            act_retry.triggered.connect(lambda: self.manager.resume_task(self.task_id))

        menu.addSeparator()
        act_rm = menu.addAction(make_qicon("trash", color=T.c("danger")), t("ctx_remove"))
        act_rm.triggered.connect(self._remove_self)

        menu.exec(self.mapToGlobal(pos))

    def _remove_self(self) -> None:
        self.manager.cancel_task(self.task_id)
        self.state.remove_task(self.task_id)

    def paintEvent(self, event) -> None:
        item = self.state.tasks.get(self.task_id)
        if not item:
            return

        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        cat_color = T.category_color(item.group_type, item.group_id)

        p.setBrush(T.c("surface_hi", alpha=220) if self._hover else T.c("surface"))
        border_col = cat_color if (item.status == "downloading" or self._hover) else T.c("border")
        p.setPen(QPen(border_col, 1.4 if (item.status == "downloading" or self._hover) else 1.0))
        p.drawRoundedRect(r, 16.0, 16.0)

        is_rtl = I18N.is_rtl()

        strip_w = 5.5
        strip_x = (r.right() - strip_w - 4) if is_rtl else (r.left() + 4)
        strip_rect = QRectF(strip_x, r.top() + 10, strip_w, r.height() - 20)
        p.setBrush(cat_color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(strip_rect, 2.75, 2.75)

        thumb_rect = self._thumb_rect()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(thumb_rect, 10.0, 10.0)
        p.save()
        p.setClipPath(clip_path)
        pix: Optional[QPixmap] = self.state.thumbnails.get(self.task_id)
        if pix and not pix.isNull():
            scaled = pix.scaled(
                int(thumb_rect.width()),
                int(thumb_rect.height()),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            p.drawPixmap(int(thumb_rect.left()), int(thumb_rect.top()), scaled)
        else:
            p.fillPath(clip_path, T.c("bg2"))

        tcx, tcy = thumb_rect.center().x(), thumb_rect.center().y()
        p.setBrush(QColor(0, 0, 0, 145))
        p.setPen(QPen(QColor(255, 255, 255, 205), 1.6))
        p.drawEllipse(QPointF(tcx, tcy), 16.0, 16.0)

        ov_icon = (
            "check"
            if item.status == "completed"
            else ("refresh" if item.status == "error" else ("play" if item.status in ("paused", "canceled") else "stop"))
        )
        draw_icon(p, ov_icon, QRectF(tcx - 7.5, tcy - 7.5, 15, 15), color=QColor("#FFFFFF"))

        dur_txt = _format_duration(item.duration_sec)
        p.setFont(app_font(10, QFont.Bold))
        dw = p.fontMetrics().horizontalAdvance(dur_txt) + 10
        dur_rect = QRectF(thumb_rect.right() - dw - 5, thumb_rect.bottom() - 20, dw, 16)
        p.setBrush(QColor(0, 0, 0, 195))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(dur_rect, 4.5, 4.5)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(dur_rect, int(Qt.AlignCenter), force_ltr(dur_txt))
        p.restore()

        if is_rtl:
            content_left = r.left() + self.ACTION_ZONE_W
            content_right = thumb_rect.left() - 14
        else:
            content_left = thumb_rect.right() + 14
            content_right = r.right() - self.ACTION_ZONE_W
        content_w = max(140.0, content_right - content_left)

        full_title = f"{item.smart_prefix}{item.title}"
        p.setFont(app_font(13, QFont.Bold))
        p.setPen(T.c("text"))
        title_rect = QRectF(content_left, r.top() + 9, content_w, 22)
        elided_title = p.fontMetrics().elidedText(full_title, Qt.ElideRight, int(content_w))
        p.drawText(title_rect, rtl_text_flags(True, True), tl(elided_title))

        badge_y = r.top() + 34
        if item.group_type == "playlist":
            pl_num = T.playlist_index_number(item.group_id)
            cat_label = f"{t('badge_playlist')} #{pl_num}: {item.group_title[:18]} ({item.playlist_index}/{item.playlist_total})"
        elif item.group_type == "channel":
            cat_label = f"{t('badge_channel')}: {item.group_title[:18]} ({item.playlist_index}/{item.playlist_total})"
        elif item.group_type == "m3u8":
            cat_label = t("badge_m3u8")
        elif item.media_mode == "subtitles_only":
            cat_label = t("badge_sub_only")
        else:
            cat_label = t("badge_audio") if item.media_mode == "audio" else t("badge_single")

        p.setFont(app_font(10, QFont.Bold))
        max_cat_w = min(220.0, content_w * 0.52)
        cat_label_elided = p.fontMetrics().elidedText(cat_label, Qt.ElideRight, int(max_cat_w - 14))
        cat_w = min(max_cat_w, p.fontMetrics().horizontalAdvance(cat_label_elided) + 14)
        cat_bx = (content_right - cat_w) if is_rtl else content_left
        cat_pill = QRectF(cat_bx, badge_y, cat_w, 19)
        bg_cat = QColor(cat_color)
        bg_cat.setAlpha(40)
        p.setBrush(bg_cat)
        p.setPen(QPen(cat_color, 1.0))
        p.drawRoundedRect(cat_pill, 5.5, 5.5)
        p.setPen(cat_color.lighter(118) if T.effective_mode() == "dark" else cat_color.darker(118))
        p.drawText(cat_pill, int(Qt.AlignCenter), tl(cat_label_elided))

        if item.media_mode == "subtitles_only":
            qual_info = "SRT SUBTITLE"
        else:
            qual_info = f"{item.quality.upper()} • {item.container.upper()}"
            if item.audio_lang:
                aud_disp = localized_lang_name(item.audio_lang)
                qual_info += f" • {tp('صوت:', 'Audio:')} {aud_disp}"

        if item.sub_enabled:
            src_disp = localized_lang_name(item.sub_source_lang)
            sub_tag = f"{src_disp}"
            if item.sub_translate_to and item.sub_translate_to != item.sub_source_lang:
                tgt_disp = localized_lang_name(item.sub_translate_to)
                sub_tag += f" → {tgt_disp}"
            qual_info += f" • {sub_tag}"

        p.setFont(app_font(11, QFont.DemiBold))
        p.setPen(T.c("text2"))
        rem_w = max(40.0, content_w - cat_w - 10.0)
        if is_rtl:
            meta_rect = QRectF(content_left, badge_y, rem_w, 19)
        else:
            meta_rect = QRectF(content_left + cat_w + 10, badge_y, rem_w, 19)
        elided_qual = p.fontMetrics().elidedText(qual_info, Qt.ElideRight, int(rem_w))
        p.drawText(meta_rect, rtl_text_flags(True, True), tl(elided_qual))

        pct = max(0.0, min(100.0, item.progress))
        if item.status == "downloading":
            phase_prefix = f"[{item.stream_phase}] " if item.stream_phase else ""
            parts = [f"{phase_prefix}{t('status_downloading', pct=f'{pct:.1f}')}"]
            if item.downloaded_bytes > 0 and item.total_bytes > 0:
                parts.append(f"{_format_bytes(item.downloaded_bytes)} / {_format_bytes(item.total_bytes)}")
            elif item.downloaded_bytes > 0:
                parts.append(_format_bytes(item.downloaded_bytes))
            if item.eta_str:
                parts.append(f"ETA {item.eta_str}")
            if item.speed_str:
                parts.append(item.speed_str)
            st_text = "  ·  ".join(parts)
        else:
            status_map = {
                "queued": t("status_queued"),
                "fetching": t("status_fetching"),
                "translating_sub": t("status_translating_sub"),
                "merging": t("status_merging"),
                "paused": f"{t('status_paused')} ({pct:.1f}%)",
                "completed": (
                    item.warning_message
                    if getattr(item, "skipped_archive", False) and item.warning_message
                    else (f"{t('status_completed')}  ·  {item.warning_message}" if item.warning_message else t("status_completed"))
                ),
                "error": f"{t('status_error')}: {item.error_message[:120]}",
                "canceled": t("status_canceled"),
            }
            st_text = status_map.get(item.status, item.status)

        p.setFont(app_font(11, QFont.Medium))
        p.setPen(
            T.c("warn")
            if (item.status == "completed" and item.warning_message)
            else (
                T.c("ok")
                if item.status == "completed"
                else (T.c("danger") if item.status == "error" else T.c("text2"))
            )
        )
        st_rect = QRectF(content_left, r.top() + 56, content_w, 18)
        elided_st = p.fontMetrics().elidedText(st_text, Qt.ElideRight, int(content_w))
        p.drawText(st_rect, rtl_text_flags(True, True), tl(elided_st))

        prog_y = r.bottom() - 14
        bar_rect = QRectF(content_left, prog_y, content_w, 6.0)
        p.setBrush(T.c("bg2"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bar_rect, 3.0, 3.0)

        if pct > 0:
            fill_w = (bar_rect.width() * pct) / 100.0
            fill_x = (bar_rect.right() - fill_w) if is_rtl else bar_rect.left()
            fill_rect = QRectF(fill_x, bar_rect.top(), fill_w, bar_rect.height())
            if item.status == "completed":
                p.setBrush(T.c("ok"))
            elif item.status == "error":
                p.setBrush(T.c("danger"))
            else:
                grad = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
                grad.setColorAt(0.0, cat_color)
                grad.setColorAt(1.0, T.c("accent"))
                p.setBrush(grad)
            p.drawRoundedRect(fill_rect, 3.0, 3.0)

        p.end()


class DownloadsPage(QWidget):
    def __init__(
        self,
        state: AppState,
        manager: DownloadManager,
        on_open_smart_dialog: Callable[[AnalyzedMediaInfo], None],
        on_navigate_page: Callable[[int], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.manager = manager
        self.on_open_smart_dialog = on_open_smart_dialog
        self.on_navigate_page = on_navigate_page
        self._cards: Dict[str, DownloadItemCard] = {}
        self._active_filter: str = "all"

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 14)
        root.setSpacing(10)

        # 0. FFmpeg Missing Alert Banner (only visible if FFmpeg is missing!)
        self.ffmpeg_banner = GlassCard(radius=14.0)
        ff_lay = QHBoxLayout(self.ffmpeg_banner)
        ff_lay.setContentsMargins(14, 8, 14, 8)
        ff_lay.setSpacing(10)
        lbl_ff_warn = QLabel(
            tp(
                "تنبيه: أداة FFmpeg غير مثبتة حالياً — بدونها لن يعمل دمج الجودات العالية (1080p/4K) أو تحويل MP3.",
                "Notice: FFmpeg is not installed — 1080p/4K stream merging and MP3 conversion require FFmpeg.",
            )
        )
        lbl_ff_warn.setFont(app_font(11, QFont.Bold))
        lbl_ff_warn.setStyleSheet(f"color: {T.token_str('warn')};")
        btn_ff_install_now = Button(
            tp("تثبيت FFmpeg تلقائياً بضغطة واحدة", "Auto-Install FFmpeg in 1 Click"),
            icon_name="downloads",
            variant="emerald",
            height=30,
            compact=True,
        )
        btn_ff_install_now.clicked.connect(self.manager.trigger_ffmpeg_auto_install)
        ff_lay.addWidget(lbl_ff_warn, 1)
        ff_lay.addWidget(btn_ff_install_now)
        self.ffmpeg_banner.setVisible(not self.state.ffmpeg_available)
        root.addWidget(self.ffmpeg_banner)

        # 1. Two-Tier Luxury Command Deck
        top_card = GlassCard(radius=20.0)
        top_v = QVBoxLayout(top_card)
        top_v.setContentsMargins(16, 12, 16, 12)
        top_v.setSpacing(10)

        omnibar_row = QHBoxLayout()
        omnibar_row.setSpacing(10)

        self.btn_paste = Button(
            t("btn_paste"),
            icon_name="paste",
            variant="emerald",
            height=42,
        )
        self.btn_paste.clicked.connect(self._on_paste_and_analyze)
        omnibar_row.addWidget(self.btn_paste)

        self.url_input = StyledLineEdit(
            placeholder=t("paste_url_placeholder"),
            on_paste_and_go=self._on_paste_and_analyze,
        )
        self.url_input.setFixedHeight(42)
        self.url_input.setFont(app_font(13, QFont.Medium))
        self.url_input.setStyleSheet(
            f"QLineEdit {{ background: {T.token_str('bg0')}; color: {T.token_str('text')}; "
            f"border: 1px solid {T.token_str('border')}; border-radius: 12px; padding: 0 14px; }}"
            f"QLineEdit:focus {{ border: 1.5px solid {T.token_str('accent')}; }}"
        )
        self.url_input.returnPressed.connect(self._on_analyze_clicked)
        omnibar_row.addWidget(self.url_input, 1)

        self.btn_analyze = Button(
            t("btn_analyze"),
            icon_name="search",
            variant="primary",
            height=42,
        )
        self.btn_analyze.clicked.connect(self._on_analyze_clicked)
        omnibar_row.addWidget(self.btn_analyze)

        self.btn_cancel_analyze = Button(
            tp("إلغاء التحليل", "Cancel Analysis"),
            icon_name="close",
            variant="danger",
            height=42,
            compact=True,
        )
        self.btn_cancel_analyze.setVisible(False)
        self.btn_cancel_analyze.clicked.connect(self.manager.cancel_analysis)
        omnibar_row.addWidget(self.btn_cancel_analyze)

        self.btn_reopen = Button(
            t("btn_reopen_last"),
            icon_name="history",
            variant="glass",
            height=42,
            compact=True,
        )
        self.btn_reopen.setToolTip(
            tp("إعادة فتح نافذة آخر رابط تم تحليله فوراً", "Reopen the last analyzed link dialog immediately")
        )
        self.btn_reopen.setVisible(self.state.last_analyzed_info is not None)
        self.btn_reopen.clicked.connect(self._on_reopen_last_analysis)
        omnibar_row.addWidget(self.btn_reopen)

        top_v.addLayout(omnibar_row)

        smart_strip = QHBoxLayout()
        smart_strip.setSpacing(10)

        self.sw_smart_mode = ToggleSwitch(self.state.config.smart_mode_enabled)
        self.sw_smart_mode.toggled.connect(self._on_smart_mode_toggled)
        smart_strip.addWidget(self.sw_smart_mode)

        self.lbl_smart_hint = QLabel(t("smart_mode_label"))
        self.lbl_smart_hint.setFont(app_font(12, QFont.Bold))
        self.lbl_smart_hint.setStyleSheet(
            f"color: {T.token_str('accent_hi' if self.state.config.smart_mode_enabled else 'text2')};"
        )
        smart_strip.addWidget(self.lbl_smart_hint)

        smart_strip.addStretch(1)

        qual_choices = [
            ("2160p", tp("جودة: 2160p 4K (MP4)", "Quality: 2160p 4K (MP4)")),
            ("1440p", tp("جودة: 1440p 2K (MP4)", "Quality: 1440p 2K (MP4)")),
            ("1080p", tp("جودة: 1080p Full HD", "Quality: 1080p Full HD")),
            ("720p", tp("جودة: 720p HD", "Quality: 720p HD")),
            ("480p", tp("جودة: 480p", "Quality: 480p")),
            ("360p", tp("جودة: 360p", "Quality: 360p")),
            ("audio_only", tp("صوت فقط: MP3 320kbps", "Audio Only: MP3 320kbps")),
            ("best", tp("أعلى جودة متاحة", "Best Max Quality")),
        ]
        self.combo_quick_quality = SearchCombo(
            qual_choices,
            self.state.config.preferred_quality,
            min_width=175,
            height=32,
            icon_name="video",
        )
        self.combo_quick_quality.changed.connect(self._on_quick_quality_picked)
        smart_strip.addWidget(self.combo_quick_quality)

        sub_lang_choices: List[Tuple[str, str]] = [
            ("none", tp("الترجمة: بدون ترجمة", "Subtitles: None")),
        ]
        for lcode, lname in localized_languages():
            sub_lang_choices.append((lcode, tp(f"الترجمة: {lname}", f"Subtitles: {lname}")))

        active_sub_pref = (
            "none"
            if self.state.config.subtitle_mode == "none"
            else (self.state.config.preferred_subtitle_lang or "ar")
        )
        self.combo_quick_sub = SearchCombo(
            sub_lang_choices,
            active_sub_pref,
            min_width=175,
            height=32,
            icon_name="translate",
        )
        self.combo_quick_sub.changed.connect(self._on_quick_sub_picked)
        smart_strip.addWidget(self.combo_quick_sub)

        top_v.addLayout(smart_strip)
        root.addWidget(top_card)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.filter_seg = SegmentedControl(
            [
                ("all", t("filter_all")),
                ("active", t("filter_active")),
                ("playlists", t("filter_playlists")),
                ("channels", t("filter_channels")),
                ("single", t("filter_single")),
                ("completed", t("filter_completed")),
            ],
            "all",
            compact=True,
        )
        self.filter_seg.changed.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_seg)
        toolbar.addStretch(1)

        self.btn_pause_all = Button(t("btn_pause_all"), icon_name="pause", variant="ghost", height=32, compact=True)
        self.btn_pause_all.clicked.connect(self.manager.pause_all)
        self.btn_resume_all = Button(t("btn_resume_all"), icon_name="play", variant="ghost", height=32, compact=True)
        self.btn_resume_all.clicked.connect(self.manager.resume_all)
        self.btn_clear = Button(t("btn_clear_completed"), icon_name="trash", variant="ghost", height=32, compact=True)
        self.btn_clear.clicked.connect(self.state.clear_completed)

        toolbar.addWidget(self.btn_pause_all)
        toolbar.addWidget(self.btn_resume_all)
        toolbar.addWidget(self.btn_clear)
        root.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(T.scrollbar_qss())

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 2, 4, 14)
        self.list_layout.setSpacing(8)

        self.empty_showcase = ServiceHeroShowcase(self.list_container)
        self.empty_showcase.pasteClicked.connect(self._on_paste_and_analyze)
        self.empty_showcase.subtitleStudioClicked.connect(lambda: self.on_navigate_page(1))
        self.empty_showcase.focusUrlRequested.connect(self._on_focus_sample_url)

        self.list_layout.addWidget(self.empty_showcase)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_container)
        root.addWidget(self.scroll, 1)

        self.state.task_added.connect(self._on_task_added)
        self.state.task_updated.connect(self._on_task_updated)
        self.state.task_removed.connect(self._on_task_removed)
        self.state.thumbnail_loaded.connect(self._on_thumb_loaded)
        self.state.analysis_started.connect(self._on_analysis_started)
        self.state.analysis_completed.connect(self._on_analysis_done)
        self.state.analysis_failed.connect(self._on_analysis_failed)
        self.state.ffmpeg_status_changed.connect(lambda ok, _p: self.ffmpeg_banner.setVisible(not ok))

        for tid in reversed(self.state.task_order):
            self._on_task_added(tid)
        self._apply_filter()

    def _on_quick_quality_picked(self, q_key: str) -> None:
        self.state.config.preferred_quality = q_key
        self.state.config.save()
        self.state.config_changed.emit()

    def _on_quick_sub_picked(self, s_key: str) -> None:
        if s_key == "none":
            self.state.config.subtitle_mode = "none"
        else:
            self.state.config.subtitle_mode = "prefer_target_then_translate"
            self.state.config.preferred_subtitle_lang = s_key
        self.state.config.save()
        self.state.config_changed.emit()

    def _on_smart_mode_toggled(self, enabled: bool) -> None:
        self.state.config.smart_mode_enabled = enabled
        self.state.config.save()
        self.lbl_smart_hint.setStyleSheet(
            f"color: {T.token_str('accent_hi' if enabled else 'text2')};"
        )
        msg = t("smart_mode_active_hint") if enabled else t("smart_mode_off_hint")
        self.state.toast_requested.emit(msg, "ok" if enabled else "info")

    def _on_reopen_last_analysis(self) -> None:
        if self.state.last_analyzed_info is not None:
            self.on_open_smart_dialog(self.state.last_analyzed_info)

    def _on_focus_sample_url(self, sample: str) -> None:
        self.url_input.setFocus()
        if not self.url_input.text().strip():
            self.url_input.setPlaceholderText(sample)

    def _on_paste_and_analyze(self) -> None:
        cb = QGuiApplication.clipboard()
        if cb is not None and cb.text().strip():
            self.url_input.setText(cb.text().strip())
            self._on_analyze_clicked()
        elif self.url_input.text().strip():
            self._on_analyze_clicked()
        else:
            self.url_input.setFocus()
            self.state.toast_requested.emit(
                tp("الحافظة فارغة — انسخ رابط فيديو أو قائمة تشغيل أولاً", "Clipboard is empty — copy a media link first"),
                "warn",
            )

    def _on_analyze_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self.state.toast_requested.emit(
                tp("يرجى لصق رابط صحيح أولاً", "Please paste a valid media link first"),
                "warn",
            )
            return
        self.manager.analyze_link(url)

    def _on_analysis_started(self, _url: str) -> None:
        self.btn_analyze.set_busy(True)
        self.btn_paste.set_busy(True)
        self.btn_cancel_analyze.setVisible(True)

    def _on_analysis_failed(self, _err: str) -> None:
        self.btn_analyze.set_busy(False)
        self.btn_paste.set_busy(False)
        self.btn_cancel_analyze.setVisible(False)

    def _on_analysis_done(self, info: AnalyzedMediaInfo) -> None:
        self.btn_analyze.set_busy(False)
        self.btn_paste.set_busy(False)
        self.btn_cancel_analyze.setVisible(False)
        self.url_input.clear()
        self.state.last_analyzed_info = info
        self.btn_reopen.setVisible(True)

        is_multi = info.is_playlist or info.is_channel or len(info.entries) > 1
        scope_pref = self.state.config.smart_mode_scope
        if self.state.config.smart_mode_enabled and (not is_multi or scope_pref in ("single", "playlist", "channel")):
            chosen_scope = scope_pref if (is_multi and scope_pref in ("single", "playlist", "channel")) else "single"
            self.manager.enqueue_smart_one_click(info, scope=chosen_scope)
            self.state.toast_requested.emit(
                tp(f"بدأ التحميل الفوري: {info.title[:40]}", f"Turbo One-Click Download Started: {info.title[:40]}"),
                "ok",
            )
        else:
            self.on_open_smart_dialog(info)

    def _on_task_added(self, task_id: str) -> None:
        if task_id in self._cards:
            return
        card = DownloadItemCard(task_id, self.state, self.manager, self.list_container)
        self._cards[task_id] = card
        self.list_layout.insertWidget(0, card)
        self._apply_filter()

    def _on_task_updated(self, task_id: str, status_changed: bool = False) -> None:
        card = self._cards.get(task_id)
        if card:
            if status_changed:
                card.refresh_state()
            else:
                card.update()
        if status_changed:
            self._apply_filter()

    def _on_task_removed(self, task_id: str) -> None:
        card = self._cards.pop(task_id, None)
        if card:
            self.list_layout.removeWidget(card)
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self._apply_filter()

    def _on_thumb_loaded(self, task_id: str, _pix: QPixmap) -> None:
        card = self._cards.get(task_id)
        if card:
            card.update()

    def _on_filter_changed(self, flt: str) -> None:
        self._active_filter = flt
        self._apply_filter()

    def _apply_filter(self) -> None:
        visible_count = 0
        for tid, card in self._cards.items():
            item = self.state.tasks.get(tid)
            if not item:
                continue
            show = True
            if self._active_filter == "active":
                show = item.status in ("queued", "fetching", "downloading", "translating_sub", "merging", "paused")
            elif self._active_filter == "completed":
                show = item.status == "completed"
            elif self._active_filter == "playlists":
                show = item.group_type == "playlist"
            elif self._active_filter == "channels":
                show = item.group_type == "channel"
            elif self._active_filter == "single":
                show = item.group_type in ("single", "m3u8")

            card.setVisible(show)
            if show:
                visible_count += 1

        self.empty_showcase.setVisible(visible_count == 0)
