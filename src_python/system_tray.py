import threading
from PyQt6.QtCore import QObject, pyqtSignal
from pystray import MenuItem, Icon
from PIL import Image
import config

class SignalEmitter(QObject):
    toggle_window_signal = pyqtSignal()
    quit_app_signal = pyqtSignal()

def setup_tray_icon(signal_emitter):
    try:
        image = Image.open(config.TRAY_ICON_PATH)
    except FileNotFoundError:
        image = Image.new('RGB', (64, 64), color='black')

    menu = (
        MenuItem('Mostrar/Ocultar', lambda: signal_emitter.toggle_window_signal.emit(), default=True),
        MenuItem('Sair', lambda: signal_emitter.quit_app_signal.emit())
    )
    icon = Icon("AltCloud", image, "AltCloud Sync", menu)
    
    threading.Thread(target=icon.run, daemon=True).start()
    
    return icon