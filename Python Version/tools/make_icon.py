import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication

from app.theme import T
from app.ui.icons import logo_pixmap


def generate_icons() -> Path:
    app = QGuiApplication.instance() or QGuiApplication([])
    T.set_theme("cyber_violet", "dark")

    assets = ROOT / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    png_path = assets / "icon.png"
    pix_256 = logo_pixmap(256, dpr=1.0)
    pix_256.save(str(png_path), "PNG")

    sizes = [256, 128, 64, 48, 32, 24, 16]
    png_blobs = []
    for sz in sizes:
        px = logo_pixmap(sz, dpr=1.0)
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        px.save(buf, "PNG")
        png_blobs.append((sz, bytes(buf.data())))

    ico_path = assets / "icon.ico"
    with open(ico_path, "wb") as f:
        # ICONDIR header: reserved=0, type=1 (ICO), count=len(sizes)
        f.write(struct.pack("<HHH", 0, 1, len(png_blobs)))
        offset = 6 + len(png_blobs) * 16
        for sz, blob in png_blobs:
            w_byte = 0 if sz >= 256 else sz
            h_byte = 0 if sz >= 256 else sz
            f.write(struct.pack("<BBBBHHII", w_byte, h_byte, 0, 0, 1, 32, len(blob), offset))
            offset += len(blob)
        for _, blob in png_blobs:
            f.write(blob)

    return ico_path


if __name__ == "__main__":
    out = generate_icons()
    print(f"Generated multi-resolution icon at: {out}")
