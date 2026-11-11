import importlib
import os
import pkgutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENGINE_CONTENTS_DIR = "V-Stream-Engine"

# Excluded heavy GUI/test/Unix-only stdlib modules that are never needed at runtime
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


def discover_all_hidden_imports() -> list[str]:
    """
    Dynamically discovers every cross-platform Python Standard Library module and submodule
    on the build machine (via `sys.stdlib_module_names` and `pkgutil.walk_packages`), plus
    core third-party modules so that the frozen `.exe` never misses any stdlib module
    (such as `getpass`, `optparse`, `html.parser`, `xml.etree`, `http.cookiejar`, `sqlite3`, etc.).
    """
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

    # Add all top-level stdlib modules from Python 3.10+ sys.stdlib_module_names
    for mod_name in getattr(sys, "stdlib_module_names", ()):
        if not mod_name.startswith(EXCLUDED_STDLIB_PREFIXES):
            modules.add(mod_name)

    # Walk all submodules inside multi-file stdlib packages (html.*, xml.*, urllib.*, http.*, email.*, etc.)
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
    """
    Builds a standalone, fast-starting, antivirus-friendly `--onedir` distribution
    that runs completely independently on Windows/Linux machines without Python installed.
    Renames PyInstaller's default `_internal` directory to `V-Stream-Engine`.
    """
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

    # Collect installed third-party packages completely (code, submodules, and data files)
    for pkg in COLLECT_ALL_PACKAGES:
        try:
            if importlib.util.find_spec(pkg) is not None:
                cmd.extend(["--collect-all", pkg])
        except Exception:
            pass

    # Bundle all standard library modules & submodules
    hidden_imports = discover_all_hidden_imports()
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # Explicitly exclude unwanted heavy test/GUI modules
    for exc_mod in ("tkinter", "turtledemo", "turtle", "idlelib", "test", "lib2to3", "ensurepip", "venv"):
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
