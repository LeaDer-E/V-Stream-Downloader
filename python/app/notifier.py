from PySide6.QtCore import QObject, Signal

from app.sound import SOUND
from app.state import AppState


class NotifierEngine(QObject):
    popup_triggered = Signal(str, str, str)  # title, message, file_path

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.state.notification_requested.connect(self.notify)

    def notify(self, title: str, message: str, file_path: str = "") -> None:
        if not self.state.config.notifications_enabled:
            return
        SOUND.play_chime(self.state.config.sound_enabled)
        self.popup_triggered.emit(title, message, file_path)
