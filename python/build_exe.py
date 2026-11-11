import os
import subprocess
import sys
from pathlib import Path

from tools.make_icon import generate_icons

ROOT = Path(__file__).resolve().parent
ENGINE_CONTENTS_DIR = "V-Stream-Engine"


def build() -> None:
    """
    Builds a fast-starting, antivirus-friendly `--onedir` distribution
    and renames PyInstaller's default `_internal` directory to `V-Stream-Engine`
    via `--contents-directory V-Stream-Engine`.
    """
    ico_path = generate_icons()
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
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "yt_dlp_ejs",
        str(ROOT / "main.py"),
    ]
    print(f"Building --onedir V-Stream-Downloader distribution (runtime folder: {ENGINE_CONTENTS_DIR})...")
    subprocess.check_call(cmd)
    print("\nBuild Complete! Distribution folder is in: dist/V-Stream-Downloader/")


if __name__ == "__main__":
    build()
