import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

APP_SLUG = "VStreamDownloader"
STARTUP_REG_NAME = "VStreamDownloaderPro"
ENGINE_CONTENTS_DIR = "V-Stream-Engine"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        exe_parent = Path(sys.executable).resolve().parent
        custom_engine = exe_parent / ENGINE_CONTENTS_DIR
        if custom_engine.exists():
            return custom_engine
        return exe_parent
    return Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    candidate = bundle_dir().joinpath("assets", *parts)
    if candidate.exists():
        return candidate
    exe_dir = Path(sys.executable).resolve().parent
    for sub in (ENGINE_CONTENTS_DIR, ""):
        alt = (exe_dir / sub / "assets").joinpath(*parts) if sub else exe_dir.joinpath("assets", *parts)
        if alt.exists():
            return alt
    return candidate


def _startup_command_string() -> str:
    """Returns the command line registered in Windows Startup (HKCU\\...\\Run)."""
    if is_frozen():
        exe_p = Path(sys.executable).resolve()
        return f'"{exe_p}"'
    root_dir = Path(__file__).resolve().parent.parent
    main_py = root_dir / "main.py"
    py_exe = Path(sys.executable).resolve()
    # Prefer pythonw.exe on Windows so no console window flashes on startup
    if sys.platform == "win32" and py_exe.name.lower() == "python.exe":
        pyw = py_exe.with_name("pythonw.exe")
        if pyw.exists():
            py_exe = pyw
    return f'"{py_exe}" "{main_py}"'


def is_windows_startup_enabled() -> bool:
    """Checks whether V-Stream Downloader is registered to launch automatically with Windows."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            ) as key:
                val, _ = winreg.QueryValueEx(key, STARTUP_REG_NAME)
                return bool(val and str(val).strip())
        except OSError:
            return False
        except Exception as exc:
            logger.debug("Windows startup check error: %s", exc)
            return False

    # Linux XDG autostart fallback
    desktop_file = Path.home() / ".config" / "autostart" / f"{STARTUP_REG_NAME}.desktop"
    return desktop_file.exists()


def set_windows_startup(enabled: bool) -> bool:
    """
    Registers or unregisters V-Stream Downloader in Windows Startup
    (`HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`), with Linux XDG autostart fallback.
    """
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    cmd = _startup_command_string()
                    winreg.SetValueEx(key, STARTUP_REG_NAME, 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, STARTUP_REG_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except Exception as exc:
            logger.error("Failed to update Windows startup registry: %s", exc)
            return False

    # Linux / POSIX XDG Autostart fallback
    try:
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / f"{STARTUP_REG_NAME}.desktop"
        if enabled:
            autostart_dir.mkdir(parents=True, exist_ok=True)
            cmd = _startup_command_string()
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=V-Stream Downloader Pro\n"
                f"Exec={cmd}\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            desktop_file.write_text(content, encoding="utf-8")
        else:
            if desktop_file.exists():
                desktop_file.unlink()
        return True
    except Exception as exc:
        logger.error("Failed to update autostart entry: %s", exc)
        return False


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    target = base / APP_SLUG
    target.mkdir(parents=True, exist_ok=True)
    return target


def bin_dir() -> Path:
    target = app_data_dir() / "bin"
    target.mkdir(parents=True, exist_ok=True)
    return target


def queue_state_path() -> Path:
    return app_data_dir() / "queue_state.json"


def download_archive_path() -> Path:
    return app_data_dir() / "download_archive.txt"


def cache_dir() -> Path:
    target = app_data_dir() / "cache"
    target.mkdir(parents=True, exist_ok=True)
    return target


def thumbs_cache_dir() -> Path:
    target = cache_dir() / "thumbnails"
    target.mkdir(parents=True, exist_ok=True)
    return target


def logs_dir() -> Path:
    target = app_data_dir() / "logs"
    target.mkdir(parents=True, exist_ok=True)
    return target


def default_download_dir() -> Path:
    dl = Path.home() / "Downloads" / "V-Stream"
    try:
        dl.mkdir(parents=True, exist_ok=True)
    except OSError:
        dl = app_data_dir() / "Downloads"
        dl.mkdir(parents=True, exist_ok=True)
    return dl
