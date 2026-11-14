from typing import Optional
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.domain.downloader import collect_diagnostics_report, detect_js_runtime, get_ytdlp_version
from app.domain.manager import DownloadManager
from app.i18n import localized_languages, t, tp, ui_language_choices
from app.paths import is_windows_startup_enabled, set_windows_startup
from app.state import AppState
from app.theme import T
from app.ui.widgets import (
    Button,
    GlassCard,
    NumberInput,
    SearchCombo,
    StyledLineEdit,
    ToggleSwitch,
    app_font,
)


def _setting_row(title: str, subtitle: str, control: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    txt_col = QVBoxLayout()
    txt_col.setSpacing(2)
    lbl_t = QLabel(title)
    lbl_t.setFont(app_font(13, QFont.Bold))
    lbl_t.setStyleSheet(f"color: {T.token_str('text')};")
    txt_col.addWidget(lbl_t)
    if subtitle:
        lbl_s = QLabel(subtitle)
        lbl_s.setWordWrap(True)
        lbl_s.setFont(app_font(11, QFont.Medium))
        lbl_s.setStyleSheet(f"color: {T.token_str('text2')};")
        txt_col.addWidget(lbl_s)
    row.addLayout(txt_col, 1)
    row.addWidget(control)
    return row


class SettingsPage(QWidget):
    def __init__(self, state: AppState, manager: DownloadManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self.manager = manager

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 18)
        root.setSpacing(14)

        title = QLabel(t("settings_title"))
        title.setFont(app_font(20, QFont.ExtraBold))
        title.setStyleSheet(f"color: {T.token_str('text')};")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(T.scrollbar_qss())

        body = QWidget()
        body.setObjectName("settingsScrollBody")
        body.setStyleSheet("QWidget#settingsScrollBody { background: transparent; }")
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 6, 20)
        v.setSpacing(14)

        # =====================================================================
        # 1. Core Engines: FFmpeg Auto-Installer, yt-dlp Updater, JS Runtime & Diagnostics
        # =====================================================================
        card_eng = GlassCard()
        lay_eng = QVBoxLayout(card_eng)
        lay_eng.setContentsMargins(20, 16, 20, 16)
        lay_eng.setSpacing(12)

        sec_eng = QLabel(tp("محركات النظام والتحديث الذاتي (FFmpeg & yt-dlp)", "Core Engines & Self-Updater (FFmpeg & yt-dlp)"))
        sec_eng.setFont(app_font(15, QFont.ExtraBold))
        sec_eng.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        lay_eng.addWidget(sec_eng)

        ff_box = QWidget()
        ff_row = QHBoxLayout(ff_box)
        ff_row.setContentsMargins(0, 0, 0, 0)
        ff_row.setSpacing(8)
        self.lbl_ff_status = QLabel()
        self.lbl_ff_status.setFont(app_font(11, QFont.Bold))
        self.btn_ff_auto = Button(
            tp("تثبيت FFmpeg تلقائياً", "Auto-Install FFmpeg"),
            icon_name="downloads",
            variant="emerald",
            height=34,
            compact=True,
        )
        self.btn_ff_auto.clicked.connect(self.manager.trigger_ffmpeg_auto_install)
        btn_ff_browse = Button(t("btn_browse"), icon_name="folder", variant="glass", height=34, compact=True)
        btn_ff_browse.clicked.connect(self._browse_ffmpeg)
        ff_row.addWidget(self.lbl_ff_status)
        ff_row.addWidget(self.btn_ff_auto)
        ff_row.addWidget(btn_ff_browse)
        self._refresh_ff_label()
        lay_eng.addLayout(
            _setting_row(
                tp("محرك الدمج والتحويل الصوتي (FFmpeg)", "FFmpeg Stream Merger & Audio Converter"),
                tp(
                    "يفحص وجود الأداة أولاً؛ فإذا كانت مثبّتة يؤكد جاهزيتها فوراً دون إعادة التحميل",
                    "Checks if FFmpeg is already installed first; only downloads if missing",
                ),
                ff_box,
            )
        )

        ytdlp_box = QWidget()
        ytdlp_row = QHBoxLayout(ytdlp_box)
        ytdlp_row.setContentsMargins(0, 0, 0, 0)
        ytdlp_row.setSpacing(8)
        js_rt = detect_js_runtime()
        js_tag = f" • JS: {js_rt.split(':')[0]}" if js_rt else ""
        self.lbl_ytdlp_ver = QLabel(f"v{get_ytdlp_version()}{js_tag}")
        self.lbl_ytdlp_ver.setFont(app_font(11, QFont.Bold))
        self.lbl_ytdlp_ver.setStyleSheet(f"color: {T.token_str('ok')};")
        self.btn_ytdlp_upd = Button(
            tp("فحص وتحديث yt-dlp", "Check & Update yt-dlp"),
            icon_name="refresh",
            variant="primary",
            height=34,
            compact=True,
        )
        self.btn_ytdlp_upd.clicked.connect(lambda: self.manager.trigger_ytdlp_update(silent=False))
        btn_diag = Button(
            tp("نسخ التشخيص", "Copy Diagnostics"),
            icon_name="copy",
            variant="glass",
            height=34,
            compact=True,
        )
        btn_diag.clicked.connect(self._copy_diagnostics)
        ytdlp_row.addWidget(self.lbl_ytdlp_ver)
        ytdlp_row.addWidget(self.btn_ytdlp_upd)
        ytdlp_row.addWidget(btn_diag)
        lay_eng.addLayout(
            _setting_row(
                tp("فحص وتحديث محرك الاستخراج (yt-dlp)", "yt-dlp Extractor Engine Check & Updater"),
                tp(
                    "يتحقق أولاً من رقم الإصدار الحالي على PyPI مع التحقق الأمني SHA-256 وتحديث yt-dlp-ejs",
                    "Compares your installed version against PyPI first and skips downloading if already up-to-date",
                ),
                ytdlp_box,
            )
        )

        sw_js = ToggleSwitch(self.state.config.js_runtime_enabled)
        sw_js.toggled.connect(lambda v_b: self._save_attr("js_runtime_enabled", v_b))
        lay_eng.addLayout(
            _setting_row(
                tp("تفعيل محرك JavaScript الخارجي (Deno / Node / QuickJS / Bun)", "Enable External JS Runtime for YouTube EJS"),
                tp(
                    "يمرر محركات JS المتوفرة على جهازك إلى yt-dlp لفك تحديات سرعة وجودات يوتيوب بأقصى سرعة",
                    "Passes detected JS runtimes (Deno, Node, QuickJS, Bun) to yt-dlp for YouTube EJS challenges",
                ),
                sw_js,
            )
        )

        sw_auto_upd = ToggleSwitch(self.state.config.auto_update_ytdlp_on_startup)
        sw_auto_upd.toggled.connect(lambda v_b: self._save_attr("auto_update_ytdlp_on_startup", v_b))
        lay_eng.addLayout(
            _setting_row(
                tp("فحص تحديثات yt-dlp تلقائياً عند تشغيل البرنامج", "Auto-Check yt-dlp Updates on Startup"),
                tp("يضمن عمل الروابط دائماً بأحدث إصدار في الخلفية", "Silently checks for extractor updates on startup"),
                sw_auto_upd,
            )
        )
        v.addWidget(card_eng)

        # =====================================================================
        # 2. General, Clipboard Monitor, Scheduler & Post-Queue Actions Card
        # =====================================================================
        card_gen = GlassCard()
        lay_gen = QVBoxLayout(card_gen)
        lay_gen.setContentsMargins(20, 16, 20, 16)
        lay_gen.setSpacing(12)

        sec1 = QLabel(t("settings_general"))
        sec1.setFont(app_font(15, QFont.ExtraBold))
        sec1.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        lay_gen.addWidget(sec1)

        seg_lang = SearchCombo(ui_language_choices(), self.state.config.language, min_width=195, icon_name="globe")
        seg_lang.changed.connect(self._set_language)
        lay_gen.addLayout(
            _setting_row(
                tp("لغة الواجهة", "Interface Language"),
                tp("تبديل فوري للاتجاه RTL / LTR بدون إعادة تشغيل", "Instant RTL / LTR mirroring without restart"),
                seg_lang,
            )
        )

        sw_clip = ToggleSwitch(self.state.config.auto_paste_clipboard)
        sw_clip.toggled.connect(lambda v_b: self._save_attr("auto_paste_clipboard", v_b))
        lay_gen.addLayout(
            _setting_row(
                tp("مراقبة الحافظة التلقائية (Auto-Paste Clipboard)", "Smart Clipboard URL Monitor"),
                tp(
                    "التقاط وتحليل أي رابط فيديو أو قائمة تشغيل بمجرد نسخه في الحافظة تلقائياً",
                    "Automatically detect and analyze media URLs copied to your clipboard",
                ),
                sw_clip,
            )
        )

        sw_notify = ToggleSwitch(self.state.config.notifications_enabled)
        sw_notify.toggled.connect(lambda v_b: self._save_attr("notifications_enabled", v_b))
        lay_gen.addLayout(
            _setting_row(
                tp("الإشعارات المنبثقة", "Desktop Popup Notifications"),
                tp("إظهار تنبيه أنيق عند اكتمال التحميل أو الترجمة", "Show bottom-right alert when downloads finish"),
                sw_notify,
            )
        )

        sw_sound = ToggleSwitch(self.state.config.sound_enabled)
        sw_sound.toggled.connect(lambda v_b: self._save_attr("sound_enabled", v_b))
        lay_gen.addLayout(
            _setting_row(
                tp("المؤثرات الصوتية", "Completion Sound Chime"),
                tp("تشغيل نغمة هادئة عند انتهاء المهمة", "Play subtle audio chime on task completion"),
                sw_sound,
            )
        )

        sw_tray = ToggleSwitch(self.state.config.minimize_to_tray)
        sw_tray.toggled.connect(lambda v_b: self._save_attr("minimize_to_tray", v_b))
        lay_gen.addLayout(
            _setting_row(
                tp("التصغير إلى شريط النظام (System Tray)", "Minimize to System Tray on Close"),
                tp("استمرار التحميلات في الخلفية عند إغلاق النافذة", "Keep active downloads running in background"),
                sw_tray,
            )
        )

        initial_startup = is_windows_startup_enabled() or self.state.config.run_on_startup
        self.sw_startup = ToggleSwitch(initial_startup)
        self.sw_startup.toggled.connect(self._on_toggle_windows_startup)
        lay_gen.addLayout(
            _setting_row(
                tp("التشغيل التلقائي مع بدء الويندوز (Run on Windows Startup)", "Launch Automatically on Windows Startup"),
                tp(
                    "فتح البرنامج تلقائياً عند إقلاع نظام الويندوز لمتابعة التحميلات المجدولة والحافظة",
                    "Automatically start V-Stream Downloader when you sign in to Windows",
                ),
                self.sw_startup,
            )
        )

        sched_box = QWidget()
        sched_row = QHBoxLayout(sched_box)
        sched_row.setContentsMargins(0, 0, 0, 0)
        sched_row.setSpacing(8)
        self.input_sched_time = StyledLineEdit(placeholder="02:00", ltr_mode=True)
        self.input_sched_time.setText(self.state.config.schedule_time or "02:00")
        self.input_sched_time.setFixedSize(95, 34)
        self.input_sched_time.textChanged.connect(self._on_sched_time_edited)
        sw_sched = ToggleSwitch(self.state.config.schedule_enabled)
        sw_sched.toggled.connect(lambda v_b: self._save_attr("schedule_enabled", v_b))
        sched_row.addWidget(self.input_sched_time)
        sched_row.addWidget(sw_sched)
        lay_gen.addLayout(
            _setting_row(
                tp("جدولة بدء التحميلات في وقت محدد (Download Scheduler)", "Scheduled Queue Start Time (HH:MM)"),
                tp(
                    "عند التفعيل، تضاف التحميلات في وضع الانتظار وتبدأ تلقائياً في الساعة المحددة (مثل 02:00 صباحاً)",
                    "Queue tasks in paused state and automatically start downloading at the specified 24h time",
                ),
                sched_box,
            )
        )

        post_actions = [
            ("none", tp("لا شيء (البقاء جاهزاً)", "Do Nothing (Stay Idle)")),
            ("quit_app", tp("إغلاق البرنامج تلقائياً", "Close Application")),
            ("sleep", tp("وضع السكون للكمبيوتر (Sleep)", "Put Computer to Sleep")),
            ("shutdown", tp("إيقاف تشغيل الكمبيوتر (Shutdown)", "Shut Down Computer")),
        ]
        self.combo_post = SearchCombo(post_actions, self.state.config.post_queue_action, min_width=220)
        self.combo_post.changed.connect(lambda k: self._save_attr("post_queue_action", k))
        lay_gen.addLayout(
            _setting_row(
                tp("إجراء ما بعد انتهاء جميع التحميلات", "Post-Queue Completion Action"),
                tp(
                    "يُنفذ لمرة واحدة فقط في الجلسة الحالية بعد عدّ تنازلي 60 ثانية قابل للإلغاء ويعود تلقائياً لـ «لا شيء»",
                    "One-shot session action with a 60s cancellable countdown dialog (resets to None after firing)",
                ),
                self.combo_post,
            )
        )
        v.addWidget(card_gen)

        # =====================================================================
        # 3. Download Engine, Templates, Archive, Metadata & Bandwidth Card
        # =====================================================================
        card_dl = GlassCard()
        lay_dl = QVBoxLayout(card_dl)
        lay_dl.setContentsMargins(20, 16, 20, 16)
        lay_dl.setSpacing(12)

        sec2 = QLabel(t("settings_downloads"))
        sec2.setFont(app_font(15, QFont.ExtraBold))
        sec2.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        lay_dl.addWidget(sec2)

        dir_box = QWidget()
        dir_row = QHBoxLayout(dir_box)
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.setSpacing(8)
        self.lbl_path = QLabel(self.state.config.download_dir)
        self.lbl_path.setFont(app_font(12, QFont.Medium))
        self.lbl_path.setStyleSheet(f"color: {T.token_str('text2')};")
        btn_dir = Button(t("btn_browse"), icon_name="folder", variant="glass", height=34, compact=True)
        btn_dir.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.lbl_path)
        dir_row.addWidget(btn_dir)
        lay_dl.addLayout(
            _setting_row(
                tp("مجلد الحفظ الافتراضي", "Default Download Folder"),
                tp("المسار الذي تُحفظ فيه الفيديوهات والقوائم", "Target directory for saved videos & playlists"),
                dir_box,
            )
        )

        qual_items = [
            ("best", tp("أعلى جودة متاحة (4K/8K)", "Best Available (4K/8K)")),
            ("2160p", "2160p (4K Ultra HD)"),
            ("1440p", "1440p (2K QHD)"),
            ("1080p", "1080p (Full HD)"),
            ("720p", "720p (HD)"),
            ("480p", "480p"),
            ("360p", "360p"),
            ("audio_only", tp("صوت فقط (MP3)", "Audio Only (MP3)")),
        ]
        combo_qual = SearchCombo(qual_items, self.state.config.preferred_quality, icon_name="video")
        combo_qual.changed.connect(lambda q: self._save_attr("preferred_quality", q))
        lay_dl.addLayout(
            _setting_row(
                tp("الجودة الافتراضية للتحميل", "Default Download Quality"),
                tp("الجودة التي يختارها البرنامج تلقائياً عند التحميل الفوري", "Default resolution used for instant downloads"),
                combo_qual,
            )
        )

        scope_items = [
            ("ask", tp("السؤال عند وجود قائمة تشغيل (افتراضي)", "Ask When Playlist Detected")),
            ("single", tp("تحميل الفيديو المنفرد دائماً", "Always Download Single Video")),
            ("playlist", tp("تحميل قائمة التشغيل كاملة دائماً", "Always Download Full Playlist")),
        ]
        combo_scope = SearchCombo(scope_items, self.state.config.smart_mode_scope, min_width=230)
        combo_scope.changed.connect(lambda sc: self._save_attr("smart_mode_scope", sc))
        lay_dl.addLayout(
            _setting_row(
                tp("سلوك الوضع الفوري (Turbo Mode) مع قوائم التشغيل", "Turbo One-Click Playlist Behavior"),
                tp("تحديد ما إذا كان الوضع الفوري يحمّل الفيديو فقط أم القائمة كاملة", "Default scope when Turbo One-Click is active"),
                combo_scope,
            )
        )

        tmpl_items = [
            ("{prefix}{title}", tp("الاسم القياسي: 01 - عنوان الفيديو", "Standard: 01 - Video Title")),
            ("{prefix}{channel} - {title}", tp("اسم القناة + العنوان: 01 - القناة - العنوان", "Channel + Title: 01 - Channel - Title")),
            ("{prefix}{title} [{id}]", tp("العنوان + معرف الفيديو: 01 - العنوان [ID]", "Title + ID: 01 - Title [ID]")),
        ]
        combo_tmpl = SearchCombo(tmpl_items, self.state.config.filename_template, min_width=250)
        combo_tmpl.changed.connect(lambda tm: self._save_attr("filename_template", tm))
        lay_dl.addLayout(
            _setting_row(
                tp("قالب تسمية الملفات المحمّلة", "Output Filename Template"),
                tp("طريقة تنسيق أسماء ملفات الفيديو والصوت عند حفظها", "Pattern used to name downloaded files"),
                combo_tmpl,
            )
        )

        num_conc = NumberInput(self.state.config.max_concurrent_downloads, 1, 10)
        num_conc.valueChanged.connect(lambda n: self._save_attr("max_concurrent_downloads", n))
        lay_dl.addLayout(
            _setting_row(
                tp("عدد التحميلات المتزامنة", "Max Concurrent Downloads"),
                tp("عدد الفيديوهات التي يتم تحميلها في نفس اللحظة", "Number of parallel active download workers"),
                num_conc,
            )
        )

        speed_items = [
            ("0", tp("بدون حد أقصى (أقصى سرعة)", "Unlimited (Full Speed)")),
            ("512", "512 KB/s (~0.5 MB/s)"),
            ("1024", "1024 KB/s (1 MB/s)"),
            ("2048", "2048 KB/s (2 MB/s)"),
            ("5120", "5120 KB/s (5 MB/s)"),
            ("10240", "10240 KB/s (10 MB/s)"),
        ]
        cur_spd = str(self.state.config.speed_limit_kbps or 0)
        combo_spd = SearchCombo(speed_items, cur_spd if cur_spd in dict(speed_items) else "0", min_width=195)
        combo_spd.changed.connect(lambda s_val: self._save_attr("speed_limit_kbps", int(s_val)))
        lay_dl.addLayout(
            _setting_row(
                tp("الحد الأقصى لإجمالي سرعة التحميل (Global Bandwidth Limit)", "Global Download Speed Limit"),
                tp("يتم توزيع الحد الأقصى للسرعة بالتساوي على جميع التحميلات النشطة", "Shared evenly across all currently active downloads"),
                combo_spd,
            )
        )

        sw_smart = ToggleSwitch(self.state.config.smart_numbering)
        sw_smart.toggled.connect(lambda v_b: self._save_attr("smart_numbering", v_b))
        lay_dl.addLayout(
            _setting_row(
                t("smart_numbering_toggle"),
                tp(
                    "ترقيم ملفات القائمة تلقائياً (01 - اسم الفيديو، أو 001 عندما تزيد عن 100 فيديو)",
                    "Prefix playlist files with 01 - Title (or 001 - Title when playlist >= 100 items)",
                ),
                sw_smart,
            )
        )

        sw_subf = ToggleSwitch(self.state.config.create_subfolder_for_playlists)
        sw_subf.toggled.connect(lambda v_b: self._save_attr("create_subfolder_for_playlists", v_b))
        lay_dl.addLayout(
            _setting_row(
                tp("إنشاء مجلد فرعي لكل قائمة تشغيل أو قناة", "Create Dedicated Subfolder per Playlist/Channel"),
                tp("تنظيم ملفات كل بلاي ليست في فولدر مستقل باسمها", "Organize playlist items neatly inside their own folder"),
                sw_subf,
            )
        )

        sw_arch = ToggleSwitch(self.state.config.use_download_archive)
        sw_arch.toggled.connect(lambda v_b: self._save_attr("use_download_archive", v_b))
        lay_dl.addLayout(
            _setting_row(
                tp("تفعيل سجل التحميلات (Download Archive) لتخطي المكرر", "Enable Download Archive Log"),
                tp(
                    "تذكر الفيديوهات التي تم تحميلها سابقاً وتخطيها تلقائياً عند تحديث قوائم التشغيل",
                    "Skip videos that were already downloaded in previous sessions",
                ),
                sw_arch,
            )
        )

        sw_open_fld = ToggleSwitch(self.state.config.open_folder_on_complete)
        sw_open_fld.toggled.connect(lambda v_b: self._save_attr("open_folder_on_complete", v_b))
        lay_dl.addLayout(
            _setting_row(
                tp("فتح مجلد الحفظ تلقائياً عند اكتمال التحميل", "Open Download Folder When Completed"),
                tp("يفتح مجلد الملف المحمّل تلقائياً فور انتهاء المهمة", "Automatically opens the destination folder when a download finishes"),
                sw_open_fld,
            )
        )

        cleanup_items = [
            ("0", tp("الاحتفاظ بالسجل دائماً (بدون حذف تلقائي)", "Keep History (No Auto-Delete)")),
            ("1", tp("حذف المكتمل بعد يوم واحد", "Remove Completed After 1 Day")),
            ("3", tp("حذف المكتمل بعد 3 أيام", "Remove Completed After 3 Days")),
            ("7", tp("حذف المكتمل بعد 7 أيام", "Remove Completed After 7 Days")),
            ("30", tp("حذف المكتمل بعد 30 يوماً", "Remove Completed After 30 Days")),
        ]
        cur_cln = str(self.state.config.auto_cleanup_days or 0)
        combo_cln = SearchCombo(cleanup_items, cur_cln if cur_cln in dict(cleanup_items) else "0", min_width=220)
        combo_cln.changed.connect(lambda d_val: self._on_cleanup_days_changed(int(d_val)))
        lay_dl.addLayout(
            _setting_row(
                tp("تنظيف سجل المهام المكتملة تلقائياً", "Auto-Clean Completed Tasks From List"),
                tp(
                    "حذف البطاقات المكتملة القديمة من واجهة البرنامج تلقائياً (دون المساس بالملفات المحمّلة)",
                    "Automatically prunes old completed entries from the queue list (keeps downloaded files on disk)",
                ),
                combo_cln,
            )
        )

        sw_emb_thumb = ToggleSwitch(self.state.config.embed_thumbnail)
        sw_emb_thumb.toggled.connect(lambda v_b: self._save_attr("embed_thumbnail", v_b))
        lay_dl.addLayout(
            _setting_row(
                tp("تضمين الصورة المصغّرة غلافاً للملف (Embed Thumbnail)", "Embed Video Thumbnail as Cover Art"),
                tp("دمج صورة الفيديو داخل ملف MP4 / MKV / MP3 (يتطلب FFmpeg)", "Embeds cover artwork into MP4/MKV/MP3 files"),
                sw_emb_thumb,
            )
        )

        sw_emb_meta = ToggleSwitch(self.state.config.embed_metadata)
        sw_emb_meta.toggled.connect(lambda v_b: self._save_attr("embed_metadata", v_b))
        lay_dl.addLayout(
            _setting_row(
                tp("تضمين البيانات الوصفية وفصول الفيديو (Metadata & Chapters)", "Embed Media Metadata & Video Chapters"),
                tp("حفظ اسم القناة وتاريخ النشر وتقسيمات الفصول داخل الملف", "Writes artist, title, and chapter markers into the media file"),
                sw_emb_meta,
            )
        )
        v.addWidget(card_dl)

        # =====================================================================
        # 4. Cookies (Browser / File) & Proxy Card
        # =====================================================================
        card_net = GlassCard()
        lay_net = QVBoxLayout(card_net)
        lay_net.setContentsMargins(20, 16, 20, 16)
        lay_net.setSpacing(12)

        sec_net = QLabel(tp("الكوكيز والفيديوهات المقيّدة والبروكسي (Cookies & Proxy)", "Cookies, Private Videos & Proxy"))
        sec_net.setFont(app_font(15, QFont.ExtraBold))
        sec_net.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        lay_net.addWidget(sec_net)

        browser_items = [
            ("none", tp("بدون سحب كوكيز (افتراضي)", "None (No Browser Cookies)")),
            ("firefox", "Mozilla Firefox (★ Recommended)"),
            ("chrome", "Google Chrome"),
            ("edge", "Microsoft Edge"),
            ("brave", "Brave Browser"),
            ("opera", "Opera"),
        ]
        combo_browser = SearchCombo(browser_items, self.state.config.cookies_browser, min_width=220)
        combo_browser.changed.connect(self._on_browser_cookie_changed)
        lay_net.addLayout(
            _setting_row(
                tp("سحب الكوكيز تلقائياً من المتصفح", "Extract Cookies from Browser"),
                tp(
                    "تنبيه مهم على ويندوز: متصفحات Chrome و Edge الحديثة تشفّر الكوكيز أثناء عملها (App-Bound Encryption)؛ لذا يُنصح بشدة باستخدام Firefox أو ملف cookies.txt",
                    "Windows Note: Modern Chrome & Edge lock/encrypt cookies while running (App-Bound Encryption); Firefox or cookies.txt is strongly recommended",
                ),
                combo_browser,
            )
        )

        cfile_box = QWidget()
        cfile_row = QHBoxLayout(cfile_box)
        cfile_row.setContentsMargins(0, 0, 0, 0)
        cfile_row.setSpacing(8)
        self.lbl_cookie_file = QLabel(self.state.config.cookies_file_path or tp("غير محدد", "None"))
        self.lbl_cookie_file.setFont(app_font(11, QFont.Medium))
        self.lbl_cookie_file.setStyleSheet(f"color: {T.token_str('text2')};")
        btn_cfile = Button(tp("ملف cookies.txt...", "Browse cookies.txt..."), icon_name="folder", variant="glass", height=32, compact=True)
        btn_cfile.clicked.connect(self._browse_cookies_file)
        btn_cfile_clr = Button(tp("مسح", "Clear"), variant="ghost", height=32, compact=True)
        btn_cfile_clr.clicked.connect(self._clear_cookies_file)
        cfile_row.addWidget(self.lbl_cookie_file)
        cfile_row.addWidget(btn_cfile)
        cfile_row.addWidget(btn_cfile_clr)
        lay_net.addLayout(
            _setting_row(
                tp("أو استخدام ملف كوكيز خارجي (Netscape cookies.txt)", "Or Use External cookies.txt File"),
                tp("اختياري: إذا كنت تفضل تصدير ملف cookies.txt يدوياً", "Optional manual cookies.txt file path"),
                cfile_box,
            )
        )

        proxy_box = QWidget()
        proxy_row = QHBoxLayout(proxy_box)
        proxy_row.setContentsMargins(0, 0, 0, 0)
        proxy_row.setSpacing(6)
        self.input_proxy = StyledLineEdit(
            placeholder="http://127.0.0.1:8080  |  socks5://127.0.0.1:1080",
            ltr_mode=True,
        )
        self.input_proxy.setText(self.state.config.proxy_url)
        self.input_proxy.setMinimumWidth(260)
        self.input_proxy.setFixedHeight(36)
        self.input_proxy.textChanged.connect(self._on_proxy_text_changed)
        self.input_proxy.returnPressed.connect(
            lambda: self.state.toast_requested.emit(t("settings_saved_toast"), "ok")
        )
        btn_proxy_paste = Button(t("edit_paste"), icon_name="paste", variant="glass", height=34, compact=True)
        btn_proxy_paste.clicked.connect(self._paste_proxy)
        btn_proxy_clear = Button(tp("مسح", "Clear"), variant="ghost", height=34, compact=True)
        btn_proxy_clear.clicked.connect(self._clear_proxy)
        proxy_row.addWidget(self.input_proxy, 1)
        proxy_row.addWidget(btn_proxy_paste)
        proxy_row.addWidget(btn_proxy_clear)
        lay_net.addLayout(
            _setting_row(
                tp("خادم البروكسي (HTTP / SOCKS5 Proxy)", "Network Proxy Server (HTTP / SOCKS5)"),
                tp(
                    "اكتب أو الصق عنوان البروكسي مباشرة لتخطي الحجب الجغرافي (يُحفظ تلقائياً أثناء الكتابة)",
                    "Type or paste your HTTP/SOCKS5 proxy URL (saved automatically as you type)",
                ),
                proxy_box,
            )
        )
        v.addWidget(card_net)

        # =====================================================================
        # 5. Smart Subtitles & BiDi RTL/LTR Sync Card
        # =====================================================================
        card_sub = GlassCard()
        lay_sub = QVBoxLayout(card_sub)
        lay_sub.setContentsMargins(20, 16, 20, 16)
        lay_sub.setSpacing(12)

        sec3 = QLabel(t("settings_subtitles"))
        sec3.setFont(app_font(15, QFont.ExtraBold))
        sec3.setStyleSheet(f"color: {T.token_str('accent_hi')};")
        lay_sub.addWidget(sec3)

        sub_modes = [
            ("prefer_target_then_translate", tp("تفضيل اللغة الأصلية ثم الترجمة التلقائية", "Prefer Native Track, Else Auto-Translate")),
            ("always_translate", tp("ترجمة دائماً إلى لغتي المفضلة", "Always Translate to Preferred Language")),
            ("original_only", tp("تحميل الترجمة الأصلية فقط بدون ترجمة", "Original Subtitle Only (No Translation)")),
            ("none", tp("إيقاف تحميل الترجمة افتراضياً", "Disable Subtitles by Default")),
        ]
        combo_sub_mode = SearchCombo(sub_modes, self.state.config.subtitle_mode, min_width=250)
        combo_sub_mode.changed.connect(lambda m_k: self._save_attr("subtitle_mode", m_k))
        lay_sub.addLayout(
            _setting_row(
                tp("وضع التعامل الافتراضي مع الترجمة", "Default Subtitle Selection Mode"),
                tp("كيف يتعامل البرنامج تلقائياً مع ملفات الترجمة", "How subtitles are selected and translated by default"),
                combo_sub_mode,
            )
        )

        combo_pref_sub = SearchCombo(localized_languages(), self.state.config.preferred_subtitle_lang, icon_name="translate")
        combo_pref_sub.changed.connect(lambda k: self._save_attr("preferred_subtitle_lang", k))
        lay_sub.addLayout(
            _setting_row(
                tp("اللغة المفضلة للترجمة (تُفحص أولاً في الفيديو)", "Preferred Target Subtitle Language"),
                tp(
                    "إذا وجد البرنامج هذه اللغة في الفيديو يحمّلها مباشرة، وإلا يترجم إليها تلقائياً",
                    "Uses native track if available on video; otherwise auto-translates into it",
                ),
                combo_pref_sub,
            )
        )

        combo_fb_sub = SearchCombo(localized_languages(), self.state.config.fallback_source_lang, icon_name="subtitles")
        combo_fb_sub.changed.connect(lambda k: self._save_attr("fallback_source_lang", k))
        lay_sub.addLayout(
            _setting_row(
                tp("لغة المصدر الاحتياطية عند عدم توفر لغتك", "Fallback Source Language for Translation"),
                tp("اللغة التي يسحبها البرنامج ليترجم منها (عادة الإنجليزية)", "Source track language fetched when translating"),
                combo_fb_sub,
            )
        )

        sw_auto_gen = ToggleSwitch(self.state.config.allow_auto_generated_subs)
        sw_auto_gen.toggled.connect(lambda v_b: self._save_attr("allow_auto_generated_subs", v_b))
        lay_sub.addLayout(
            _setting_row(
                tp("دعم الترجمة التلقائية من يوتيوب", "Allow YouTube Auto-Generated Captions"),
                tp(
                    "إمكانية سحب الترجمة المولدة تلقائياً ودمج الجمل المقطعة وترجمتها بدقة",
                    "Fallback to YouTube auto-captions, coalesce fragments, and translate cleanly",
                ),
                sw_auto_gen,
            )
        )

        sw_bidi = ToggleSwitch(self.state.config.enforce_bidi_rtl_fix)
        sw_bidi.toggled.connect(lambda v_b: self._save_attr("enforce_bidi_rtl_fix", v_b))
        lay_sub.addLayout(
            _setting_row(
                t("sub_bidi_fix"),
                tp(
                    "منع انعكاس الأقواس والأرقام وعلامات الترقيم في الترجمة العربية مع الحفاظ التام على التوقيت",
                    "Fixes RTL/LTR punctuation & bracket ordering while preserving exact timestamps",
                ),
                sw_bidi,
            )
        )

        sw_tv_bidi = ToggleSwitch(self.state.config.tv_safe_bidi)
        sw_tv_bidi.toggled.connect(lambda v_b: self._save_attr("tv_safe_bidi", v_b))
        lay_sub.addLayout(
            _setting_row(
                tp("وضع BiDi المتوافق مع شاشات التلفزيون الذكية (Smart TV Safe)", "Smart TV & Hardware Player Safe BiDi"),
                tp(
                    "يستخدم علامات RLM/LRM القياسية ويتجنب رموز RLE/PDF التي قد تظهر كمربعات على بعض شاشات التلفزيون",
                    "Uses universal RLM/LRM marks instead of RLE/PDF controls that render as boxes on some Smart TVs",
                ),
                sw_tv_bidi,
            )
        )

        sw_emb_sub = ToggleSwitch(self.state.config.embed_subtitles_in_video)
        sw_emb_sub.toggled.connect(lambda v_b: self._save_attr("embed_subtitles_in_video", v_b))
        lay_sub.addLayout(
            _setting_row(
                tp("دمج الترجمة أيضاً كمسار داخلي في ملف الفيديو (Mux Subtitle)", "Also Embed Subtitle Track Inside Video File"),
                tp("بالإضافة لحفظ ملف .srt الخارجي، يتم تضمينه داخل الفيديو عبر FFmpeg", "Muxes the synced .srt into MP4/MKV alongside the standalone .srt file"),
                sw_emb_sub,
            )
        )

        # Privacy & API Quota Disclosure for Subtitle Translation
        priv_lbl = QLabel(
            tp(
                "إفصاح خصوصية الترجمة: عند ترجمة ملفات .srt/.vtt يتم إرسال جمل النص فقط إلى خدمة Google Translate (ومزود MyMemory الاحتياطي بحصة مجانية يومية) دون إرسال أي بيانات شخصية.",
                "Subtitle Translation Privacy Notice: Translating subtitles sends cue text to Google Translate (and MyMemory fallback API, subject to daily free quota) with zero personal data.",
            )
        )
        priv_lbl.setWordWrap(True)
        priv_lbl.setFont(app_font(10, QFont.Medium))
        priv_lbl.setStyleSheet(f"color: {T.token_str('text3')}; padding-top: 4px;")
        lay_sub.addWidget(priv_lbl)

        v.addWidget(card_sub)
        v.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self.state.ffmpeg_status_changed.connect(lambda _ok, _p: self._refresh_ff_label())
        self.state.config_changed.connect(self._on_config_changed)

    def _copy_diagnostics(self) -> None:
        report = collect_diagnostics_report(self.state.config)
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setText(report)
        self.state.toast_requested.emit(
            tp("✓ تم نسخ تقرير التشخيص الفني إلى الحافظة", "✓ Diagnostics report copied to clipboard"),
            "ok",
        )

    def _on_browser_cookie_changed(self, b_key: str) -> None:
        self._save_attr("cookies_browser", b_key)
        if b_key in ("chrome", "edge", "brave", "opera"):
            self.state.toast_requested.emit(
                tp(
                    "ملاحظة: متصفح Chrome/Edge على ويندوز يشفّر الكوكيز أثناء عمله — يُفضّل Firefox أو ملف cookies.txt",
                    "Note: Chrome/Edge on Windows encrypts cookies while open — Firefox or cookies.txt is recommended",
                ),
                "warn",
            )

    def _on_cleanup_days_changed(self, days: int) -> None:
        self._save_attr("auto_cleanup_days", days)
        if days > 0:
            self.state.prune_expired_history(save_immediately=True)

    def _refresh_ff_label(self) -> None:
        if self.state.ffmpeg_available:
            self.lbl_ff_status.setText(tp("✓ مفعّل وجاهز", "✓ Active & Ready"))
            self.lbl_ff_status.setStyleSheet(f"color: {T.token_str('ok')};")
            self.btn_ff_auto.setText(tp("فحص FFmpeg (مثبّت ✓)", "Verify FFmpeg (Installed ✓)"))
            self.btn_ff_auto.set_icon("check")
            self.btn_ff_auto.set_variant("glass")
        else:
            self.lbl_ff_status.setText(tp("غير مثبت (اضغط للتثبيت التلقائي)", "Missing (Click Auto-Install)"))
            self.lbl_ff_status.setStyleSheet(f"color: {T.token_str('warn')};")
            self.btn_ff_auto.setText(tp("تثبيت FFmpeg تلقائياً", "Auto-Install FFmpeg"))
            self.btn_ff_auto.set_icon("downloads")
            self.btn_ff_auto.set_variant("emerald")

    def _on_config_changed(self) -> None:
        js_rt = detect_js_runtime()
        js_tag = f" • JS: {js_rt.split(':')[0]}" if js_rt else ""
        self.lbl_ytdlp_ver.setText(f"v{get_ytdlp_version()}{js_tag}")
        self._refresh_ff_label()

    def _on_proxy_text_changed(self, txt: str) -> None:
        self.state.config.proxy_url = txt.strip()
        self.state.config.save()

    def _paste_proxy(self) -> None:
        cb = QGuiApplication.clipboard()
        if cb is not None and cb.text().strip():
            self.input_proxy.setText(cb.text().strip())
            self.input_proxy.setFocus()
            self.state.toast_requested.emit(t("settings_saved_toast"), "ok")

    def _clear_proxy(self) -> None:
        self.input_proxy.clear()
        self.state.config.proxy_url = ""
        self.state.config.save()
        self.state.toast_requested.emit(t("settings_saved_toast"), "ok")

    def _on_sched_time_edited(self, txt: str) -> None:
        val = txt.strip() or "02:00"
        self.state.config.schedule_time = val
        self.state.config.save()

    def _browse_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("btn_browse"), self.state.config.download_dir)
        if folder:
            self.lbl_path.setText(folder)
            self._save_attr("download_dir", folder)

    def _browse_ffmpeg(self) -> None:
        file_p, _ = QFileDialog.getOpenFileName(
            self,
            tp("اختر ملف ffmpeg التنفيذي", "Select ffmpeg executable"),
            self.state.config.ffmpeg_custom_path or "",
        )
        if file_p:
            self._save_attr("ffmpeg_custom_path", file_p)
            self.manager.refresh_ffmpeg_status(notify_if_missing=False)

    def _browse_cookies_file(self) -> None:
        file_p, _ = QFileDialog.getOpenFileName(
            self,
            tp("اختر ملف cookies.txt", "Select cookies.txt file"),
            "",
            "Text Files (*.txt);;All Files (*)",
        )
        if file_p:
            self.lbl_cookie_file.setText(file_p)
            self._save_attr("cookies_file_path", file_p)

    def _clear_cookies_file(self) -> None:
        self.lbl_cookie_file.setText(tp("غير محدد", "None"))
        self._save_attr("cookies_file_path", "")

    def _on_toggle_windows_startup(self, enabled: bool) -> None:
        ok = set_windows_startup(enabled)
        self.state.config.run_on_startup = enabled
        self.state.config.save()
        if ok:
            self.state.toast_requested.emit(
                tp(
                    "✓ تم تفعيل التشغيل التلقائي مع بدء الويندوز" if enabled else "تم إيقاف التشغيل التلقائي مع بدء الويندوز",
                    "✓ Enabled launch on Windows startup" if enabled else "Disabled launch on Windows startup",
                ),
                "ok" if enabled else "info",
            )
        else:
            self.state.toast_requested.emit(
                tp("تعذّر تحديث إعداد بدء التشغيل في النظام", "Could not update OS startup entry"),
                "warn",
            )

    def _set_language(self, lang: str) -> None:
        if lang != self.state.config.language:
            self.state.config.language = lang
            self.state.config.save()
            self.state.language_changed.emit(lang)

    def _save_attr(self, key: str, val: object) -> None:
        setattr(self.state.config, key, val)
        self.state.config.save()
        self.state.config_changed.emit()
