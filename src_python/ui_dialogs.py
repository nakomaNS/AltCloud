import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, 
                             QHBoxLayout, QFormLayout, QLineEdit, QFileDialog, QCompleter, QWidget, 
                             QGraphicsDropShadowEffect, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSlot, QStringListModel, QRectF, QSize,QTimer
from PyQt6.QtGui import QMouseEvent, QPainter, QColor, QPixmap, QPainterPath, QPen, QRegion
from PyQt6.QtSvgWidgets import QSvgWidget
from ui_components import SvgPushButton
from workers import AutocompleteSearcher
import config
from utils import launch_steam, is_steam_running, load_svg_data
from ui_components import SvgPushButton, RotatingSvgWidget


class ModernDialog(QDialog):
    def __init__(self, parent=None, background_position="50% 50%", border_radius=10):
        super().__init__(parent)
        self.old_pos = None
        self.background_position = background_position 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        if hasattr(config, 'LIGHT_EFFECT_PATH') and os.path.exists(config.LIGHT_EFFECT_PATH):
            self.light_pixmap = QPixmap(config.LIGHT_EFFECT_PATH)
        else:
            self.light_pixmap = None

        self.main_layout = QVBoxLayout(self)

        self.dialog_shadow_effect = QGraphicsDropShadowEffect(self)
        self.dialog_shadow_effect.setBlurRadius(30) 
        self.dialog_shadow_effect.setXOffset(0)   
        self.dialog_shadow_effect.setYOffset(0) 
        self.dialog_shadow_effect.setColor(QColor("#8A2BE2"))
        self.setGraphicsEffect(self.dialog_shadow_effect)
        self.main_layout.setContentsMargins(0, 0, 0, 0) 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | 
            QPainter.RenderHint.SmoothPixmapTransform
        )
        
        safe_margin = 1
        paint_rect = QRectF(self.rect()).adjusted(safe_margin, safe_margin, -safe_margin, -safe_margin)
        
        painter.setPen(Qt.PenStyle.NoPen)

        border_color = QColor("#8A2BE2")
        painter.setBrush(border_color)
        painter.drawRoundedRect(paint_rect, 10, 10)

        border_thickness = 1.0 
        inner_rect = paint_rect.adjusted(border_thickness, border_thickness, -border_thickness, -border_thickness)
        
        inner_corner_radius = max(0, 10 - border_thickness) 

        painter.setBrush(QColor("#161B40"))
        painter.drawRoundedRect(inner_rect, inner_corner_radius, inner_corner_radius)

        if self.light_pixmap and not self.light_pixmap.isNull():
            clip_path = QPainterPath()
            clip_path.addRoundedRect(inner_rect, inner_corner_radius, inner_corner_radius)
            painter.setClipPath(clip_path)
            
            try:
                parts = self.background_position.split()
                if len(parts) == 2:
                    x_str, y_str = parts
                    x_percent = float(x_str.strip('%'))
                    y_percent = float(y_str.strip('%'))
                    
                    scaled_width = self.width() * 1.5
                    scaled_height = self.height() * 1.5
                    scaled_pixmap = self.light_pixmap.scaled(
                        int(scaled_width), int(scaled_height),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )

                    pannable_width = scaled_pixmap.width() - self.width()
                    pannable_height = scaled_pixmap.height() - self.height()
                    
                    draw_x = -pannable_width * (x_percent / 100.0)
                    draw_y = -pannable_height * (y_percent / 100.0)
                    
                    painter.drawPixmap(int(draw_x), int(draw_y), scaled_pixmap)
            except Exception as e:
                print(f"Erro ao posicionar imagem de fundo: {e}")

        painter.setBrush(Qt.BrushStyle.NoBrush)

        glow_color = QColor("#8A2BE2") 
        glow_color.setAlpha(150)
        pen_glow = QPen(glow_color, 2)
        painter.setPen(pen_glow)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)

        line_color = QColor("#2A3042")
        pen_line = QPen(line_color, 1)
        painter.setPen(pen_line)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        
        region = QRegion(path.toFillPolygon().toPolygon())
        
        self.setMask(region)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton: self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event: QMouseEvent): self.old_pos = None


class SettingsDialog(ModernDialog):
    def __init__(self, parent=None):
        super().__init__(parent, background_position=config.DIALOG_BG_POSITIONS.get("settings", "center")) 
        self.setWindowTitle("Configurações")
        self.setFixedSize(400, 200)
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        self.title_label = QLabel("Configurações")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 15px; color: #f0f0f0; background:transparent;")

        self.start_win_checkbox = QCheckBox("Iniciar com o Windows")
        self.start_win_checkbox.setStyleSheet("QCheckBox { color: #f0f0f0; font-size: 14px; background:transparent; }")

        self.close_to_tray_checkbox = QCheckBox("Manter na bandeja do sistema ao fechar")
        self.close_to_tray_checkbox.setStyleSheet("QCheckBox { color: #f0f0f0; font-size: 14px; background:transparent; }")

        self.save_button = QPushButton("Salvar")
        self.cancel_button = QPushButton("Cancelar")

        button_style = "QPushButton { background-color: #4a5162; border: none; padding: 8px 16px; border-radius: 5px; color: #f0f0f0; } QPushButton:hover { background-color: #5a6378; }"
        submit_button_style = "QPushButton { background-color: #007AFF; border: none; padding: 8px 16px; border-radius: 5px; color: white; } QPushButton:hover { background-color: #0056b3; }"
        
        self.save_button.setStyleSheet(submit_button_style)
        self.cancel_button.setStyleSheet(button_style)
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.save_button)

        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.start_win_checkbox)
        self.main_layout.addWidget(self.close_to_tray_checkbox)
        self.main_layout.addStretch()
        self.main_layout.addLayout(buttons_layout)
        
    def get_settings(self) -> dict:
        return {
        "start_with_windows": self.start_win_checkbox.isChecked(),
        "close_to_tray": self.close_to_tray_checkbox.isChecked()
    }

    def set_settings(self, settings_data: dict):
        self.start_win_checkbox.setChecked(settings_data.get("start_with_windows", False))
        self.close_to_tray_checkbox.setChecked(settings_data.get("close_to_tray", False))


class AddGameDialog(ModernDialog):
    def __init__(self, threadpool, existing_games, parent=None):
        super().__init__(parent, background_position=config.DIALOG_BG_POSITIONS.get("add_game", "center")) 
        self.threadpool = threadpool
        self.existing_games = existing_games
        self.editing_game_data = None
        self.setFixedSize(500, 280)
        self._setup_ui()
        
    def _setup_ui(self):
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.title_label = QLabel("Adicionar Novo Jogo")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px; color: #f0f0f0; background:transparent;")
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        input_style = "background-color: #111827; border: 1px solid #323d52; border-radius: 5px; padding: 8px; color: #f0f0f0;"
        button_style = "QPushButton { background-color: #4a5162; border: none; padding: 8px; border-radius: 5px; color: #f0f0f0; } QPushButton:hover { background-color: #5a6378; }"
        self.name_input = QLineEdit()
        self.process_input = QLineEdit()
        self.save_path_input = QLineEdit()
        self.name_input.setStyleSheet(input_style)
        self.process_input.setStyleSheet(input_style)
        self.save_path_input.setStyleSheet(input_style)
        self.completer = QCompleter([])
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer_model = QStringListModel()
        self.completer.setModel(self.completer_model)
        self.name_input.setCompleter(self.completer)
        self.name_input.textChanged.connect(self.update_autocomplete)
        self.completer.activated.connect(self.on_suggestion_selected)
        self.is_manual_selection = False
        self.browse_process_button = QPushButton("Procurar...")
        self.browse_save_path_button = QPushButton("Procurar...")
        self.browse_process_button.setStyleSheet(button_style)
        self.browse_save_path_button.setStyleSheet(button_style)
        self.browse_process_button.clicked.connect(self.find_process_path)
        self.browse_save_path_button.clicked.connect(self.find_save_folder_path)
        process_layout = QHBoxLayout()
        process_layout.addWidget(self.process_input)
        process_layout.addWidget(self.browse_process_button)
        save_path_layout = QHBoxLayout()
        save_path_layout.addWidget(self.save_path_input)
        save_path_layout.addWidget(self.browse_save_path_button)
        form_layout.addRow("Nome do Jogo:", self.name_input)
        form_layout.addRow("Executável do Jogo (.exe):", process_layout)
        form_layout.addRow("Pasta de Save:", save_path_layout)
        self.submit_button = QPushButton("Adicionar Jogo")
        self.cancel_button = QPushButton("Cancelar")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 12px; padding-left: 5px; background:transparent;")
        self.error_label.hide()
        submit_button_style = "QPushButton { background-color: #007AFF; border: none; padding: 8px; border-radius: 5px; color: white; } QPushButton:hover { background-color: #0056b3; }"
        self.submit_button.setStyleSheet(submit_button_style)
        self.cancel_button.setStyleSheet(button_style)
        self.submit_button.clicked.connect(self.validate_and_accept)
        self.name_input.textChanged.connect(self.error_label.hide)
        self.process_input.textChanged.connect(self.error_label.hide)
        self.save_path_input.textChanged.connect(self.error_label.hide)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.submit_button)
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addLayout(form_layout)
        self.main_layout.addWidget(self.error_label)
        self.main_layout.addStretch()
        self.main_layout.addLayout(buttons_layout)
        
    def set_edit_mode(self, game_data: dict):
        self.editing_game_data = game_data
        self.title_label.setText("Editar Jogo")
        self.name_input.setText(game_data.get("name", ""))
        self.process_input.setText(game_data.get("process", ""))
        self.save_path_input.setText(game_data.get("save_path", ""))
        self.submit_button.setText("Salvar Alterações")

    def get_game_data(self) -> dict:
        game_data = { "name": self.name_input.text().strip(), "process": self.process_input.text().strip(), "save_path": self.save_path_input.text().strip() }
        if self.editing_game_data: game_data["is_favorite"] = self.editing_game_data.get("is_favorite", False)
        return game_data

    @pyqtSlot(str)
    def on_suggestion_selected(self, text: str):
        self.name_input.setText(text)

    def update_autocomplete(self, text: str):
        if self.is_manual_selection: self.is_manual_selection = False; return
        if len(text) < 3: self.completer_model.setStringList([]); return
        searcher = AutocompleteSearcher(text)
        searcher.signals.finished.connect(self.set_autocomplete_results)
        self.threadpool.start(searcher)

    @pyqtSlot(object)
    def set_autocomplete_results(self, results: list):
        if self.name_input.text() in results and self.name_input.text() != "": self.completer_model.setStringList([]); self.completer.popup().hide()
        else: self.completer_model.setStringList(results)
    
    def find_process_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar Executável", "", "Executables (*.exe)");
        if file_path: self.process_input.setText(os.path.basename(file_path))

    def find_save_folder_path(self):
        start_dir = os.getenv('APPDATA')
        if not start_dir or not os.path.isdir(start_dir): start_dir = ""
        folder_path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Save", start_dir)
        if folder_path: self.save_path_input.setText(folder_path)

    def validate_and_accept(self):
        name = self.name_input.text().strip()
        process = self.process_input.text().strip()
        save_path = self.save_path_input.text().strip()
        if not all([name, process, save_path]): self.error_label.setText("Todos os campos são obrigatórios."); self.error_label.show(); return
        if not process.lower().endswith('.exe'): self.error_label.setText("O processo do jogo deve ser um arquivo .exe."); self.error_label.show(); return
        other_games = [g for g in self.existing_games if g != self.editing_game_data]
        if any(g['process'].lower() == process.lower() for g in other_games): self.error_label.setText(f"O processo '{process}' já está sendo monitorado."); self.error_label.show(); return
        self.error_label.hide()
        super().accept()

class ConfirmationDialog(ModernDialog):
    def __init__(self, parent=None,
                 icon_path: str = None,
                 title: str = "Confirmação",
                 text: str = "",
                 informative_text: str = "",
                 accept_text: str = "OK",
                 reject_text: str = "Cancelar"):
        
        super().__init__(parent, background_position=config.DIALOG_BG_POSITIONS.get("confirmation", "50% 50%"))
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.setModal(True)
        
        self.main_layout.setContentsMargins(0, 0, 0, 20)
        self.main_layout.setSpacing(20)

        title_bar_layout = QHBoxLayout()
        title_bar_layout.setContentsMargins(15, 10, 10, 10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #f0f0f0; font-size: 14px; font-weight: bold; background: transparent;")
        
        self.close_button = SvgPushButton(config.CLOSE_ICON_PATH, parent=self)
        self.close_button.setFixedSize(30, 30)
        self.close_button.setSvgIconSize(QSize(12, 12))
        self.close_button.setStyleSheet("""
            SvgPushButton { background-color: transparent; border: none; border-radius: 5px; }
            SvgPushButton:hover { background-color: #E81123; }
        """)
        self.close_button.clicked.connect(self.reject)

        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(self.close_button)
        
        self.main_layout.addLayout(title_bar_layout)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(25, 10, 25, 10)
        content_layout.setSpacing(20)

        if icon_path and os.path.exists(icon_path):
            self.icon_widget = QSvgWidget(icon_path)
            self.icon_widget.setFixedSize(64, 64)
            content_layout.addWidget(self.icon_widget)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: #f0f0f0; font-size: 18px; font-weight: bold; background: transparent;")
        
        self.informative_label = QLabel(informative_text)
        self.informative_label.setWordWrap(True)
        self.informative_label.setStyleSheet("color: #8a95b3; font-size: 14px; background: transparent;")

        text_layout.addWidget(self.text_label)
        text_layout.addWidget(self.informative_label)
        text_layout.addStretch()

        content_layout.addLayout(text_layout)
        self.main_layout.addLayout(content_layout)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(25, 0, 25, 0)
        button_layout.addStretch()

        self.reject_button = QPushButton(reject_text)
        self.reject_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reject_button.setStyleSheet("""
            QPushButton {
                background-color: #4a5162; border: none; padding: 10px 22px;
                border-radius: 5px; color: #f0f0f0; font-weight: bold;
            }
            QPushButton:hover { background-color: #5a6378; }
        """)
        self.reject_button.clicked.connect(self.reject)

        self.accept_button = QPushButton(accept_text)
        self.accept_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.accept_button.setStyleSheet("""
            QPushButton {
                background-color: #E53935; border: none; padding: 10px 22px;
                border-radius: 5px; color: white; font-weight: bold;
            }
            QPushButton:hover { background-color: #F44336; }
        """)
        self.accept_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.reject_button)
        button_layout.addWidget(self.accept_button)

        self.main_layout.addLayout(button_layout)
