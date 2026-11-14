import importlib
import importlib.util
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE_CONTENTS_DIR = "V-Stream-Engine"

REQUIRED_BUILD_IMPORTS = (
    ("PySide6", "PySide6>=6.6.0"),
    ("yt_dlp", "yt-dlp[default]>=2025.11.12"),
    ("yt_dlp_ejs", "yt-dlp-ejs>=0.3.0"),
    ("requests", "requests>=2.31.0"),
    ("urllib3", "urllib3>=2.0.0"),
    ("certifi", "certifi>=2024.2.2"),
    ("charset_normalizer", "charset-normalizer>=3.3.0"),
    ("idna", "idna>=3.6"),
    ("socks", "PySocks>=1.7.1"),
    ("mutagen", "mutagen>=1.47.0"),
    ("brotli", "brotli>=1.1.0"),
    ("websockets", "websockets>=12.0"),
    ("PyInstaller", "pyinstaller>=6.3.0"),
)

EXCLUDED_STDLIB_PREFIXES = (
    "_",
    "antigravity",
    "this",
    "tkinter",
    "turtledemo",
    "turtle",
    "idlelib",
    "test",
    "lib2to3",
    "ensurepip",
    "venv",
    "distutils",
    "curses",
    "dbm",
    "nis",
    "ossaudiodev",
    "pty",
    "pwd",
    "grp",
    "resource",
    "spwd",
    "syslog",
    "termios",
    "tty",
    "fcntl",
    "posix",
    "crypt",
)

STDLIB_MULTI_PACKAGES = (
    "html",
    "xml",
    "urllib",
    "http",
    "email",
    "concurrent",
    "ctypes",
    "importlib",
    "logging",
    "asyncio",
    "wsgiref",
    "xmlrpc",
    "zoneinfo",
    "multiprocessing",
    "collections",
    "unittest",
    "encodings",
)

COLLECT_ALL_PACKAGES = (
    "yt_dlp",
    "yt_dlp_ejs",
    "certifi",
    "requests",
    "urllib3",
    "idna",
    "charset_normalizer",
    "websockets",
    "mutagen",
    "brotli",
)


def ensure_build_dependencies_installed() -> None:
    """
    Automatically checks if all required packages (including `yt-dlp[default]`, `yt-dlp-ejs`,
    `mutagen`, `brotli`, `websockets`, `PySocks`, `certifi`, `PySide6`, `PyInstaller`) are
    installed in the active Python environment. If any package is missing, installs
    `requirements.txt` automatically so no manual `pip install` command is ever required.
    """
    missing_specs: list[str] = []
    for mod_name, pip_spec in REQUIRED_BUILD_IMPORTS:
        if importlib.util.find_spec(mod_name) is None:
            missing_specs.append(pip_spec)

    if not missing_specs:
        return

    print(f"[*] Installing missing build dependencies automatically: {', '.join(missing_specs)} ...")
    req_file = ROOT / "requirements.txt"
    if req_file.exists():
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "-r", str(req_file)])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", *missing_specs])
    importlib.invalidate_caches()


def discover_all_hidden_imports() -> list[str]:
    modules: set[str] = {
        "app.stdlib_preload",
        "_markupbase",
        "_strptime",
        "_compression",
        "_compat_pickle",
        "_pydecimal",
        "_pyio",
        "_sitebuiltins",
        "_threading_local",
        "_weakrefset",
        "_elementtree",
        "_sqlite3",
        "_ctypes",
        "_lzma",
        "_bz2",
        "_hashlib",
        "_ssl",
        "_socket",
        "_asyncio",
        "_multiprocessing",
        "_queue",
        "_uuid",
        "_zoneinfo",
        "_csv",
        "_json",
        "_decimal",
        "_datetime",
        "_overlapped",
        "_winapi",
        "optparse",
        "getpass",
        "html",
        "html.parser",
        "html.entities",
        "xml.etree.ElementTree",
        "xml.dom.minidom",
        "xml.sax",
        "http.client",
        "http.cookiejar",
        "http.cookies",
        "http.server",
        "urllib.parse",
        "urllib.request",
        "urllib.error",
        "urllib.robotparser",
        "email.message",
        "email.utils",
        "email.header",
        "netrc",
        "plistlib",
        "sqlite3",
        "ctypes",
        "ctypes.wintypes",
        "ctypes.util",
        "secrets",
        "shlex",
        "uuid",
        "hmac",
        "hashlib",
        "zlib",
        "gzip",
        "bz2",
        "lzma",
        "zipfile",
        "tarfile",
        "csv",
        "configparser",
        "decimal",
        "fractions",
        "numbers",
        "statistics",
        "ipaddress",
        "mimetypes",
        "calendar",
        "bisect",
        "difflib",
        "unicodedata",
        "stringprep",
        "socketserver",
        "ftplib",
        "poplib",
        "imaplib",
        "smtplib",
        "xmlrpc.client",
        "wsgiref.simple_server",
        "socks",
        "brotli",
        "certifi",
        "mutagen",
        "websockets",
        "yt_dlp",
        "yt_dlp.version",
        "yt_dlp.options",
        "yt_dlp.utils",
        "yt_dlp.cookies",
        "yt_dlp.aes",
        "yt_dlp.networking",
        "yt_dlp.downloader",
        "yt_dlp.postprocessor",
        "yt_dlp.extractor",
        "yt_dlp_ejs",
    }

    for mod_name in getattr(sys, "stdlib_module_names", ()):
        if not mod_name.startswith(EXCLUDED_STDLIB_PREFIXES):
            modules.add(mod_name)

    for pkg_name in STDLIB_MULTI_PACKAGES:
        try:
            pkg = importlib.import_module(pkg_name)
            if hasattr(pkg, "__path__"):
                for info in pkgutil.walk_packages(pkg.__path__, pkg_name + "."):
                    if not any(part.startswith("_") for part in info.name.split(".")):
                        modules.add(info.name)
        except Exception:
            pass

    return sorted(modules)


def build() -> None:
    ensure_build_dependencies_installed()

    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/IM", "V-Stream-Downloader.exe"], capture_output=True)

    ico_path = ROOT / "assets" / "icon.ico"
    try:
        from tools.make_icon import generate_icons
        ico_path = generate_icons()
    except Exception:
        pass

    assets_dir = ROOT / "assets"
    sep = ";" if os.name == "nt" else ":"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--contents-directory",
        ENGINE_CONTENTS_DIR,
        "--name",
        "V-Stream-Downloader",
        "--icon",
        str(ico_path),
        "--add-data",
        f"{assets_dir}{sep}assets",
    ]

    for pkg in COLLECT_ALL_PACKAGES:
        try:
            if importlib.util.find_spec(pkg) is not None:
                cmd.extend(["--collect-all", pkg])
        except Exception:
            pass

    hidden_imports = discover_all_hidden_imports()
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    for exc_mod in (
        "tkinter",
        "turtledemo",
        "turtle",
        "idlelib",
        "test",
        "lib2to3",
        "ensurepip",
        "venv",
        "urllib3.contrib.emscripten",
    ):
        cmd.extend(["--exclude-module", exc_mod])

    cmd.append(str(ROOT / "main.py"))

    print(
        f"Building standalone V-Stream-Downloader distribution "
        f"(runtime folder: {ENGINE_CONTENTS_DIR}, bundled stdlib modules: {len(hidden_imports)})..."
    )
    subprocess.check_call(cmd)
    print("\nBuild Complete! Distribution folder is in: dist/V-Stream-Downloader/")


if __name__ == "__main__":
    build()
