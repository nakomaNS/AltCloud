CURRENT_VERSION = "1.0.0" 

import os
import sys

def resource_path(relative_path):
    try:

        base_path = sys._MEIPASS
    except Exception:

        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src_python"))
    
    return os.path.join(base_path, relative_path)


if getattr(sys, 'frozen', False):

    BASE_DIR = os.path.join(os.path.dirname(sys.executable), '_internal')
else:

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GAMES_TO_MONITOR = []
STEAM_APP_LIST = []


CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'AltCloud')
IMAGE_CACHE_DIR = os.path.join(CONFIG_DIR, 'cache', 'images')
STATUS_DIR = CONFIG_DIR
CONFIG_FILE = os.path.join(CONFIG_DIR, 'games.json')
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'settings.json')



EXE_PATH = os.path.join(BASE_DIR, "main", "bin", "altcloud_util.exe")
DELETER_EXE_PATH = os.path.join(BASE_DIR, "main", "bin", "deleter.exe")


DB_PATH = resource_path(os.path.join("data", "steam_games.db"))


TRAY_ICON_PATH = resource_path(os.path.join("icons", "tray_icon.png"))
ADD_ICON_PATH = resource_path(os.path.join("icons", "add_icon.svg"))
DELETE_ICON_PATH = resource_path(os.path.join("icons", "delete_icon.svg"))
EDIT_ICON_PATH = resource_path(os.path.join("icons", "edit_icon.svg"))
SYNC_ICON_PATH = resource_path(os.path.join("icons", "sync_icon.svg"))
SPINNER_ICON_PATH = resource_path(os.path.join("icons", "spinner_icon.svg"))
SUCCESS_SYNC_ICON_PATH = resource_path(os.path.join("icons", "success_sync.svg"))
FAVORITE_ICON_PATH = resource_path(os.path.join("icons", "favorite_icon.svg"))
SEARCH_ICON_PATH = resource_path(os.path.join("icons", "search_icon.svg"))
FILTER_ICON_PATH = resource_path(os.path.join("icons", "search_filter.svg"))
CLOUD_GAMING_ICON_PATH = resource_path(os.path.join("icons", "cloud_gaming_icon.svg"))
MINIMIZE_ICON_PATH = resource_path(os.path.join("icons", "minimize_icon.svg"))
CLOSE_ICON_PATH = resource_path(os.path.join("icons", "close_icon.svg"))
MONITORING_STATUS_PATH = resource_path(os.path.join("icons", "monitoring_status.svg"))
INATIVE_STATUS_PATH = resource_path(os.path.join("icons", "inative_status.svg"))
TOTAL_SIZE_ICON_PATH = resource_path(os.path.join("icons", "total_size.svg"))
INFO_ICON_PATH = resource_path(os.path.join("icons", "info.svg"))
SETTINGS_ICON_PATH = resource_path(os.path.join("icons", "settings_icon.svg"))
SIZE_ICON_PATH = resource_path(os.path.join("icons", "size_icon.svg"))
CALENDAR_ICON_PATH = resource_path(os.path.join("icons", "calendar_icon.svg"))
CLOUD_UPLOAD_ICON_PATH = resource_path(os.path.join("icons", "cloud_upload_icon.svg"))
LIGHT_EFFECT_PATH = resource_path(os.path.join("icons", "background.jpg"))
CHECK_ICON_PATH = resource_path(os.path.join("icons", "check.svg"))
APP_ICON_PATH = resource_path(os.path.join("icons", "app_icon.ico"))

DIALOG_BG_POSITIONS = {
    "settings": "100% 100%", "add_game": "100% 100%",
    "info": "100% 100%", "confirmation": "100% 100%"
}

os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)