from pathlib import Path
from typing import Dict, Optional
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.domain.manager import DownloadManager
from app.i18n import I18N, localized_lang_name, localized_languages, t, tl, tp
from app.state import AppState
from app.theme import T
from app.ui.icons import draw_icon
from app.ui.notification import reveal_in_file_manager
from app.ui.widgets import (
    Button,
    GlassCard,
    IconButton,
    SearchCombo,
    ToggleSwitch,
    app_font,
    rtl_text_flags,
)


class SubtitleJobCard(QWidget):
    ACTION_W = 116

    def __init__(self, job_id: str, state: AppState, manager: DownloadManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self.state = state
        self.manager = manager
        self.setFixedHeight(86)

        self.btn_folder = IconButton("folder", size=32, tooltip=t("ctx_open_folder"), subtle_bg=True, parent=self)
        self.btn_folder.clicked.connect(self._on_open_folder)

        self.btn_retry = IconButton("refresh", size=32, tooltip=t("ctx_retry"), subtle_bg=True, parent=self)
        self.btn_retry.clicked.connect(lambda: self.manager.retry_sub_job(self.job_id))

        self.btn_cancel_rm = IconButton("close", size=32, tooltip=t("ctx_remove"), danger_hover=True, subtle_bg=True, parent=self)
        self.btn_cancel_rm.clicked.connect(self._on_cancel_or_remove)

        self.refresh_state()

    def _layout_buttons(self) -> None:
        vis = [b for b in (self.btn_folder, self.btn_retry, self.btn_cancel_rm) if not b.isHidden()]
        if not vis:
            return
        is_rtl = I18N.is_rtl()
        cy = (self.height() - 32) // 2
        gap = 6
        if is_rtl:
            x = 14
            for b in vis:
                b.move(x, cy)
                x += 32 + gap
        else:
            x = self.width() - 14 - 32
            for b in reversed(vis):
                b.move(x, cy)
                x -= 32 + gap

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_buttons()

    def refresh_state(self) -> None:
        job = self.state.sub_jobs.get(self.job_id)
        if not job:
            return
        self.btn_folder.setVisible(job.status == "completed" or bool(job.source_path))
        self.btn_retry.setVisible(job.status in ("error", "canceled"))
        self._layout_buttons()
        self.update()

    def _on_open_folder(self) -> None:
        job = self.state.sub_jobs.get(self.job_id)
        if job:
            reveal_in_file_manager(job.output_path or job.source_path)

    def _on_cancel_or_remove(self) -> None:
        job = self.state.sub_jobs.get(self.job_id)
        if not job:
            return
        if job.status in ("queued", "processing"):
            self.manager.cancel_sub_job(self.job_id)
        else:
            self.state.remove_sub_job(self.job_id)

    def paintEvent(self, event) -> None:
        job = self.state.sub_jobs.get(self.job_id)
        if not job:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)

        accent_col = (
            T.c("ok")
            if job.status == "completed"
            else (T.c("danger") if job.status == "error" else T.c("accent_hi"))
        )

        p.setBrush(T.c("surface"))
        p.setPen(QPen(accent_col if job.status == "processing" else T.c("border"), 1.3 if job.status == "processing" else 1.0))
        p.drawRoundedRect(r, 15.0, 15.0)

        is_rtl = I18N.is_rtl()

        ic_x = (r.right() - 52) if is_rtl else (r.left() + 14)
        ic_rect = QRectF(ic_x, r.top() + 14, 38, 38)
        ic_bg = QColor(accent_col)
        ic_bg.setAlpha(35)
        p.setBrush(ic_bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(ic_rect, 11.0, 11.0)
        draw_icon(p, "subtitles", ic_rect.adjusted(8, 8, -8, -8), color=accent_col)

        if is_rtl:
            c_left = r.left() + self.ACTION_W
            c_right = ic_rect.left() - 12
        else:
            c_left = ic_rect.right() + 12
            c_right = r.right() - self.ACTION_W
        c_w = max(120.0, c_right - c_left)

        p.setFont(app_font(13, QFont.Bold))
        p.setPen(T.c("text"))
        tgt_disp = localized_lang_name(job.target_lang)
        mode_tag = f"→ {tgt_disp}" if job.do_translate else tp("ضبط BiDi فقط", "BiDi Sync Only")
        if job.enforce_bidi:
            mode_tag += " (RTL/LTR BiDi)"
        title_str = f"{job.filename}   •   {mode_tag}"
        elided_t = p.fontMetrics().elidedText(title_str, Qt.ElideRight, int(c_w))
        p.drawText(QRectF(c_left, r.top() + 10, c_w, 22), rtl_text_flags(True, True), tl(elided_t))

        pct = max(0.0, min(100.0, job.progress))
        rem_cues = max(0, job.total_cues - job.done_cues)
        if job.status == "queued":
            st_txt = tp("في قائمة الانتظار...", "Pending in queue...")
        elif job.status == "processing":
            if job.total_cues > 0:
                st_txt = tp(
                    f"جاري الترجمة ({pct:.1f}%)  ·  تم إنجاز {job.done_cues} جملة  ·  متبقي {rem_cues} جملة (من أصل {job.total_cues})",
                    f"Translating ({pct:.1f}%)  ·  {job.done_cues} cues done  ·  {rem_cues} remaining (of {job.total_cues})",
                )
            else:
                st_txt = tp("جاري قراءة وتحليل توقيت الملف...", "Parsing subtitle cues & timestamps...")
        elif job.status == "completed":
            out_name = Path(job.output_path).name if job.output_path else job.filename
            st_txt = tp(
                f"✓ مكتمل (100%)  ·  تم ترجمة وضبط {job.total_cues} جملة بالكامل  →  {out_name}",
                f"✓ Completed (100%)  ·  Synced all {job.total_cues} cues  →  {out_name}",
            )
        elif job.status == "canceled":
            st_txt = tp(
                f"تم الإلغاء (تم إنجاز {job.done_cues} من {job.total_cues} جملة)",
                f"Canceled ({job.done_cues} of {job.total_cues} cues processed)",
            )
        else:
            st_txt = f"{t('status_error')}: {job.error_message[:65]}"

        p.setFont(app_font(11, QFont.DemiBold))
        p.setPen(
            T.c("ok")
            if job.status == "completed"
            else (T.c("danger") if job.status == "error" else T.c("text2"))
        )
        elided_st = p.fontMetrics().elidedText(st_txt, Qt.ElideRight, int(c_w))
        p.drawText(QRectF(c_left, r.top() + 34, c_w, 20), rtl_text_flags(True, True), tl(elided_st))

        bar_rect = QRectF(c_left, r.bottom() - 15, c_w, 6.0)
        p.setBrush(T.c("bg2"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bar_rect, 3.0, 3.0)

        if pct > 0:
            fw = (bar_rect.width() * pct) / 100.0
            fx = (bar_rect.right() - fw) if is_rtl else bar_rect.left()
            frect = QRectF(fx, bar_rect.top(), fw, bar_rect.height())
            if job.status == "completed":
                p.setBrush(T.c("ok"))
            elif job.status == "error":
                p.setBrush(T.c("danger"))
            else:
                grad = QLinearGradient(frect.topLeft(), frect.topRight())
                grad.setColorAt(0.0, T.c("accent"))
                grad.setColorAt(1.0, T.c("accent_hi"))
                p.setBrush(grad)
            p.drawRoundedRect(frect, 3.0, 3.0)

        p.end()


class SubtitleStudioPage(QWidget):
    def __init__(self, state: AppState, manager: DownloadManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self.manager = manager
        self._cards: Dict[str, SubtitleJobCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)
        root.setSpacing(12)

        title = QLabel(
            tp(
                "استوديو الترجمة الذكي وقائمة مهام الـ Subtitles",
                "Smart Subtitle Translator & Persistent Task Queue",
            )
        )
        title.setFont(app_font(19, QFont.ExtraBold))
        title.setStyleSheet(f"color: {T.token_str('text')};")
        root.addWidget(title)

        card = GlassCard(radius=18.0)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(12)

        lbl_tr = QLabel(t("sub_translate_to"))
        lbl_tr.setFont(app_font(13, QFont.Bold))
        lbl_tr.setStyleSheet(f"color: {T.token_str('text')};")
        self.combo_target = SearchCombo(localized_languages(), "ar", min_width=200, icon_name="translate")
        row1.addWidget(lbl_tr)
        row1.addWidget(self.combo_target)

        row1.addSpacing(12)

        lbl_do_tr = QLabel(tp("ترجمة آلية للنص:", "Auto-Translate:"))
        lbl_do_tr.setFont(app_font(12, QFont.Bold))
        lbl_do_tr.setStyleSheet(f"color: {T.token_str('text')};")
        self.sw_translate = ToggleSwitch(True)
        row1.addWidget(lbl_do_tr)
        row1.addWidget(self.sw_translate)

        row1.addSpacing(12)

        lbl_bidi = QLabel(tp("ضبط RTL/LTR BiDi:", "RTL/LTR BiDi Fix:"))
        lbl_bidi.setFont(app_font(12, QFont.Bold))
        lbl_bidi.setStyleSheet(f"color: {T.token_str('text')};")
        self.sw_bidi = ToggleSwitch(True)
        row1.addWidget(lbl_bidi)
        row1.addWidget(self.sw_bidi)

        row1.addStretch(1)

        self.btn_add_files = Button(
            tp("اختيار ملفات (.srt / .vtt) وبدء الترجمة...", "Select Subtitle Files (.srt / .vtt) & Start..."),
            icon_name="translate",
            variant="emerald",
            height=40,
        )
        self.btn_add_files.clicked.connect(self._pick_and_enqueue_files)
        row1.addWidget(self.btn_add_files)

        lay.addLayout(row1)
        root.addWidget(card)

        summary_bar = QHBoxLayout()
        summary_bar.setSpacing(10)

        self.lbl_summary = QLabel()
        self.lbl_summary.setFont(app_font(12, QFont.Bold))
        self.lbl_summary.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        summary_bar.addWidget(self.lbl_summary)

        summary_bar.addStretch(1)

        self.btn_clear_sub = Button(
            t("btn_clear_completed"),
            icon_name="trash",
            variant="ghost",
            height=32,
            compact=True,
        )
        self.btn_clear_sub.clicked.connect(self.state.clear_completed_sub_jobs)
        summary_bar.addWidget(self.btn_clear_sub)
        root.addLayout(summary_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(T.scrollbar_qss())

        self.list_host = QWidget()
        self.list_host.setStyleSheet("background: transparent;")
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 2, 4, 14)
        self.list_lay.setSpacing(8)

        self.empty_lbl = QLabel(
            tp(
                "لا توجد مهام ترجمة حالياً — اضغط على «اختيار ملفات (.srt / .vtt)» بالأعلى لإضافة ملف أو عدة ملفات ترجمة دفعة واحدة.\n"
                "جميع المهام تظل محفوظة وتعمل في الخلفية حتى لو انتقلت لأي تبويب آخر داخل البرنامج!",
                "No subtitle tasks in queue — click 'Select Subtitle Files (.srt / .vtt)' above to batch-translate & BiDi-sync one or more files.\n"
                "All tasks persist in the background even when you switch tabs!",
            )
        )
        self.empty_lbl.setAlignment(Qt.AlignCenter)
        self.empty_lbl.setWordWrap(True)
        self.empty_lbl.setMinimumHeight(180)
        self.empty_lbl.setFont(app_font(13, QFont.DemiBold))
        self.empty_lbl.setStyleSheet(f"color: {T.token_str('text2')};")
        self.list_lay.addWidget(self.empty_lbl)
        self.list_lay.addStretch(1)

        self.scroll.setWidget(self.list_host)
        root.addWidget(self.scroll, 1)

        self.state.sub_job_added.connect(self._on_job_added)
        self.state.sub_job_updated.connect(self._on_job_updated)
        self.state.sub_job_removed.connect(self._on_job_removed)
        self.state.sub_queue_changed.connect(self._refresh_summary)

        for jid in reversed(self.state.sub_job_order):
            self._on_job_added(jid)
        self._refresh_summary()

    def _pick_and_enqueue_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tp("اختر ملف أو أكثر من ملفات الترجمة (.srt / .vtt)", "Select One or More Subtitle Files (.srt / .vtt)"),
            self.state.config.download_dir,
            "Subtitle Files (*.srt *.vtt)",
        )
        if not files:
            return
        self.manager.enqueue_subtitle_files(
            file_paths=files,
            target_lang=self.combo_target.current_key() or "ar",
            do_translate=self.sw_translate.isChecked(),
            enforce_bidi=self.sw_bidi.isChecked(),
        )

    def _on_job_added(self, job_id: str) -> None:
        if job_id in self._cards:
            return
        card = SubtitleJobCard(job_id, self.state, self.manager, self.list_host)
        self._cards[job_id] = card
        self.list_lay.insertWidget(0, card)
        self._refresh_summary()

    def _on_job_updated(self, job_id: str, status_changed: bool = False) -> None:
        card = self._cards.get(job_id)
        if card:
            if status_changed:
                card.refresh_state()
            else:
                card.update()
        self._refresh_summary()

    def _on_job_removed(self, job_id: str) -> None:
        card = self._cards.pop(job_id, None)
        if card:
            self.list_lay.removeWidget(card)
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        jobs = list(self.state.sub_jobs.values())
        total = len(jobs)
        active = sum(1 for j in jobs if j.status == "processing")
        pending = sum(1 for j in jobs if j.status == "queued")
        done = sum(1 for j in jobs if j.status == "completed")

        self.empty_lbl.setVisible(total == 0)
        self.lbl_summary.setText(
            tp(
                f"إجمالي المهام: {total}   •   جاري المعالجة الآن: {active}   •   في الانتظار: {pending}   •   مكتمل: {done}",
                f"Total Tasks: {total}   •   Processing: {active}   •   Pending: {pending}   •   Completed: {done}",
            )
        )
