import os
import re
import json
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
                             QWidget, QScrollArea, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEasingCurve, QPropertyAnimation, pyqtSlot, QParallelAnimationGroup, QRectF
from PyQt6.QtGui import QMouseEvent, QFont, QPainter, QColor, QPen, QPainterPath
from PyQt6.QtSvgWidgets import QSvgWidget

from utils import format_bytes, format_timestamp, load_svg_data
import config
from ui_dialogs import ModernDialog, ConfirmationDialog

class SaveCardWidget(QFrame):
    deletion_confirmed = pyqtSignal(object)
    card_removed = pyqtSignal(object)

    def __init__(self, file_data, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.file_data = file_data
        self.is_hovering = False
        self.setMouseTracking(True)
        self.setObjectName("SaveCard")

        self.min_height_anim = QPropertyAnimation(self, b'minimumHeight')
        self.min_height_anim.setDuration(200)
        self.min_height_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.max_height_anim = QPropertyAnimation(self, b'maximumHeight')
        self.max_height_anim.setDuration(200)
        self.max_height_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.animation_group = QParallelAnimationGroup(self)
        self.animation_group.addAnimation(self.min_height_anim)
        self.animation_group.addAnimation(self.max_height_anim)

        self.min_height_anim.valueChanged.connect(self._request_parent_update)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_value = 3

        self._setup_ui()
        self.normal_height = self.sizeHint().height()
        self.expanded_height = self.normal_height + 80
        self.setMinimumHeight(self.normal_height)
        self.setMaximumHeight(self.normal_height)

    def paintEvent(self, event):
        """ Desenha manualmente o fundo e a borda para funcionar com WA_TranslucentBackground. """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        border_color = QColor(102, 178, 255, 178) if self.is_hovering else QColor(255, 255, 255, 39)
        background_color = QColor(30, 35, 45, 178)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        
        painter.fillPath(path, background_color)
        
        pen = QPen(border_color, 1)
        painter.setPen(pen)
        painter.drawPath(path)
        
    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15); self.main_layout.setSpacing(10)
        header_layout = QHBoxLayout()
        name_label = QLabel(self.file_data['name']); name_label.setObjectName("FileName"); name_label.setWordWrap(True)
        self.delete_button = QPushButton("Deletar"); self.delete_button.setFixedSize(90, 35); self.delete_button.setObjectName("DeleteButton")
        self.delete_button.clicked.connect(self._start_deletion_process)
        header_layout.addWidget(name_label); header_layout.addStretch(); header_layout.addWidget(self.delete_button)
        self.main_layout.addLayout(header_layout)
        self.info_container = QWidget()
        info_layout = QHBoxLayout(self.info_container)
        info_layout.setContentsMargins(0, 5, 0, 0); info_layout.setSpacing(20)
        size_widget = self._createInfoBlock(config.SIZE_ICON_PATH, "Tamanho", format_bytes(self.file_data['size']))
        mod_widget = self._createInfoBlock(config.CALENDAR_ICON_PATH, "Modificado", format_timestamp(self.file_data['mod_time']))
        upload_widget = self._createInfoBlock(config.CLOUD_UPLOAD_ICON_PATH, "Último Upload", format_timestamp(self.file_data['upload_time']))
        info_layout.addWidget(size_widget, 1); info_layout.addWidget(mod_widget, 1); info_layout.addWidget(upload_widget, 1)
        self.main_layout.addWidget(self.info_container)
        
        self.confirm_container = QFrame(); self.confirm_container.setObjectName("ConfirmFrame")
        confirm_layout = QVBoxLayout(self.confirm_container); confirm_layout.setContentsMargins(10, 10, 10, 10)
        
        self.warning_label = QLabel("O save será excluído <b>LOCALMENTE e da NUVEM</b>.")
        self.warning_label.setObjectName("WarningLabel")
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        confirm_layout.addWidget(self.warning_label)
        
        buttons_confirm_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancelar"); self.cancel_button.setObjectName("CancelButton")
        self.cancel_button.clicked.connect(self._cancel_deletion_process)
        self.confirm_countdown_button = QPushButton(); self.confirm_countdown_button.setObjectName("ConfirmButton")
        self.confirm_countdown_button.setDisabled(True)
        self.confirm_countdown_button.clicked.connect(lambda: self.deletion_confirmed.emit(self))
        buttons_confirm_layout.addStretch(); buttons_confirm_layout.addWidget(self.cancel_button); buttons_confirm_layout.addWidget(self.confirm_countdown_button); buttons_confirm_layout.addStretch()
        confirm_layout.addLayout(buttons_confirm_layout)
        
        self.main_layout.addWidget(self.confirm_container); self.confirm_container.hide()
        
        self.success_container = QWidget(); 
        success_layout = QVBoxLayout(self.success_container)
        
        success_icon = QSvgWidget()
        success_icon.load(load_svg_data(config.CHECK_ICON_PATH, "#69F0AE"))
        success_icon.setFixedSize(32, 32)
        success_layout.addWidget(success_icon, 0, Qt.AlignmentFlag.AlignCenter)

        success_text_label = QLabel("Excluído com Sucesso")
        font = success_text_label.font(); font.setBold(True); success_text_label.setFont(font)
        success_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_text_label.setStyleSheet("color: #69F0AE; font-size: 16px; background: transparent;")
        
        success_layout.addWidget(success_text_label)
        
        self.main_layout.addWidget(self.success_container); self.success_container.hide()
        self.update_style()

    def _request_parent_update(self):
        """
        Força o widget pai a se redesenhar. É crucial para limpar os artefatos
        deixados pela animação ao usar fundos translúcidos.
        """
        if self.parentWidget():
            self.parentWidget().update()

    def _start_deletion_process(self):
        self.delete_button.hide()
        self.confirm_container.show()
        self.countdown_value = 3
        self.confirm_countdown_button.setText(f"Confirmar ({self.countdown_value})")
        self.countdown_timer.start()
        current_height = self.height()
        self.min_height_anim.setStartValue(current_height)
        self.min_height_anim.setEndValue(self.expanded_height)
        self.max_height_anim.setStartValue(current_height)
        self.max_height_anim.setEndValue(self.expanded_height)
        self.animation_group.start()

    def _cancel_deletion_process(self):
        self.countdown_timer.stop()
        self.confirm_countdown_button.setDisabled(True)
        self.confirm_container.hide()
        self.delete_button.show()
        QTimer.singleShot(0, self._start_shrink_animation)

    def _start_shrink_animation(self):
        current_height = self.height()
        self.min_height_anim.setStartValue(current_height)
        self.min_height_anim.setEndValue(self.normal_height)
        self.max_height_anim.setStartValue(current_height)
        self.max_height_anim.setEndValue(self.normal_height)
        self.animation_group.start()

    def _update_countdown(self):
        self.countdown_value -= 1; self.confirm_countdown_button.setText(f"Confirmar ({self.countdown_value})")
        if self.countdown_value == 0:
            self.countdown_timer.stop(); self.confirm_countdown_button.setText("EXCLUIR PERMANENTEMENTE"); self.confirm_countdown_button.setDisabled(False)

    def show_deleted_state(self):
        self.delete_button.hide(); self.info_container.hide(); self.confirm_container.hide(); self.success_container.show()
        self.setMinimumHeight(self.normal_height); self.setMaximumHeight(self.normal_height)
        QTimer.singleShot(2000, lambda: self.card_removed.emit(self))

    def _createInfoBlock(self, icon_path, label_text, value_text):
        widget = QWidget(); layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0); layout.setSpacing(10)
        icon = QSvgWidget(); icon.load(load_svg_data(icon_path, "#8a95b3")); icon.setFixedSize(24, 24)
        text_layout = QVBoxLayout(); text_layout.setSpacing(0)
        label = QLabel(label_text); label.setObjectName("InfoLabel")
        value = QLabel(value_text); value.setObjectName("InfoValue"); value.setWordWrap(True)
        text_layout.addWidget(label); text_layout.addWidget(value)
        layout.addWidget(icon); layout.addLayout(text_layout); layout.addStretch()
        return widget

    def update_style(self):
        self.setStyleSheet(f"""
            #SaveCard {{ border-radius: 8px; }}
            #FileName, #InfoValue {{ color: #f0f0f0; font-weight: bold; background: transparent; }}
            #FileName {{ font-size: 16px; }} #InfoValue {{ font-size: 13px; }} #InfoLabel {{ color: #8a95b3; font-size: 11px; background: transparent; }}
            #DeleteButton, #ConfirmButton, #CancelButton {{ border: none; border-radius: 5px; font-weight: bold; padding: 8px 12px; }}
            #DeleteButton {{ background-color: #a62626; color: white; }} #DeleteButton:hover {{ background-color: #E53935; }}
            #CancelButton {{ background-color: #4a5162; color: #f0f0f0; }} #CancelButton:hover {{ background-color: #5a6378; }}
            #ConfirmButton:disabled {{ background-color: #333; color: #777; }}
            #ConfirmButton:!disabled {{ background-color: #E53935; color: white; }}
            #ConfirmButton:!disabled:hover {{ background-color: #F44336; }}
            #ConfirmFrame {{ background-color: transparent; border: none; }}
            #WarningLabel {{ 
                color: #FFC107; /* Amarelo mais vibrante */
                background-color: rgba(60, 65, 75, 0.5); /* Fundo semi-transparente para destaque */
                border-radius: 5px;
                padding: 8px;
                font-size: 12px; /* Aumenta um pouco a fonte */
                font-weight: bold; /* Garante que seja negrito */
                margin-bottom: 10px; /* Espaçamento abaixo da label */
            }}
        """)

    def enterEvent(self, event: QMouseEvent):
        self.is_hovering = True; self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QMouseEvent):
        self.is_hovering = False; self.update()
        super().leaveEvent(event)


class InfoDialog(ModernDialog):
    deletion_requested = pyqtSignal(list)

    def __init__(self, game_data, config_dir, parent=None):
        super().__init__(parent, background_position=config.DIALOG_BG_POSITIONS.get("info", "center"))
        self.game_data = game_data; self.config_dir = config_dir; self.local_filenames = []
        self.setMinimumSize(720, 520)
        self._setup_ui()
        self._populate_info()

    def _setup_ui(self):
        self.main_layout.setContentsMargins(20, 20, 20, 20); self.main_layout.setSpacing(15)
        title = QLabel(f"Gerenciador de Saves - {self.game_data.get('name', '')}")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #f0f0f0; background: transparent; padding-bottom: 5px;")
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setFrameShadow(QFrame.Shadow.Sunken); line.setStyleSheet("background-color: #4a5162;")
        self.main_layout.addWidget(title); self.main_layout.addWidget(line)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setObjectName("InfoScrollArea")
        scroll_area.setStyleSheet("""
            #InfoScrollArea { border: 1px solid #323d52; background-color: transparent; border-radius: 5px; }
            QScrollBar:vertical { border: none; background: transparent; width: 10px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: #4a5162; min-height: 20px; border-radius: 5px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        
        scroll_content = QWidget()
        scroll_content.setAutoFillBackground(True)
        scroll_content.setObjectName("ScrollContent"); scroll_content.setStyleSheet("#ScrollContent { background: transparent; }")
        self.files_layout = QVBoxLayout(scroll_content)
        self.files_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.files_layout.setSpacing(10)
        scroll_area.setWidget(scroll_content)
        self.main_layout.addWidget(scroll_area, 1)
        bottom_layout = QHBoxLayout()
        self.delete_all_button = QPushButton("Excluir Todos"); self.delete_all_button.setObjectName("DeleteAllButton")
        self.delete_all_button.clicked.connect(self._handle_delete_all)
        self.close_button = QPushButton("Voltar"); self.close_button.setObjectName("SecondaryButton")
        self.close_button.clicked.connect(self.accept)
        bottom_layout.addWidget(self.delete_all_button); bottom_layout.addStretch(); bottom_layout.addWidget(self.close_button)
        self.main_layout.addLayout(bottom_layout)
        self.setStyleSheet("""
            #DeleteAllButton { background-color: transparent; border: 1px solid #a62626; color: #a62626; padding: 8px 16px; border-radius: 5px; font-weight: bold; }
            #DeleteAllButton:hover { background-color: #a62626; color: white; }
            #SecondaryButton { background-color: #4a5162; border: none; padding: 8px 16px; border-radius: 5px; color: #f0f0f0; font-weight: bold; }
            #SecondaryButton:hover { background-color: #5a6378; }
        """)

    def _check_empty_state(self):
        if self.files_layout.count() == 0:
            if hasattr(self, 'delete_all_button'): self.delete_all_button.hide()
            empty_label = QLabel("Nenhum arquivo de save encontrado para este jogo."); empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #8a95b3; background: transparent; font-size: 14px;"); self.files_layout.addWidget(empty_label)

    def _populate_info(self):
        while self.files_layout.count():
            child = self.files_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        save_path = self.game_data.get('save_path', '')
        if not os.path.isdir(save_path): self._check_empty_state(); return
        files_in_dir = sorted([f for f in os.listdir(save_path) if not f.endswith('.bak') and os.path.isfile(os.path.join(save_path, f))])
        self.local_filenames = [{'name': fn, 'path': os.path.join(save_path, fn), 'size': os.path.getsize(os.path.join(save_path, fn)), 'mod_time': os.path.getmtime(os.path.join(save_path, fn)), 'upload_time': self._get_last_upload_timestamp(fn)} for fn in files_in_dir]
        if not self.local_filenames: self.delete_all_button.setDisabled(True); self._check_empty_state(); return
        self.delete_all_button.setDisabled(False)
        for file_data in self.local_filenames:
            card = SaveCardWidget(file_data)
            card.deletion_confirmed.connect(self._on_deletion_confirmed)
            card.card_removed.connect(self._on_card_removed)
            self.files_layout.addWidget(card)

    def _on_deletion_confirmed(self, card_widget):
        remote_path = self._get_remote_path(card_widget.file_data['name']); self.deletion_requested.emit([remote_path]); card_widget.show_deleted_state()

    @pyqtSlot(object)
    def _on_card_removed(self, card_widget):
        self.local_filenames = [f for f in self.local_filenames if f['name'] != card_widget.file_data['name']]
        card_widget.deleteLater(); self._check_empty_state()

    def _handle_delete_all(self):
        if not self.local_filenames: return
        dialog = ConfirmationDialog(parent=self, icon_path=config.DELETE_ICON_PATH, title="Confirmar Deleção de Todos", text=f"Deletar TODOS os {len(self.local_filenames)} saves para '{self.game_data['name']}'?", informative_text="Esta ação é IRREVERSÍVEL e removerá os saves LOCALMENTE e da NUVEM.", accept_text="Sim, excluir tudo", reject_text="Cancelar")
        if dialog.exec():
            remote_paths = [self._get_remote_path(f['name']) for f in self.local_filenames]; self.deletion_requested.emit(remote_paths); self.accept()

    def _get_last_upload_timestamp(self, filename):
        try:
            sanitized_folder = re.sub(r'[™®©:/\\?*|"<>]+', '', self.game_data['name']).strip()
            status_file_path = os.path.join(config.STATUS_DIR, f"status_{sanitized_folder}_{filename}.json")
            if os.path.exists(status_file_path):
                with open(status_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get("last_upload_timestamp", 0)
        except (IOError, json.JSONDecodeError): pass
        return 0
        
    def _get_remote_path(self, filename):
        sanitized_folder = re.sub(r'[™®©:/\\?*|"<>]+', '', self.game_data['name']).strip()
        return f"{sanitized_folder}/{filename}"