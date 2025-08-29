import os
import json
import config

def load_steam_app_list():
    FORBIDDEN_WORDS = { "server", "sdk", "demo", "beta", "dlc", "editor", "toolkit", "authoring tools", "benchmark", "dedicated", "bonus content", "configs", "redist", "test", "pack", "kit", "steam", "valve", "linux", "mac", "macos", "vr", "controller", "sharing", "client", "awards", "filmmaker", "add-on", "winui2", "slice", "greenlight", "depot", "key", "rgl/sc", "soundtrack", "playtest", "trailer", "artbook", "season pass", "episode", "movie", "filme", "application" }
    try:
        with open(config.APPLIST_PATH, 'r', encoding='utf-8') as f:
            full_list = json.load(f).get("applist", {}).get("apps", [])
            config.STEAM_APP_LIST = [app for app in full_list if app.get("name", "").lower() and not any(word in app.get("name", "").lower() for word in FORBIDDEN_WORDS)]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERRO: Não foi possível carregar 'applist.json'. Detalhes: {e}")
        config.STEAM_APP_LIST = []

def load_games():
    if os.path.isfile(config.CONFIG_FILE):
        try:
            with open(config.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config.GAMES_TO_MONITOR = json.load(f)
        except (json.JSONDecodeError, IOError):
            config.GAMES_TO_MONITOR = []

def save_games():
    try:
        os.makedirs(config.CONFIG_DIR, exist_ok=True) 
        with open(config.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config.GAMES_TO_MONITOR, f, indent=4)
    except IOError as e:
        print(f"Erro ao salvar configuração de jogos: {e}")

def load_settings():
    settings = {
        "start_with_windows": False,
        "close_to_tray": False
    }
    if os.path.isfile(config.SETTINGS_FILE):
        try:
            with open(config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings.update(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
    return settings

def save_settings(settings_data):
    try:
        os.makedirs(config.CONFIG_DIR, exist_ok=True)
        with open(config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_data, f, indent=4)
    except IOError as e:
        print(f"Erro ao salvar configurações: {e}")