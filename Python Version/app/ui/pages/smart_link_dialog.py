from typing import List, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.domain.downloader import parse_playlist_selection_range
from app.domain.manager import DownloadManager
from app.i18n import localized_lang_name, localized_languages, t, tp
from app.state import AnalyzedMediaInfo, AppState
from app.theme import T
from app.ui.widgets import (
    Button,
    GlassCard,
    IconButton,
    ScopeChoiceCard,
    SearchCombo,
    SegmentedControl,
    StyledLineEdit,
    ToggleSwitch,
    app_font,
)


def get_translation_targets() -> List[Tuple[str, str]]:
    """Returns translation target options in the active UI language (Arabic or English)."""
    items: List[Tuple[str, str]] = [
        ("", tp("بدون ترجمة إضافية (حفظ اللغة الأصلية)", "No Extra Translation (Keep Original)")),
    ]
    items.extend(localized_languages())
    return items


class BlobStreamHelperOverlay(QWidget):
    def __init__(self, state: AppState, manager: DownloadManager, parent: QWidget) -> None:
        super().__init__(parent)
        self.state = state
        self.manager = manager
        self.hide()

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        self.card = GlassCard(radius=26.0, opaque=True, parent=self)
        self.card.setFixedSize(680, 490)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(12)

        top = QHBoxLayout()
        self.hdr_lbl = QLabel()
        self.hdr_lbl.setFont(app_font(17, QFont.ExtraBold))
        self.btn_close = IconButton("close", size=30, danger_hover=True)
        self.btn_close.clicked.connect(self.hide)
        top.addWidget(self.hdr_lbl)
        top.addStretch(1)
        top.addWidget(self.btn_close)
        lay.addLayout(top)

        self.explain_lbl = QLabel()
        self.explain_lbl.setWordWrap(True)
        self.explain_lbl.setFont(app_font(12, QFont.Medium))
        lay.addWidget(self.explain_lbl)

        steps_card = GlassCard(radius=14.0)
        s_lay = QVBoxLayout(steps_card)
        s_lay.setContentsMargins(14, 10, 14, 10)
        s_lay.setSpacing(6)
        self.steps_lbl = QLabel()
        self.steps_lbl.setWordWrap(True)
        self.steps_lbl.setFont(app_font(12, QFont.DemiBold))
        s_lay.addWidget(self.steps_lbl)
        lay.addWidget(steps_card)

        self.lbl_stream = QLabel()
        self.lbl_stream.setFont(app_font(12, QFont.Bold))
        lay.addWidget(self.lbl_stream)

        stream_row = QHBoxLayout()
        self.input_stream = StyledLineEdit(placeholder="https://.../master.m3u8")
        self.input_stream.setFixedHeight(38)
        self.input_stream.setFont(app_font(12, QFont.Medium))
        self.btn_paste_s = Button(t("btn_paste"), icon_name="paste", variant="glass", height=38, compact=True)
        self.btn_paste_s.clicked.connect(self._paste_stream_url)
        stream_row.addWidget(self.input_stream, 1)
        stream_row.addWidget(self.btn_paste_s)
        lay.addLayout(stream_row)

        self.lbl_referer = QLabel()
        self.lbl_referer.setFont(app_font(12, QFont.Bold))
        lay.addWidget(self.lbl_referer)

        self.input_referer = StyledLineEdit()
        self.input_referer.setFixedHeight(36)
        self.input_referer.setFont(app_font(12, QFont.Medium))
        lay.addWidget(self.input_referer)

        lay.addStretch(1)

        btn_row = QHBoxLayout()
        self.btn_cancel = Button(t("btn_cancel"), variant="ghost", height=38)
        self.btn_cancel.clicked.connect(self.hide)
        self.btn_go = Button("", icon_name="downloads", variant="emerald", height=38)
        self.btn_go.clicked.connect(self._start_sniff_or_download)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_go)
        lay.addLayout(btn_row)

        root.addWidget(self.card)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.hdr_lbl.setText(
            tp("تنبيه ذكي: رابط Blob مؤقت في ذاكرة المتصفح (RAM)", "Smart Alert: Browser In-Memory Blob URL Detected")
        )
        self.hdr_lbl.setStyleSheet(f"color: {T.token_str('warn')};")
        self.explain_lbl.setText(
            tp(
                "الرابط الذي يبدأ بـ (blob:https://...) هو عنوان وهمي مؤقت ينشئه مشغل الفيديو داخل ذاكرة المتصفح (RAM) فقط، ولا يمثل ملفاً حقيقياً على السيرفر يمكن لأي برنامج خارجي الوصول إليه مباشرة.",
                "A 'blob:https://...' URL is a temporary in-memory pointer created inside your browser tab's RAM by JavaScript (MediaSource). External downloaders cannot read your browser's private RAM UUID directly.",
            )
        )
        self.explain_lbl.setStyleSheet(f"color: {T.token_str('text')};")
        self.steps_lbl.setText(
            tp(
                "الحل في 3 ثوانٍ لتحميل الفيديو بأعلى جودة:\n"
                "1) من صفحة الفيديو في المتصفح اضغط (F12) لفتح أدوات المطور ثم اختر تبويب (Network).\n"
                "2) اكتب في خانة البحث بالأعلى كلمة:  m3u8  ثم شغّل الفيديو لثانية واحدة.\n"
                "3) اضغط كليك يمين على ملف الـ (.m3u8) الذي سيظهر واختر (Copy -> Copy link address) والصقه بالأسفل:",
                "How to grab the real stream in 3 seconds:\n"
                "1) On the video tab in your browser, press (F12) -> open the (Network) tab.\n"
                "2) Filter by 'm3u8' and play the video for 1 second.\n"
                "3) Right-click the '.m3u8' entry -> Copy link address and paste it below:",
            )
        )
        self.steps_lbl.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        self.lbl_stream.setText(
            tp("رابط ملف البث الحقيقي (.m3u8) أو رابط صفحة المشغل (Embed URL):", "Real .m3u8 Stream URL or Embed Webpage URL:")
        )
        self.lbl_stream.setStyleSheet(f"color: {T.token_str('text')};")
        self.lbl_referer.setText(
            tp(
                "نطاق الإحالة لتخطي الحماية (Referer Header — تم تعبئته تلقائياً من رابط الـ Blob):",
                "Protected Stream Referer Header (Auto-filled from your Blob URL):",
            )
        )
        self.lbl_referer.setStyleSheet(f"color: {T.token_str('text2')};")

        qss = (
            f"QLineEdit {{ background: {T.token_str('bg0')}; color: {T.token_str('text')}; "
            f"border: 1px solid {T.token_str('border')}; border-radius: 10px; padding: 0 12px; }}"
            f"QLineEdit:focus {{ border: 1.5px solid {T.token_str('accent')}; }}"
        )
        self.input_stream.setStyleSheet(qss)
        self.input_referer.setStyleSheet(qss)
        self.btn_paste_s.setText(t("btn_paste"))
        self.btn_cancel.setText(t("btn_cancel"))
        self.btn_go.setText(
            tp("فحص وتحميل البث مع تخطي الحماية (Referer)", "Analyze & Download with Referer Bypass")
        )
        self.update()

    def open_for_blob(self, raw_blob_url: str, origin_domain: str) -> None:
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        self.refresh_theme()
        self.input_stream.clear()
        self.input_referer.setText(origin_domain)
        self.show()
        self.raise_()
        self.input_stream.setFocus()

    def _paste_stream_url(self) -> None:
        cb = QGuiApplication.clipboard()
        if cb is not None and cb.text().strip():
            self.input_stream.setText(cb.text().strip())

    def _start_sniff_or_download(self) -> None:
        target_u = self.input_stream.text().strip()
        ref_u = self.input_referer.text().strip()
        if not target_u or target_u.lower().startswith("blob:"):
            self.state.toast_requested.emit(
                tp(
                    "يرجى لصق رابط .m3u8 الحقيقي من تبويب Network (وليس رابط blob:)",
                    "Please paste the real .m3u8 URL from the Network tab (not the blob: URL)",
                ),
                "warn",
            )
            return
        self.hide()
        self.manager.analyze_link(target_u, custom_referer=ref_u)

    def mousePressEvent(self, event) -> None:
        event.accept()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), T.c("bg0", alpha=210, force_dark=True))
        p.end()


class SmartLinkOverlay(QWidget):
    """
    Full-window modal glass overlay shown after analyzing a link (v5.0):
    1. Only shows Scope choice cards (Single Video vs Full Playlist) when the link is inside a Playlist or Channel.
    2. Playlist Range & Item Selector (`1-10, 15, 20-25` or `all`) when downloading a Playlist or Channel.
    3. Splits Mode into 3 dedicated options:
       - Video + Audio (real detected resolutions 4320p..144p + MP4/MKV/WebM + Multi-Audio Dub Track selector)
       - Audio Only (audio bitrates 320k..64k + MP3/M4A/FLAC/WAV/OGG + Multi-Audio Track selector)
       - Subtitles Only (.SRT) (downloads & translates only the subtitle track for a single video or full playlist)
    4. Smart Playlist Ceiling ('أقصى جودة حتى 720p') + 'Save as Default' toggle.
    """

    def __init__(self, state: AppState, manager: DownloadManager, parent: QWidget) -> None:
        super().__init__(parent)
        self.state = state
        self.manager = manager
        self.info: Optional[AnalyzedMediaInfo] = None
        self._selected_scope: str = "single"
        self.hide()

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        self.card = GlassCard(radius=26.0, opaque=True, parent=self)
        self.card.setFixedWidth(760)
        self.card.setMinimumHeight(460)
        self.card.setMaximumHeight(665)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(9)

        top = QHBoxLayout()
        self.hdr_lbl = QLabel(t("scope_prompt_title"))
        self.hdr_lbl.setFont(app_font(17, QFont.ExtraBold))
        self.hdr_lbl.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        self.btn_close = IconButton("close", size=30, danger_hover=True)
        self.btn_close.clicked.connect(self.hide)
        top.addWidget(self.hdr_lbl)
        top.addStretch(1)
        top.addWidget(self.btn_close)
        lay.addLayout(top)

        self.media_title_lbl = QLabel()
        self.media_title_lbl.setFont(app_font(14, QFont.Bold))
        self.media_title_lbl.setStyleSheet(f"color: {T.token_str('text')};")
        self.media_title_lbl.setMaximumHeight(40)
        self.media_title_lbl.setWordWrap(True)
        lay.addWidget(self.media_title_lbl)

        self.meta_lbl = QLabel()
        self.meta_lbl.setFont(app_font(11, QFont.DemiBold))
        self.meta_lbl.setStyleSheet(f"color: {T.token_str('text2')};")
        lay.addWidget(self.meta_lbl)

        # 1. Scope Choice Cards Container (ONLY shown when URL belongs to a Playlist or Channel!)
        self.scope_cards_widget = QWidget()
        scope_cards_row = QHBoxLayout(self.scope_cards_widget)
        scope_cards_row.setContentsMargins(0, 0, 0, 0)
        scope_cards_row.setSpacing(10)

        self.card_single = ScopeChoiceCard(
            "single",
            "video",
            t("scope_single"),
            t("scope_single_desc"),
            selected=True,
        )
        self.card_playlist = ScopeChoiceCard(
            "playlist",
            "playlist",
            t("scope_playlist"),
            t("scope_playlist_desc"),
            selected=False,
        )
        self.card_channel = ScopeChoiceCard(
            "channel",
            "channel",
            t("scope_channel"),
            t("scope_channel_desc"),
            selected=False,
        )

        self.card_single.clicked.connect(self._select_scope)
        self.card_playlist.clicked.connect(self._select_scope)
        self.card_channel.clicked.connect(self._select_scope)

        scope_cards_row.addWidget(self.card_single, 1)
        scope_cards_row.addWidget(self.card_playlist, 1)
        scope_cards_row.addWidget(self.card_channel, 1)
        lay.addWidget(self.scope_cards_widget)

        # 1b. Playlist Range & Item Selector (ONLY shown when scope is Playlist or Channel!)
        self.range_widget = QWidget()
        range_row = QHBoxLayout(self.range_widget)
        range_row.setContentsMargins(0, 0, 0, 0)
        range_row.setSpacing(10)

        self.lbl_range = QLabel(tp("تحديد فيديوهات القائمة (النطاق):", "Select Playlist Videos (Range):"))
        self.lbl_range.setFont(app_font(12, QFont.Bold))
        self.lbl_range.setStyleSheet(f"color: {T.token_str('text')};")

        self.input_range = StyledLineEdit(
            placeholder=tp("اتركه فارغاً لتحميل الكل، أو اكتب مثل: 1-10, 15, 20-25", "Leave empty for All, or type e.g. 1-10, 15, 20-25")
        )
        self.input_range.setFixedHeight(32)
        self.input_range.setFont(app_font(11, QFont.Medium))
        self.input_range.textChanged.connect(self._update_range_badge)

        self.lbl_range_count = QLabel()
        self.lbl_range_count.setFont(app_font(11, QFont.Bold))
        self.lbl_range_count.setStyleSheet(f"color: {T.token_str('ok')};")

        range_row.addWidget(self.lbl_range)
        range_row.addWidget(self.input_range, 1)
        range_row.addWidget(self.lbl_range_count)
        lay.addWidget(self.range_widget)

        # 2. Download Mode Segmented Control (Video + Audio | Audio Only | Subtitles Only)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self.lbl_mode = QLabel(tp("وضع التحميل:", "Download Mode:"))
        self.lbl_mode.setFont(app_font(12, QFont.Bold))
        self.lbl_mode.setStyleSheet(f"color: {T.token_str('text')};")

        self.seg_mode = SegmentedControl(
            [
                ("video", t("media_mode_video")),
                ("audio", t("media_mode_audio")),
                ("subtitles_only", t("media_mode_subtitles")),
            ],
            "video",
            compact=True,
        )
        self.seg_mode.changed.connect(self._on_mode_switched)
        mode_row.addWidget(self.lbl_mode)
        mode_row.addWidget(self.seg_mode, 1)
        lay.addLayout(mode_row)

        # 3. Quality + Container Format Row
        self.qual_row_widget = QWidget()
        qual_row = QHBoxLayout(self.qual_row_widget)
        qual_row.setContentsMargins(0, 0, 0, 0)
        qual_row.setSpacing(10)

        self.lbl_qual = QLabel(t("quality_label"))
        self.lbl_qual.setFont(app_font(12, QFont.Bold))
        self.lbl_qual.setStyleSheet(f"color: {T.token_str('text')};")

        self.combo_quality = SearchCombo([("1080p", "1080p Full HD")], "1080p", min_width=240, icon_name="video")
        self.combo_container = SearchCombo([("mp4", "MP4"), ("mkv", "MKV"), ("webm", "WebM")], "mp4", min_width=130)

        qual_row.addWidget(self.lbl_qual)
        qual_row.addStretch(1)
        qual_row.addWidget(self.combo_quality)
        qual_row.addWidget(self.combo_container)
        lay.addWidget(self.qual_row_widget)

        # 4. Multi-Language Audio Track Row
        self.audio_track_widget = QWidget()
        aud_row = QHBoxLayout(self.audio_track_widget)
        aud_row.setContentsMargins(0, 0, 0, 0)
        aud_row.setSpacing(10)

        self.lbl_audio_track = QLabel(t("audio_track_label"))
        self.lbl_audio_track.setFont(app_font(12, QFont.Bold))
        self.lbl_audio_track.setStyleSheet(f"color: {T.token_str('text')};")

        self.combo_audio_lang = SearchCombo(
            [("", tp("الصوت الأصلي الافتراضي للفيديو", "Default Original Audio"))],
            "",
            min_width=380,
            icon_name="audio",
        )
        aud_row.addWidget(self.lbl_audio_track)
        aud_row.addStretch(1)
        aud_row.addWidget(self.combo_audio_lang)
        lay.addWidget(self.audio_track_widget)

        # 5. Smart Numbering Toggle Container
        self.num_widget = QWidget()
        num_row = QHBoxLayout(self.num_widget)
        num_row.setContentsMargins(0, 0, 0, 0)
        self.lbl_num = QLabel(t("smart_numbering_toggle"))
        self.lbl_num.setFont(app_font(12, QFont.Bold))
        self.lbl_num.setStyleSheet(f"color: {T.token_str('text')};")
        self.sw_numbering = ToggleSwitch(self.state.config.smart_numbering)
        num_row.addWidget(self.lbl_num)
        num_row.addStretch(1)
        num_row.addWidget(self.sw_numbering)
        lay.addWidget(self.num_widget)

        # 6. Smart Subtitle & Translation Box
        self.sub_card = GlassCard(radius=16.0)
        sub_lay = QVBoxLayout(self.sub_card)
        sub_lay.setContentsMargins(16, 10, 16, 10)
        sub_lay.setSpacing(7)

        sub_hdr_row = QHBoxLayout()
        self.lbl_sub_sec = QLabel(t("subtitle_section"))
        self.lbl_sub_sec.setFont(app_font(12, QFont.ExtraBold))
        self.lbl_sub_sec.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        self.sub_status_badge = QLabel()
        self.sub_status_badge.setFont(app_font(11, QFont.Bold))
        self.sub_status_badge.setStyleSheet(f"color: {T.token_str('ok')};")
        sub_hdr_row.addWidget(self.lbl_sub_sec)
        sub_hdr_row.addStretch(1)
        sub_hdr_row.addWidget(self.sub_status_badge)
        sub_lay.addLayout(sub_hdr_row)

        src_row = QHBoxLayout()
        self.lbl_src = QLabel(tp("مسار الترجمة المتاح بالفيديو:", "Available Video Subtitle Track:"))
        self.lbl_src.setFont(app_font(12, QFont.DemiBold))
        self.lbl_src.setStyleSheet(f"color: {T.token_str('text')};")
        self.combo_sub_source = SearchCombo([("none", t("sub_none"))], "none", min_width=310, icon_name="subtitles")
        self.combo_sub_source.changed.connect(self._on_sub_source_changed)
        src_row.addWidget(self.lbl_src)
        src_row.addStretch(1)
        src_row.addWidget(self.combo_sub_source)
        sub_lay.addLayout(src_row)

        tr_row = QHBoxLayout()
        self.lbl_tr = QLabel(t("sub_translate_to"))
        self.lbl_tr.setFont(app_font(12, QFont.DemiBold))
        self.lbl_tr.setStyleSheet(f"color: {T.token_str('text')};")
        self.combo_sub_translate = SearchCombo(get_translation_targets(), "", min_width=310, icon_name="translate")
        self.combo_sub_translate.changed.connect(self._on_sub_translate_changed)
        tr_row.addWidget(self.lbl_tr)
        tr_row.addStretch(1)
        tr_row.addWidget(self.combo_sub_translate)
        sub_lay.addLayout(tr_row)

        bidi_row = QHBoxLayout()
        self.lbl_bidi = QLabel(t("sub_bidi_fix"))
        self.lbl_bidi.setFont(app_font(11, QFont.Medium))
        self.lbl_bidi.setStyleSheet(f"color: {T.token_str('text2')};")
        self.sw_bidi = ToggleSwitch(self.state.config.enforce_bidi_rtl_fix)
        bidi_row.addWidget(self.lbl_bidi)
        bidi_row.addStretch(1)
        bidi_row.addWidget(self.sw_bidi)
        sub_lay.addLayout(bidi_row)

        lay.addWidget(self.sub_card)

        # 7. Save as Default Toggle Row
        def_row = QHBoxLayout()
        self.lbl_save_def = QLabel(t("save_as_default_toggle"))
        self.lbl_save_def.setFont(app_font(11, QFont.DemiBold))
        self.lbl_save_def.setStyleSheet(f"color: {T.token_str('text2')};")
        self.sw_save_default = ToggleSwitch(False)
        def_row.addWidget(self.lbl_save_def)
        def_row.addStretch(1)
        def_row.addWidget(self.sw_save_default)
        lay.addLayout(def_row)

        lay.addStretch(1)

        btn_row = QHBoxLayout()
        self.btn_cancel = Button(t("btn_cancel"), variant="ghost", height=40)
        self.btn_cancel.clicked.connect(self.hide)
        self.btn_start = Button(t("btn_download_now"), icon_name="downloads", variant="emerald", height=40)
        self.btn_start.clicked.connect(self._confirm_download)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_start)
        lay.addLayout(btn_row)

        root.addWidget(self.card)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        self.card_single.set_content(t("scope_single"), t("scope_single_desc"))
        self.card_playlist.set_content(t("scope_playlist"), t("scope_playlist_desc"))
        self.card_channel.set_content(t("scope_channel"), t("scope_channel_desc"))
        self.seg_mode.set_items(
            [
                ("video", t("media_mode_video")),
                ("audio", t("media_mode_audio")),
                ("subtitles_only", t("media_mode_subtitles")),
            ],
            self.seg_mode.current_key() or "video",
        )
        self.hdr_lbl.setText(t("scope_prompt_title"))
        self.hdr_lbl.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        self.media_title_lbl.setStyleSheet(f"color: {T.token_str('text')};")
        self.meta_lbl.setStyleSheet(f"color: {T.token_str('text2')};")
        self.lbl_range.setText(tp("تحديد فيديوهات القائمة (النطاق):", "Select Playlist Videos (Range):"))
        self.lbl_range.setStyleSheet(f"color: {T.token_str('text')};")
        self.input_range.setPlaceholderText(
            tp("اتركه فارغاً لتحميل الكل، أو اكتب مثل: 1-10, 15, 20-25", "Leave empty for All, or type e.g. 1-10, 15, 20-25")
        )
        self.input_range.setStyleSheet(
            f"QLineEdit {{ background: {T.token_str('bg0')}; color: {T.token_str('text')}; "
            f"border: 1px solid {T.token_str('border')}; border-radius: 9px; padding: 0 10px; }}"
            f"QLineEdit:focus {{ border: 1.5px solid {T.token_str('accent')}; }}"
        )
        self.lbl_mode.setText(tp("وضع التحميل:", "Download Mode:"))
        self.lbl_mode.setStyleSheet(f"color: {T.token_str('text')};")
        self.lbl_qual.setText(t("quality_label"))
        self.lbl_qual.setStyleSheet(f"color: {T.token_str('text')};")
        self.lbl_audio_track.setText(t("audio_track_label"))
        self.lbl_audio_track.setStyleSheet(f"color: {T.token_str('text')};")
        self.lbl_num.setText(t("smart_numbering_toggle"))
        self.lbl_num.setStyleSheet(f"color: {T.token_str('text')};")
        self.lbl_sub_sec.setText(t("subtitle_section"))
        self.lbl_sub_sec.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        self.lbl_src.setText(tp("مسار الترجمة المتاح بالفيديو:", "Available Video Subtitle Track:"))
        self.lbl_src.setStyleSheet(f"color: {T.token_str('text')};")
        self.lbl_tr.setText(t("sub_translate_to"))
        self.lbl_tr.setStyleSheet(f"color: {T.token_str('text')};")
        self.lbl_bidi.setText(t("sub_bidi_fix"))
        self.lbl_bidi.setStyleSheet(f"color: {T.token_str('text2')};")
        self.lbl_save_def.setText(t("save_as_default_toggle"))
        self.lbl_save_def.setStyleSheet(f"color: {T.token_str('text2')};")
        self.btn_cancel.setText(t("btn_cancel"))
        mode = self.seg_mode.current_key()
        self.btn_start.setText(t("btn_download_subs_now") if mode == "subtitles_only" else t("btn_download_now"))
        self.combo_sub_translate.set_items(get_translation_targets(), self.combo_sub_translate.current_key())
        self.update()

    def _update_range_badge(self) -> None:
        if not self.info or not self.info.entries:
            self.lbl_range_count.setText("")
            return
        total = len(self.info.entries)
        sel = parse_playlist_selection_range(self.input_range.text(), total)
        self.lbl_range_count.setText(
            tp(f"المحدد: {len(sel)} من {total}", f"Selected: {len(sel)} / {total}")
        )

    def _select_scope(self, key: str) -> None:
        self._selected_scope = key
        self.card_single.set_selected(key == "single")
        self.card_playlist.set_selected(key == "playlist")
        self.card_channel.set_selected(key == "channel")
        is_multi = key in ("playlist", "channel")
        self.num_widget.setVisible(is_multi)
        self.range_widget.setVisible(is_multi and bool(self.info and len(self.info.entries) > 1))
        self._update_range_badge()
        self._populate_quality_and_format(self.seg_mode.current_key())

    def open_for_info(self, info: AnalyzedMediaInfo) -> None:
        self.info = info
        self.state.last_analyzed_info = info
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())

        self.input_range.clear()
        self.media_title_lbl.setText(info.title)
        parts = [info.channel_name]
        if len(info.entries) > 1:
            parts.append(tp(f"قائمة ({len(info.entries)} فيديو)", f"List ({len(info.entries)} videos)"))
        if info.available_qualities:
            real_res = [q for q in info.available_qualities if q != "best"]
            if real_res:
                parts.append(tp(f"الجودات المتاحة: {', '.join(real_res)}", f"Available: {', '.join(real_res)}"))
        if len(info.available_audio_tracks) > 1:
            parts.append(
                tp(
                    f"مسارات الصوت: {len(info.available_audio_tracks) - 1} لغات",
                    f"Audio Tracks: {len(info.available_audio_tracks) - 1} languages",
                )
            )
        self.meta_lbl.setText("  •  ".join(parts))

        has_pl = bool(info.is_playlist and len(info.entries) > 1)
        has_ch = bool(info.is_channel)

        if has_pl or has_ch:
            self.scope_cards_widget.setVisible(True)
            self.card_single.set_content(t("scope_single"), t("scope_single_desc"))
            pl_count_str = f" ({len(info.entries)})" if info.entries else ""
            self.card_playlist.set_content(
                f"{t('scope_playlist')}{pl_count_str}",
                info.playlist_title[:36] if info.playlist_title else t("scope_playlist_desc"),
            )
            self.card_playlist.setVisible(has_pl)
            self.card_channel.set_content(
                f"{t('scope_channel')}{pl_count_str if has_ch else ''}",
                info.channel_name[:36] if info.channel_name else t("scope_channel_desc"),
            )
            self.card_channel.setVisible(has_ch)
            if has_ch:
                self._select_scope("channel")
            else:
                self._select_scope("playlist")
        else:
            self.scope_cards_widget.setVisible(False)
            self._select_scope("single")

        audio_choices: List[Tuple[str, str]] = [
            ("", tp("المسار الصوتي الأصلي للفيديو (Default)", "Original Video Audio Track (Default)")),
        ]
        for atrk in info.available_audio_tracks:
            if not atrk.lang_code:
                continue
            loc_name = localized_lang_name(atrk.lang_code)
            orig_badge = tp(" — أصلي", " — Original") if atrk.is_default else tp(" — مدبلج", " — Dubbed")
            audio_choices.append((atrk.lang_code, f"{loc_name} [{atrk.lang_code}]{orig_badge}"))
        self.combo_audio_lang.set_items(audio_choices, "")

        if info.is_m3u8:
            self.seg_mode.set_items(
                [
                    ("m3u8", t("media_mode_m3u8")),
                    ("audio", t("media_mode_audio")),
                ],
                "m3u8",
            )
        else:
            init_mode = (
                "audio"
                if self.state.config.preferred_quality in ("audio_only", "320k", "256k", "192k", "128k", "64k")
                else "video"
            )
            self.seg_mode.set_items(
                [
                    ("video", t("media_mode_video")),
                    ("audio", t("media_mode_audio")),
                    ("subtitles_only", t("media_mode_subtitles")),
                ],
                init_mode,
            )

        pref_lang = self.state.config.preferred_subtitle_lang or "ar"
        pref_disp = localized_lang_name(pref_lang)
        sub_choices: List[Tuple[str, str]] = [("none", t("sub_none"))]
        selected_sub_key = "none"
        recommended_translate = ""

        native_pref_found = False
        for trk in info.manual_subtitles:
            key = f"manual:{trk.lang_code}"
            disp_name = localized_lang_name(trk.lang_code)
            sub_choices.append((key, f"{disp_name} ({t('sub_original')})"))
            if trk.lang_code == pref_lang or trk.lang_code.startswith(f"{pref_lang}-"):
                selected_sub_key = key
                native_pref_found = True

        for trk in info.auto_subtitles:
            key = f"auto:{trk.lang_code}"
            disp_name = localized_lang_name(trk.lang_code)
            sub_choices.append((key, f"{disp_name} ({t('sub_auto_gen')})"))

        if pref_lang == "none" or self.state.config.subtitle_mode == "none":
            self.sub_status_badge.setText(t("sub_none"))
            self.sub_status_badge.setStyleSheet(f"color: {T.token_str('text3')};")
        elif native_pref_found and self.state.config.subtitle_mode != "always_translate":
            self.sub_status_badge.setText(
                tp(f"✓ الترجمة ({pref_disp}) متوفرة أصلياً في الفيديو!", f"✓ Native ({pref_disp}) subtitle found!")
            )
            self.sub_status_badge.setStyleSheet(f"color: {T.token_str('ok')};")
            recommended_translate = ""
        else:
            fb_lang = self.state.config.fallback_source_lang or "en"
            fallback_key = "none"
            for trk in info.manual_subtitles:
                if trk.lang_code.startswith(fb_lang):
                    fallback_key = f"manual:{trk.lang_code}"
                    break
            if fallback_key == "none" and info.manual_subtitles:
                fallback_key = f"manual:{info.manual_subtitles[0].lang_code}"
            if fallback_key == "none" and self.state.config.allow_auto_generated_subs:
                for trk in info.auto_subtitles:
                    if trk.lang_code.startswith(fb_lang):
                        fallback_key = f"auto:{trk.lang_code}"
                        break
                if fallback_key == "none" and info.auto_subtitles:
                    fallback_key = f"auto:{info.auto_subtitles[0].lang_code}"

            if fallback_key != "none":
                selected_sub_key = fallback_key
                recommended_translate = (
                    pref_lang
                    if (self.state.config.translate_subtitles and self.state.config.subtitle_mode != "original_only")
                    else ""
                )
                self.sub_status_badge.setText(
                    tp(
                        f"سيتم سحب الترجمة وترجمتها سياقياً إلى {pref_disp}",
                        f"Will fetch source & context-translate to {pref_disp}",
                    )
                    if recommended_translate
                    else tp("سيتم حفظ الترجمة بلغتها الأصلية", "Will save original subtitle language")
                )
                self.sub_status_badge.setStyleSheet(f"color: {T.token_str('accent_hi')};")
            else:
                self.sub_status_badge.setText(tp("لا توجد ملفات ترجمة متاحة لهذا الرابط", "No subtitle tracks detected"))
                self.sub_status_badge.setStyleSheet(f"color: {T.token_str('text3')};")

        self.combo_sub_source.set_items(sub_choices, selected_sub_key)
        self.combo_sub_translate.set_items(get_translation_targets(), recommended_translate)
        self._on_mode_switched(self.seg_mode.current_key())

        self.show()
        self.raise_()

    def _populate_quality_and_format(self, mode: str) -> None:
        is_multi_scope = self._selected_scope in ("playlist", "channel")
        if mode == "audio":
            aud_quals = (
                self.info.available_audio_qualities
                if (self.info and self.info.available_audio_qualities)
                else [
                    ("320k", "320 kbps (أعلى نقاء / Studio)"),
                    ("256k", "256 kbps (عالي جداً / High)"),
                    ("192k", "192 kbps (قياسي / Standard)"),
                    ("128k", "128 kbps (متوسط / Medium)"),
                    ("64k", "64 kbps (حجم صغير / Compact)"),
                ]
            )
            self.combo_quality.set_items(aud_quals, "320k")
            self.combo_container.set_items(
                [
                    ("mp3", "MP3 (الأكثر توافقاً)"),
                    ("m4a", "M4A (AAC Apple)"),
                    ("flac", "FLAC (بدون فقدان Lossless)"),
                    ("wav", "WAV (خام غير مضغوط)"),
                    ("ogg", "OGG Vorbis"),
                ],
                self.state.config.preferred_audio_format or "mp3",
            )
        else:
            quals = (
                self.info.available_qualities
                if (self.info and self.info.available_qualities)
                else ["1080p", "720p", "480p", "360p", "240p", "144p", "best"]
            )
            details_map = dict(self.info.quality_details) if (self.info and self.info.quality_details) else {}
            q_items: List[Tuple[str, str]] = []
            for q in quals:
                if q == "best":
                    lbl = tp("أعلى جودة متاحة تلقائياً (Best Max)", "Best Available Quality (Auto Max)")
                elif is_multi_scope:
                    lbl = tp(
                        f"أقصى جودة حتى {q} (أو المتاح تحتها)",
                        f"Max Quality up to {q} (Smart Ceiling)",
                    )
                else:
                    lbl = details_map.get(q, q)
                q_items.append((q, lbl))

            pref_q = self.state.config.preferred_quality
            active_q = pref_q if pref_q in quals else quals[0]
            self.combo_quality.set_items(q_items, active_q)
            self.combo_container.set_items(
                [
                    ("mp4", "MP4 (H.264/AAC قياسي)"),
                    ("mkv", "MKV (Matroska متعدد المسارات)"),
                    ("webm", "WebM (VP9/Opus)"),
                ],
                self.state.config.preferred_video_format or "mp4",
            )

    def _on_mode_switched(self, mode: str) -> None:
        if mode == "subtitles_only":
            self.qual_row_widget.setVisible(False)
            self.audio_track_widget.setVisible(False)
            self.btn_start.setText(t("btn_download_subs_now"))
            if self.combo_sub_source.current_key() == "none" and self.info:
                if self.info.manual_subtitles:
                    self.combo_sub_source.set_items(
                        self.combo_sub_source._items,
                        f"manual:{self.info.manual_subtitles[0].lang_code}",
                    )
                elif self.info.auto_subtitles:
                    self.combo_sub_source.set_items(
                        self.combo_sub_source._items,
                        f"auto:{self.info.auto_subtitles[0].lang_code}",
                    )
        else:
            self.qual_row_widget.setVisible(True)
            has_multi_audio = bool(self.info and len(self.info.available_audio_tracks) > 1)
            self.audio_track_widget.setVisible(has_multi_audio)
            self.btn_start.setText(t("btn_download_now"))
            self._populate_quality_and_format(mode)

    def _on_sub_source_changed(self, key: str) -> None:
        targets = get_translation_targets()
        if key == "none":
            self.combo_sub_translate.set_items(targets, "")
        else:
            lang = key.split(":", 1)[-1]
            pref = self.state.config.preferred_subtitle_lang or "ar"
            if pref == "none" or lang.startswith(pref):
                self.combo_sub_translate.set_items(targets, "")
            else:
                self.combo_sub_translate.set_items(targets, pref)

    def _on_sub_translate_changed(self, target_lang: str) -> None:
        if target_lang and self.combo_sub_source.current_key() == "none" and self.info:
            if self.info.manual_subtitles:
                self.combo_sub_source.set_items(
                    self.combo_sub_source._items,
                    f"manual:{self.info.manual_subtitles[0].lang_code}",
                )
            elif self.info.auto_subtitles:
                self.combo_sub_source.set_items(
                    self.combo_sub_source._items,
                    f"auto:{self.info.auto_subtitles[0].lang_code}",
                )

    def _confirm_download(self) -> None:
        if not self.info:
            return
        scope = self._selected_scope
        if scope == "channel" and not self.info.entries and self.info.channel_url:
            ch_url = self.info.channel_url
            self.hide()
            self.state.toast_requested.emit(
                tp("جاري فحص جميع فيديوهات القناة...", "Inspecting all videos on channel..."),
                "info",
            )
            self.manager.analyze_link(ch_url)
            return

        mode = self.seg_mode.current_key()
        chosen_qual = self.combo_quality.current_key()
        chosen_container = self.combo_container.current_key()
        chosen_audio_lang = self.combo_audio_lang.current_key()

        sub_key = self.combo_sub_source.current_key()
        sub_tr_to = self.combo_sub_translate.current_key()

        if mode == "subtitles_only":
            sub_enabled = True
            if sub_key == "none":
                sub_is_auto = True
                sub_src_lang = self.state.config.fallback_source_lang or "en"
            else:
                sub_is_auto = sub_key.startswith("auto:")
                sub_src_lang = sub_key.split(":", 1)[-1]
        elif sub_key == "none" and sub_tr_to:
            sub_enabled = True
            sub_is_auto = True
            sub_src_lang = self.state.config.fallback_source_lang or "en"
        else:
            sub_enabled = sub_key != "none"
            sub_is_auto = sub_key.startswith("auto:")
            sub_src_lang = sub_key.split(":", 1)[-1] if sub_enabled else ""
            if not sub_enabled:
                sub_tr_to = ""

        if self.sw_save_default.isChecked():
            cfg = self.state.config
            if mode == "video":
                cfg.preferred_quality = chosen_qual
                cfg.preferred_video_format = chosen_container
            elif mode == "audio":
                cfg.preferred_quality = "audio_only"
                cfg.preferred_audio_format = chosen_container
            cfg.enforce_bidi_rtl_fix = self.sw_bidi.isChecked()
            if scope in ("playlist", "channel"):
                cfg.smart_numbering = self.sw_numbering.isChecked()
            if sub_tr_to:
                cfg.preferred_subtitle_lang = sub_tr_to
            elif sub_enabled and sub_src_lang:
                cfg.preferred_subtitle_lang = sub_src_lang
            cfg.save()
            self.state.config_changed.emit()
            self.state.toast_requested.emit(t("settings_saved_toast"), "ok")

        selected_indices: Optional[List[int]] = None
        if scope in ("playlist", "channel") and self.info.entries:
            selected_indices = parse_playlist_selection_range(self.input_range.text(), len(self.info.entries))

        self.manager.enqueue_from_analysis(
            info=self.info,
            scope=scope,
            media_mode=mode,
            quality=chosen_qual,
            container=chosen_container,
            sub_enabled=sub_enabled,
            sub_source_lang=sub_src_lang,
            sub_is_auto=sub_is_auto,
            sub_translate_to=sub_tr_to,
            sub_bidi_fix=self.sw_bidi.isChecked(),
            use_smart_numbering=(self.sw_numbering.isChecked() and scope in ("playlist", "channel")),
            audio_lang=chosen_audio_lang,
            selected_indices=selected_indices,
        )
        self.hide()

    def mousePressEvent(self, event) -> None:
        event.accept()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), T.c("bg0", alpha=205, force_dark=True))
        p.end()
