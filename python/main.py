import logging
from logging.handlers import RotatingFileHandler
import sys

from PySide6.QtCore import QLockFile, Qt
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from app import __app_name__, __version__
from app.config import AppConfig
from app.domain.manager import DownloadManager
from app.i18n import I18N
from app.paths import app_data_dir, asset_path, logs_dir
from app.state import AppState
from app.theme import T
from app.ui.icons import logo_pixmap
from app.ui.window import MainWindow

IPC_SERVER_NAME = "VStreamDownloaderPro_SingleInstance_IPC"


def setup_logging() -> None:
    """
    Configures RotatingFileHandler (2 MB x 3 backups) and safely checks
    `sys.stdout is not None` so `--windowed` GUI builds never crash on NoneType stdout.
    """
    log_file = logs_dir() / "v_stream.log"
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    ]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def load_bundled_fonts() -> None:
    fonts_dir = asset_path("fonts")
    if not fonts_dir.exists():
        return
    for ttf in fonts_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(ttf))


def _notify_existing_instance() -> bool:
    """Sends an ACTIVATE message to the running primary instance via QLocalSocket."""
    sock = QLocalSocket()
    sock.connectToServer(IPC_SERVER_NAME)
    if sock.waitForConnected(400):
        sock.write(b"ACTIVATE")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def main() -> int:
    setup_logging()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    # Single-instance guard via QLockFile + QLocalServer IPC activation
    lock_path = str(app_data_dir() / "v_stream.lock")
    lock_file = QLockFile(lock_path)
    lock_file.setStaleLockTime(0)
    if not lock_file.tryLock(100):
        _notify_existing_instance()
        logging.info("Activated existing instance of V-Stream Downloader.")
        return 0

    load_bundled_fonts()

    cfg = AppConfig.load()
    T.set_theme(cfg.palette_id, cfg.theme_mode, cfg.custom_accent)
    I18N.set_language(cfg.language)

    app.setWindowIcon(QIcon(logo_pixmap(64)))

    state = AppState(cfg)
    manager = DownloadManager(state)
    win = MainWindow(state, manager)

    # Setup QLocalServer to bring window to foreground when a second instance is launched
    QLocalServer.removeServer(IPC_SERVER_NAME)
    ipc_server = QLocalServer(app)
    if ipc_server.listen(IPC_SERVER_NAME):
        def _on_ipc_conn() -> None:
            conn = ipc_server.nextPendingConnection()
            if conn is not None:
                conn.waitForReadyRead(200)
                _ = conn.readAll()
                conn.close()
                win._restore_from_tray()

        ipc_server.newConnection.connect(_on_ipc_conn)

    app.aboutToQuit.connect(manager.shutdown)
    win.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
