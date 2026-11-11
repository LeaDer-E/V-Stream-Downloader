import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from app.paths import app_data_dir, default_download_dir

logger = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = 6


@dataclass
class AppConfig:
    schema_version: int = CURRENT_SCHEMA_VERSION
    language: str = "ar"  # 13 supported UI languages
    theme_mode: str = "dark"  # "dark", "light", "auto"
    palette_id: str = "cyber_violet"
    custom_accent: str = "#8B5CF6"
    first_run_completed: bool = False

    # Turbo One-Click Smart Mode
    smart_mode_enabled: bool = False
    smart_mode_scope: str = "ask"  # "ask", "single", "playlist", "channel"

    # Download settings
    download_dir: str = field(default_factory=lambda: str(default_download_dir()))
    max_concurrent_downloads: int = 3
    preferred_quality: str = "1080p"  # "best", "2160p", "1440p", "1080p", "720p", "480p", "360p", "audio_only"
    preferred_video_format: str = "mp4"  # "mp4", "mkv", "webm"
    preferred_audio_format: str = "mp3"  # "mp3", "m4a", "flac", "wav", "ogg"
    smart_numbering: bool = True  # 01 - Title or 001 - Title when >= 100
    create_subfolder_for_playlists: bool = True
    filename_template: str = "{prefix}{title}"  # "{prefix}{title}", "{prefix}{channel} - {title}", "{prefix}{title} [{id}]"

    # Post-processing & Embedding (requires FFmpeg)
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    embed_chapters: bool = True
    embed_subtitles_in_video: bool = False

    # Archive, Duplicate Prevention & Post-Download Hygiene
    use_download_archive: bool = False
    prevent_duplicate_tasks: bool = True
    open_folder_on_complete: bool = False
    auto_cleanup_days: int = 0  # 0 = keep forever, >0 = auto-remove completed tasks older than N days
    max_history_items: int = 250  # Caps completed/canceled history entries in queue_state.json

    # Subtitle & Translation settings
    subtitle_mode: str = "prefer_target_then_translate"
    # modes: "none", "original_only", "prefer_target_then_translate", "always_translate"
    preferred_subtitle_lang: str = "ar"
    fallback_source_lang: str = "en"
    allow_auto_generated_subs: bool = True
    translate_subtitles: bool = True
    translate_target_lang: str = "ar"
    enforce_bidi_rtl_fix: bool = True
    tv_safe_bidi: bool = True  # Avoids raw RLE/LRE/PDF control chars that render as boxes on some TVs

    # Network, Cookies, Proxy & JS Runtime
    cookies_browser: str = "none"  # "none", "chrome", "edge", "firefox", "brave", "opera"
    cookies_file_path: str = ""
    proxy_url: str = ""
    js_runtime_enabled: bool = True
    auto_update_ytdlp_on_startup: bool = False

    # Notifications, Clipboard, Scheduler & Power Management
    notifications_enabled: bool = True
    sound_enabled: bool = True
    minimize_to_tray: bool = True
    run_on_startup: bool = False
    auto_paste_clipboard: bool = False
    ffmpeg_custom_path: str = ""
    speed_limit_kbps: int = 0  # Global speed limit in KB/s (0 = unlimited)
    schedule_enabled: bool = False
    schedule_time: str = "02:00"  # HH:MM 24h start time for scheduled queue
    last_schedule_run_date: str = ""  # YYYY-MM-DD of last triggered schedule so missed minute still runs today
    post_queue_action: str = "none"  # One-shot session action: "none", "quit_app", "sleep", "shutdown"

    def save(self) -> None:
        cfg_file = app_data_dir() / "config.json"
        try:
            payload = asdict(self)
            # Safety: Never persist destructive power actions across restarts!
            # `post_queue_action` is strictly a one-shot session setting.
            payload["post_queue_action"] = "none"
            temp_file = cfg_file.with_suffix(".tmp")
            temp_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_file.replace(cfg_file)
        except Exception as exc:
            logger.error("Failed to save config: %s", exc)

    @classmethod
    def load(cls) -> "AppConfig":
        cfg_file = app_data_dir() / "config.json"
        defaults = asdict(cls())
        if not cfg_file.exists():
            instance = cls()
            instance.save()
            return instance

        try:
            raw: Dict[str, Any] = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Corrupted config.json, restoring defaults: %s", exc)
            instance = cls()
            instance.save()
            return instance

        migrated = cls._migrate(raw, defaults)
        valid_keys = {f for f in defaults.keys()}
        filtered = {k: v for k, v in migrated.items() if k in valid_keys}
        # Safety: Always start a fresh session with post_queue_action = "none"
        filtered["post_queue_action"] = "none"
        instance = cls(**filtered)
        if raw.get("schema_version") != CURRENT_SCHEMA_VERSION:
            instance.save()
        return instance

    @staticmethod
    def _migrate(raw: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(raw)
        for key, default_val in defaults.items():
            data.setdefault(key, default_val)

        version = data.get("schema_version", 1)
        if version < CURRENT_SCHEMA_VERSION:
            if data.get("preferred_quality") not in (
                "best",
                "4320p",
                "2160p",
                "1440p",
                "1080p",
                "720p",
                "480p",
                "360p",
                "240p",
                "144p",
                "audio_only",
            ):
                data["preferred_quality"] = "1080p"
            data["post_queue_action"] = "none"
            data["schema_version"] = CURRENT_SCHEMA_VERSION
        return data
