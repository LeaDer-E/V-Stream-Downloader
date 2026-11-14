# Changelog

All notable changes to **V-Stream Downloader** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.1.0]

### Added
- Cryptographic SHA-256 verification (`verify_file_sha256`) for PyPI wheels (`yt-dlp` and `yt-dlp-ejs`) and FFmpeg release archives (`verify_file_sha256` / `verify_file_md5`) before extraction.
- Path-traversal protection (`safe_extract_zip` and `safe_extract_tar` with Python 3.12+ `filter="data"`) blocking `..` segments, absolute paths, and unsafe symlinks.
- Automatic detection and wiring of external JavaScript runtimes (`deno`, `node`, `quickjs`, `bun`) via `detect_all_js_runtimes()` into `yt-dlp` options (`js_runtimes`) alongside `yt-dlp-ejs` challenge-solver package installation.
- Cross-platform FFmpeg auto-installer supporting Windows (`win64` GPL via BtbN GitHub Releases API), macOS (`ffmpeg` + `ffprobe` via Evermeet JSON API), and Linux (`amd64` and `arm64` static builds).
- Interactive 60-second cancellable confirmation modal (`PostQueueCountdownOverlay`) with live countdown, `Execute Now`, and `Cancel` (`Esc`) before running `shutdown`, `sleep`, or `quit_app`.
- Technical diagnostics report generator (`collect_diagnostics_report`) and one-click `Copy Diagnostics` button in Settings and the About modal.
- Post-download hygiene settings: `open_folder_on_complete` ("Open Download Folder When Completed"), `auto_cleanup_days` (auto-prune completed entries after 1, 3, 7, or 30 days), and `max_history_items` (250-entry history cap).
- Complete 13-language localization catalog (`app/i18n_catalog.py`) covering 113 `t()` keys, 227 static `tp()` phrases, 30 dynamic regex templates, 32 theme palette names, and 8 home showcase cards across Arabic (`ar`), English (`en`), Spanish (`es`), French (`fr`), German (`de`), Russian (`ru`), Turkish (`tr`), Urdu (`ur`), Persian (`fa`), Indonesian (`id`), Malay (`ms`), Bengali (`bn`), and Greek (`el`).
- Redesigned `AboutOverlay` with synchronized banner/logo geometry (`_AboutCardContainer.required_top_spacer()`), 4 feature chips, live engine status bar, clickable email and WhatsApp (`wa.me`) rows, open-source license attributions, legal notice, and `Esc` key handling.
- Windows startup registration toggle (`set_windows_startup` / `is_windows_startup_enabled`) using `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` on Windows and XDG `~/.config/autostart/VStreamDownloaderPro.desktop` on Linux.
- Companion engineering files: `run.bat`, `run.sh`, `requirements-dev.txt`, `LICENSE` (MIT), `assets/fonts/OFL.txt`, `installer.iss` (Inno Setup script for `--onedir` `V-Stream-Engine`), and `.github/workflows/ci.yml`.

### Changed
- `post_queue_action` is now strictly a one-shot session setting: it resets to `"none"` immediately upon firing and is always written as `"none"` to `config.json` so a previous session's shutdown choice never triggers unexpectedly on future runs.
- `AppState.save_queue_state()` now uses a 1000 ms single-shot `QTimer` debounce during normal UI operation (with immediate synchronous flush via `flush_queue_state()` on exit) to prevent UI-thread disk thrashing when enqueueing large playlists.
- `DownloadManager._check_scheduled_queue()` now triggers when `current_HH:MM >= schedule_time` and `last_schedule_run_date != today` so scheduled queues still start even if the PC was asleep at the exact target minute.
- `DownloadManager.resume_all()` now resumes only `"paused"` tasks by default (`include_failed=False`), separating it from `retry_failed_all()`.
- `GlassCard` now supports `opaque=True` for modal overlays (`OnboardingOverlay`, `SmartLinkOverlay`, `BlobStreamHelperOverlay`) and higher-contrast Light Mode tokens in `app/theme.py`.
- PyInstaller `--onedir` build (`build_exe.py`) renames `_internal` to `V-Stream-Engine` via `--contents-directory V-Stream-Engine`.

### Fixed
- `{prefix}{title} [{id}]` filename template now uses the real media/YouTube video ID (`task.video_id` / `info["id"]`) instead of the internal random `task.task_id`.
- `AppState.find_duplicate_task()` now verifies that a `"completed"` task's output file still exists on disk (`Path(check_path).is_file()`) before blocking re-downloads.
- `execute_download_task()` now detects videos skipped by `yt-dlp`'s `download_archive` and marks them with `skipped_archive=True` and a clear localized status message instead of completing with an empty path.
- `embed_subtitles_in_video` muxing command now passes `-map 0 -map 1:0` to preserve multi-language audio tracks and chapters, scales timeout dynamically with file size (`180s`–`1800s`), and surfaces warnings if muxing fails.
- `DownloadManager.trigger_ytdlp_update()` now blocks in-place `yt-dlp` self-updates while downloads are active to prevent `sys.modules["yt_dlp"]` reloads mid-download.
- `OnboardingOverlay` now refreshes all 3 steps, segmented controls, palette names, layout directions (`RTL`/`LTR`), and Light/Dark text colors immediately when switching language or appearance mode on first run.

## [5.0.0]

### Added
- Initial v5 architecture featuring frameless glass UI, 32 color palettes, Smart Media & Audio Track Inspector (`SmartLinkOverlay`), In-Memory `blob:` URL Helper (`BlobStreamHelperOverlay`), Non-Overlapping BiDi Subtitle Engine (`app/domain/subtitles.py`), Persistent Subtitle Studio (`SubtitleStudioPage`), and single-instance IPC (`QLockFile` + `QLocalServer`).
