import hashlib
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import time
import types
import unittest
from unittest.mock import MagicMock, patch
import zipfile

if "PySide6" not in sys.modules:
    try:
        import PySide6  # noqa: F401
    except ImportError:
        qtcore = types.ModuleType("PySide6.QtCore")

        class _DummyQObject:
            def __init__(self, *a, **kw):
                pass

        class _DummySignal:
            def __init__(self, *a, **kw):
                self._subs = []

            def connect(self, fn):
                self._subs.append(fn)

            def emit(self, *args):
                for fn in list(self._subs):
                    fn(*args)

        class _DummyTimer:
            def __init__(self, *a, **kw):
                self._active = False

            def setSingleShot(self, *a):
                pass

            def setInterval(self, *a):
                pass

            @property
            def timeout(self):
                return _DummySignal()

            def isActive(self):
                return self._active

            def start(self, *a):
                self._active = True

            def stop(self):
                self._active = False

            @staticmethod
            def singleShot(_ms, fn):
                pass

        qtcore.QObject = _DummyQObject
        qtcore.QRunnable = _DummyQObject
        qtcore.QThreadPool = types.SimpleNamespace(globalInstance=lambda: types.SimpleNamespace(setMaxThreadCount=lambda *a: None, start=lambda *a: None, waitForDone=lambda *a: True))
        qtcore.Signal = _DummySignal
        qtcore.QTimer = _DummyTimer
        qtcore.QCoreApplication = types.SimpleNamespace(instance=lambda: None)
        qtcore.QUrl = types.SimpleNamespace(fromLocalFile=lambda p: p)
        qtcore.Qt = types.SimpleNamespace(RightToLeft=1, LeftToRight=0)
        qtgui = types.ModuleType("PySide6.QtGui")
        qtgui.QPixmap = object
        qtgui.QDesktopServices = types.SimpleNamespace(openUrl=lambda u: None)
        qtwidgets = types.ModuleType("PySide6.QtWidgets")
        qtwidgets.QApplication = types.SimpleNamespace(instance=lambda: None, quit=lambda: None)
        sys.modules["PySide6"] = types.ModuleType("PySide6")
        sys.modules["PySide6.QtCore"] = qtcore
        sys.modules["PySide6.QtGui"] = qtgui
        sys.modules["PySide6.QtWidgets"] = qtwidgets

from app.config import AppConfig
from app.domain.downloader import (
    _apply_network_and_auth_opts,
    _extract_real_qualities_and_audio,
    _find_downloaded_files_safe,
    _parse_entries_from_info,
    _parse_version_tuple,
    build_safe_output_stem,
    cleanup_task_temp_files,
    extract_video_id_from_url,
    install_ffmpeg_automatically,
    normalize_channel_url,
    parse_playlist_selection_range,
    safe_extract_tar,
    safe_extract_zip,
    sanitize_filename,
    translate_download_error,
    update_ytdlp_runtime,
    verify_file_sha256,
)
from app.domain.manager import DownloadManager
from app.domain.subtitles import (
    SubtitleCue,
    format_bidi_line,
    ms_to_srt_tc,
    reconstruct_and_clamp_cues,
    tc_to_ms,
    wrap_subtitle_lines_cleanly,
)
from app.i18n import LRE, PDF, RLE, RLM
from app.state import AppState, DownloadTaskItem


class TestSubtitleEngine(unittest.TestCase):
    def test_timecode_conversion_roundtrip(self) -> None:
        self.assertEqual(tc_to_ms("01:02:03,456"), 3723456)
        self.assertEqual(ms_to_srt_tc(3723456), "01:02:03,456")
        self.assertEqual(tc_to_ms("05:10.250"), 310250)

    def test_auto_generated_coalescing_and_overlap_clamping(self) -> None:
        raw_cues = [
            SubtitleCue(1, "00:00:01,000", "00:00:04,500", "Welcome to the Python tutorial"),
            SubtitleCue(2, "00:00:02,800", "00:00:06,200", "Welcome to the Python tutorial\nwhere we build an API server"),
            SubtitleCue(3, "00:00:05,100", "00:00:08,000", "using FastAPI and Docker."),
        ]
        clamped = reconstruct_and_clamp_cues(raw_cues, is_auto_generated=True)
        for i in range(len(clamped) - 1):
            self.assertLess(clamped[i].end_ms, clamped[i + 1].start_ms)
        self.assertEqual(clamped[0].text, "Welcome to the Python tutorial where we build an API server")

    def test_manual_subtitles_preserve_boundaries_and_repeated_short_lines(self) -> None:
        manual_cues = [
            SubtitleCue(1, "00:00:01,000", "00:00:02,000", "No."),
            SubtitleCue(2, "00:00:02,200", "00:00:03,200", "No."),
            SubtitleCue(3, "00:00:03,500", "00:00:05,000", "Wait a second"),
        ]
        result = reconstruct_and_clamp_cues(manual_cues, is_auto_generated=False)
        self.assertEqual(len(result), 3)
        self.assertEqual([c.text for c in result], ["No.", "No.", "Wait a second"])

    def test_tv_safe_bidi_avoids_box_characters(self) -> None:
        line_tv = format_bidi_line("درس برمجة Python (المستوى 1).", target_is_rtl=True, tv_safe=True)
        self.assertNotIn(RLE, line_tv)
        self.assertNotIn(LRE, line_tv)
        self.assertNotIn(PDF, line_tv)
        self.assertTrue(line_tv.startswith(RLM))
        self.assertTrue(line_tv.endswith(RLM))

    def test_wrap_subtitle_lines_balanced(self) -> None:
        long_txt = "هذا النص طويل نسبياً ويحتاج إلى تقسيم متوازن على سطرين فقط دون أن يتجاوز الحد المسموح"
        lines = wrap_subtitle_lines_cleanly(long_txt, max_line_chars=45)
        self.assertEqual(len(lines), 2)


class TestDownloaderHelpers(unittest.TestCase):
    def test_windows_reserved_filenames_and_max_path(self) -> None:
        self.assertEqual(sanitize_filename("CON"), "_CON_")
        self.assertEqual(sanitize_filename("nul.txt"), "_nul.txt_")
        self.assertEqual(sanitize_filename("COM1"), "_COM1_")

        deep_dir = Path("C:/Users/Administrator/Downloads/" + ("very_long_subfolder_name_" * 7))
        stem = build_safe_output_stem(deep_dir, "001 - ", "A" * 200)
        self.assertLessEqual(len(str(deep_dir / f"{stem}.f137.mp4.part")), 258)

    def test_real_video_id_extraction_and_template(self) -> None:
        vid = extract_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123")
        self.assertEqual(vid, "dQw4w9WgXcQ")
        stem = build_safe_output_stem(
            target_dir=Path("/tmp"),
            prefix="01 - ",
            title="Never Gonna Give You Up",
            template="{prefix}{title} [{id}]",
            video_id=vid,
        )
        self.assertEqual(stem, "01 - Never Gonna Give You Up [dQw4w9WgXcQ]")

    def test_sha256_and_safe_archive_extraction_blocks_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            sample = tdir / "sample.bin"
            sample.write_bytes(b"vstream-security-check")
            expected = hashlib.sha256(b"vstream-security-check").hexdigest()
            self.assertTrue(verify_file_sha256(sample, expected))
            self.assertFalse(verify_file_sha256(sample, "0" * 64))

            # Malicious zip with '../evil.txt' must raise RuntimeError
            bad_zip = tdir / "bad.zip"
            with zipfile.ZipFile(bad_zip, "w") as zf:
                zf.writestr("../evil.txt", "pwned")
            with zipfile.ZipFile(bad_zip, "r") as zf_r:
                with self.assertRaises(RuntimeError):
                    safe_extract_zip(zf_r, tdir / "out_zip")

            # Malicious tar with '../evil.sh' must raise RuntimeError
            bad_tar = tdir / "bad.tar"
            with tarfile.open(bad_tar, "w") as tf:
                info = tarfile.TarInfo(name="../evil.sh")
                payload = b"echo pwn"
                info.size = len(payload)
                tf.addfile(info, io.BytesIO(payload))
            with tarfile.open(bad_tar, "r") as tf_r:
                with self.assertRaises(RuntimeError):
                    safe_extract_tar(tf_r, tdir / "out_tar")

    def test_js_runtime_enabled_wired_to_ytdlp_opts(self) -> None:
        cfg_on = AppConfig(js_runtime_enabled=True)
        opts_on: dict = {}
        _apply_network_and_auth_opts(opts_on, cfg_on)
        self.assertIn("js_runtimes", opts_on)
        self.assertTrue(len(opts_on["js_runtimes"]) >= 1)

        cfg_off = AppConfig(js_runtime_enabled=False)
        opts_off: dict = {}
        _apply_network_and_auth_opts(opts_off, cfg_off)
        self.assertEqual(opts_off.get("js_runtimes"), {})

    def test_exact_stem_matching_prevents_intro_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            (tdir / "Intro.mp4").write_bytes(b"111")
            (tdir / "Intro 2.mp4").write_bytes(b"222")
            (tdir / "Intro.ar.srt").write_bytes(b"333")
            (tdir / "Intro.mp4.part").write_bytes(b"444")

            media, subs = _find_downloaded_files_safe(tdir, "Intro")
            self.assertEqual([p.name for p in media], ["Intro.mp4"])
            self.assertEqual([p.name for p in subs], ["Intro.ar.srt"])

            removed = cleanup_task_temp_files(tdir, "Intro")
            self.assertEqual(removed, 1)
            self.assertFalse((tdir / "Intro.mp4.part").exists())
            self.assertTrue((tdir / "Intro.mp4").exists())

    def test_channel_url_normalization_and_tab_flattening(self) -> None:
        self.assertEqual(
            normalize_channel_url("https://www.youtube.com/@SomeCreator"),
            "https://www.youtube.com/@SomeCreator/videos",
        )
        self.assertEqual(
            normalize_channel_url("https://www.youtube.com/@SomeCreator/shorts"),
            "https://www.youtube.com/@SomeCreator/shorts",
        )

        nested_channel_info = {
            "_type": "playlist",
            "entries": [
                {
                    "_type": "playlist",
                    "title": "Videos",
                    "entries": [
                        {"id": "v1", "title": "First Video", "url": "https://www.youtube.com/watch?v=v1"},
                        {"id": "v2", "title": "Second Video", "url": "https://www.youtube.com/watch?v=v2"},
                    ],
                }
            ],
        }
        flat = _parse_entries_from_info(nested_channel_info)
        self.assertEqual(len(flat), 2)
        self.assertEqual(flat[0]["id"], "v1")

    def test_playlist_range_parser(self) -> None:
        self.assertEqual(parse_playlist_selection_range("1-3, 5, 8-7", 10), [1, 2, 3, 5, 7, 8])
        self.assertEqual(parse_playlist_selection_range("", 4), [1, 2, 3, 4])

    def test_real_qualities_and_multi_audio_extraction(self) -> None:
        mock_info = {
            "formats": [
                {"vcodec": "avc1", "acodec": "none", "height": 1080, "fps": 60, "filesize": 50_000_000},
                {"vcodec": "avc1", "acodec": "none", "height": 720, "fps": 30, "filesize": 25_000_000},
                {"vcodec": "avc1", "acodec": "mp4a", "height": 360, "fps": 30, "filesize": 9_000_000},
                {"vcodec": "avc1", "acodec": "none", "height": 144, "fps": 30, "filesize": 2_500_000},
                {"vcodec": "none", "acodec": "opus", "abr": 160, "language": "en", "format_note": "English original"},
                {"vcodec": "none", "acodec": "mp4a", "abr": 128, "language": "ar", "format_note": "Arabic dubbed"},
            ]
        }
        quals, _details, _aud_q, aud_tracks = _extract_real_qualities_and_audio(mock_info)
        self.assertEqual(quals, ["1080p", "720p", "360p", "144p", "best"])
        self.assertEqual([t.lang_code for t in aud_tracks], ["", "ar", "en"])

    def test_human_friendly_error_translation(self) -> None:
        err_msg = translate_download_error("ERROR: [youtube] abc: Private video. Sign in if you've been granted access")
        self.assertTrue("Private" in err_msg or "خاص" in err_msg)

    def test_version_tuple_normalization_and_no_redundant_redownload(self) -> None:
        self.assertEqual(_parse_version_tuple("2026.02.04"), _parse_version_tuple("2026.2.4"))

        with patch("app.domain.downloader.verify_ffmpeg_working", return_value="/usr/bin/ffmpeg"):
            ok, path_res, already_present = install_ffmpeg_automatically(force=False)
            self.assertTrue(ok)
            self.assertEqual(path_res, "/usr/bin/ffmpeg")
            self.assertTrue(already_present)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"info": {"version": "2026.2.4"}, "urls": []}
        mock_resp.raise_for_status.return_value = None
        with (
            patch("app.domain.downloader.get_ytdlp_version", return_value="2026.02.04"),
            patch("app.domain.downloader.is_ytdlp_ejs_installed", return_value=True),
            patch("app.domain.downloader.requests.get", return_value=mock_resp) as mock_get,
        ):
            ok_y, _msg_y = update_ytdlp_runtime(force=False)
            self.assertTrue(ok_y)
            self.assertEqual(mock_get.call_count, 1)


class TestStateAndManager(unittest.TestCase):
    def test_duplicate_check_verifies_file_exists_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            with patch("app.state.queue_state_path", return_value=tdir / "queue_state.json"):
                cfg = AppConfig()
                state = AppState(cfg, load_persisted=False)
                out_f = tdir / "video.mp4"
                out_f.write_bytes(b"data")

                item = DownloadTaskItem(
                    task_id="t1",
                    url="https://www.youtube.com/watch?v=abc12345678",
                    title="Test Video",
                    video_id="abc12345678",
                    status="completed",
                    output_path=str(out_f),
                )
                state.add_task(item)
                # File exists -> treated as duplicate
                self.assertIsNotNone(state.find_duplicate_task("https://www.youtube.com/watch?v=abc12345678", "video"))

                # User deletes file from disk -> no longer blocks re-downloading!
                out_f.unlink()
                self.assertIsNone(state.find_duplicate_task("https://www.youtube.com/watch?v=abc12345678", "video"))

    def test_history_pruning_and_post_queue_one_shot_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            with (
                patch("app.state.queue_state_path", return_value=tdir / "queue_state.json"),
                patch("app.config.app_data_dir", return_value=tdir),
            ):
                cfg = AppConfig(post_queue_action="shutdown", auto_cleanup_days=3)
                cfg.save()
                # Reloading config must never persist 'shutdown' across restarts!
                reloaded = AppConfig.load()
                self.assertEqual(reloaded.post_queue_action, "none")

                state = AppState(cfg, load_persisted=False)
                old_item = DownloadTaskItem(
                    task_id="old1",
                    url="https://example.com/1",
                    title="Old",
                    status="completed",
                    completed_at_ts=time.time() - (5 * 86400),
                )
                recent_item = DownloadTaskItem(
                    task_id="new1",
                    url="https://example.com/2",
                    title="Recent",
                    status="completed",
                    completed_at_ts=time.time() - 3600,
                )
                state.add_task(old_item)
                state.add_task(recent_item)
                state.prune_expired_history(save_immediately=True)
                self.assertNotIn("old1", state.tasks)
                self.assertIn("new1", state.tasks)

    def test_manager_blocks_ytdlp_update_during_active_download_and_one_shot_countdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            with (
                patch("app.state.queue_state_path", return_value=tdir / "queue_state.json"),
                patch("app.config.app_data_dir", return_value=tdir),
                patch("app.domain.manager.find_ffmpeg_path", return_value="/usr/bin/ffmpeg"),
            ):
                cfg = AppConfig(post_queue_action="shutdown")
                state = AppState(cfg, load_persisted=False)
                mgr = DownloadManager(state)

                toasts = []
                state.toast_requested.connect(lambda msg, kind: toasts.append((msg, kind)))

                # Simulate active download running
                mgr._running_ids.add("active_1")
                mgr.trigger_ytdlp_update(silent=False)
                self.assertFalse(mgr._ytdlp_busy)
                self.assertTrue(any(k == "warn" for _, k in toasts))

                # Finish active downloads and check one-shot post_queue_action countdown emission
                mgr._running_ids.clear()
                countdown_actions = []
                state.post_queue_countdown_requested.connect(lambda act: countdown_actions.append(act))
                mgr._check_post_queue_action()
                self.assertEqual(countdown_actions, ["shutdown"])
                # Must immediately reset post_queue_action to 'none'
                self.assertEqual(state.config.post_queue_action, "none")


if __name__ == "__main__":
    unittest.main()
