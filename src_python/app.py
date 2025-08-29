import sys
import os
import subprocess
import re
import psutil
import json
import time
import cv2
import ctypes
import sqlite3
import numpy as np
from PyQt6.QtCore import (Qt, QThreadPool, QTimer, QSize, QPoint, pyqtSlot, 
                             QEasingCurve, QPropertyAnimation, pyqtProperty, 
                             QParallelAnimationGroup, pyqtSignal)
from PyQt6.QtGui import QIcon, QAction, QWheelEvent, QColor, QPixmap, QImage, QResizeEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QMenu, QMessageBox,
                             QLineEdit, QStackedWidget, QGridLayout, QSizePolicy, 
                             QGraphicsDropShadowEffect, QStackedLayout, QGraphicsBlurEffect, QDialog)
from PyQt6.QtSvgWidgets import QSvgWidget
import config
import data_manager
from utils import render_svg_to_pixmap, is_steam_running
from workers import WorkerSignals, ManualSyncWorker, ImageDownloader, SaveDeleterWorker
from ui_components import GameListItem, SvgPushButton, PageIndicator, extract_dominant_color
from ui_dialogs import AddGameDialog, SettingsDialog, ModernDialog, ConfirmationDialog
from ui_info_dialog import InfoDialog
from system_tray import SignalEmitter, setup_tray_icon

class EmptyStateWidget(QWidget):
    clicked = pyqtSignal()
    
    def __init__(self, icon_path=config.ADD_ICON_PATH, text="Clique no ícone acima para adicionar seu primeiro jogo na nuvem", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(20)

        self.button = QPushButton()

        self.button.setFixedSize(150, 150)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 2px dashed #323d52;
                border-radius: 15px;
            }
            QPushButton:hover {
                border-color: #5a6378;
            }
        """)
        self.button.clicked.connect(self.clicked)

        button_layout = QVBoxLayout(self.button)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_widget = QSvgWidget(icon_path)
        self.icon_widget.setFixedSize(80, 80)
        button_layout.addWidget(self.icon_widget)
        
        self.info_label = QLabel(text)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #8a95b3; font-size: 14px;")
        self.info_label.setWordWrap(True)
        self.info_label.setMaximumWidth(300)

        main_layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.info_label)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(config.APP_ICON_PATH))
        self.setWindowTitle("AltCloud"); self.setFixedSize(780, 700)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.old_pos = None; self.threadpool = QThreadPool()
        self.image_cache = {}
        self.MAX_CACHE_SIZE = 50
        self.is_animating = False
        self.current_page, self.total_pages = 0, 1
        self.GAMES_PER_PAGE, self.NUM_COLUMNS = 8, 4
        self.favorites_only_mode, self.current_sort_mode, self.current_search_query = False, "default", ""
        
        data_manager.load_games(); self.settings = data_manager.load_settings()
        self.game_running_states = {}
        self._initialize_game_states()
        
        self.container = QWidget()
        self.container.setObjectName("mainContainer")
        background_image_path = config.LIGHT_EFFECT_PATH.replace("\\", "/")
        self.container.setStyleSheet(f"""
            QWidget#mainContainer {{
                border-image: url({background_image_path}) 0 0 0 0 stretch stretch;
                border-radius: 10px;
            }}
        """)
        self.setCentralWidget(self.container)

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(15, 20, 15, 5); main_layout.setSpacing(0)
        
        self._setup_header_bar(main_layout); main_layout.addSpacing(20)
        
        content_layout = QVBoxLayout(); content_layout.setSpacing(0)
        self.viewport = QWidget(); self.viewport.setStyleSheet("background:transparent;")
        
        viewport_layout = QVBoxLayout(self.viewport)
        viewport_layout.setContentsMargins(0,0,0,0)

        self.main_stack = QStackedWidget()
        self.main_stack.setStyleSheet("background: transparent;")
        
        self.pages_stack = QStackedWidget()
        self.pages_stack.setStyleSheet("background: transparent;")
        
        self.empty_state_widget = EmptyStateWidget()
        
        no_fav_text = "Reúna aqui seus jogos preferidos.<br>Para adicionar, clique no ícone de coração que aparece sobre cada jogo na sua biblioteca."
        self.no_favorites_widget = EmptyStateWidget(icon_path=config.FAVORITE_ICON_PATH, text=no_fav_text)
        self.no_favorites_widget.clicked.connect(self._handle_no_favorites_click)
        
        self.main_stack.addWidget(self.pages_stack)   
        self.main_stack.addWidget(self.empty_state_widget) 
        self.main_stack.addWidget(self.no_favorites_widget)
        
        viewport_layout.addWidget(self.main_stack)
        
        self.GRID_MARGIN, self.GRID_VERTICAL_SPACING = 15, 35
        viewport_height = (232 * 2) + self.GRID_VERTICAL_SPACING + (self.GRID_MARGIN * 2)
        viewport_width = (162 * 4) + (25 * 3) + (self.GRID_MARGIN * 2)
        self.viewport.setFixedSize(viewport_width, viewport_height)
        
        viewport_wrapper = QHBoxLayout(); viewport_wrapper.addStretch(1); viewport_wrapper.addWidget(self.viewport); viewport_wrapper.addStretch(1)
        self.page_indicator = PageIndicator()
        indicator_wrapper = QHBoxLayout(); indicator_wrapper.addStretch(1); indicator_wrapper.addWidget(self.page_indicator); indicator_wrapper.addStretch(1)
        content_layout.addLayout(viewport_wrapper); content_layout.addSpacing(15); content_layout.addLayout(indicator_wrapper)
        main_layout.addLayout(content_layout); main_layout.addStretch(1)
        
        self.game_widgets = []
        
        self.main_blur_effect = QGraphicsBlurEffect()
        self.main_blur_effect.setBlurRadius(0)
        self.container.setGraphicsEffect(self.main_blur_effect)

        self.beta_label = QLabel("Beta - 1.0", self.container)
        self.beta_label.setStyleSheet("""
            background: transparent;
            color: rgba(255, 255, 255, 50); /* Cor branca com 20% de opacidade */
            font-size: 10px;
            font-weight: bold;
        """)
        self.beta_label.adjustSize()

        self._connect_signals()
        self._refresh_game_list_display()
        self.tray_icon = None
        self.status_timer = QTimer(self); self.status_timer.timeout.connect(self.check_game_statuses); self.status_timer.start(3000)

    def _initialize_game_states(self):
        try:
            current_processes = {p.name() for p in psutil.process_iter(['name'])}
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            current_processes = set()
        for game in config.GAMES_TO_MONITOR:
            if process_name := game.get('process'):
                self.game_running_states[process_name] = process_name in current_processes

    def _setup_header_bar(self, parent_layout):
        header_layout = QHBoxLayout(); header_layout.setContentsMargins(10, 0, 10, 0); header_layout.setSpacing(10)
        self.icon_svg_widget = QSvgWidget(config.CLOUD_GAMING_ICON_PATH); self.icon_svg_widget.setFixedSize(22, 22)
        title_label = QLabel("AltCloud"); title_label.setStyleSheet("font-size: 15px; font-weight: bold; background: transparent; padding-top: 2px; margin-right: 10px; color: #f0f0f0;")
        self.search_bar = QLineEdit(); self.search_bar.setPlaceholderText("Pesquisar jogo..."); self.search_bar.setFixedHeight(36); self.search_bar.setMinimumWidth(300)
        self.search_bar.setStyleSheet("background-color: #111827; border: 1px solid #323d52; border-radius: 5px; padding: 5px 10px 5px 10px; color: #f0f0f0;")
        search_icon_action = QAction(QIcon(render_svg_to_pixmap(config.SEARCH_ICON_PATH, 18, "#AAAAAA")), "", self.search_bar)
        self.search_bar.addAction(search_icon_action, QLineEdit.ActionPosition.LeadingPosition)
        header_layout.addWidget(self.icon_svg_widget); header_layout.addWidget(title_label); header_layout.addWidget(self.search_bar)
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred); header_layout.addWidget(spacer)
        btn_size, icon_size = 36, 20
        self.settings_button = SvgPushButton(config.SETTINGS_ICON_PATH, parent=self); self.favorites_button = SvgPushButton(config.FAVORITE_ICON_PATH, parent=self); self.favorites_button.setCheckable(True)
        self.add_button = SvgPushButton(config.ADD_ICON_PATH, parent=self); self.sort_button = SvgPushButton(config.FILTER_ICON_PATH, parent=self)
        for btn in [self.settings_button, self.favorites_button, self.add_button, self.sort_button]:
            btn.setFixedSize(btn_size, btn_size); btn.setSvgIconSize(QSize(icon_size, icon_size))
            btn.setStyleSheet("SvgPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 5px; color: #FFFFFF; } SvgPushButton:hover { background-color: rgba(255, 255, 255, 0.1); border: 1px solid #323d52; } SvgPushButton:checked { background-color: #E53935; border: 1px solid transparent; }")
        self.minimize_button = SvgPushButton(config.MINIMIZE_ICON_PATH, parent=self); self.close_button = SvgPushButton(config.CLOSE_ICON_PATH, parent=self)
        for btn in [self.minimize_button, self.close_button]:
            btn.setFixedSize(40, 30); btn.setSvgIconSize(QSize(14, 14))
            btn.setStyleSheet("SvgPushButton { background-color: transparent; border: none; border-radius: 5px; } SvgPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }")
        self.close_button.setStyleSheet("SvgPushButton { background-color: transparent; border: none; border-radius: 5px; } SvgPushButton:hover { background-color: #E81123; }")
        header_layout.addWidget(self.settings_button); header_layout.addWidget(self.favorites_button); header_layout.addWidget(self.add_button); header_layout.addWidget(self.sort_button)
        header_layout.addSpacing(10); header_layout.addWidget(self.minimize_button); header_layout.addWidget(self.close_button)
        parent_layout.addLayout(header_layout)

    def _connect_signals(self):
        self.minimize_button.clicked.connect(self.showMinimized); self.close_button.clicked.connect(self._handle_close_action)
        self.search_bar.textChanged.connect(self._on_search_changed); self.sort_button.clicked.connect(self._on_sort_button_clicked)
        self.settings_button.clicked.connect(self.show_settings_dialog); self.add_button.clicked.connect(self.show_add_game_dialog)
        self.favorites_button.clicked.connect(self._on_favorites_button_clicked)
        self.empty_state_widget.clicked.connect(self.show_add_game_dialog)
        self.signal_emitter = SignalEmitter()
        self.signal_emitter.toggle_window_signal.connect(self.handle_toggle_window); self.signal_emitter.quit_app_signal.connect(self.handle_quit_app)

    def _get_filtered_and_sorted_games(self):
        games = list(config.GAMES_TO_MONITOR)
        if self.favorites_only_mode: games = [g for g in games if g.get('is_favorite', False)]
        if self.current_search_query: games = [g for g in games if self.current_search_query in g['name'].lower()]
        if self.current_sort_mode == 'alpha_asc': games.sort(key=lambda g: g['name'].lower())
        elif self.current_sort_mode == 'alpha_desc': games.sort(key=lambda g: g['name'].lower(), reverse=True)
        elif self.current_sort_mode == 'favorites_first': games.sort(key=lambda g: (not g.get('is_favorite', False), g['name'].lower()))
        return games
    
    def _refresh_game_list_display(self, game_added=False):
        games_to_display = self._get_filtered_and_sorted_games()

        if len(games_to_display) == 0:

            if self.favorites_only_mode:
                self.main_stack.setCurrentIndex(2) 
            else:
                self.main_stack.setCurrentIndex(1)
            
            self.page_indicator.hide()
            return 
        else:
            self.main_stack.setCurrentIndex(0)
            self.page_indicator.show()

        while self.pages_stack.count() > 0:
            widget = self.pages_stack.widget(0)
            self.pages_stack.removeWidget(widget)
            widget.deleteLater()
        
        self.game_widgets.clear()
        
        self.total_pages = max(1, (len(games_to_display) + self.GAMES_PER_PAGE - 1) // self.GAMES_PER_PAGE)
        
        if game_added:
            self.current_page = self.total_pages - 1
        else:
            if self.current_page >= self.total_pages:
                self.current_page = max(0, self.total_pages - 1)

        for i in range(self.total_pages):
            page_widget = QWidget()
            page_grid = QGridLayout(page_widget)
            page_grid.setContentsMargins(self.GRID_MARGIN, self.GRID_MARGIN, self.GRID_MARGIN, self.GRID_MARGIN)
            page_grid.setHorizontalSpacing(25)
            page_grid.setVerticalSpacing(self.GRID_VERTICAL_SPACING)
            page_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            
            page_games = games_to_display[i * self.GAMES_PER_PAGE : (i * self.GAMES_PER_PAGE) + self.GAMES_PER_PAGE]
            
            for idx, game_data in enumerate(page_games):
                widget = self._create_game_widget(game_data)
                self.game_widgets.append(widget)
                row, col = divmod(idx, self.NUM_COLUMNS)
                page_grid.addWidget(widget, row, col)
            
            self.pages_stack.addWidget(page_widget)

        self.pages_stack.setCurrentIndex(self.current_page)
        self.page_indicator.set_page_count(self.total_pages)
        self.page_indicator.set_current_page(self.current_page)
        
        self.check_game_statuses()
    
    def _create_game_widget(self, game_data):
        widget = GameListItem(game_data)
        widget.deletion_requested.connect(self.handle_game_deletion); widget.edit_requested.connect(self.show_edit_game_dialog)
        widget.sync_requested.connect(self.handle_manual_sync); widget.favorite_toggled.connect(self.handle_favorite_toggled)
        widget.info_requested.connect(self.show_info_dialog)
        self._find_appid_and_download_image(game_data, widget)
        if 'image_path' in game_data and os.path.exists(game_data['image_path']):
            self._load_and_cache_image(game_data['image_path'], widget)
        return widget

    def _on_search_changed(self, text): self.current_search_query = text.lower().strip(); self._refresh_game_list_display()
    
    def _on_sort_button_clicked(self):
        menu = QMenu(self); menu.setStyleSheet("QMenu { background-color: #111827; color: #f0f0f0; border: 1px solid #323d52; } QMenu::item:selected { background-color: #1E2A44; }")
        actions = {"Padrão": "default", "Favoritos Primeiro": "favorites_first", "Nome (A-Z)": "alpha_asc", "Nome (Z-A)": "alpha_desc"}
        for text, key in actions.items():
            action = QAction(text, self, triggered=lambda c, k=key: self._set_sort_mode(k)); menu.addAction(action)
        menu.exec(self.sort_button.mapToGlobal(QPoint(0, self.sort_button.height())))
    
    def _set_sort_mode(self, mode): self.current_sort_mode = mode; self._refresh_game_list_display()
    
    def _on_favorites_button_clicked(self): self.favorites_only_mode = self.favorites_button.isChecked(); self._refresh_game_list_display()
    
    def show_add_game_dialog(self):
        self._apply_blur_animation()
        try:
            dialog = AddGameDialog(self.threadpool, config.GAMES_TO_MONITOR, self)
            if dialog.exec():
                self.handle_new_game_added(dialog.get_game_data())
        finally:
            self._remove_blur_animation()
            
    def show_edit_game_dialog(self, game_data):
        self._apply_blur_animation()
        try:
            dialog = AddGameDialog(self.threadpool, config.GAMES_TO_MONITOR, self)
            dialog.set_edit_mode(game_data)
            if dialog.exec():
                self.handle_game_edited(game_data, dialog.get_game_data())
        finally:
            self._remove_blur_animation()
            
    def show_settings_dialog(self):
        self._apply_blur_animation()
        try:
            dialog = SettingsDialog(self)
            dialog.set_settings(self.settings)
            if dialog.exec():
                self.settings.update(dialog.get_settings())
                data_manager.save_settings(self.settings)
        finally:
            self._remove_blur_animation()
    
    @pyqtSlot(dict)
    def show_info_dialog(self, game_data):
        self._apply_blur_animation()
        try:
            dialog = InfoDialog(game_data, config.CONFIG_DIR, self)
            dialog.deletion_requested.connect(self.handle_save_deletion)
            dialog.exec()
        finally:
            self._remove_blur_animation()

    @pyqtSlot(dict)
    def handle_new_game_added(self, game_data):
        game_data['is_favorite'] = False
        config.GAMES_TO_MONITOR.append(game_data)
        data_manager.save_games()
        self.game_running_states[game_data['process']] = False
        self._refresh_game_list_display(game_added=True)
        
    @pyqtSlot(dict, dict)
    def handle_game_edited(self, old_data, new_data):
        try:
            config.GAMES_TO_MONITOR[config.GAMES_TO_MONITOR.index(old_data)] = new_data
            data_manager.save_games()
            if old_data['process'] in self.game_running_states:
                self.game_running_states.pop(old_data['process'])
            self.game_running_states[new_data['process']] = False
            self._refresh_game_list_display()
        except ValueError: pass
        
    @pyqtSlot(dict)
    def handle_game_deletion(self, game_data):
        self._apply_blur_animation()
        try:
            dialog = ConfirmationDialog(
                parent=self, icon_path=config.DELETE_ICON_PATH, title="Remover da Biblioteca",
                text=f"Remover o card do jogo:\n'{game_data.get('name')}'?", informative_text="Seus saves na nuvem serão mantidos. Apenas o atalho na tela principal será removido.",
                accept_text="Sim, remover", reject_text="Cancelar"
            )
            if dialog.exec():
                try:
                    if game_data['process'] in self.game_running_states:
                        self.game_running_states.pop(game_data['process'])
                    config.GAMES_TO_MONITOR.remove(game_data)
                    data_manager.save_games()
                    self._refresh_game_list_display()
                except (ValueError, KeyError) as e: 
                    print(f"Erro na deleção: {e}")
        finally:
            self._remove_blur_animation()
            
    @pyqtSlot(dict)
    def handle_favorite_toggled(self, game_data):
        game_data['is_favorite'] = not game_data.get('is_favorite', False); data_manager.save_games()
        if widget := next((w for w in self.game_widgets if w.game_data == game_data), None): widget.update_favorite_status()
        if self.favorites_only_mode: self._refresh_game_list_display()
        
    def _find_appid(self, name):
     if not name or not os.path.exists(config.DB_PATH):
         return None

     conn = None
     try:
         conn = sqlite3.connect(config.DB_PATH)
         cursor = conn.cursor()

         cursor.execute("SELECT appid FROM games WHERE name = ? LIMIT 1", (name,))
         result = cursor.fetchone()
         if result:
             return result[0]

         pattern = f'%{name}%'
         cursor.execute("SELECT appid FROM games WHERE name LIKE ? LIMIT 1", (pattern,))
         result = cursor.fetchone()
         if result:
             return result[0]

     except sqlite3.Error as e:
         print(f"Erro ao buscar appid no banco de dados: {e}")
     finally:
         if conn:
             conn.close()

     return None
        
    def _find_appid_and_download_image(self, game_data, widget):
        if appid := self._find_appid(game_data["name"]):
            path = os.path.join(config.IMAGE_CACHE_DIR, f"{appid}.jpg")
            update_json = game_data.get("image_path") != path
            
            if update_json:
                game_data["image_path"] = path
                data_manager.save_games()

            if os.path.exists(path):
                self._load_and_cache_image(path, widget)
            else:
                dl = ImageDownloader(appid, path, WorkerSignals())
                dl.signals.finished.connect(lambda p, w=widget: self.on_image_downloaded(p, w))
                self.threadpool.start(dl)
                
    def on_image_downloaded(self, path, widget):
        try:
            if widget and path and os.path.exists(path):
                self._load_and_cache_image(path, widget)
        except RuntimeError: pass

    @pyqtSlot(object)
    def on_sync_finished(self, result):
        game_data = result["game_data"]
        widget = next((w for w in self.game_widgets if w.game_data == game_data), None)
        try:
            if not widget: return
            widget.stop_sync_animation()
            if result.get("success", False):
                self._refresh_single_game_status(widget)
            else:
                log = result.get("log", "Nenhum log detalhado.")
                error = result.get("message", "Erro desconhecido.")
                msg = QMessageBox(self); msg.setWindowTitle("Falha na Sincronização"); msg.setText(error)
                msg.setInformativeText("Log detalhado abaixo."); msg.setDetailedText(log); msg.setIcon(QMessageBox.Icon.Critical)
                msg.setStyleSheet("QMessageBox { min-width: 600px; }"); msg.exec()
        finally:
            pass

    @pyqtSlot(object)
    def on_auto_sync_finished(self, result):
        game_name = result.get("game_data", {}).get("name", "Desconhecido")
        success = result.get("success", False)
        if success:
            print(f"Sincronização automática para '{game_name}' concluída com sucesso.")
            self.check_game_statuses()
        else:
            error = result.get("message", "Erro desconhecido.")
            print(f"ERRO na sincronização automática para '{game_name}': {error}")

    @pyqtSlot(dict)
    def handle_manual_sync(self, game_data):
        if widget := next((w for w in self.game_widgets if w.game_data == game_data), None):
            widget.start_sync_animation()
            worker = ManualSyncWorker(game_data, WorkerSignals(), config.CONFIG_DIR, mode='--sync-now')
            worker.signals.finished.connect(self.on_sync_finished)
            self.threadpool.start(worker)

    def _refresh_single_game_status(self, widget: GameListItem):
        if not widget: return
        game_data = widget.game_data
        is_running = self.game_running_states.get(game_data['process'], False)
        mod_time, upload_time = 0, 0
        if os.path.isdir(save_path := game_data.get('save_path', '')):
            try:
                mod_times = [os.path.getmtime(fp) for f in os.listdir(save_path) if not f.endswith('.bak') and os.path.isfile(fp := os.path.join(save_path, f))]
                if mod_times: mod_time = max(mod_times)
            except (FileNotFoundError, ValueError): pass
            upload_times = []
            for fn in os.listdir(save_path):
                if not fn.endswith('.bak') and os.path.isfile(os.path.join(save_path, fn)):
                    s_folder = re.sub(r'[™®©:/\\?*|"<>]+', '', game_data['name']).strip()
                    s_file = os.path.join(config.STATUS_DIR, f"status_{s_folder}_{fn}.json")
                    if os.path.exists(s_file):
                        try:
                            with open(s_file, 'r', encoding='utf-8') as f: upload_times.append(json.load(f).get("last_upload_timestamp", 0))
                        except (json.JSONDecodeError, IOError): pass
            if upload_times: upload_time = max(upload_times)
        widget.update_status(is_running, mod_time, upload_time)
        widget.update_overlay_visibility()

    def check_game_statuses(self):
        for widget in self.game_widgets: self._refresh_single_game_status(widget)
        try:
            current_processes = {p.name() for p in psutil.process_iter(['name'])}
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            current_processes = set()
        for game in config.GAMES_TO_MONITOR:
            process_name = game.get('process')
            if not process_name: continue
            is_running = process_name in current_processes
            was_running = self.game_running_states.get(process_name, False)
            if is_running and not was_running:
                print(f"EVENTO: Jogo '{game['name']}' iniciado. Disparando sync de download.")
                self.game_running_states[process_name] = True
                worker = ManualSyncWorker(game, WorkerSignals(), config.CONFIG_DIR, mode='--sync-now')
                worker.signals.finished.connect(self.on_auto_sync_finished)
                self.threadpool.start(worker)
                self._refresh_single_game_status(next((w for w in self.game_widgets if w.game_data == game), None))
            elif not is_running and was_running:
                print(f"EVENTO: Jogo '{game['name']}' fechado. Disparando sync de upload.")
                self.game_running_states[process_name] = False
                worker = ManualSyncWorker(game, WorkerSignals(), config.CONFIG_DIR, mode='--upload-only')
                worker.signals.finished.connect(self.on_auto_sync_finished)
                self.threadpool.start(worker)
                self._refresh_single_game_status(next((w for w in self.game_widgets if w.game_data == game), None))
            
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.old_pos = e.globalPosition().toPoint()
    
    def mouseMoveEvent(self, e):
        if self.old_pos: delta = e.globalPosition().toPoint() - self.old_pos; self.move(self.x()+delta.x(), self.y()+delta.y()); self.old_pos = e.globalPosition().toPoint()
    
    def mouseReleaseEvent(self, e): self.old_pos = None
    
    def wheelEvent(self, e: QWheelEvent):
        if self.total_pages <= 1 or self.is_animating:
            return
        
        direction = 1 if e.angleDelta().y() < 0 else -1
        new_page = self.current_page + direction
            
        if 0 <= new_page < self.total_pages:
            self.current_page = new_page
            self.page_indicator.set_current_page(self.current_page)
            
            self._transition_page(new_page, direction)

    def _transition_page(self, new_page_index: int, direction: int):
        self.is_animating = True
        
        current_widget = self.pages_stack.currentWidget()
        next_widget = self.pages_stack.widget(new_page_index)
        
        if not current_widget or not next_widget or current_widget == next_widget:
            self.is_animating = False
            return

        width = self.pages_stack.width()
        
        next_widget.setGeometry(direction * width, 0, width, self.pages_stack.height())
        next_widget.show()
        next_widget.raise_()

        anim_current = QPropertyAnimation(current_widget, b"pos")
        anim_current.setEndValue(QPoint(-direction * width, 0))
        anim_current.setDuration(350)
        anim_current.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_next = QPropertyAnimation(next_widget, b"pos")
        anim_next.setEndValue(QPoint(0, 0))
        anim_next.setDuration(350)
        anim_next.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(anim_current)
        self.anim_group.addAnimation(anim_next)
        
        self.anim_group.finished.connect(lambda: self.on_transition_finished(new_page_index))
        
        self.anim_group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def on_transition_finished(self, new_page_index):
        self.pages_stack.setCurrentIndex(new_page_index)
        self.is_animating = False

    def _apply_blur_animation(self):
        self.main_blur_effect.setEnabled(True)
        self.blur_animation = QPropertyAnimation(self.main_blur_effect, b"blurRadius")
        self.blur_animation.setDuration(150)
        self.blur_animation.setStartValue(0)
        self.blur_animation.setEndValue(8)
        self.blur_animation.start()

    def _remove_blur_animation(self):
        self.blur_animation = QPropertyAnimation(self.main_blur_effect, b"blurRadius")
        self.blur_animation.setDuration(150)
        self.blur_animation.setStartValue(self.main_blur_effect.blurRadius())
        self.blur_animation.setEndValue(0)
        self.blur_animation.finished.connect(lambda: self.main_blur_effect.setEnabled(False))
        self.blur_animation.start()
    
    def _handle_no_favorites_click(self):
        if self.favorites_button.isChecked():
            self.favorites_button.click()

    def _handle_close_action(self):
        if self.settings.get("close_to_tray", False):
            self.hide()
        else:
            self.handle_quit_app()

    def _create_blurred_version(self, pixmap: QPixmap, radius: int = 8):
        if pixmap.isNull(): return QPixmap()
        qimage = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)
        w, h = qimage.width(), qimage.height()
        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())
        arr = np.array(ptr).reshape(h, w, 4)
        blurred_arr = cv2.GaussianBlur(arr, (0, 0), sigmaX=radius, sigmaY=radius)
        return QPixmap.fromImage(QImage(blurred_arr.data, w, h, QImage.Format.Format_RGBA8888_Premultiplied))

    def _load_and_cache_image(self, image_path: str, widget: GameListItem):
        if not image_path or not os.path.exists(image_path):
            return

        cached_data = self.image_cache.get(image_path)
        
        if cached_data:
            sharp_pixmap, blurred_pixmap, dominant_color = cached_data
            widget.set_game_image(sharp_pixmap, blurred_pixmap, dominant_color)
        else:
            temp_pixmap = QPixmap(image_path)
            dpr = self.devicePixelRatioF()
            target_size = QSize(162, 232) * dpr

            sharp_pixmap = temp_pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            sharp_pixmap.setDevicePixelRatio(dpr)

            blur_source_pixmap = sharp_pixmap.scaled(sharp_pixmap.size() * 1.1, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            blurred_pixmap = self._create_blurred_version(blur_source_pixmap, radius=4)
            blurred_pixmap.setDevicePixelRatio(dpr)
            
            dominant_color = extract_dominant_color(sharp_pixmap)

            data_to_cache = (sharp_pixmap, blurred_pixmap, dominant_color)
            self.image_cache[image_path] = data_to_cache
            
            if len(self.image_cache) > self.MAX_CACHE_SIZE:
                oldest_key = next(iter(self.image_cache))
                del self.image_cache[oldest_key]
            widget.set_game_image(sharp_pixmap, blurred_pixmap, dominant_color)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if hasattr(self, 'beta_label'):
            margin_x = 10
            margin_y = 5
            x = self.container.width() - self.beta_label.width() - margin_x
            y = self.container.height() - self.beta_label.height() - margin_y
            
            self.beta_label.move(x, y)

    @pyqtSlot()
    def handle_toggle_window(self):
        if self.isVisible(): self.hide()
        else: self.show(); self.activateWindow()

    @pyqtSlot()
    def handle_quit_app(self):
        print("Iniciando o processo de encerramento do AltCloud...")
        processes_to_kill = ["altcloud.exe", "deleter.exe"]
        
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'].lower() in processes_to_kill:
                    print(f"Encontrado processo '{proc.info['name']}' (PID: {proc.info['pid']}). Encerrando...")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        print("Limpando ícone da bandeja do sistema...")
        if self.tray_icon:
            self.tray_icon.stop()

        print("Encerrando a aplicação.")
        QApplication.instance().quit()

    @pyqtSlot(list)
    def handle_save_deletion(self, remote_files_to_delete):
        worker = SaveDeleterWorker(remote_files_to_delete, WorkerSignals())
        worker.signals.finished.connect(self.on_save_deletion_finished)
        self.threadpool.start(worker)

    @pyqtSlot(object)
    def on_save_deletion_finished(self, result):
        print("\n\n" + "="*25 + " RELATÓRIO DE DELEÇÃO " + "="*25)
        log = result.get("log", "Nenhum log detalhado.")
        if result.get("success", False):
            print("STATUS: SUCESSO\nO processo de deleção foi concluído.\n--- Log ---\n" + log)
            self.check_game_statuses()
        else:
            error = result.get("message", "Erro desconhecido.")
            print(f"STATUS: FALHA\nERRO: {error}\n--- Log ---\n" + log)
        print("="*72 + "\n")

def main():
    if not is_steam_running():
        titulo = "Steam não detectada"
        mensagem = "O AltCloud precisa que a Steam esteja em execução para funcionar. Por favor, abra a Steam e tente novamente."
        ctypes.windll.user32.MessageBoxW(0, mensagem, titulo, 16)
        sys.exit(1)

    myappid = u'Altcloud'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)

    for exe_path in [config.EXE_PATH, getattr(config, 'DELETER_EXE_PATH', None)]:
        if exe_path and not os.path.exists(exe_path):
            QMessageBox.critical(None, "Erro Crítico", f"O executável '{os.path.basename(exe_path)}' não foi encontrado.")
            return
            
    app.setQuitOnLastWindowClosed(False)

    main_window = MainWindow()
    main_window.tray_icon = setup_tray_icon(main_window.signal_emitter)
    main_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()