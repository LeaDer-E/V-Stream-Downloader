from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

from app.config import AppConfig
from app.paths import queue_state_path

logger = logging.getLogger(__name__)


@dataclass
class SubtitleTrackInfo:
    lang_code: str
    lang_name: str
    is_auto_generated: bool = False
    ext: str = "srt"


@dataclass
class AudioTrackInfo:
    lang_code: str
    lang_name: str
    is_default: bool = False


@dataclass
class DownloadTaskItem:
    task_id: str
    url: str
    title: str
    video_id: str = ""  # Real media/YouTube video ID (e.g. dQw4w9WgXcQ) for {id} template
    channel_name: str = ""
    duration_sec: int = 0
    thumbnail_url: str = ""
    referer_url: str = ""

    # Grouping & Smart Numbering
    group_type: str = "single"  # "single", "playlist", "channel", "m3u8"
    group_id: str = ""
    group_title: str = ""
    playlist_index: int = 1
    playlist_total: int = 1
    smart_prefix: str = ""  # e.g., "01 - " or "001 - "

    # Media format configuration
    media_mode: str = "video"  # "video", "audio", "subtitles_only", "m3u8"
    quality: str = "1080p"  # e.g., "1080p", "720p", "360p", or audio bitrate "320k", "192k", "128k"
    container: str = "mp4"  # "mp4", "mkv", "webm", "mp3", "m4a", "flac", "wav", "srt"
    audio_lang: str = ""  # "" = default/original audio track, or specific language code like "ar", "en"

    # Subtitle & Translation configuration
    sub_enabled: bool = False
    sub_source_lang: str = ""
    sub_is_auto: bool = False
    sub_translate_to: str = ""
    sub_bidi_fix: bool = True

    # Live runtime status & timestamps
    status: str = "queued"  # queued, fetching, downloading, translating_sub, merging, paused, completed, error, canceled
    skipped_archive: bool = False  # True if skipped because video was already in download_archive.txt
    stream_phase: str = ""  # e.g. "1/2 فيديو", "2/2 صوت"
    progress: float = 0.0  # 0.0 -> 100.0
    speed_str: str = ""
    eta_str: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    output_path: str = ""
    subtitle_path: str = ""
    error_message: str = ""
    warning_message: str = ""
    created_at_ts: float = field(default_factory=time.time)
    completed_at_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "DownloadTaskItem":
        valid = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        item = cls(**valid)
        # If the app was closed while a task was actively running, restore it as 'paused'
        # so the user can resume it cleanly without losing their queue!
        if item.status in ("fetching", "downloading", "translating_sub", "merging"):
            item.status = "paused"
            item.speed_str = ""
            item.eta_str = ""
        return item


@dataclass
class SubtitleJobItem:
    job_id: str
    source_path: str
    filename: str
    target_lang: str = "ar"
    do_translate: bool = True
    enforce_bidi: bool = True

    status: str = "queued"  # "queued", "processing", "paused", "completed", "error", "canceled"
    progress: float = 0.0
    done_cues: int = 0
    total_cues: int = 0
    output_path: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "SubtitleJobItem":
        valid = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        job = cls(**valid)
        if job.status == "processing":
            job.status = "queued"
        return job


@dataclass
class AnalyzedMediaInfo:
    url: str
    webpage_url: str
    title: str
    channel_name: str
    video_id: str = ""
    duration_sec: int = 0
    thumbnail_url: str = ""
    referer_url: str = ""
    is_playlist: bool = False
    is_channel: bool = False
    is_m3u8: bool = False
    playlist_title: str = ""
    playlist_id: str = ""
    channel_id: str = ""
    channel_url: str = ""
    entries: List[Dict[str, object]] = field(default_factory=list)
    available_qualities: List[str] = field(
        default_factory=lambda: ["1080p", "720p", "480p", "360p", "240p", "144p"]
    )
    quality_details: Dict[str, str] = field(default_factory=dict)
    available_audio_qualities: List[Tuple[str, str]] = field(default_factory=list)
    available_audio_tracks: List[AudioTrackInfo] = field(default_factory=list)
    manual_subtitles: List[SubtitleTrackInfo] = field(default_factory=list)
    auto_subtitles: List[SubtitleTrackInfo] = field(default_factory=list)


class AppState(QObject):
    config_changed = Signal()
    theme_changed = Signal()
    language_changed = Signal(str)

    task_added = Signal(str)
    task_updated = Signal(str, bool)
    task_removed = Signal(str)
    queue_changed = Signal()
    thumbnail_loaded = Signal(str, QPixmap)

    sub_job_added = Signal(str)
    sub_job_updated = Signal(str, bool)
    sub_job_removed = Signal(str)
    sub_queue_changed = Signal()

    toast_requested = Signal(str, str)
    notification_requested = Signal(str, str, str)
    analysis_started = Signal(str)
    analysis_completed = Signal(object)
    analysis_failed = Signal(str)
    blob_help_requested = Signal(str, str)
    ffmpeg_status_changed = Signal(bool, str)
    post_queue_countdown_requested = Signal(str)  # Emits action ("shutdown", "sleep", "quit_app")

    def __init__(self, config: AppConfig, load_persisted: bool = True) -> None:
        super().__init__()
        self.config = config
        self.tasks: Dict[str, DownloadTaskItem] = {}
        self.task_order: List[str] = []
        self.thumbnails: Dict[str, QPixmap] = {}
        self.last_analyzed_info: Optional[AnalyzedMediaInfo] = None

        self.sub_jobs: Dict[str, SubtitleJobItem] = {}
        self.sub_job_order: List[str] = []
        self.ffmpeg_available: bool = False
        self.ffmpeg_resolved_path: str = ""
        self._save_dirty: bool = False

        # Debounced queue persistence timer (1000 ms) so adding a 500-item playlist
        # performs a single consolidated disk write instead of 500 synchronous writes on the UI thread!
        self._save_timer: Optional[QTimer] = None
        if hasattr(QTimer, "setSingleShot"):
            try:
                self._save_timer = QTimer(self)
                self._save_timer.setSingleShot(True)
                self._save_timer.setInterval(1000)
                self._save_timer.timeout.connect(self._flush_debounced_save)
            except Exception:
                self._save_timer = None

        if load_persisted:
            self.load_queue_state()
            self.prune_expired_history(save_immediately=False)

    def _prune_history_if_needed(self) -> List[str]:
        """
        Enforces `auto_cleanup_days` (removes completed tasks older than N days)
        and `max_history_items` (caps total completed/canceled history so queue_state.json never grows unbounded).
        """
        removed_ids: List[str] = []
        now_ts = time.time()
        cleanup_days = int(getattr(self.config, "auto_cleanup_days", 0) or 0)
        if cleanup_days > 0:
            cutoff = now_ts - (cleanup_days * 86400.0)
            for tid in list(self.task_order):
                item = self.tasks.get(tid)
                if item and item.status in ("completed", "canceled"):
                    done_ts = item.completed_at_ts or item.created_at_ts
                    if done_ts > 0 and done_ts < cutoff:
                        self.tasks.pop(tid, None)
                        self.task_order.remove(tid)
                        removed_ids.append(tid)

        max_hist = max(20, int(getattr(self.config, "max_history_items", 250) or 250))
        finished_ids = [
            tid for tid in self.task_order
            if tid in self.tasks and self.tasks[tid].status in ("completed", "canceled")
        ]
        if len(finished_ids) > max_hist:
            for old_tid in finished_ids[max_hist:]:
                self.tasks.pop(old_tid, None)
                if old_tid in self.task_order:
                    self.task_order.remove(old_tid)
                removed_ids.append(old_tid)

        return removed_ids

    def prune_expired_history(self, save_immediately: bool = True) -> int:
        removed_ids = self._prune_history_if_needed()
        for tid in removed_ids:
            self.task_removed.emit(tid)
        if removed_ids:
            if save_immediately:
                self.save_queue_state(immediate=True)
            self.queue_changed.emit()
        return len(removed_ids)

    def _flush_debounced_save(self) -> None:
        if self._save_dirty:
            self.save_queue_state(immediate=True)

    def flush_queue_state(self) -> None:
        """Forces an immediate synchronous write of queue_state.json (called on app shutdown)."""
        if self._save_timer is not None:
            try:
                self._save_timer.stop()
            except Exception:
                pass
        self.save_queue_state(immediate=True)

    def save_queue_state(self, immediate: bool = False) -> None:
        """
        Persists all download tasks, history, and subtitle jobs to queue_state.json.
        Uses a 1-second debounce timer during normal UI operation unless `immediate=True`
        or no Qt application instance is running.
        """
        self._save_dirty = True
        has_app = QCoreApplication.instance() is not None if hasattr(QCoreApplication, "instance") else False
        if not immediate and self._save_timer is not None and has_app:
            try:
                if not self._save_timer.isActive():
                    self._save_timer.start()
                return
            except Exception:
                pass

        self._prune_history_if_needed()
        q_file = queue_state_path()
        try:
            payload = {
                "version": 6,
                "task_order": self.task_order,
                "tasks": [self.tasks[tid].to_dict() for tid in self.task_order if tid in self.tasks],
                "sub_job_order": self.sub_job_order,
                "sub_jobs": [self.sub_jobs[jid].to_dict() for jid in self.sub_job_order if jid in self.sub_jobs],
            }
            tmp_file = q_file.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_file.replace(q_file)
            self._save_dirty = False
        except Exception as exc:
            logger.error("Failed to save queue_state.json: %s", exc)

    def load_queue_state(self) -> None:
        """Restores saved download queue, completed history, and subtitle studio jobs on startup."""
        q_file = queue_state_path()
        if not q_file.exists():
            return
        try:
            raw = json.loads(q_file.read_text(encoding="utf-8"))
            tasks_list = raw.get("tasks") or []
            for t_dict in tasks_list:
                item = DownloadTaskItem.from_dict(t_dict)
                self.tasks[item.task_id] = item
                if item.task_id not in self.task_order:
                    self.task_order.append(item.task_id)

            sub_list = raw.get("sub_jobs") or []
            for s_dict in sub_list:
                job = SubtitleJobItem.from_dict(s_dict)
                self.sub_jobs[job.job_id] = job
                if job.job_id not in self.sub_job_order:
                    self.sub_job_order.append(job.job_id)
        except Exception as exc:
            logger.warning("Could not restore queue_state.json: %s", exc)

    def find_duplicate_task(self, url: str, media_mode: str) -> Optional[DownloadTaskItem]:
        """
        Checks if an identical URL + media_mode is already active/queued or completed.
        If an item is marked 'completed', verifies that its output file STILL EXISTS on disk;
        if the user deleted the file, allows re-downloading cleanly!
        """
        norm = (url or "").strip().rstrip("/")
        if not norm:
            return None
        for item in self.tasks.values():
            if item.url.strip().rstrip("/") == norm and item.media_mode == media_mode:
                if item.status in ("queued", "fetching", "downloading", "translating_sub", "merging"):
                    return item
                if item.status == "completed":
                    check_path = item.subtitle_path if media_mode == "subtitles_only" else item.output_path
                    if check_path and Path(check_path).is_file():
                        return item
        return None

    def add_task(self, item: DownloadTaskItem) -> None:
        self.tasks[item.task_id] = item
        if item.task_id not in self.task_order:
            self.task_order.insert(0, item.task_id)
        self.save_queue_state(immediate=False)
        self.task_added.emit(item.task_id)
        self.queue_changed.emit()

    def update_task(self, task_id: str, **kwargs: object) -> None:
        item = self.tasks.get(task_id)
        if not item:
            return
        old_status = item.status
        for k, v in kwargs.items():
            if hasattr(item, k):
                setattr(item, k, v)
        status_changed = item.status != old_status
        if status_changed and item.status == "completed" and item.completed_at_ts <= 0:
            item.completed_at_ts = time.time()
        if status_changed or "output_path" in kwargs or "error_message" in kwargs:
            self.save_queue_state(immediate=False)
        self.task_updated.emit(task_id, status_changed)

    def remove_task(self, task_id: str) -> None:
        if task_id in self.tasks:
            del self.tasks[task_id]
            if task_id in self.task_order:
                self.task_order.remove(task_id)
            self.save_queue_state(immediate=False)
            self.task_removed.emit(task_id)
            self.queue_changed.emit()

    def clear_completed(self) -> None:
        to_remove = [tid for tid, t in self.tasks.items() if t.status in ("completed", "canceled")]
        for tid in to_remove:
            self.tasks.pop(tid, None)
            if tid in self.task_order:
                self.task_order.remove(tid)
            self.task_removed.emit(tid)
        if to_remove:
            self.save_queue_state(immediate=True)
            self.queue_changed.emit()

    def active_count(self) -> int:
        dl_active = sum(
            1
            for item in self.tasks.values()
            if item.status in ("fetching", "downloading", "translating_sub", "merging")
        )
        sub_active = sum(1 for j in self.sub_jobs.values() if j.status == "processing")
        return dl_active + sub_active

    def add_sub_job(self, job: SubtitleJobItem) -> None:
        self.sub_jobs[job.job_id] = job
        if job.job_id not in self.sub_job_order:
            self.sub_job_order.insert(0, job.job_id)
        self.save_queue_state(immediate=False)
        self.sub_job_added.emit(job.job_id)
        self.sub_queue_changed.emit()
        self.queue_changed.emit()

    def update_sub_job(self, job_id: str, **kwargs: object) -> None:
        job = self.sub_jobs.get(job_id)
        if not job:
            return
        old_status = job.status
        for k, v in kwargs.items():
            if hasattr(job, k):
                setattr(job, k, v)
        status_changed = job.status != old_status
        if status_changed or "output_path" in kwargs:
            self.save_queue_state(immediate=False)
        self.sub_job_updated.emit(job_id, status_changed)
        if status_changed:
            self.sub_queue_changed.emit()
            self.queue_changed.emit()

    def remove_sub_job(self, job_id: str) -> None:
        if job_id in self.sub_jobs:
            del self.sub_jobs[job_id]
            if job_id in self.sub_job_order:
                self.sub_job_order.remove(job_id)
            self.save_queue_state(immediate=False)
            self.sub_job_removed.emit(job_id)
            self.sub_queue_changed.emit()
            self.queue_changed.emit()

    def clear_completed_sub_jobs(self) -> None:
        to_rm = [jid for jid, j in self.sub_jobs.items() if j.status in ("completed", "canceled")]
        for jid in to_rm:
            self.sub_jobs.pop(jid, None)
            if jid in self.sub_job_order:
                self.sub_job_order.remove(jid)
            self.sub_job_removed.emit(jid)
        if to_rm:
            self.save_queue_state(immediate=True)
            self.sub_queue_changed.emit()
            self.queue_changed.emit()
