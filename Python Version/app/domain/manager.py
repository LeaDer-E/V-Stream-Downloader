from datetime import datetime
from pathlib import Path
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
import uuid
from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import QApplication

from app.domain.downloader import (
    BlobUrlDetectedError,
    CancelRequestedError,
    PauseRequestedError,
    analyze_media_url,
    build_safe_output_stem,
    cleanup_task_temp_files,
    execute_download_task,
    extract_video_id_from_url,
    fetch_thumbnail_cached,
    find_ffmpeg_path,
    install_ffmpeg_automatically,
    sanitize_filename,
    update_ytdlp_runtime,
    verify_ffmpeg_working,
)
from app.domain.subtitles import (
    SubtitleCancelRequested,
    SubtitlePauseRequested,
    process_and_sync_subtitle,
)
from app.i18n import smart_pad_index, t, tp
from app.state import AnalyzedMediaInfo, AppState, DownloadTaskItem, SubtitleJobItem
from app.workers import run_async, wait_for_all_workers


def resolve_smart_subtitle_choice(
    info: AnalyzedMediaInfo,
    pref_lang: str = "ar",
    fallback_lang: str = "en",
    allow_auto: bool = True,
    subtitle_mode: str = "prefer_target_then_translate",
    do_translate_flag: bool = True,
) -> Tuple[bool, str, bool, str]:
    if subtitle_mode == "none":
        return False, "", False, ""

    if subtitle_mode != "always_translate":
        for trk in info.manual_subtitles:
            if trk.lang_code == pref_lang or trk.lang_code.startswith(f"{pref_lang}-"):
                return True, trk.lang_code, False, ""

    if subtitle_mode == "original_only":
        for trk in info.manual_subtitles:
            if trk.lang_code.startswith(fallback_lang):
                return True, trk.lang_code, False, ""
        if info.manual_subtitles:
            return True, info.manual_subtitles[0].lang_code, False, ""
        if allow_auto and info.auto_subtitles:
            return True, info.auto_subtitles[0].lang_code, True, ""
        return False, "", False, ""

    target_tr = pref_lang if do_translate_flag else ""

    for trk in info.manual_subtitles:
        if trk.lang_code.startswith(fallback_lang):
            return True, trk.lang_code, False, target_tr

    if info.manual_subtitles:
        return True, info.manual_subtitles[0].lang_code, False, target_tr

    if allow_auto:
        if subtitle_mode != "always_translate":
            for trk in info.auto_subtitles:
                if trk.lang_code == pref_lang or trk.lang_code.startswith(f"{pref_lang}-"):
                    return True, trk.lang_code, True, ""
        for trk in info.auto_subtitles:
            if trk.lang_code.startswith(fallback_lang):
                return True, trk.lang_code, True, target_tr
        if info.auto_subtitles:
            return True, info.auto_subtitles[0].lang_code, True, target_tr

    return False, "", False, ""


class _TaskSignalBridge(QObject):
    progress_signal = Signal(str, dict)
    completed_signal = Signal(str, dict)
    paused_signal = Signal(str)
    canceled_signal = Signal(str)
    failed_signal = Signal(str, str)
    blob_detected_signal = Signal(str, str)

    # Subtitle Studio Job signals
    sub_progress_signal = Signal(str, int, int, float)
    sub_completed_signal = Signal(str, str, int, int)
    sub_paused_signal = Signal(str)
    sub_canceled_signal = Signal(str)
    sub_failed_signal = Signal(str, str)

    # Maintenance signals (FFmpeg / yt-dlp)
    maint_progress_signal = Signal(str)
    maint_done_signal = Signal(bool, str, str)  # ok, msg, kind ("ffmpeg" | "ytdlp")


class DownloadManager(QObject):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self._bridge = _TaskSignalBridge()
        self._bridge.progress_signal.connect(self._on_worker_progress)
        self._bridge.completed_signal.connect(self._on_worker_completed)
        self._bridge.paused_signal.connect(self._on_worker_paused)
        self._bridge.canceled_signal.connect(self._on_worker_canceled)
        self._bridge.failed_signal.connect(self._on_worker_failed)
        self._bridge.blob_detected_signal.connect(self._on_blob_detected)

        self._bridge.sub_progress_signal.connect(self._on_sub_worker_progress)
        self._bridge.sub_completed_signal.connect(self._on_sub_worker_completed)
        self._bridge.sub_paused_signal.connect(self._on_sub_worker_paused)
        self._bridge.sub_canceled_signal.connect(self._on_sub_worker_canceled)
        self._bridge.sub_failed_signal.connect(self._on_sub_worker_failed)

        self._bridge.maint_progress_signal.connect(self._on_maint_progress)
        self._bridge.maint_done_signal.connect(self._on_maint_done)

        self._running_ids: set[str] = set()
        self._control_flags: Dict[str, str] = {}

        self._running_sub_ids: set[str] = set()
        self._sub_control_flags: Dict[str, str] = {}
        self._shutting_down = False
        self._ffmpeg_busy = False
        self._ytdlp_busy = False

        for tid, t_item in list(self.state.tasks.items()):
            if t_item.thumbnail_url:
                self._load_thumbnail_async(tid, t_item.thumbnail_url)

        self.refresh_ffmpeg_status(notify_if_missing=True)

        self._scheduler_timer = QTimer(self)
        self._scheduler_timer.setInterval(20_000)
        self._scheduler_timer.timeout.connect(self._check_scheduled_queue)
        self._scheduler_timer.start()

        # Auto-resume any 'queued' download tasks and subtitle jobs restored on startup
        if hasattr(QTimer, "singleShot"):
            QTimer.singleShot(600, self._auto_resume_restored_queues)
            if self.state.config.auto_update_ytdlp_on_startup:
                QTimer.singleShot(2500, lambda: self.trigger_ytdlp_update(silent=True))

    def _auto_resume_restored_queues(self) -> None:
        if self._shutting_down:
            return
        if not self.state.config.schedule_enabled:
            has_queued = any(t_item.status == "queued" for t_item in self.state.tasks.values())
            if has_queued:
                self.pump_queue()
        has_sub_queued = any(jb.status == "queued" for jb in self.state.sub_jobs.values())
        if has_sub_queued:
            self.pump_sub_queue()

    def refresh_ffmpeg_status(self, notify_if_missing: bool = False) -> bool:
        ff_path = find_ffmpeg_path(self.state.config.ffmpeg_custom_path)
        self.state.ffmpeg_available = bool(ff_path)
        self.state.ffmpeg_resolved_path = ff_path or ""
        self.state.ffmpeg_status_changed.emit(self.state.ffmpeg_available, self.state.ffmpeg_resolved_path)
        if notify_if_missing and not self.state.ffmpeg_available:
            QTimer.singleShot(
                900,
                lambda: self.state.toast_requested.emit(
                    tp(
                        "تنبيه: أداة FFmpeg غير موجودة — افتح الإعدادات لتحميلها بضغطة واحدة لتفعيل دمج 1080p/4K وتحويل MP3",
                        "Notice: FFmpeg not found — open Settings to auto-install FFmpeg in 1 click for 1080p/4K & MP3",
                    ),
                    "warn",
                ),
            )
        return self.state.ffmpeg_available

    def trigger_ffmpeg_auto_install(self) -> None:
        """
        First checks if FFmpeg is already installed and working:
        - If already installed, confirms immediately without re-downloading!
        - Otherwise downloads and installs FFmpeg once.
        """
        if self._ffmpeg_busy:
            self.state.toast_requested.emit(
                tp("جاري فحص/تثبيت FFmpeg بالفعل — يرجى الانتظار...", "FFmpeg check/install is already in progress..."),
                "info",
            )
            return

        existing_ff = verify_ffmpeg_working(self.state.config.ffmpeg_custom_path)
        if existing_ff:
            if not self.state.config.ffmpeg_custom_path:
                self.state.config.ffmpeg_custom_path = existing_ff
                self.state.config.save()
            self.refresh_ffmpeg_status(notify_if_missing=False)
            self.state.toast_requested.emit(
                tp(
                    "✓ تم الفحص: أداة FFmpeg مثبتة ومفعّلة بالفعل وجاهزة للعمل — لا حاجة لإعادة التحميل!",
                    "✓ Verified: FFmpeg is already installed and ready — no re-download needed!",
                ),
                "ok",
            )
            return

        self._ffmpeg_busy = True
        self.state.toast_requested.emit(
            tp("أداة FFmpeg غير موجودة — بدء التحميل والتثبيت التلقائي...", "FFmpeg not found — starting automatic download & installation..."),
            "info",
        )
        custom_p = self.state.config.ffmpeg_custom_path

        def _job() -> Tuple[bool, str, bool]:
            return install_ffmpeg_automatically(
                custom_path=custom_p,
                progress_cb=lambda _pct, msg: self._bridge.maint_progress_signal.emit(msg),
                force=False,
            )

        run_async(
            _job,
            on_done=lambda res: self._bridge.maint_done_signal.emit(res[0], res[1], "ffmpeg"),
            on_error=lambda err: self._bridge.maint_done_signal.emit(False, err, "ffmpeg"),
        )

    def trigger_ytdlp_update(self, silent: bool = False) -> None:
        # Safety: Block updating yt-dlp while any download task is actively running
        # because updating reloads sys.modules["yt_dlp"] in-place!
        if self._running_ids or self.state.active_count() > 0:
            if not silent:
                self.state.toast_requested.emit(
                    tp(
                        "لا يمكن تحديث yt-dlp أثناء وجود تحميلات نشطة — أوقف التحميلات مؤقتاً أو انتظر اكتمالها",
                        "Cannot update yt-dlp while downloads are active — pause or wait for them to finish",
                    ),
                    "warn",
                )
            return

        if self._ytdlp_busy:
            if not silent:
                self.state.toast_requested.emit(
                    tp("جاري فحص/تحديث yt-dlp بالفعل — يرجى الانتظار...", "yt-dlp check/update is already in progress..."),
                    "info",
                )
            return

        self._ytdlp_busy = True
        if not silent:
            self.state.toast_requested.emit(
                tp("جاري فحص إصدار محرك yt-dlp...", "Checking yt-dlp version..."),
                "info",
            )

        def _job() -> Tuple[bool, str]:
            return update_ytdlp_runtime(
                progress_cb=(None if silent else lambda msg: self._bridge.maint_progress_signal.emit(msg)),
                force=False,
            )

        run_async(
            _job,
            on_done=lambda res: self._bridge.maint_done_signal.emit(res[0], res[1], "ytdlp"),
            on_error=lambda err: self._bridge.maint_done_signal.emit(False, err, "ytdlp"),
        )

    def _on_maint_progress(self, msg: str) -> None:
        if msg:
            self.state.toast_requested.emit(msg, "info")

    def _on_maint_done(self, ok: bool, msg: str, kind: str) -> None:
        if kind == "ffmpeg":
            self._ffmpeg_busy = False
            if ok:
                self.state.config.ffmpeg_custom_path = msg
                self.state.config.save()
                self.refresh_ffmpeg_status(notify_if_missing=False)
                self.state.toast_requested.emit(
                    tp("✓ تم تثبيت وتفعيل FFmpeg بنجاح! كل الأمور جاهزة.", "✓ FFmpeg installed & activated!"),
                    "ok",
                )
            else:
                self.state.toast_requested.emit(msg, "danger")
        elif kind == "ytdlp":
            self._ytdlp_busy = False
            self.state.toast_requested.emit(msg, "ok" if ok else "warn")
            self.state.config_changed.emit()

    def _check_scheduled_queue(self) -> None:
        """
        Resilient Scheduler:
        Checks if current time >= `schedule_time` AND `last_schedule_run_date != today`
        so even if the PC was asleep or the app was opened a few minutes after `schedule_time`,
        today's scheduled queue still starts reliably!
        """
        if self._shutting_down or not self.state.config.schedule_enabled:
            return
        target_hm = (self.state.config.schedule_time or "").strip()
        if not target_hm or ":" not in target_hm:
            return
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        now_hm = now.strftime("%H:%M")

        has_waiting = any(t_item.status in ("paused", "queued") for t_item in self.state.tasks.values())
        if not has_waiting:
            return

        if now_hm >= target_hm and self.state.config.last_schedule_run_date != today_str:
            self.state.config.last_schedule_run_date = today_str
            self.state.config.save()
            self.resume_all(include_failed=False)
            self.pump_queue()

    def cancel_analysis(self) -> None:
        """Immediately cancels any active link analysis and resets the UI state."""
        self._analysis_seq = getattr(self, "_analysis_seq", 0) + 1
        self._analysis_canceled = True
        self.state.analysis_failed.emit("")
        self.state.toast_requested.emit(
            tp("تم إلغاء تحليل الرابط فوراً", "Link analysis canceled"),
            "info",
        )

    def analyze_link(self, url: str, custom_referer: str = "") -> None:
        clean = url.strip()
        if not clean:
            return
        self._analysis_seq = getattr(self, "_analysis_seq", 0) + 1
        req_id = self._analysis_seq
        self._analysis_canceled = False
        self.state.analysis_started.emit(clean)
        cfg = self.state.config

        def _job() -> Optional[AnalyzedMediaInfo]:
            try:
                return analyze_media_url(clean, custom_referer=custom_referer, cfg=cfg)
            except BlobUrlDetectedError as b_exc:
                if req_id == getattr(self, "_analysis_seq", 0) and not getattr(self, "_analysis_canceled", False):
                    self._bridge.blob_detected_signal.emit(b_exc.raw_blob_url, b_exc.origin_domain)
                return None

        def _done(info: Optional[AnalyzedMediaInfo]) -> None:
            if req_id != getattr(self, "_analysis_seq", 0) or getattr(self, "_analysis_canceled", False):
                return
            if info is not None:
                self.state.analysis_completed.emit(info)
            else:
                self.state.analysis_failed.emit("")

        def _err(msg: str) -> None:
            if req_id != getattr(self, "_analysis_seq", 0) or getattr(self, "_analysis_canceled", False):
                return
            self.state.analysis_failed.emit(msg)
            if msg:
                self.state.toast_requested.emit(msg[:140], "danger")

        run_async(_job, on_done=_done, on_error=_err)

    def _on_blob_detected(self, raw_blob_url: str, origin_domain: str) -> None:
        self.state.blob_help_requested.emit(raw_blob_url, origin_domain)

    def enqueue_smart_one_click(self, info: AnalyzedMediaInfo, scope: Optional[str] = None) -> None:
        cfg = self.state.config
        resolved_scope = scope or (
            cfg.smart_mode_scope
            if cfg.smart_mode_scope in ("single", "playlist", "channel")
            else ("playlist" if info.is_playlist else ("channel" if info.is_channel else "single"))
        )
        is_audio = cfg.preferred_quality in ("audio_only", "320k", "256k", "192k", "128k", "64k")
        media_mode = "m3u8" if info.is_m3u8 else ("audio" if is_audio else "video")
        container = cfg.preferred_audio_format if is_audio else cfg.preferred_video_format
        quality = "320k" if cfg.preferred_quality == "audio_only" else cfg.preferred_quality

        sub_en, sub_src, sub_auto, sub_tr = resolve_smart_subtitle_choice(
            info,
            pref_lang=cfg.preferred_subtitle_lang or "ar",
            fallback_lang=cfg.fallback_source_lang or "en",
            allow_auto=cfg.allow_auto_generated_subs,
            subtitle_mode=cfg.subtitle_mode,
            do_translate_flag=cfg.translate_subtitles,
        )

        self.enqueue_from_analysis(
            info=info,
            scope=resolved_scope,
            media_mode=media_mode,
            quality=quality,
            container=container,
            sub_enabled=sub_en,
            sub_source_lang=sub_src,
            sub_is_auto=sub_auto,
            sub_translate_to=sub_tr,
            sub_bidi_fix=cfg.enforce_bidi_rtl_fix,
            use_smart_numbering=(cfg.smart_numbering and resolved_scope in ("playlist", "channel")),
            audio_lang="",
        )

    def enqueue_from_analysis(
        self,
        info: AnalyzedMediaInfo,
        scope: str,
        media_mode: str,
        quality: str,
        container: str,
        sub_enabled: bool,
        sub_source_lang: str,
        sub_is_auto: bool,
        sub_translate_to: str,
        sub_bidi_fix: bool,
        use_smart_numbering: bool,
        audio_lang: str = "",
        selected_indices: Optional[List[int]] = None,
    ) -> None:
        if media_mode == "subtitles_only":
            sub_enabled = True
            container = "srt"
            quality = "srt"

        cfg = self.state.config
        initial_status = "paused" if cfg.schedule_enabled else "queued"
        if cfg.schedule_enabled:
            # Reset last_schedule_run_date so newly scheduled items can run at the next schedule check
            cfg.last_schedule_run_date = ""

        if scope in ("playlist", "channel") and info.entries:
            total = len(info.entries)
            allowed_set = set(selected_indices) if selected_indices else set(range(1, total + 1))
            group_id = info.playlist_id or info.channel_id or uuid.uuid4().hex[:8]
            group_title = info.playlist_title if scope == "playlist" else info.channel_name
            added_count = 0
            skipped_dups = 0

            for idx, ent in enumerate(info.entries, start=1):
                if idx not in allowed_set:
                    continue
                ent_url = str(ent.get("url") or info.url)
                if cfg.prevent_duplicate_tasks and self.state.find_duplicate_task(ent_url, media_mode):
                    skipped_dups += 1
                    continue

                prefix = f"{smart_pad_index(idx, total)} - " if use_smart_numbering else ""
                tid = uuid.uuid4().hex[:10]
                ent_vid = str(ent.get("id") or extract_video_id_from_url(ent_url) or "")
                item = DownloadTaskItem(
                    task_id=tid,
                    url=ent_url,
                    title=str(ent.get("title") or f"Video {idx}"),
                    video_id=ent_vid,
                    channel_name=str(ent.get("channel") or info.channel_name),
                    duration_sec=int(ent.get("duration") or 0),
                    thumbnail_url=str(ent.get("thumbnail") or info.thumbnail_url),
                    referer_url=info.referer_url,
                    group_type=scope,
                    group_id=group_id,
                    group_title=group_title,
                    playlist_index=idx,
                    playlist_total=total,
                    smart_prefix=prefix,
                    media_mode=media_mode,
                    quality=quality,
                    container=container,
                    audio_lang=audio_lang,
                    sub_enabled=sub_enabled,
                    sub_source_lang=sub_source_lang,
                    sub_is_auto=sub_is_auto,
                    sub_translate_to=sub_translate_to,
                    sub_bidi_fix=sub_bidi_fix,
                    status=initial_status,
                )
                self._control_flags[tid] = "pause" if initial_status == "paused" else "run"
                self.state.add_task(item)
                self._load_thumbnail_async(tid, item.thumbnail_url)
                added_count += 1

            if skipped_dups > 0 and added_count == 0:
                self.state.toast_requested.emit(
                    tp("جميع الفيديوهات المحددة موجودة بالفعل في قائمة التحميلات", "Selected videos are already in the queue"),
                    "warn",
                )
        else:
            single_url = info.webpage_url or info.url
            if cfg.prevent_duplicate_tasks:
                dup = self.state.find_duplicate_task(single_url, media_mode)
                if dup is not None:
                    self.state.toast_requested.emit(
                        tp(f"هذا الرابط موجود بالفعل في القائمة: {dup.title[:38]}", f"Link is already in queue: {dup.title[:38]}"),
                        "warn",
                    )
                    return

            tid = uuid.uuid4().hex[:10]
            gtype = "m3u8" if (info.is_m3u8 or media_mode == "m3u8") else "single"
            real_vid = info.video_id or extract_video_id_from_url(single_url)
            item = DownloadTaskItem(
                task_id=tid,
                url=single_url,
                title=info.title,
                video_id=real_vid,
                channel_name=info.channel_name,
                duration_sec=info.duration_sec,
                thumbnail_url=info.thumbnail_url,
                referer_url=info.referer_url,
                group_type=gtype,
                group_id=tid,
                group_title=info.title,
                playlist_index=1,
                playlist_total=1,
                smart_prefix="",
                media_mode=media_mode,
                quality=quality,
                container=container,
                audio_lang=audio_lang,
                sub_enabled=sub_enabled,
                sub_source_lang=sub_source_lang,
                sub_is_auto=sub_is_auto,
                sub_translate_to=sub_translate_to,
                sub_bidi_fix=sub_bidi_fix,
                status=initial_status,
            )
            self._control_flags[tid] = "pause" if initial_status == "paused" else "run"
            self.state.add_task(item)
            self._load_thumbnail_async(tid, item.thumbnail_url)

        if initial_status == "paused":
            self.state.toast_requested.emit(
                tp(
                    f"تمت جدولة التحميل ليبدأ تلقائياً الساعة {cfg.schedule_time}",
                    f"Download scheduled to start automatically at {cfg.schedule_time}",
                ),
                "info",
            )
        else:
            self.pump_queue()

    def _load_thumbnail_async(self, task_id: str, thumb_url: str) -> None:
        if not thumb_url:
            return

        def _done(path_obj: Optional[object]) -> None:
            if path_obj:
                pix = QPixmap(str(path_obj))
                if not pix.isNull():
                    self.state.thumbnails[task_id] = pix
                    self.state.thumbnail_loaded.emit(task_id, pix)

        run_async(fetch_thumbnail_cached, on_done=_done, url=thumb_url)

    def pump_queue(self) -> None:
        if self._shutting_down:
            return
        max_conc = max(1, self.state.config.max_concurrent_downloads)
        while len(self._running_ids) < max_conc:
            next_tid = self._find_next_queued()
            if not next_tid:
                break
            self._start_worker(next_tid)

    def _find_next_queued(self) -> Optional[str]:
        for tid in reversed(self.state.task_order):
            t_item = self.state.tasks.get(tid)
            if t_item and t_item.status == "queued" and tid not in self._running_ids:
                return tid
        return None

    def _start_worker(self, task_id: str) -> None:
        item = self.state.tasks.get(task_id)
        if not item:
            return
        self._running_ids.add(task_id)
        self._control_flags[task_id] = "run"
        self.state.update_task(
            task_id,
            status="fetching",
            skipped_archive=False,
            error_message="",
            warning_message="",
        )

        cfg = self.state.config
        active_workers = max(1, len(self._running_ids))
        per_worker_kbps = (max(32, cfg.speed_limit_kbps // active_workers)) if cfg.speed_limit_kbps > 0 else 0

        def _worker_fn() -> None:
            try:
                res = execute_download_task(
                    task=item,
                    base_download_dir=cfg.download_dir,
                    create_playlist_subfolder=cfg.create_subfolder_for_playlists,
                    ffmpeg_custom_path=cfg.ffmpeg_custom_path,
                    speed_limit_kbps=per_worker_kbps,
                    on_progress=lambda d: self._bridge.progress_signal.emit(task_id, d),
                    check_state=lambda: self._control_flags.get(task_id, "run"),
                    cfg=cfg,
                )
                self._bridge.completed_signal.emit(task_id, res)
            except PauseRequestedError:
                self._bridge.paused_signal.emit(task_id)
            except CancelRequestedError:
                self._bridge.canceled_signal.emit(task_id)
            except Exception as exc:
                self._bridge.failed_signal.emit(task_id, str(exc))

        run_async(_worker_fn)

    def _on_worker_progress(self, task_id: str, data: dict) -> None:
        self.state.update_task(task_id, **data)

    def _on_worker_completed(self, task_id: str, result: dict) -> None:
        self._running_ids.discard(task_id)
        out_p = str(result.get("output_path") or "")
        sub_p = str(result.get("subtitle_path") or "")
        warn_m = str(result.get("warning_message") or "")
        skipped_arc = bool(result.get("skipped_archive", False))
        vid = str(result.get("video_id") or "")

        update_kw: Dict[str, object] = {
            "status": "completed",
            "skipped_archive": skipped_arc,
            "stream_phase": "",
            "progress": 100.0,
            "speed_str": "",
            "eta_str": "",
            "output_path": out_p,
            "subtitle_path": sub_p,
            "warning_message": warn_m,
        }
        if vid:
            update_kw["video_id"] = vid

        self.state.update_task(task_id, **update_kw)
        if warn_m:
            self.state.toast_requested.emit(warn_m, "warn" if not skipped_arc else "info")

        item = self.state.tasks.get(task_id)
        if item and not skipped_arc:
            self.state.notification_requested.emit(
                t("status_completed"),
                f"{item.smart_prefix}{item.title}",
                out_p,
            )
            if self.state.config.open_folder_on_complete and out_p:
                try:
                    p_obj = Path(out_p)
                    folder_to_open = p_obj if p_obj.is_dir() else p_obj.parent
                    if folder_to_open.exists():
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder_to_open)))
                except Exception:
                    pass

        self.state.queue_changed.emit()
        self.pump_queue()
        self._check_post_queue_action()

    def _check_post_queue_action(self) -> None:
        if self._shutting_down:
            return
        action = self.state.config.post_queue_action
        if not action or action == "none":
            return
        any_pending = any(
            t_item.status in ("queued", "fetching", "downloading", "translating_sub", "merging")
            for t_item in self.state.tasks.values()
        )
        if any_pending or self._running_ids:
            return

        # Safety: Reset post_queue_action to "none" immediately (one-shot only!)
        # and request the 60-second cancellable confirmation countdown dialog!
        self.state.config.post_queue_action = "none"
        self.state.config.save()
        self.state.config_changed.emit()
        self.state.post_queue_countdown_requested.emit(action)

    def execute_power_action_now(self, action: str) -> None:
        """Executes the confirmed post-queue action after the countdown dialog completes."""
        if action == "quit_app":
            self.state.toast_requested.emit(
                tp("اكتملت جميع التحميلات — جاري إغلاق البرنامج تلقائياً...", "All downloads finished — closing application..."),
                "info",
            )
            QTimer.singleShot(400, QApplication.quit)
        elif action == "shutdown":
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["shutdown", "/s", "/t", "5"])
                elif sys.platform == "darwin":
                    subprocess.Popen(["osascript", "-e", 'tell app "System Events" to shut down'])
                else:
                    subprocess.Popen(["systemctl", "poweroff"])
            except Exception:
                pass
        elif action == "sleep":
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
                elif sys.platform == "darwin":
                    subprocess.Popen(["pmset", "sleepnow"])
                else:
                    subprocess.Popen(["systemctl", "suspend"])
            except Exception:
                pass

    def _on_worker_paused(self, task_id: str) -> None:
        self._running_ids.discard(task_id)
        self.state.update_task(task_id, status="paused", stream_phase="", speed_str="", eta_str="")
        self.state.queue_changed.emit()
        self.pump_queue()

    def _on_worker_canceled(self, task_id: str) -> None:
        self._running_ids.discard(task_id)
        self._cleanup_canceled_task_files(task_id)
        self.state.update_task(task_id, status="canceled", stream_phase="", speed_str="", eta_str="")
        self.state.queue_changed.emit()
        self.pump_queue()

    def _on_worker_failed(self, task_id: str, err: str) -> None:
        self._running_ids.discard(task_id)
        self.state.update_task(
            task_id,
            status="error",
            stream_phase="",
            error_message=err[:360],
            speed_str="",
            eta_str="",
        )
        self.state.queue_changed.emit()
        self.pump_queue()

    def _cleanup_canceled_task_files(self, task_id: str) -> None:
        item = self.state.tasks.get(task_id)
        if not item:
            return
        cfg = self.state.config
        target_dir = Path(cfg.download_dir)
        if cfg.create_subfolder_for_playlists and item.group_type in ("playlist", "channel") and item.group_title:
            target_dir = target_dir / sanitize_filename(item.group_title, max_len=65)
        real_vid = item.video_id or extract_video_id_from_url(item.url)
        stem = build_safe_output_stem(
            target_dir=target_dir,
            prefix=item.smart_prefix,
            title=item.title,
            template=cfg.filename_template,
            channel=item.channel_name,
            video_id=real_vid,
        )
        cleanup_task_temp_files(target_dir, stem)

    def pause_task(self, task_id: str) -> None:
        item = self.state.tasks.get(task_id)
        if not item:
            return
        if item.status == "queued" and task_id not in self._running_ids:
            self.state.update_task(task_id, status="paused")
        else:
            self._control_flags[task_id] = "pause"
            if item.status in ("fetching", "translating_sub"):
                self.state.update_task(task_id, status="paused", speed_str="", eta_str="")

    def resume_task(self, task_id: str) -> None:
        item = self.state.tasks.get(task_id)
        if not item:
            return
        if item.status in ("paused", "error", "canceled"):
            self._control_flags[task_id] = "run"
            self.state.update_task(task_id, status="queued", error_message="")
            self.pump_queue()

    def cancel_task(self, task_id: str) -> None:
        item = self.state.tasks.get(task_id)
        if not item:
            return
        if task_id in self._running_ids:
            self._control_flags[task_id] = "cancel"
        else:
            self._cleanup_canceled_task_files(task_id)
            self.state.update_task(task_id, status="canceled", speed_str="", eta_str="")
            self.state.queue_changed.emit()

    def pause_all(self) -> None:
        for tid, item in list(self.state.tasks.items()):
            if item.status in ("queued", "fetching", "downloading", "translating_sub"):
                self.pause_task(tid)

    def resume_all(self, include_failed: bool = False) -> None:
        """Resumes paused tasks (and only retries failed tasks when `include_failed=True`)."""
        allowed = ("paused", "error") if include_failed else ("paused",)
        for tid, item in list(self.state.tasks.items()):
            if item.status in allowed:
                self.resume_task(tid)
        self.pump_queue()

    def retry_failed_all(self) -> None:
        """Explicitly retries all failed download tasks."""
        for tid, item in list(self.state.tasks.items()):
            if item.status == "error":
                self.resume_task(tid)

    # =========================================================================
    # Persistent Subtitle Studio Queue Engine
    # =========================================================================
    def enqueue_subtitle_files(
        self,
        file_paths: List[str],
        target_lang: str,
        do_translate: bool,
        enforce_bidi: bool,
    ) -> None:
        for fp in file_paths:
            p = Path(fp)
            if not p.exists():
                continue
            jid = uuid.uuid4().hex[:10]
            job = SubtitleJobItem(
                job_id=jid,
                source_path=str(p),
                filename=p.name,
                target_lang=target_lang or "ar",
                do_translate=do_translate,
                enforce_bidi=enforce_bidi,
                status="queued",
            )
            self._sub_control_flags[jid] = "run"
            self.state.add_sub_job(job)
        self.pump_sub_queue()

    def pump_sub_queue(self) -> None:
        if self._shutting_down:
            return
        while len(self._running_sub_ids) < 2:
            next_jid = None
            for jid in reversed(self.state.sub_job_order):
                jb = self.state.sub_jobs.get(jid)
                if jb and jb.status == "queued" and jid not in self._running_sub_ids:
                    next_jid = jid
                    break
            if not next_jid:
                break
            self._start_sub_worker(next_jid)

    def _start_sub_worker(self, job_id: str) -> None:
        job = self.state.sub_jobs.get(job_id)
        if not job:
            return
        self._running_sub_ids.add(job_id)
        self._sub_control_flags[job_id] = "run"
        self.state.update_sub_job(job_id, status="processing", error_message="")
        tv_safe = self.state.config.tv_safe_bidi

        def _sub_worker() -> None:
            try:
                out_path, cue_count, failed_cues = process_and_sync_subtitle(
                    raw_sub_path=Path(job.source_path),
                    source_lang="auto",
                    target_lang=job.target_lang,
                    do_translate=job.do_translate,
                    enforce_bidi=job.enforce_bidi,
                    is_auto_generated=None,
                    tv_safe_bidi=tv_safe,
                    cue_progress_cb=lambda done_c, tot_c, pct: self._bridge.sub_progress_signal.emit(
                        job_id, done_c, tot_c, pct
                    ),
                    state_check=lambda: self._sub_control_flags.get(job_id, "run"),
                )
                self._bridge.sub_completed_signal.emit(job_id, str(out_path), cue_count, failed_cues)
            except SubtitlePauseRequested:
                self._bridge.sub_paused_signal.emit(job_id)
            except SubtitleCancelRequested:
                self._bridge.sub_canceled_signal.emit(job_id)
            except Exception as exc:
                self._bridge.sub_failed_signal.emit(job_id, str(exc))

        run_async(_sub_worker)

    def _on_sub_worker_progress(self, job_id: str, done_cues: int, total_cues: int, pct: float) -> None:
        self.state.update_sub_job(
            job_id,
            status="processing",
            done_cues=done_cues,
            total_cues=total_cues,
            progress=pct,
        )

    def _on_sub_worker_completed(self, job_id: str, out_path: str, total_cues: int, failed_cues: int) -> None:
        self._running_sub_ids.discard(job_id)
        self.state.update_sub_job(
            job_id,
            status="completed",
            progress=100.0,
            done_cues=total_cues,
            total_cues=total_cues,
            output_path=out_path,
        )
        if failed_cues > 0:
            self.state.toast_requested.emit(
                tp(
                    f"اكتمل الضبط، ولكن تعذّرت ترجمة {failed_cues} من {total_cues} جملة",
                    f"Completed sync, but {failed_cues} of {total_cues} cues failed to translate",
                ),
                "warn",
            )
        else:
            self.state.toast_requested.emit(
                tp(
                    f"اكتملت ترجمة وضبط {total_cues} جملة بنجاح!",
                    f"Completed translating & syncing {total_cues} subtitle cues!",
                ),
                "ok",
            )
        self.state.notification_requested.emit(
            t("status_completed"),
            Path(out_path).name,
            out_path,
        )
        self.pump_sub_queue()

    def _on_sub_worker_paused(self, job_id: str) -> None:
        self._running_sub_ids.discard(job_id)
        self.state.update_sub_job(job_id, status="paused")
        self.pump_sub_queue()

    def _on_sub_worker_canceled(self, job_id: str) -> None:
        self._running_sub_ids.discard(job_id)
        self.state.update_sub_job(job_id, status="canceled")
        self.pump_sub_queue()

    def _on_sub_worker_failed(self, job_id: str, err: str) -> None:
        self._running_sub_ids.discard(job_id)
        self.state.update_sub_job(job_id, status="error", error_message=err[:360])
        self.pump_sub_queue()

    def cancel_sub_job(self, job_id: str) -> None:
        job = self.state.sub_jobs.get(job_id)
        if not job:
            return
        if job_id in self._running_sub_ids:
            self._sub_control_flags[job_id] = "cancel"
        else:
            self.state.update_sub_job(job_id, status="canceled")

    def retry_sub_job(self, job_id: str) -> None:
        job = self.state.sub_jobs.get(job_id)
        if not job:
            return
        if job.status in ("error", "canceled", "paused"):
            self._sub_control_flags[job_id] = "run"
            self.state.update_sub_job(job_id, status="queued", progress=0.0, done_cues=0, error_message="")
            self.pump_sub_queue()

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._scheduler_timer.stop()

        for tid in list(self._running_ids):
            self._control_flags[tid] = "pause"
            item = self.state.tasks.get(tid)
            if item and item.status in ("fetching", "downloading", "translating_sub", "merging"):
                item.status = "paused"
                item.speed_str = ""
                item.eta_str = ""

        for jid in list(self._running_sub_ids):
            self._sub_control_flags[jid] = "pause"
            jb = self.state.sub_jobs.get(jid)
            if jb and jb.status == "processing":
                jb.status = "queued"

        self.state.flush_queue_state()
        wait_for_all_workers(3500)
