from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QCheckBox, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QBrush

class SettingsPage(QWidget):
    settings_saved = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel("Configurações")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #f0f0f0; background: transparent;")
        layout.addWidget(title_label)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #4a5162;")
        layout.addWidget(line)

        self.start_win_checkbox = QCheckBox("Iniciar AltCloud com o Windows")
        self.start_win_checkbox.setStyleSheet("color: #f0f0f0; background: transparent;")
        layout.addWidget(self.start_win_checkbox)

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        btn_style = "QPushButton { background-color: #4a5162; border: none; padding: 8px 16px; border-radius: 5px; color: #f0f0f0; } QPushButton:hover { background-color: #5a6378; }"
        
        self.save_button = QPushButton("Salvar")
        self.save_button.setStyleSheet(btn_style)
        self.save_button.clicked.connect(self.settings_saved)

        self.cancel_button = QPushButton("Voltar")
        self.cancel_button.setStyleSheet(btn_style)
        self.cancel_button.clicked.connect(self.cancelled)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#2a2d34"))
        gradient.setColorAt(1.0, QColor("#21252b"))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)