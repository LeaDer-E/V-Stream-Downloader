import app.stdlib_preload  # noqa: F401
from concurrent.futures import ThreadPoolExecutor
import ctypes
import getpass
import hashlib
import netrc
import optparse
import plistlib
import secrets
import sqlite3
import importlib
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import zipfile

import requests

from app.config import AppConfig
from app.domain.subtitles import (
    SubtitleCancelRequested,
    SubtitlePauseRequested,
    process_and_sync_subtitle,
)
from app.i18n import localized_lang_name, tp
from app.paths import bin_dir, bundle_dir, download_archive_path, is_frozen, logs_dir, thumbs_cache_dir
from app.state import AnalyzedMediaInfo, AudioTrackInfo, DownloadTaskItem, SubtitleTrackInfo

logger = logging.getLogger(__name__)

APP_VERSION = "5.1.0"

# Prepend external updated yt_dlp package directory if downloaded via self-updater
_EXT_YTDLP_DIR = bin_dir() / "yt_dlp_pkg"
if _EXT_YTDLP_DIR.exists() and str(_EXT_YTDLP_DIR) not in sys.path:
    sys.path.insert(0, str(_EXT_YTDLP_DIR))

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

UUID_PATH_RE = re.compile(r"^/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
M3U8_SNIFF_RE = re.compile(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)', re.IGNORECASE)
YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([0-9A-Za-z_-]{11})")

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

STANDARD_VIDEO_TIERS: List[Tuple[int, str, str]] = [
    (4320, "4320p", "4320p 8K Ultra HD"),
    (2160, "2160p", "2160p 4K Ultra HD"),
    (1440, "1440p", "1440p 2K QHD"),
    (1080, "1080p", "1080p Full HD"),
    (720, "720p", "720p HD"),
    (480, "480p", "480p SD"),
    (360, "360p", "360p"),
    (240, "240p", "240p"),
    (144, "144p", "144p"),
]


class BlobUrlDetectedError(Exception):
    def __init__(self, raw_blob_url: str, origin_domain: str) -> None:
        super().__init__(f"Blob URL detected from {origin_domain}")
        self.raw_blob_url = raw_blob_url
        self.origin_domain = origin_domain


class PauseRequestedError(Exception):
    pass


class CancelRequestedError(Exception):
    pass


def extract_video_id_from_url(url: str) -> str:
    """Extracts the real video ID from YouTube or common media URLs when possible."""
    if not url:
        return ""
    m = YT_ID_RE.search(url)
    if m:
        return m.group(1)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return str(qs["v"][0]).strip()
    return ""


def verify_file_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Computes SHA-256 of `file_path` and compares against `expected_sha256`."""
    if not expected_sha256 or not file_path.is_file():
        return False
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower() == expected_sha256.strip().lower()


def verify_file_md5(file_path: Path, expected_md5: str) -> bool:
    """Computes MD5 of `file_path` and compares against `expected_md5`."""
    if not expected_md5 or not file_path.is_file():
        return False
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower() == expected_md5.strip().lower()


def _is_safe_member_path(dest_dir: Path, member_name: str) -> bool:
    """Prevents Zip-Slip and Tar path-traversal attacks (`..`, absolute paths, drive letters)."""
    if not member_name or member_name.startswith(("/", "\\")) or ".." in Path(member_name).parts:
        return False
    base_resolved = dest_dir.resolve()
    try:
        target_resolved = (dest_dir / member_name).resolve()
        return str(target_resolved).startswith(str(base_resolved) + os.sep) or target_resolved == base_resolved
    except Exception:
        return False


def safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Extracts a ZipFile after validating every member against path traversal."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        if not _is_safe_member_path(dest_dir, info.filename):
            raise RuntimeError(f"Unsafe path detected inside zip archive: {info.filename!r}")
    zf.extractall(dest_dir)


def safe_extract_tar(tf: tarfile.TarFile, dest_dir: Path) -> None:
    """Extracts a TarFile safely, blocking path traversal, symlinks outside root, and special devices."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_members: List[tarfile.TarInfo] = []
    for member in tf.getmembers():
        if not _is_safe_member_path(dest_dir, member.name):
            raise RuntimeError(f"Unsafe path detected inside tar archive: {member.name!r}")
        if member.ischr() or member.isblk() or member.isfifo():
            continue
        if member.issym() or member.islnk():
            link_target = Path(member.name).parent / member.linkname
            if not _is_safe_member_path(dest_dir, str(link_target)):
                raise RuntimeError(f"Unsafe symlink target in tar archive: {member.linkname!r}")
        safe_members.append(member)

    if sys.version_info >= (3, 12):
        tf.extractall(dest_dir, members=safe_members, filter="data")
    else:
        tf.extractall(dest_dir, members=safe_members)


def sanitize_filename(name: str, max_len: int = 120) -> str:
    """
    Sanitizes a filename for cross-platform & Windows compatibility:
    1. Replaces illegal filesystem characters (`<>:"/\\|?*` and control chars).
    2. Strips leading/trailing dots and spaces.
    3. Protects against Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`).
    4. Enforces `max_len` character ceiling.
    """
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (name or "").strip()).strip(" .")
    if not cleaned:
        cleaned = "video"

    stem_part = cleaned.split(".")[0].strip().upper()
    if stem_part in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}_"

    limit = max(16, int(max_len))
    cleaned = cleaned[:limit].rstrip(" .")
    return cleaned or "video"


def build_safe_output_stem(
    target_dir: Path,
    prefix: str,
    title: str,
    template: str = "{prefix}{title}",
    channel: str = "",
    video_id: str = "",
) -> str:
    """
    Builds a safe output filename stem while guaranteeing the full path (`target_dir / stem + .part.mp4`)
    never exceeds the Windows 260-character `MAX_PATH` limit!
    """
    try:
        dir_str = str(target_dir.resolve())
    except Exception:
        dir_str = str(target_dir)

    available_for_stem = max(24, min(145, 230 - len(dir_str)))

    safe_title = sanitize_filename(title, max_len=available_for_stem)
    safe_channel = sanitize_filename(channel, max_len=36) if channel else "Channel"
    safe_id = sanitize_filename(video_id, max_len=24) if video_id else ""

    if template == "{prefix}{channel} - {title}" and channel:
        raw_stem = f"{prefix}{safe_channel} - {safe_title}"
    elif template == "{prefix}{title} [{id}]" and safe_id:
        id_suffix = f" [{safe_id}]"
        title_budget = max(16, available_for_stem - len(prefix) - len(id_suffix))
        trimmed_title = sanitize_filename(title, max_len=title_budget)
        raw_stem = f"{prefix}{trimmed_title}{id_suffix}"
    else:
        raw_stem = f"{prefix}{safe_title}"

    return sanitize_filename(raw_stem, max_len=available_for_stem)


def parse_playlist_selection_range(spec: str, total_count: int) -> List[int]:
    if total_count <= 0:
        return []
    clean = (spec or "").strip().lower()
    if not clean or clean in ("all", "الكل", "*"):
        return list(range(1, total_count + 1))

    selected: set[int] = set()
    for part in clean.replace("،", ",").split(","):
        tok = part.strip()
        if not tok:
            continue
        if "-" in tok:
            bounds = tok.split("-", 1)
            if bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                start_i = int(bounds[0].strip())
                end_i = int(bounds[1].strip())
                if start_i > end_i:
                    start_i, end_i = end_i, start_i
                for idx in range(max(1, start_i), min(total_count, end_i) + 1):
                    selected.add(idx)
        elif tok.isdigit():
            idx = int(tok)
            if 1 <= idx <= total_count:
                selected.add(idx)

    return sorted(selected) if selected else list(range(1, total_count + 1))


def normalize_channel_url(url: str) -> str:
    clean = (url or "").strip()
    if not is_youtube_url(clean):
        return clean
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    is_ch = any(seg in path for seg in ("/@", "/channel/", "/c/", "/user/"))
    if not is_ch:
        return clean
    known_tabs = ("/videos", "/shorts", "/streams", "/live", "/releases", "/playlists", "/featured", "/community")
    if any(path.lower().endswith(tab) for tab in known_tabs):
        return clean
    new_path = f"{path}/videos"
    return urlunparse((parsed.scheme, parsed.netloc, new_path, parsed.params, parsed.query, parsed.fragment))


def translate_download_error(raw_err: str) -> str:
    msg = (raw_err or "").strip()
    low = msg.lower()

    if "dpapi" in low or "failed to decrypt" in low or ("cookie" in low and ("permission denied" in low or "locked" in low)):
        return tp(
            "تعذّر فك تشفير كوكيز Chrome/Edge (بسبب حماية ويندوز أو لأن المتصفح مفتوح) — يُنصح باختيار Firefox أو تصدير ملف cookies.txt.",
            "Chrome/Edge cookie decryption blocked by Windows App-Bound Encryption — use Firefox or a cookies.txt file instead.",
        )
    if "private video" in low or "sign in if you've been granted access" in low:
        return tp(
            "فيديو خاص (Private): يتطلب تسجيل الدخول — فعّل «سحب الكوكيز من المتصفح» في الإعدادات.",
            "Private Video: Login required — enable 'Browser Cookies' in Settings.",
        )
    if "sign in to confirm your age" in low or "age-restricted" in low or "inappropriate for some users" in low:
        return tp(
            "فيديو مقيّد بالعمر: فعّل «سحب الكوكيز من المتصفح» في الإعدادات لتحميله.",
            "Age-Restricted Video: Enable 'Browser Cookies' in Settings to download.",
        )
    if "confirm you’re not a bot" in low or "confirm you're not a bot" in low or "sign in to confirm" in low:
        return tp(
            "يطلب يوتيوب التحقق من الجلسة (Cookies) — فعّل «سحب الكوكيز من المتصفح» أو حدّث محرك yt-dlp من الإعدادات.",
            "YouTube requested session verification — enable 'Browser Cookies' or update yt-dlp in Settings.",
        )
    if "not available in your country" in low or ("geo" in low and "restricted" in low) or "blocked in your country" in low:
        return tp(
            "الفيديو محظور جغرافياً في منطقتك — أضف عنوان Proxy في الإعدادات لتخطي الحجب.",
            "Geo-Restricted Video: Not available in your country — configure a Proxy in Settings.",
        )
    if "http error 403" in low or "403: forbidden" in low:
        return tp(
            "خطأ 403 (انتهت صلاحية الجلسة أو الرابط محمي) — اضغط إعادة المحاولة أو حدّث yt-dlp من الإعدادات.",
            "HTTP 403 Forbidden (Session expired or protected stream) — click Retry or update yt-dlp in Settings.",
        )
    if "http error 429" in low or "too many requests" in low:
        return tp(
            "خطأ 429 (طلبات كثيرة جداً) — يرجى الانتظار قليلاً أو تفعيل الكوكيز/البروكسي.",
            "HTTP 429 Too Many Requests — wait a moment or enable Cookies/Proxy in Settings.",
        )
    if "ffmpeg" in low and ("not found" in low or "not installed" in low):
        return tp(
            "أداة الدمج FFmpeg غير مثبتة — افتح الإعدادات واضغط «تثبيت FFmpeg تلقائياً».",
            "FFmpeg is not installed — open Settings and click 'Auto-Install FFmpeg'.",
        )
    if "no space left" in low or "insufficient disk space" in low or "مساحة القرص" in low:
        return tp(
            "مساحة القرص الصلب غير كافية في مجلد الحفظ — يرجى تفريغ مساحة أو تغيير مجلد التحميل.",
            "Insufficient disk space in download folder — free up space or change download directory.",
        )
    if "timed out" in low or "connection aborted" in low or "network is unreachable" in low or "name or service not known" in low:
        return tp(
            "انقطع الاتصال بالشبكة أثناء التحميل — اضغط زر «استئناف / إعادة المحاولة» لإكمال التحميل من حيث توقف.",
            "Network connection interrupted — click Resume/Retry to continue from where it stopped.",
        )

    clean = re.sub(r"\x1b\[[0-9;]*m", "", msg).replace("ERROR:", "").strip()
    return clean[:360] if clean else tp("حدث خطأ غير متوقع أثناء التحميل", "Unexpected download error occurred")


def is_m3u8_url(url: str) -> bool:
    u = url.lower().split("?")[0]
    return u.endswith(".m3u8") or ".m3u8" in url.lower()


def is_youtube_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(d in host for d in ("youtube.com", "youtu.be", "youtube-nocookie.com"))


def find_ffmpeg_path(custom_path: str = "") -> Optional[str]:
    """
    Locates FFmpeg across:
    1. User custom path (file or directory).
    2. Auto-installed `app_data_dir()/bin/ffmpeg(.exe)`.
    3. App bundle directory (`./ffmpeg(.exe)`).
    4. System `PATH` (`shutil.which("ffmpeg")`).
    """
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates: List[Path] = []
    if custom_path:
        cp = Path(custom_path)
        if cp.is_file():
            candidates.append(cp)
        elif cp.is_dir():
            candidates.append(cp / exe_name)

    candidates.append(bin_dir() / exe_name)
    candidates.append(bundle_dir() / exe_name)

    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        candidates.append(Path(sys_ff))

    for cand in candidates:
        try:
            if cand.is_file() and cand.stat().st_size > 10_000:
                return str(cand)
        except OSError:
            continue
    return None


def verify_ffmpeg_working(custom_path: str = "") -> Optional[str]:
    """
    Checks if FFmpeg is already installed on disk AND responds cleanly to `ffmpeg -version`.
    Returns the verified executable path if ready, or None if missing/corrupted.
    """
    ff_path = find_ffmpeg_path(custom_path)
    if not ff_path:
        return None
    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        res = subprocess.run(
            [ff_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            creationflags=creationflags,
        )
        if res.returncode == 0:
            return ff_path
    except Exception as exc:
        logger.debug("FFmpeg verification probe failed for %s: %s", ff_path, exc)
    return None


def detect_js_runtime() -> Optional[str]:
    """Returns the primary detected JavaScript runtime (`deno`, `node`, `quickjs`, `bun`) and its path."""
    for rt in ("deno", "node", "quickjs", "bun"):
        local_cand = bin_dir() / (f"{rt}.exe" if os.name == "nt" else rt)
        if local_cand.is_file():
            return f"{rt}:{local_cand}"
        found = shutil.which(rt)
        if found:
            return f"{rt}:{found}"
    return None


def detect_all_js_runtimes() -> Dict[str, Dict[str, Optional[str]]]:
    """
    Builds the `js_runtimes` dictionary for `yt_dlp.YoutubeDL(params)`:
    Note: `yt-dlp` enables `deno` by default, while `node`, `quickjs`, and `bun`
    MUST be explicitly passed in `js_runtimes` to be used for YouTube EJS challenges!
    """
    runtimes: Dict[str, Dict[str, Optional[str]]] = {}
    for rt in ("deno", "node", "quickjs", "bun"):
        local_cand = bin_dir() / (f"{rt}.exe" if os.name == "nt" else rt)
        if local_cand.is_file():
            runtimes[rt] = {"path": str(local_cand)}
            continue
        found = shutil.which(rt)
        if found:
            runtimes[rt] = {"path": found}
    if not runtimes:
        runtimes["deno"] = {"path": None}
    return runtimes


def is_ytdlp_ejs_installed() -> bool:
    """Checks whether `yt-dlp-ejs` challenge solver scripts are installed."""
    ext_ejs = bin_dir() / "yt_dlp_pkg" / "yt_dlp_ejs"
    if ext_ejs.is_dir():
        return True
    try:
        import importlib.util
        return importlib.util.find_spec("yt_dlp_ejs") is not None
    except Exception:
        return False


def _parse_version_tuple(ver_str: str) -> Tuple[int, ...]:
    """
    Normalizes version strings like `'2026.02.04'` and PyPI's `'2026.2.4'` into `(2026, 2, 4)`
    so leading zeros never cause false version mismatches!
    """
    nums = [int(n) for n in re.findall(r"\d+", ver_str or "")]
    return tuple(nums) if nums else (0,)


def _ensure_external_ytdlp_loaded() -> None:
    """
    Transactionally loads an updated `yt_dlp` (and `yt_dlp_ejs`) package from `bin_dir() / "yt_dlp_pkg"`
    if present. If the external package is corrupted or fails to initialize `YoutubeDL`, automatically
    rolls back `sys.modules`, removes the broken external directory, and falls back to the bundled `yt_dlp`.
    """
    ext_pkg_dir = bin_dir() / "yt_dlp_pkg"
    ext_pkg_init = ext_pkg_dir / "yt_dlp" / "__init__.py"
    if not ext_pkg_init.exists():
        return
    ext_root = str(ext_pkg_dir)
    if ext_root not in sys.path:
        sys.path.insert(0, ext_root)

    existing_mod = sys.modules.get("yt_dlp")
    loaded_file = getattr(existing_mod, "__file__", "") or ""
    if existing_mod is not None and ext_root in loaded_file and hasattr(existing_mod, "YoutubeDL"):
        return

    saved_modules = {
        k: v for k, v in list(sys.modules.items())
        if k in ("yt_dlp", "yt_dlp_ejs") or k.startswith(("yt_dlp.", "yt_dlp_ejs."))
    }
    try:
        for k in list(saved_modules.keys()):
            sys.modules.pop(k, None)
        importlib.invalidate_caches()
        mod = importlib.import_module("yt_dlp")
        if not hasattr(mod, "YoutubeDL"):
            raise RuntimeError("Loaded yt_dlp module is missing YoutubeDL attribute")
    except Exception as exc:
        logger.warning("External yt_dlp_pkg failed to load (%s); rolling back to bundled yt_dlp", exc)
        for k in [
            m for m in list(sys.modules.keys())
            if m in ("yt_dlp", "yt_dlp_ejs") or m.startswith(("yt_dlp.", "yt_dlp_ejs."))
        ]:
            sys.modules.pop(k, None)
        if ext_root in sys.path:
            sys.path.remove(ext_root)
        sys.modules.update(saved_modules)
        try:
            shutil.rmtree(ext_pkg_dir, ignore_errors=True)
        except Exception:
            pass


def get_ytdlp_version() -> str:
    """
    Reads the active `yt-dlp` version, checking `bin_dir() / "yt_dlp_pkg"` first
    so self-updated installations always report their true updated version.
    """
    ext_ver_file = bin_dir() / "yt_dlp_pkg" / "yt_dlp" / "version.py"
    if ext_ver_file.exists():
        try:
            txt = ext_ver_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]', txt)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
    try:
        import yt_dlp.version
        return str(yt_dlp.version.__version__)
    except Exception:
        return "unknown"


def _download_and_verify_pypi_wheel(pkg_name: str, dest_dir: Path) -> Tuple[bool, str]:
    """
    Fetches PyPI JSON metadata for `pkg_name`, finds the universal wheel,
    downloads it, verifies its cryptographic SHA-256 against `digests["sha256"]`,
    and safely extracts it into `dest_dir`.
    """
    resp = requests.get(f"https://pypi.org/pypi/{pkg_name}/json", timeout=12, headers={"User-Agent": DEFAULT_UA})
    resp.raise_for_status()
    meta = resp.json()
    latest_ver = str((meta.get("info") or {}).get("version") or "").strip()
    urls = meta.get("urls") or []

    wheel_url = ""
    expected_sha256 = ""
    for u_info in urls:
        fn = str(u_info.get("filename") or "")
        if fn.endswith(".whl") and ("none-any" in fn or "py3" in fn):
            wheel_url = str(u_info.get("url") or "")
            expected_sha256 = str((u_info.get("digests") or {}).get("sha256") or "").strip()
            break

    if not wheel_url or not expected_sha256:
        return False, f"No verified wheel found on PyPI for {pkg_name}"

    whl_path = bin_dir() / f"{pkg_name.replace('-', '_')}_latest.whl"
    with requests.get(wheel_url, stream=True, timeout=30, headers={"User-Agent": DEFAULT_UA}) as r_dl:
        r_dl.raise_for_status()
        with open(whl_path, "wb") as f_out:
            for chunk in r_dl.iter_content(chunk_size=65536):
                if chunk:
                    f_out.write(chunk)

    if not verify_file_sha256(whl_path, expected_sha256):
        try:
            whl_path.unlink()
        except OSError:
            pass
        raise RuntimeError(
            tp(
                f"فشل التحقق الأمني SHA-256 لحزمة {pkg_name} — تم إلغاء التحديث للحماية",
                f"SHA-256 integrity check failed for {pkg_name} wheel — update aborted",
            )
        )

    with zipfile.ZipFile(whl_path, "r") as zf:
        safe_extract_zip(zf, dest_dir)

    try:
        whl_path.unlink()
    except OSError:
        pass
    return True, latest_ver


def update_ytdlp_runtime(
    progress_cb: Optional[Callable[[str], None]] = None,
    force: bool = False,
) -> Tuple[bool, str]:
    """
    Checks if `yt-dlp` (and `yt-dlp-ejs`) is already on the latest PyPI release first:
    - If `current_version >= latest_pypi_version`, `yt-dlp-ejs` is present, and `not force`:
      Immediately returns without re-downloading!
    - Otherwise, downloads, SHA-256 verifies, and installs both `yt-dlp` and `yt-dlp-ejs`
      wheels into `bin_dir() / "yt_dlp_pkg"`.
    """
    try:
        current_ver = get_ytdlp_version()
        if progress_cb:
            progress_cb(
                tp(
                    f"جاري فحص الإصدار الحالي ({current_ver}) مقارنة بأحدث إصدار على PyPI...",
                    f"Checking current yt-dlp ({current_ver}) against latest PyPI release...",
                )
            )

        resp = requests.get("https://pypi.org/pypi/yt-dlp/json", timeout=12, headers={"User-Agent": DEFAULT_UA})
        resp.raise_for_status()
        meta = resp.json()
        latest_ver = str((meta.get("info") or {}).get("version") or "").strip()

        if (
            not force
            and current_ver != "unknown"
            and latest_ver
            and _parse_version_tuple(current_ver) >= _parse_version_tuple(latest_ver)
            and is_ytdlp_ejs_installed()
        ):
            return (
                True,
                tp(
                    f"✓ محرك yt-dlp محدّث بالفعل لأحدث إصدار ({current_ver}) — لا حاجة لإعادة التحميل!",
                    f"✓ yt-dlp is already up-to-date ({current_ver}) — no re-download needed!",
                ),
            )

        if progress_cb:
            progress_cb(
                tp(
                    f"يتوفر تحديث جديد ({latest_ver}) — جاري التحميل والتحقق الأمني SHA-256...",
                    f"New version ({latest_ver}) found — downloading & verifying SHA-256...",
                )
            )

        target_pkg_dir = bin_dir() / "yt_dlp_pkg"
        tmp_pkg_dir = bin_dir() / "yt_dlp_pkg_tmp"
        if tmp_pkg_dir.exists():
            shutil.rmtree(tmp_pkg_dir, ignore_errors=True)
        tmp_pkg_dir.mkdir(parents=True, exist_ok=True)

        ok_main, _ = _download_and_verify_pypi_wheel("yt-dlp", tmp_pkg_dir)
        if ok_main:
            # Also install yt-dlp-ejs challenge solver scripts into the same package root
            try:
                _download_and_verify_pypi_wheel("yt-dlp-ejs", tmp_pkg_dir)
            except Exception as ejs_exc:
                logger.warning("Optional yt-dlp-ejs wheel update skipped: %s", ejs_exc)

            if target_pkg_dir.exists():
                shutil.rmtree(target_pkg_dir, ignore_errors=True)
            tmp_pkg_dir.rename(target_pkg_dir)

            for mod_name in [
                k for k in list(sys.modules.keys())
                if k in ("yt_dlp", "yt_dlp_ejs") or k.startswith(("yt_dlp.", "yt_dlp_ejs."))
            ]:
                sys.modules.pop(mod_name, None)
            importlib.invalidate_caches()
            _ensure_external_ytdlp_loaded()

            new_v = get_ytdlp_version()
            return (
                True,
                tp(
                    f"✓ تم تحديث محرك yt-dlp بنجاح إلى الإصدار {new_v}!",
                    f"✓ Successfully updated yt-dlp to v{new_v}!",
                ),
            )

        if not is_frozen():
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]"])
            return True, tp(f"✓ تم تحديث yt-dlp إلى {latest_ver}", f"✓ Updated yt-dlp to {latest_ver}")

        return False, tp("لم يتم العثور على حزمة التحديث المباشر", "Could not find wheel package on PyPI")
    except Exception as exc:
        logger.error("yt-dlp update failed: %s", exc)
        return False, tp(f"تعذّر تحديث yt-dlp: {str(exc)[:90]}", f"Failed to update yt-dlp: {str(exc)[:90]}")


def _resolve_btbn_win64_ffmpeg_release() -> Tuple[str, str]:
    """
    Queries the official BtbN/FFmpeg-Builds GitHub Releases API to retrieve the latest
    win64 GPL zip URL and its SHA-256 checksum (from asset digest or checksums.sha256).
    """
    fallback_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    target_name = "ffmpeg-master-latest-win64-gpl.zip"
    try:
        resp = requests.get(
            "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest",
            timeout=10,
            headers={"User-Agent": DEFAULT_UA, "Accept": "application/vnd.github+json"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assets = data.get("assets") or []
            dl_url = fallback_url
            sha256_hex = ""
            checksums_url = ""
            for asset in assets:
                aname = str(asset.get("name") or "")
                if aname == target_name:
                    dl_url = str(asset.get("browser_download_url") or fallback_url)
                    digest_str = str(asset.get("digest") or "")
                    if digest_str.lower().startswith("sha256:"):
                        sha256_hex = digest_str.split(":", 1)[1].strip()
                elif aname == "checksums.sha256":
                    checksums_url = str(asset.get("browser_download_url") or "")

            if not sha256_hex and checksums_url:
                c_resp = requests.get(checksums_url, timeout=8, headers={"User-Agent": DEFAULT_UA})
                if c_resp.status_code == 200:
                    for line in c_resp.text.splitlines():
                        if target_name in line:
                            parts = line.strip().split()
                            if parts and len(parts[0]) == 64:
                                sha256_hex = parts[0]
                                break
            return dl_url, sha256_hex
    except Exception as exc:
        logger.debug("GitHub API probe for BtbN FFmpeg checksum skipped: %s", exc)
    return fallback_url, ""


def install_ffmpeg_automatically(
    custom_path: str = "",
    progress_cb: Optional[Callable[[float, str], None]] = None,
    force: bool = False,
) -> Tuple[bool, str, bool]:
    """
    First checks if `ffmpeg` is already installed and working via `verify_ffmpeg_working(custom_path)`:
    - If already present and working (and `not force`), immediately returns `(True, existing_path, True)`
      without re-downloading!
    - Otherwise downloads, verifies checksum, and safely extracts static `ffmpeg` + `ffprobe`
      into `app_data_dir()/bin/` across Windows, macOS (both ffmpeg + ffprobe), and Linux (amd64 + arm64).
    """
    if not force:
        existing_ff = verify_ffmpeg_working(custom_path)
        if existing_ff:
            return True, existing_ff, True

    target_bin = bin_dir()
    extract_tmp = target_bin / "ffmpeg_extract_tmp"
    if extract_tmp.exists():
        shutil.rmtree(extract_tmp, ignore_errors=True)
    extract_tmp.mkdir(parents=True, exist_ok=True)

    try:
        if progress_cb:
            progress_cb(5.0, tp("جاري الاتصال بسيرفر تحميل FFmpeg...", "Connecting to FFmpeg release server..."))

        if sys.platform == "darwin":
            # On macOS, download and SHA-256 verify BOTH ffmpeg and ffprobe from Evermeet JSON API
            for idx, tool_name in enumerate(("ffmpeg", "ffprobe")):
                info_url = f"https://evermeet.cx/ffmpeg/info/{tool_name}/release"
                r_info = requests.get(info_url, timeout=12, headers={"User-Agent": DEFAULT_UA})
                r_info.raise_for_status()
                info_json = r_info.json()
                zip_meta = (info_json.get("download") or {}).get("zip") or {}
                dl_url = str(zip_meta.get("url") or f"https://evermeet.cx/ffmpeg/getrelease/{tool_name}/zip")
                expected_sha = str(zip_meta.get("sha256") or "").strip()
                arc_p = target_bin / f"{tool_name}_mac.zip"
                with requests.get(dl_url, stream=True, timeout=30, headers={"User-Agent": DEFAULT_UA}) as r_dl:
                    r_dl.raise_for_status()
                    with open(arc_p, "wb") as f_out:
                        for chunk in r_dl.iter_content(chunk_size=131072):
                            if chunk:
                                f_out.write(chunk)
                if expected_sha and not verify_file_sha256(arc_p, expected_sha):
                    arc_p.unlink(missing_ok=True)
                    raise RuntimeError(f"SHA-256 mismatch for macOS {tool_name} archive")
                with zipfile.ZipFile(arc_p, "r") as zf:
                    safe_extract_zip(zf, extract_tmp)
                arc_p.unlink(missing_ok=True)
                if progress_cb:
                    progress_cb(45.0 * (idx + 1), tp("جاري فك ضغط وتثبيت محرك FFmpeg...", "Extracting FFmpeg binaries..."))
        else:
            expected_sha256 = ""
            expected_md5 = ""
            if sys.platform == "win32":
                dl_url, expected_sha256 = _resolve_btbn_win64_ffmpeg_release()
                archive_name = "ffmpeg_static.zip"
            else:
                mach = platform.machine().lower()
                arch_slug = "arm64" if mach in ("aarch64", "arm64") else "amd64"
                dl_url = f"https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch_slug}-static.tar.xz"
                archive_name = f"ffmpeg_linux_{arch_slug}.tar.xz"
                try:
                    md5_resp = requests.get(f"{dl_url}.md5", timeout=8, headers={"User-Agent": DEFAULT_UA})
                    if md5_resp.status_code == 200:
                        parts = md5_resp.text.strip().split()
                        if parts and len(parts[0]) == 32:
                            expected_md5 = parts[0]
                except Exception:
                    pass

            archive_path = target_bin / archive_name
            with requests.get(dl_url, stream=True, timeout=30, headers={"User-Agent": DEFAULT_UA}) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                last_notify_pct = 0.0
                with open(archive_path, "wb") as f_out:
                    for chunk in resp.iter_content(chunk_size=131072):
                        if not chunk:
                            continue
                        f_out.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and progress_cb:
                            pct = min(88.0, (downloaded / float(total)) * 85.0 + 5.0)
                            if pct - last_notify_pct >= 18.0:
                                last_notify_pct = pct
                                mb_d = downloaded / (1024 * 1024)
                                mb_t = total / (1024 * 1024)
                                progress_cb(
                                    pct,
                                    tp(
                                        f"جاري تحميل FFmpeg ({mb_d:.1f} / {mb_t:.1f} MB)...",
                                        f"Downloading FFmpeg ({mb_d:.1f} / {mb_t:.1f} MB)...",
                                    ),
                                )

            if expected_sha256 and not verify_file_sha256(archive_path, expected_sha256):
                archive_path.unlink(missing_ok=True)
                raise RuntimeError("SHA-256 checksum verification failed for FFmpeg archive")
            if expected_md5 and not verify_file_md5(archive_path, expected_md5):
                archive_path.unlink(missing_ok=True)
                raise RuntimeError("MD5 checksum verification failed for Linux FFmpeg archive")

            if progress_cb:
                progress_cb(92.0, tp("جاري فك ضغط وتثبيت محرك FFmpeg...", "Extracting FFmpeg binaries..."))

            if archive_name.endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    safe_extract_zip(zf, extract_tmp)
            else:
                with tarfile.open(archive_path, "r:*") as tf:
                    safe_extract_tar(tf, extract_tmp)

            try:
                archive_path.unlink()
            except OSError:
                pass

        found_ffmpeg = None
        for root_p, _dirs, files in os.walk(extract_tmp):
            for fn in files:
                if fn.lower() in ("ffmpeg", "ffmpeg.exe", "ffprobe", "ffprobe.exe"):
                    src_f = Path(root_p) / fn
                    dst_f = target_bin / fn
                    shutil.copy2(src_f, dst_f)
                    if os.name != "nt":
                        dst_f.chmod(dst_f.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                    if fn.lower().startswith("ffmpeg"):
                        found_ffmpeg = dst_f

        shutil.rmtree(extract_tmp, ignore_errors=True)

        if found_ffmpeg and found_ffmpeg.exists():
            return True, str(found_ffmpeg), False

        return False, tp("لم يتم العثور على الملف التنفيذي داخل الحزمة", "FFmpeg binary not found in archive"), False
    except Exception as exc:
        shutil.rmtree(extract_tmp, ignore_errors=True)
        logger.error("Auto-install FFmpeg failed: %s", exc)
        return False, tp(f"تعذّر تحميل FFmpeg تلقائياً: {str(exc)[:90]}", f"Failed to auto-install FFmpeg: {str(exc)[:90]}"), False


def check_disk_space_available(target_dir: Path, min_free_bytes: int = 100 * 1024 * 1024) -> Tuple[bool, int]:
    try:
        check_p = target_dir if target_dir.exists() else target_dir.parent
        usage = shutil.disk_usage(check_p)
        return usage.free >= min_free_bytes, usage.free
    except Exception:
        return True, 0


def cleanup_task_temp_files(target_dir: Path, file_stem: str) -> int:
    removed = 0
    if not target_dir.exists() or not file_stem:
        return removed
    try:
        for f in target_dir.iterdir():
            if not f.is_file():
                continue
            if f.name == file_stem or f.name.startswith(file_stem + "."):
                low_name = f.name.lower()
                if (
                    low_name.endswith(".part")
                    or low_name.endswith(".ytdl")
                    or low_name.endswith(".temp")
                    or ".part-frag" in low_name
                    or re.search(r"\.f\d+\.(mp4|webm|m4a)$", low_name)
                ):
                    try:
                        f.unlink()
                        removed += 1
                    except OSError:
                        pass
    except Exception as exc:
        logger.debug("Cleanup temp files error: %s", exc)
    return removed


def fetch_thumbnail_cached(url: str) -> Optional[Path]:
    if not url:
        return None
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    target = thumbs_cache_dir() / f"{digest}.jpg"
    if target.exists() and target.stat().st_size > 100:
        return target
    try:
        resp = requests.get(url, timeout=6, headers={"User-Agent": DEFAULT_UA})
        if resp.status_code == 200 and resp.content:
            target.write_bytes(resp.content)
            return target
    except Exception as exc:
        logger.debug("Thumbnail fetch failed: %s", exc)
    return None


def _build_stream_headers(url: str, custom_referer: str = "") -> Dict[str, str]:
    parsed = urlparse(custom_referer or url)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    ref = custom_referer if custom_referer else (f"{origin}/" if origin else "")
    headers = {"User-Agent": DEFAULT_UA}
    if ref:
        headers["Referer"] = ref
    if origin:
        headers["Origin"] = origin
    return headers


def _apply_network_and_auth_opts(opts: Dict[str, Any], cfg: Optional[AppConfig]) -> None:
    if not cfg:
        return
    if cfg.proxy_url and cfg.proxy_url.strip():
        opts["proxy"] = cfg.proxy_url.strip()

    if cfg.cookies_file_path and Path(cfg.cookies_file_path).is_file():
        opts["cookiefile"] = cfg.cookies_file_path
    elif cfg.cookies_browser and cfg.cookies_browser not in ("none", ""):
        opts["cookiesfrombrowser"] = (cfg.cookies_browser.strip().lower(),)

    # Wire js_runtime_enabled into yt-dlp's js_runtimes option (enabling deno, node, quickjs, bun)
    if cfg.js_runtime_enabled:
        opts["js_runtimes"] = detect_all_js_runtimes()
    else:
        opts["js_runtimes"] = {}


def _inspect_m3u8_manifest_fast(clean_url: str, referer_url: str = "", cfg: Optional[AppConfig] = None) -> AnalyzedMediaInfo:
    title_guess = Path(urlparse(clean_url).path).stem or "HLS_Live_Stream"
    if title_guess.lower() in ("index", "master", "playlist", "chunklist", "manifest", "video"):
        host = urlparse(referer_url or clean_url).netloc.replace("www.", "")
        title_guess = f"Stream_{host}_{int(time.time()) % 10000}"

    qualities: List[str] = []
    q_details: Dict[str, str] = {}
    manual_subs: List[SubtitleTrackInfo] = []
    headers = _build_stream_headers(clean_url, referer_url)
    proxies = {"http": cfg.proxy_url, "https": cfg.proxy_url} if (cfg and cfg.proxy_url) else None
    try:
        resp = requests.get(clean_url, timeout=7, headers=headers, proxies=proxies)
        if resp.status_code == 200 and "#EXTM3U" in resp.text:
            heights = set()
            for m in re.finditer(r"RESOLUTION=(\d+)x(\d+)", resp.text):
                h = int(m.group(2))
                heights.add(h)
            for h_val in sorted(heights, reverse=True):
                lbl = f"{h_val}p"
                if lbl not in qualities:
                    qualities.append(lbl)
                    q_details[lbl] = f"{lbl} HLS"
            for m_sub in re.finditer(r'#EXT-X-MEDIA:TYPE=SUBTITLES.*?LANGUAGE="([^"]+)".*?NAME="([^"]+)"', resp.text):
                lcode, m_name = m_sub.group(1), m_sub.group(2)
                disp = localized_lang_name(lcode) or m_name
                manual_subs.append(
                    SubtitleTrackInfo(
                        lang_code=lcode,
                        lang_name=disp,
                        is_auto_generated=False,
                    )
                )
    except Exception as exc:
        logger.debug("Direct m3u8 manifest probe skipped: %s", exc)

    if not qualities:
        qualities = ["1080p", "720p", "480p", "360p"]
    qualities.append("best")

    return AnalyzedMediaInfo(
        url=clean_url,
        webpage_url=clean_url,
        title=title_guess,
        channel_name=urlparse(referer_url or clean_url).netloc or "HLS / m3u8 Stream",
        video_id="",
        referer_url=referer_url or headers.get("Referer", ""),
        is_m3u8=True,
        available_qualities=qualities,
        quality_details=q_details,
        available_audio_qualities=[("192k", "192 kbps"), ("128k", "128 kbps")],
        manual_subtitles=manual_subs,
    )


def sniff_m3u8_from_webpage(page_url: str, custom_referer: str = "") -> Optional[str]:
    headers = _build_stream_headers(page_url, custom_referer)
    try:
        resp = requests.get(page_url, timeout=8, headers=headers)
        if resp.status_code == 200 and resp.text:
            text = resp.text.replace(r"\/", "/")
            matches = M3U8_SNIFF_RE.findall(text)
            if matches:
                return matches[0]
    except Exception as exc:
        logger.debug("Webpage m3u8 sniff failed: %s", exc)
    return None


def _parse_entries_from_info(info: Dict[str, Any]) -> List[Dict[str, object]]:
    entries_raw = info.get("entries") or []
    flattened_raw: List[Dict[str, Any]] = []

    for item in entries_raw:
        if not item or not isinstance(item, dict):
            continue
        if item.get("_type") in ("playlist", "multi_video") and item.get("entries"):
            for sub_item in item.get("entries") or []:
                if sub_item and isinstance(sub_item, dict):
                    flattened_raw.append(sub_item)
        else:
            flattened_raw.append(item)

    entries_list: List[Dict[str, object]] = []
    for ent in flattened_raw:
        ent_url = str(ent.get("url") or ent.get("webpage_url") or "")
        if ent.get("_type") == "url" and any(
            ent_url.rstrip("/").endswith(tab) for tab in ("/videos", "/shorts", "/streams")
        ):
            continue
        ent_id = str(ent.get("id") or extract_video_id_from_url(ent_url) or "")
        if ent_url and not ent_url.startswith("http"):
            ent_url = f"https://www.youtube.com/watch?v={ent_id or ent_url}"
        thumbs = ent.get("thumbnails") or []
        thumb_u = ent.get("thumbnail") or (thumbs[-1].get("url") if thumbs else "")
        entries_list.append(
            {
                "index": len(entries_list) + 1,
                "id": ent_id,
                "title": ent.get("title") or f"Video {len(entries_list) + 1}",
                "url": ent_url,
                "duration": int(ent.get("duration") or 0),
                "thumbnail": thumb_u,
                "channel": ent.get("uploader") or info.get("uploader") or "",
            }
        )
    return entries_list


def _extract_real_qualities_and_audio(
    sample_video_info: Dict[str, Any],
) -> Tuple[List[str], Dict[str, str], List[Tuple[str, str]], List[AudioTrackInfo]]:
    formats = sample_video_info.get("formats") or []
    duration = float(sample_video_info.get("duration") or 0)

    height_map: Dict[int, Dict[str, Any]] = {}
    best_audio_bytes = 0
    audio_abr_set = set()
    audio_langs_map: Dict[str, AudioTrackInfo] = {}

    for fmt in formats:
        vcodec = str(fmt.get("vcodec") or "none")
        acodec = str(fmt.get("acodec") or "none")
        h = fmt.get("height")
        fsize = int(fmt.get("filesize") or fmt.get("filesize_approx") or 0)
        tbr = float(fmt.get("tbr") or 0.0)
        if fsize <= 0 and tbr > 0 and duration > 0:
            fsize = int((tbr * 1000.0 / 8.0) * duration)

        if vcodec != "none" and isinstance(h, int) and h >= 120:
            matched_tier = h
            for tier_h, _, _ in STANDARD_VIDEO_TIERS:
                if abs(h - tier_h) <= 36:
                    matched_tier = tier_h
                    break
            prev = height_map.get(matched_tier)
            if not prev or fsize > prev.get("size", 0):
                height_map[matched_tier] = {
                    "size": fsize,
                    "fps": int(fmt.get("fps") or 0),
                }

        if acodec != "none" and (vcodec == "none" or not height_map):
            if fsize > best_audio_bytes:
                best_audio_bytes = min(fsize, 150 * 1024 * 1024)
            abr = float(fmt.get("abr") or fmt.get("tbr") or 0.0)
            if abr > 0:
                audio_abr_set.add(int(abr))

            lang_code = str(fmt.get("language") or "").strip()
            if lang_code and lang_code.lower() not in ("none", "und", "zxx"):
                base_l = lang_code.split("-")[0].lower()
                if base_l not in audio_langs_map:
                    disp_name = localized_lang_name(lang_code)
                    note = str(fmt.get("format_note") or "")
                    is_orig = "original" in note.lower() or "default" in note.lower()
                    if is_orig:
                        disp_name += tp(" (الصوت الأصلي)", " (Original)")
                    audio_langs_map[base_l] = AudioTrackInfo(
                        lang_code=base_l,
                        lang_name=disp_name,
                        is_default=is_orig,
                    )

    qualities: List[str] = []
    q_details: Dict[str, str] = {}

    for tier_h, q_key, q_title in STANDARD_VIDEO_TIERS:
        if tier_h in height_map:
            qualities.append(q_key)
            meta = height_map[tier_h]
            sz = meta.get("size", 0)
            if sz > 0 and best_audio_bytes > 0:
                sz += best_audio_bytes
            fps = meta.get("fps", 0)
            fps_tag = f" {fps}fps" if fps >= 50 else ""
            if sz > 1024 * 1024:
                mb = sz / (1024.0 * 1024.0)
                sz_str = f" (~{mb / 1024.0:.2f} GB)" if mb >= 1024 else f" (~{mb:.0f} MB)"
            else:
                sz_str = ""
            q_details[q_key] = f"{q_title}{fps_tag}{sz_str}"

    if not qualities:
        qualities = ["1080p", "720p", "480p", "360p", "240p", "144p"]
        for _, qk, qt in STANDARD_VIDEO_TIERS:
            if qk in qualities:
                q_details[qk] = qt

    qualities.append("best")
    q_details["best"] = tp("أعلى جودة متاحة تلقائياً (Max Quality)", "Best Available Quality (Auto Max)")

    audio_qualities: List[Tuple[str, str]] = [
        ("320k", tp("320 kbps — فائق النقاء (Studio)", "320 kbps — Studio Master")),
        ("256k", tp("256 kbps — عالي جداً (High)", "256 kbps — Very High")),
        ("192k", tp("192 kbps — قياسي ممتاز (Standard)", "192 kbps — Standard HD")),
        ("128k", tp("128 kbps — حجم متوازن (Medium)", "128 kbps — Balanced")),
        ("64k", tp("64 kbps — حجم صغير للمحاضرات (Compact)", "64 kbps — Compact Voice")),
    ]

    audio_tracks: List[AudioTrackInfo] = [
        AudioTrackInfo(
            lang_code="",
            lang_name=tp("الصوت الافتراضي للفيديو (Original Audio)", "Default Video Audio (Original)"),
            is_default=True,
        )
    ]
    for _lk, atrk in sorted(
        audio_langs_map.items(),
        key=lambda x: (0 if x[0] == "ar" else (1 if x[0] == "en" else 2), x[0]),
    ):
        audio_tracks.append(atrk)

    return qualities, q_details, audio_qualities, audio_tracks


def analyze_media_url(
    url: str,
    custom_referer: str = "",
    cfg: Optional[AppConfig] = None,
) -> AnalyzedMediaInfo:
    clean_url = normalize_channel_url(url.strip())

    if clean_url.lower().startswith("blob:"):
        inner_url = clean_url[5:].strip()
        parsed_inner = urlparse(inner_url)
        origin_domain = (
            f"{parsed_inner.scheme}://{parsed_inner.netloc}/"
            if parsed_inner.scheme and parsed_inner.netloc
            else "https://vfaststream.co/"
        )
        if UUID_PATH_RE.match(parsed_inner.path or ""):
            raise BlobUrlDetectedError(clean_url, origin_domain)
        clean_url = inner_url
        if not custom_referer:
            custom_referer = origin_domain

    if is_m3u8_url(clean_url):
        return _inspect_m3u8_manifest_fast(clean_url, referer_url=custom_referer, cfg=cfg)

    _ensure_external_ytdlp_loaded()
    import yt_dlp

    parsed = urlparse(clean_url)
    qs = parse_qs(parsed.query)
    has_video_id = "v" in qs or "youtu.be" in parsed.netloc
    list_id_val = qs.get("list", [""])[0]
    has_list_id = bool(list_id_val and not list_id_val.startswith("RD"))
    is_channel_url = any(seg in parsed.path for seg in ("/@", "/channel/", "/c/", "/user/"))

    base_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 14,
    }
    if custom_referer or not is_youtube_url(clean_url):
        base_opts["http_headers"] = _build_stream_headers(clean_url, custom_referer)

    _apply_network_and_auth_opts(base_opts, cfg)

    sample_video_info: Dict[str, Any] = {}
    playlist_info: Dict[str, Any] = {}
    entries_list: List[Dict[str, object]] = []

    try:
        if has_video_id and has_list_id and "v" in qs:
            vid_url = f"https://www.youtube.com/watch?v={qs['v'][0]}"
            pl_url = f"https://www.youtube.com/playlist?list={list_id_val}"

            def _fetch_single() -> Dict[str, Any]:
                opts = {**base_opts, "noplaylist": True}
                with yt_dlp.YoutubeDL(opts) as ydl_s:
                    return ydl_s.extract_info(vid_url, download=False) or {}

            def _fetch_playlist() -> Dict[str, Any]:
                opts = {**base_opts, "extract_flat": "in_playlist"}
                with yt_dlp.YoutubeDL(opts) as ydl_p:
                    return ydl_p.extract_info(pl_url, download=False) or {}

            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_s = pool.submit(_fetch_single)
                fut_p = pool.submit(_fetch_playlist)
                try:
                    sample_video_info = fut_s.result(timeout=22)
                except Exception as exc:
                    logger.warning("Single video probe failed: %s", exc)
                try:
                    playlist_info = fut_p.result(timeout=22)
                    entries_list = _parse_entries_from_info(playlist_info)
                except Exception as exc:
                    logger.debug("Playlist flat probe skipped: %s", exc)

            info = sample_video_info or playlist_info
        elif has_video_id and not has_list_id:
            single_opts = {**base_opts, "noplaylist": True}
            with yt_dlp.YoutubeDL(single_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False) or {}
            sample_video_info = info
        else:
            flat_opts = {**base_opts, "extract_flat": "in_playlist", "playlistend": 300}
            try:
                with yt_dlp.YoutubeDL(flat_opts) as ydl:
                    info = ydl.extract_info(clean_url, download=False) or {}
            except Exception as ydl_exc:
                sniffed_m3u8 = sniff_m3u8_from_webpage(clean_url, custom_referer=custom_referer or clean_url)
                if sniffed_m3u8:
                    return _inspect_m3u8_manifest_fast(sniffed_m3u8, referer_url=custom_referer or clean_url, cfg=cfg)
                raise ydl_exc

            info_type = info.get("_type", "video")
            if info_type in ("playlist", "multi_video"):
                playlist_info = info
                entries_list = _parse_entries_from_info(info)
                sample_video_info = info
                if entries_list:
                    first_url = str(entries_list[0].get("url") or "")
                    if first_url and first_url.startswith("http"):
                        try:
                            with yt_dlp.YoutubeDL({**base_opts, "noplaylist": True}) as ydl_single:
                                sample_video_info = ydl_single.extract_info(first_url, download=False) or info
                        except Exception:
                            sample_video_info = info
            else:
                sample_video_info = info
    except Exception as exc:
        raise RuntimeError(translate_download_error(str(exc))) from exc

    if not info and not sample_video_info:
        raise ValueError(tp("تعذّر استخراج بيانات الفيديو من هذا الرابط", "Could not extract media information from link."))

    qualities, q_details, audio_quals, audio_tracks = _extract_real_qualities_and_audio(sample_video_info)

    manual_subs: List[SubtitleTrackInfo] = []
    seen_manual = set()
    for lcode, _track_list in (sample_video_info.get("subtitles") or {}).items():
        if lcode == "live_chat":
            continue
        base_c = lcode.split("-")[0].lower()
        if base_c in seen_manual:
            continue
        seen_manual.add(base_c)
        lname = localized_lang_name(lcode)
        manual_subs.append(SubtitleTrackInfo(lang_code=lcode, lang_name=lname, is_auto_generated=False))

    auto_subs: List[SubtitleTrackInfo] = []
    seen_auto = set()
    orig_lang = str(sample_video_info.get("language") or "en").split("-")[0].lower()
    auto_dict = sample_video_info.get("automatic_captions") or {}
    for lcode in auto_dict.keys():
        if lcode == "live_chat":
            continue
        base_c = lcode.split("-")[0].lower()
        if base_c in seen_auto:
            continue
        if "orig" in lcode.lower() or base_c in (orig_lang, "en", "ar", "fr", "es", "de", "tr", "ru"):
            seen_auto.add(base_c)
            lname = localized_lang_name(base_c)
            auto_subs.append(SubtitleTrackInfo(lang_code=lcode, lang_name=lname, is_auto_generated=True))

    def _sub_sort_key(s: SubtitleTrackInfo) -> tuple:
        if "orig" in s.lang_code.lower():
            return (0, s.lang_code)
        if s.lang_code.startswith("ar"):
            return (1, s.lang_code)
        if s.lang_code.startswith("en"):
            return (2, s.lang_code)
        return (3, s.lang_code)

    manual_subs.sort(key=_sub_sort_key)
    auto_subs.sort(key=_sub_sort_key)

    channel_url = (
        sample_video_info.get("channel_url")
        or sample_video_info.get("uploader_url")
        or info.get("channel_url")
        or ""
    )
    playlist_title = (
        playlist_info.get("title")
        or (info.get("title") if info.get("_type") in ("playlist", "multi_video") else "")
        or ""
    )
    playlist_id = (
        playlist_info.get("id")
        or (info.get("id") if info.get("_type") in ("playlist", "multi_video") else "")
        or (list_id_val if has_list_id else "")
    )
    resolved_video_id = str(
        sample_video_info.get("id")
        or (info.get("id") if info.get("_type") not in ("playlist", "multi_video") else "")
        or extract_video_id_from_url(clean_url)
    )

    is_real_playlist = bool(
        (len(entries_list) > 1 or has_list_id or info.get("_type") == "playlist") and not is_channel_url
    )

    return AnalyzedMediaInfo(
        url=clean_url,
        webpage_url=sample_video_info.get("webpage_url") or clean_url,
        title=sample_video_info.get("title") or info.get("title") or "Untitled Media",
        channel_name=sample_video_info.get("uploader") or info.get("uploader") or "Unknown Channel",
        video_id=resolved_video_id,
        duration_sec=int(sample_video_info.get("duration") or 0),
        thumbnail_url=sample_video_info.get("thumbnail") or info.get("thumbnail") or "",
        referer_url=custom_referer,
        is_playlist=is_real_playlist,
        is_channel=is_channel_url,
        is_m3u8=False,
        playlist_title=playlist_title,
        playlist_id=playlist_id,
        channel_id=sample_video_info.get("channel_id") or info.get("channel_id") or "",
        channel_url=channel_url,
        entries=entries_list,
        available_qualities=qualities,
        quality_details=q_details,
        available_audio_qualities=audio_quals,
        available_audio_tracks=audio_tracks,
        manual_subtitles=manual_subs,
        auto_subtitles=auto_subs,
    )


def _find_downloaded_files_safe(target_dir: Path, file_stem: str) -> Tuple[List[Path], List[Path]]:
    media_files: List[Path] = []
    sub_files: List[Path] = []
    sub_exts = (".srt", ".vtt", ".json3", ".ttml", ".srv3", ".ass")
    temp_exts = (".part", ".ytdl", ".temp", ".webp", ".jpg", ".png")

    if not target_dir.exists():
        return media_files, sub_files

    for f in target_dir.iterdir():
        if not f.is_file():
            continue
        if f.stem == file_stem or f.name.startswith(f"{file_stem}."):
            sfx = f.suffix.lower()
            if sfx in sub_exts:
                sub_files.append(f)
            elif sfx not in temp_exts and not re.search(r"\.f\d+$", f.stem.lower()):
                media_files.append(f)
    return media_files, sub_files


def _append_tlang_to_url(sub_url: str, target_lang: str) -> str:
    parsed = urlparse(sub_url)
    if "youtube.com/api/timedtext" not in f"{parsed.netloc}{parsed.path}":
        return sub_url
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["tlang"] = [target_lang.split("-")[0]]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def _direct_fetch_subtitle_from_info(
    info: Dict[str, Any],
    preferred_lang: str,
    translate_to: str,
    target_dir: Path,
    file_stem: str,
    headers: Dict[str, str],
) -> Tuple[Optional[Path], bool]:
    if not info:
        return None, False

    sub_dicts = [
        info.get("requested_subtitles") or {},
        info.get("subtitles") or {},
        info.get("automatic_captions") or {},
    ]
    base_pref = (preferred_lang or "en").split("-")[0].lower()

    selected_tracks = None
    matched_lang = preferred_lang or "en"

    for candidate_prefix in (preferred_lang.lower(), base_pref, "en-orig", "en"):
        for sdict in sub_dicts:
            for k, val in sdict.items():
                if k.lower() == candidate_prefix or k.lower().startswith(f"{candidate_prefix}-"):
                    selected_tracks = val
                    matched_lang = k
                    break
            if selected_tracks:
                break
        if selected_tracks:
            break

    if not selected_tracks:
        return None, False

    track_list = [selected_tracks] if isinstance(selected_tracks, dict) else list(selected_tracks)
    ext_priority = {"vtt": 0, "srt": 1, "json3": 2}
    track_list.sort(key=lambda t: ext_priority.get(str(t.get("ext", "")).lower(), 99))

    for trk in track_list:
        sub_url = str(trk.get("url") or "")
        ext = str(trk.get("ext") or "vtt").lower()
        if not sub_url:
            continue

        do_tr = bool(translate_to and translate_to.split("-")[0].lower() != matched_lang.split("-")[0].lower())
        if do_tr and "youtube.com/api/timedtext" in sub_url:
            tlang_url = _append_tlang_to_url(sub_url, translate_to)
            try:
                resp_tr = requests.get(tlang_url, headers=headers, timeout=12)
                if resp_tr.status_code == 200 and len(resp_tr.text.strip()) > 40:
                    save_ext = "srt" if ext == "srt" else ("json3" if ext == "json3" else "vtt")
                    out_p = target_dir / f"{file_stem}.{translate_to}.{save_ext}"
                    out_p.write_text(resp_tr.text, encoding="utf-8")
                    return out_p, True
            except Exception as exc:
                logger.debug("YouTube tlang neural fetch skipped: %s", exc)

        try:
            resp = requests.get(sub_url, headers=headers, timeout=12)
            if resp.status_code == 200 and resp.text.strip():
                save_ext = "srt" if ext == "srt" else ("json3" if ext == "json3" else "vtt")
                out_p = target_dir / f"{file_stem}.{matched_lang}.{save_ext}"
                out_p.write_text(resp.text, encoding="utf-8")
                return out_p, False
        except Exception as exc:
            logger.debug("Direct subtitle track fetch failed: %s", exc)

    return None, False


def _is_in_download_archive(archive_file: Path, info: Dict[str, Any], fallback_vid: str = "") -> bool:
    """Checks if a video's extractor+ID key is recorded in `download_archive.txt`."""
    if not archive_file.is_file():
        return False
    vid = str(info.get("id") or fallback_vid or "").strip()
    if not vid:
        return False
    try:
        content = archive_file.read_text(encoding="utf-8", errors="ignore")
        return any(line.strip().endswith(f" {vid}") or line.strip() == vid for line in content.splitlines())
    except Exception:
        return False


def execute_download_task(
    task: DownloadTaskItem,
    base_download_dir: str,
    create_playlist_subfolder: bool,
    ffmpeg_custom_path: str,
    speed_limit_kbps: int,
    on_progress: Callable[[Dict[str, Any]], None],
    check_state: Callable[[], str],
    cfg: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    _ensure_external_ytdlp_loaded()
    import yt_dlp

    init_cmd = check_state()
    if init_cmd == "pause":
        raise PauseRequestedError("Task paused before start")
    if init_cmd == "cancel":
        raise CancelRequestedError("Task canceled before start")

    target_dir = Path(base_download_dir)
    if create_playlist_subfolder and task.group_type in ("playlist", "channel") and task.group_title:
        target_dir = target_dir / sanitize_filename(task.group_title, max_len=65)
    target_dir.mkdir(parents=True, exist_ok=True)

    ok_space, _free_b = check_disk_space_available(target_dir, min_free_bytes=100 * 1024 * 1024)
    if not ok_space:
        raise RuntimeError(
            tp(
                "مساحة القرص الصلب غير كافية في مجلد الحفظ (أقل من 100 ميجابايت متاحة)",
                "Insufficient disk space in download folder (< 100 MB free)",
            )
        )

    tmpl = cfg.filename_template if cfg else "{prefix}{title}"
    # Use the real video ID (from task.video_id or URL), NEVER the internal task_id!
    real_vid = (task.video_id or extract_video_id_from_url(task.url) or "").strip()
    if "{id}" in tmpl and not real_vid and not is_m3u8_url(task.url):
        try:
            probe_opts: Dict[str, Any] = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
            _apply_network_and_auth_opts(probe_opts, cfg)
            with yt_dlp.YoutubeDL(probe_opts) as ydl_id:
                p_info = ydl_id.extract_info(task.url, download=False) or {}
                real_vid = str(p_info.get("id") or "").strip()
                if real_vid:
                    task.video_id = real_vid
        except Exception:
            pass

    file_stem = build_safe_output_stem(
        target_dir=target_dir,
        prefix=task.smart_prefix,
        title=task.title,
        template=tmpl,
        channel=task.channel_name,
        video_id=real_vid,
    )
    outtmpl = str(target_dir / f"{file_stem}.%(ext)s")

    ff_loc = find_ffmpeg_path(ffmpeg_custom_path)
    has_ffmpeg = bool(ff_loc)

    aud_lang = (task.audio_lang or "").strip().lower()
    aud_selector = f"bestaudio[language^={aud_lang}]/bestaudio" if aud_lang else "bestaudio"

    if task.media_mode == "subtitles_only":
        fmt_str = "best"
    elif task.media_mode == "audio" or task.quality == "audio_only" or task.quality.endswith("k"):
        fmt_str = f"{aud_selector}/best"
    elif task.media_mode == "m3u8" or task.group_type == "m3u8":
        if task.quality.endswith("p") and task.quality[:-1].isdigit():
            h_num = int(task.quality[:-1])
            fmt_str = f"best[height<={h_num}]/best"
        else:
            fmt_str = "best"
    else:
        height_num = 1080
        if task.quality.endswith("p") and task.quality[:-1].isdigit():
            height_num = int(task.quality[:-1])
        if task.quality == "best":
            fmt_str = f"bestvideo+{aud_selector}/best" if has_ffmpeg else "best"
        else:
            fmt_str = (
                f"bestvideo[height<={height_num}]+{aud_selector}/best[height<={height_num}]/bestvideo+{aud_selector}/best"
                if has_ffmpeg
                else f"best[height<={height_num}]/best"
            )

    last_emit = [0.0]
    postprocessed_files: List[str] = []
    did_download_hooks = [False]

    def _hook(d: Dict[str, Any]) -> None:
        cmd = check_state()
        if cmd == "pause":
            raise PauseRequestedError("Task paused by user")
        if cmd == "cancel":
            raise CancelRequestedError("Task canceled by user")

        st = d.get("status")
        info_d = d.get("info_dict") or {}
        vcodec = str(info_d.get("vcodec") or "none")
        acodec = str(info_d.get("acodec") or "none")

        phase_lbl = ""
        if task.media_mode == "video" and has_ffmpeg:
            if vcodec != "none" and acodec == "none":
                phase_lbl = tp("1/2 الفيديو", "1/2 Video")
            elif vcodec == "none" and acodec != "none":
                phase_lbl = tp("2/2 الصوت", "2/2 Audio")

        if st == "downloading":
            did_download_hooks[0] = True
            now = time.monotonic()
            if now - last_emit[0] < 0.075:
                return
            last_emit[0] = now

            total_b = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            down_b = d.get("downloaded_bytes") or 0
            pct = (down_b / float(total_b) * 100.0) if total_b > 0 else 0.0
            if pct == 0.0 and d.get("fragment_index") and d.get("fragment_count"):
                pct = (d["fragment_index"] / float(d["fragment_count"])) * 100.0
            spd = re.sub(r"\x1b\[[0-9;]*m", "", d.get("_speed_str", "")).strip()
            eta = re.sub(r"\x1b\[[0-9;]*m", "", d.get("_eta_str", "")).strip()
            on_progress(
                {
                    "status": "downloading",
                    "stream_phase": phase_lbl,
                    "progress": min(99.2, max(0.0, pct)),
                    "speed_str": spd,
                    "eta_str": eta,
                    "downloaded_bytes": int(down_b),
                    "total_bytes": int(total_b),
                }
            )
        elif st == "finished":
            did_download_hooks[0] = True
            fn_done = d.get("filename") or info_d.get("filepath") or ""
            if fn_done:
                postprocessed_files.append(str(fn_done))
            on_progress(
                {
                    "status": "downloading",
                    "stream_phase": phase_lbl,
                    "progress": 99.2,
                    "speed_str": "",
                    "eta_str": "",
                }
            )

    def _pp_hook(d: Dict[str, Any]) -> None:
        cmd = check_state()
        if cmd == "pause":
            raise PauseRequestedError("Task paused during post-processing")
        if cmd == "cancel":
            raise CancelRequestedError("Task canceled during post-processing")

        pp_status = d.get("status")
        info_d = d.get("info_dict") or {}
        if pp_status == "started":
            on_progress(
                {
                    "status": "merging",
                    "stream_phase": "",
                    "progress": 99.5,
                    "speed_str": "",
                    "eta_str": "",
                }
            )
        elif pp_status == "finished":
            fp = info_d.get("filepath") or info_d.get("_filename")
            if fp:
                postprocessed_files.append(str(fp))

    stream_headers = _build_stream_headers(task.url, task.referer_url)
    is_sub_only = task.media_mode == "subtitles_only"

    ydl_opts: Dict[str, Any] = {
        "format": fmt_str,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "continuedl": True,
        "skip_download": is_sub_only,
        "quiet": True,
        "no_warnings": True,
        "nocolor": True,
        "progress_hooks": [_hook],
        "postprocessor_hooks": [_pp_hook],
        "concurrent_fragment_downloads": 6,
    }

    if task.referer_url or not is_youtube_url(task.url):
        ydl_opts["http_headers"] = stream_headers

    _apply_network_and_auth_opts(ydl_opts, cfg)

    if ff_loc:
        ydl_opts["ffmpeg_location"] = ff_loc

    if speed_limit_kbps and speed_limit_kbps > 0:
        ydl_opts["ratelimit"] = speed_limit_kbps * 1024

    archive_file = download_archive_path()
    use_archive = bool(cfg and cfg.use_download_archive and not is_sub_only)
    was_in_archive_before = _is_in_download_archive(archive_file, {}, real_vid) if (use_archive and real_vid) else False
    if use_archive:
        ydl_opts["download_archive"] = str(archive_file)

    postprocessors: List[Dict[str, Any]] = []
    if not is_sub_only:
        if task.media_mode == "audio" or task.quality == "audio_only" or task.quality.endswith("k"):
            if has_ffmpeg:
                bitrate_num = "192"
                if task.quality.endswith("k") and task.quality[:-1].isdigit():
                    bitrate_num = task.quality[:-1]
                target_acodec = task.container if task.container in ("mp3", "m4a", "flac", "wav", "ogg") else "mp3"
                postprocessors.append(
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": target_acodec,
                        "preferredquality": bitrate_num,
                    }
                )
                if cfg and cfg.embed_metadata:
                    postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
                if cfg and cfg.embed_thumbnail and target_acodec in ("mp3", "m4a", "flac"):
                    ydl_opts["writethumbnail"] = True
                    postprocessors.append({"key": "EmbedThumbnail"})
        else:
            if has_ffmpeg and task.container in ("mp4", "mkv", "webm"):
                ydl_opts["merge_output_format"] = task.container
            if has_ffmpeg and cfg:
                if cfg.embed_metadata or cfg.embed_chapters:
                    postprocessors.append(
                        {
                            "key": "FFmpegMetadata",
                            "add_metadata": bool(cfg.embed_metadata),
                            "add_chapters": bool(cfg.embed_chapters),
                        }
                    )
                if cfg.embed_thumbnail and task.container in ("mp4", "mkv"):
                    ydl_opts["writethumbnail"] = True
                    postprocessors.append({"key": "EmbedThumbnail"})

    if postprocessors:
        ydl_opts["postprocessors"] = postprocessors

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(task.url, download=not is_sub_only) or {}
            prepared_file = ydl.prepare_filename(info) if not is_sub_only else ""

        if not task.video_id and info.get("id"):
            task.video_id = str(info.get("id"))

        post_cmd = check_state()
        if post_cmd == "pause":
            raise PauseRequestedError("Task paused after stream extraction")
        if post_cmd == "cancel":
            raise CancelRequestedError("Task canceled after stream extraction")

        final_path: Optional[Path] = None
        skipped_archive = False
        if not is_sub_only:
            req_dls = info.get("requested_downloads") or []
            if isinstance(req_dls, list) and req_dls:
                fp_cand = req_dls[0].get("filepath") or req_dls[0].get("_filename")
                if fp_cand and Path(fp_cand).exists():
                    final_path = Path(fp_cand)

            if final_path is None:
                for pp_fp in reversed(postprocessed_files):
                    p_obj = Path(pp_fp)
                    if p_obj.exists() and not p_obj.name.endswith((".part", ".ytdl", ".webp")):
                        final_path = p_obj
                        break

            media_candidates, sub_candidates = _find_downloaded_files_safe(target_dir, file_stem)
            if final_path is None:
                if prepared_file and Path(prepared_file).exists():
                    final_path = Path(prepared_file)
                elif media_candidates:
                    final_path = media_candidates[0]
                elif use_archive and not did_download_hooks[0] and (
                    was_in_archive_before or _is_in_download_archive(archive_file, info, real_vid)
                ):
                    skipped_archive = True
                    final_path = media_candidates[0] if media_candidates else target_dir
                else:
                    final_path = Path(prepared_file) if prepared_file else Path()
        else:
            _, sub_candidates = _find_downloaded_files_safe(target_dir, file_stem)

        final_sub_str = ""
        warning_msg = ""
        if skipped_archive:
            warning_msg = tp(
                "تم التخطي — هذا الفيديو محمّل مسبقاً ومسجّل في سجل الأرشيف",
                "Skipped — video was already downloaded (recorded in archive)",
            )

        if (task.sub_enabled or is_sub_only) and not skipped_archive:
            on_progress({"status": "translating_sub", "stream_phase": "", "progress": 96.0})
            src_lang = task.sub_source_lang or (cfg.fallback_source_lang if cfg else "en") or "en"
            tgt_lang = task.sub_translate_to or src_lang

            fetched_sub, already_tr = _direct_fetch_subtitle_from_info(
                info=info,
                preferred_lang=src_lang,
                translate_to=task.sub_translate_to,
                target_dir=target_dir,
                file_stem=file_stem,
                headers=stream_headers,
            )
            if fetched_sub:
                sub_candidates = [fetched_sub]

            if sub_candidates:
                raw_sub = sub_candidates[0]
                do_tr = (not already_tr) and bool(
                    task.sub_translate_to and task.sub_translate_to.split("-")[0].lower() != src_lang.split("-")[0].lower()
                )
                try:
                    synced_srt, tot_cues, failed_cues = process_and_sync_subtitle(
                        raw_sub_path=raw_sub,
                        source_lang=tgt_lang if already_tr else src_lang,
                        target_lang=tgt_lang,
                        do_translate=do_tr,
                        enforce_bidi=task.sub_bidi_fix,
                        is_auto_generated=task.sub_is_auto,
                        tv_safe_bidi=cfg.tv_safe_bidi if cfg else True,
                        state_check=check_state,
                    )
                except SubtitlePauseRequested as sp_exc:
                    raise PauseRequestedError(str(sp_exc)) from sp_exc
                except SubtitleCancelRequested as sc_exc:
                    raise CancelRequestedError(str(sc_exc)) from sc_exc

                final_sub_str = str(synced_srt)
                if failed_cues > 0:
                    warning_msg = tp(
                        f"تنبيه: تعذّرت ترجمة {failed_cues} من أصل {tot_cues} جملة وتم الإبقاء على نصها الأصلي",
                        f"Warning: {failed_cues} of {tot_cues} subtitle cues could not be translated",
                    )

                for sc in sub_candidates:
                    if sc.exists() and sc.resolve() != synced_srt.resolve():
                        try:
                            sc.unlink()
                        except OSError:
                            pass

                if (
                    not is_sub_only
                    and cfg
                    and cfg.embed_subtitles_in_video
                    and has_ffmpeg
                    and final_path
                    and final_path.is_file()
                    and final_path.suffix.lower() in (".mp4", ".mkv")
                ):
                    try:
                        embedded_tmp = final_path.with_name(f"{final_path.stem}.embedded{final_path.suffix}")
                        sub_codec = "mov_text" if final_path.suffix.lower() == ".mp4" else "srt"
                        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                        file_mb = max(1.0, final_path.stat().st_size / (1024.0 * 1024.0))
                        mux_timeout = max(180, min(1800, int(120 + file_mb * 0.5)))
                        lang_iso = (tgt_lang or "ara")[:3].lower()
                        cmd_emb = [
                            ff_loc or "ffmpeg",
                            "-y",
                            "-i",
                            str(final_path),
                            "-i",
                            str(synced_srt),
                            "-map",
                            "0",
                            "-map",
                            "1:0",
                            "-c",
                            "copy",
                            "-c:s",
                            sub_codec,
                            f"-metadata:s:s:0",
                            f"language={lang_iso}",
                            str(embedded_tmp),
                        ]
                        res_emb = subprocess.run(
                            cmd_emb,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=mux_timeout,
                            creationflags=creationflags,
                        )
                        if res_emb.returncode == 0 and embedded_tmp.exists() and embedded_tmp.stat().st_size > 1000:
                            embedded_tmp.replace(final_path)
                        else:
                            embedded_tmp.unlink(missing_ok=True)
                            err_tail = (res_emb.stderr or b"").decode("utf-8", errors="ignore")[-120:].strip()
                            logger.warning("Subtitle muxing returned %s: %s", res_emb.returncode, err_tail)
                            mux_note = tp(
                                "تعذّر دمج الترجمة داخل الفيديو (ملف .srt الخارجي محفوظ وجاهز)",
                                "Could not mux subtitle inside video (external .srt file saved)",
                            )
                            warning_msg = f"{warning_msg} · {mux_note}" if warning_msg else mux_note
                    except Exception as emb_exc:
                        logger.warning("Optional subtitle muxing failed: %s", emb_exc)
                        mux_note = tp(
                            "تعذّر دمج الترجمة داخل الفيديو (ملف .srt الخارجي محفوظ وجاهز)",
                            "Could not mux subtitle inside video (external .srt file saved)",
                        )
                        warning_msg = f"{warning_msg} · {mux_note}" if warning_msg else mux_note
            elif is_sub_only:
                raise ValueError(
                    tp("لا توجد ملفات ترجمة متاحة في هذا الفيديو لتحميلها", "No subtitle tracks found on this video to download.")
                )

        return {
            "output_path": final_sub_str if is_sub_only else (str(final_path) if final_path else ""),
            "subtitle_path": final_sub_str,
            "warning_message": warning_msg,
            "skipped_archive": skipped_archive,
            "video_id": str(info.get("id") or real_vid),
        }

    except CancelRequestedError:
        cleanup_task_temp_files(target_dir, file_stem)
        raise
    except PauseRequestedError:
        raise
    except Exception as exc:
        raise RuntimeError(translate_download_error(str(exc))) from exc


def collect_diagnostics_report(cfg: Optional[AppConfig] = None) -> str:
    """
    Generates a clean, privacy-safe technical diagnostic summary for support & troubleshooting:
    Includes App version, OS/Arch, Python/Qt version, yt-dlp & yt-dlp-ejs versions, FFmpeg status,
    detected JS runtimes, active non-sensitive configuration, and the last 20 log lines.
    """
    try:
        import PySide6
        qt_ver = getattr(PySide6, "__version__", "unknown")
    except Exception:
        qt_ver = "unknown"

    ff_p = verify_ffmpeg_working(cfg.ffmpeg_custom_path if cfg else "")
    js_rts = detect_all_js_runtimes()
    js_str = ", ".join(f"{k} ({v.get('path') or 'auto'})" for k, v in js_rts.items())
    ejs_ok = is_ytdlp_ejs_installed()

    lines = [
        f"=== V-Stream Downloader Pro v{APP_VERSION} — Diagnostics ===",
        f"OS / Platform     : {platform.system()} {platform.release()} ({platform.machine()})",
        f"Python / PySide6  : Python {platform.python_version()} | PySide6 {qt_ver} | Frozen={is_frozen()}",
        f"yt-dlp Engine     : v{get_ytdlp_version()} | yt-dlp-ejs={'Installed' if ejs_ok else 'Missing'}",
        f"FFmpeg Engine     : {'Ready (' + ff_p + ')' if ff_p else 'Not Found'}",
        f"JS Runtimes       : {js_str} (Enabled={cfg.js_runtime_enabled if cfg else True})",
    ]
    if cfg:
        lines.append(
            f"Config Summary    : lang={cfg.language}, quality={cfg.preferred_quality}, "
            f"template={cfg.filename_template}, cookies={cfg.cookies_browser}, "
            f"proxy={'set' if cfg.proxy_url else 'none'}, archive={cfg.use_download_archive}"
        )

    log_file = logs_dir() / "v_stream.log"
    if log_file.is_file():
        try:
            tail = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:]
            if tail:
                lines.append("\n--- Recent Log Tail (last 20 lines) ---")
                lines.extend(tail)
        except Exception:
            pass
    return "\n".join(lines)
