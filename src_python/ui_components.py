import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
                             QStackedLayout, QGraphicsDropShadowEffect)
from PyQt6.QtCore import (pyqtSignal, Qt, QTimer, QRectF, QPoint, QPropertyAnimation,
                             QEasingCurve, QSize, QPointF, QByteArray, QEvent, pyqtProperty, QRect)
from PyQt6.QtGui import (QPainter, QColor, QPixmap, QIcon, QPainterPath, QPen, QBrush,
                             QImage, QLinearGradient, QTextOption)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget
from typing import Dict
from utils import load_svg_data
import config

class SvgPushButton(QPushButton):
    def __init__(self, icon_path, icon_size=QSize(24, 24), parent=None):
        super().__init__(parent)
        self.svg_widget = QSvgWidget(self)
        self.svg_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_path = icon_path
        self._icon_size = icon_size
        self.update_icon_color()

    def update_icon_color(self):
        palette = self.palette()
        color = palette.color(self.foregroundRole()).name()
        self.svg_widget.load(load_svg_data(self.icon_path, color))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        icon_rect = QRectF(0, 0, self._icon_size.width(), self._icon_size.height())
        icon_rect.moveCenter(QPointF(self.rect().center()))
        self.svg_widget.setGeometry(icon_rect.toRect())
        
    def setSvgIconSize(self, size):
        self._icon_size = size
        self.resizeEvent(None)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.StyleChange:
            self.update_icon_color()

def extract_dominant_color(pixmap: QPixmap) -> QColor:
    if pixmap.isNull(): return QColor("#00aaff")
    image = pixmap.toImage().scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    dominant_color = QColor(image.pixel(0, 0))
    h, s, v, a = dominant_color.getHsv()
    s = min(s + 60, 255); v = max(v, 150)
    return QColor.fromHsv(h, s, v, a)

class RotatingSvgWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rotation_angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_rotation)
        self._renderer = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def load(self, svg_data: QByteArray):
        self._renderer = QSvgRenderer(svg_data)
        self.update()

    def _update_rotation(self):
        self.rotation_angle = (self.rotation_angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        if not self._renderer: return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.rotation_angle)
        painter.translate(-self.width() / 2, -self.height() / 2)
        self._renderer.render(painter, QRectF(0, 0, self.width(), self.height()))

    def start(self):
        if not self.timer.isActive(): self.timer.start(25)

    def stop(self):
        if self.timer.isActive(): self.timer.stop()

class SvgButton(QWidget):
    clicked = pyqtSignal()
    def __init__(self, icon_path, size, tooltip, hover_color, default_color="#FFFFFF", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_path = icon_path
        self.default_color = default_color
        self.hover_color = hover_color
        self._is_hovering = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.svg_widget = QSvgWidget()
        layout.addWidget(self.svg_widget)
        self.update_icon()

    def update_icon(self):
        color = self.hover_color if self._is_hovering else self.default_color
        self.svg_widget.load(load_svg_data(self.icon_path, color))
        
    def enterEvent(self, event):
        self._is_hovering = True
        self.update_icon()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovering = False
        self.update_icon()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

class GameListItem(QWidget):
    deletion_requested = pyqtSignal(dict)
    edit_requested = pyqtSignal(dict)
    sync_requested = pyqtSignal(dict)
    info_requested = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(dict)

    def __init__(self, game_data: Dict, parent: QWidget = None):
        super().__init__(parent)
        self.game_data = game_data
        self.setFixedSize(162, 232)
        self.setMouseTracking(True)
        self.is_hovering = False
        self.is_running = False
        self.is_syncing = False
        self.sharp_pixmap = QPixmap()
        self.blurred_pixmap = QPixmap()
        self.dominant_color = QColor("#00aaff")
        self.last_modified = 0
        self.last_upload = 0
        self._blur_opacity = 0.0
        self._zoom_factor = 1.0
        self.opacity_animation = QPropertyAnimation(self, b'blurOpacity')
        self.opacity_animation.setDuration(250)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.zoom_animation = QPropertyAnimation(self, b'zoomFactor')
        self.zoom_animation.setDuration(200)
        self.zoom_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._setup_overlay_widgets()
        self.update_favorite_status()

    @pyqtProperty(float)
    def zoomFactor(self): return self._zoom_factor
    @zoomFactor.setter
    def zoomFactor(self, value): self._zoom_factor = value; self.update()

    @pyqtProperty(float)
    def blurOpacity(self): return self._blur_opacity
    @blurOpacity.setter
    def blurOpacity(self, value): self._blur_opacity = value; self.update()

    def enterEvent(self, event):
        if not self.is_hovering:
            self.is_hovering = True
            QTimer.singleShot(0, self.update_overlay_visibility)
            self.opacity_animation.setStartValue(self._blur_opacity)
            self.opacity_animation.setEndValue(1.0)
            self.opacity_animation.start()
            self.zoom_animation.setStartValue(self._zoom_factor)
            self.zoom_animation.setEndValue(1.08)
            self.zoom_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_hovering:
            self.is_hovering = False
            QTimer.singleShot(0, self.update_overlay_visibility)
            self.opacity_animation.setStartValue(self._blur_opacity)
            self.opacity_animation.setEndValue(0.0)
            self.opacity_animation.start()
            self.zoom_animation.setStartValue(self._zoom_factor)
            self.zoom_animation.setEndValue(1.0)
            self.zoom_animation.start()
        super().leaveEvent(event)

    def set_game_image(self, sharp_pixmap, blurred_pixmap, dominant_color):
        self.sharp_pixmap = sharp_pixmap
        self.blurred_pixmap = blurred_pixmap
        self.dominant_color = dominant_color
        self._update_dynamic_styles()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 8, 8)
        painter.setClipPath(path)
        base_rect = QRectF(self.rect())
        new_width = base_rect.width() * self._zoom_factor
        new_height = base_rect.height() * self._zoom_factor
        new_x = base_rect.x() - (new_width - base_rect.width()) / 2
        new_y = base_rect.y() - (new_height - base_rect.height()) / 2
        zoomed_rect = QRectF(new_x, new_y, new_width, new_height)
        if not self.sharp_pixmap.isNull():
            painter.drawPixmap(zoomed_rect, self.sharp_pixmap, QRectF(self.sharp_pixmap.rect()))
        else:
            painter.fillRect(self.rect(), QColor(20, 20, 20))
        if not self.blurred_pixmap.isNull() and self._blur_opacity > 0:
            painter.setOpacity(self._blur_opacity)
            painter.drawPixmap(zoomed_rect, self.blurred_pixmap, QRectF(self.blurred_pixmap.rect()))
            painter.setOpacity(1.0)
        gradient_rect = QRectF(0, self.height() - 80, self.width(), 80)
        gradient = QLinearGradient(gradient_rect.topLeft(), gradient_rect.bottomLeft())
        gradient.setColorAt(0, QColor(0, 0, 0, 0))
        gradient.setColorAt(1, QColor(0, 0, 0, 200))
        painter.fillRect(gradient_rect, gradient)
        painter.setClipping(False)
        pen = QPen(self.dominant_color if self.is_hovering else QColor(255, 255, 255, 30), 2 if self.is_hovering else 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
        if self.is_running and self.running_status_icon_renderer.isValid():
            icon_rect = QRectF(10, 10, 12, 12)
            self.running_status_icon_renderer.render(painter, icon_rect)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        name_rect = QRect(5, 189, 152, 40)
        option = QTextOption(Qt.AlignmentFlag.AlignCenter)
        option.setWrapMode(QTextOption.WrapMode.WordWrap)
        painter.setPen(QColor(0, 0, 0, 180))
        painter.drawText(QRectF(name_rect).translated(QPointF(1, 1)), self.game_data['name'], option)
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(name_rect), self.game_data['name'], option)

    def _setup_overlay_widgets(self):
        self.running_status_icon_renderer = QSvgRenderer(load_svg_data(config.MONITORING_STATUS_PATH))
        
        self.favorite_button = SvgButton(config.FAVORITE_ICON_PATH, 24, "Favoritar", "#E53935", parent=self)
        self.info_button = SvgButton(config.INFO_ICON_PATH, 26, "Info", "#3498db", parent=self)
        self.edit_button = SvgButton(config.EDIT_ICON_PATH, 26, "Editar", "#f1c40f", parent=self)
        self.delete_button = SvgButton(config.DELETE_ICON_PATH, 26, "Remover", "#e74c3c", parent=self)
        self.sync_button = QPushButton("Sincronizar", self)
        self.loading_spinner = RotatingSvgWidget(self)
        self.success_container = QWidget(self)

        self.sync_button_glow = QGraphicsDropShadowEffect()
        self.sync_button_glow.setBlurRadius(25)
        self.sync_button_glow.setColor(QColor(0,0,0,0))
        self.sync_button_glow.setOffset(0,0)
        self.sync_button.setGraphicsEffect(self.sync_button_glow)
        
        self.sync_glow_animation = QPropertyAnimation(self.sync_button_glow, b'color')
        self.sync_glow_animation.setDuration(250)
        
        self.loading_spinner.load(load_svg_data(config.SPINNER_ICON_PATH,"white"))
        self.loading_spinner.setFixedSize(32,32)
        
        s_layout = QHBoxLayout(self.success_container)
        s_layout.setContentsMargins(0,0,0,0)
        s_layout.setSpacing(5)
        self.success_icon = QSvgWidget(self.success_container)
        self.success_icon.load(load_svg_data(config.SUCCESS_SYNC_ICON_PATH,"white"))
        self.success_icon.setFixedSize(28,28)
        self.success_label = QLabel("Sincronizado", self.success_container)
        self.success_label.setStyleSheet("font-size:12px;color:white;background:transparent;")
        s_layout.addWidget(self.success_icon)
        s_layout.addWidget(self.success_label)
        s_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.info_button.clicked.connect(lambda: self.info_requested.emit(self.game_data))
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(self.game_data))
        self.delete_button.clicked.connect(lambda: self.deletion_requested.emit(self.game_data))
        self.sync_button.clicked.connect(lambda: self.sync_requested.emit(self.game_data))
        self.favorite_button.clicked.connect(lambda: self.favorite_toggled.emit(self.game_data))
        
        self.hover_only_widgets=[self.info_button, self.edit_button, self.delete_button, self.sync_button, self.loading_spinner, self.success_container]
        self.static_icons=[]
        for w in self.hover_only_widgets + self.static_icons + [self.favorite_button]: w.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.favorite_button.move(self.width() - self.favorite_button.width() - 5, 5)
        icon_y=int(self.rect().center().y() - self.info_button.height() / 2) - 15
        total_w=self.info_button.width() * 3 + (2 * 20)
        start_x=int((self.width() - total_w) / 2)
        self.info_button.move(start_x, icon_y)
        self.edit_button.move(start_x + self.info_button.width() + 20, icon_y)
        self.delete_button.move(start_x + self.info_button.width() * 2 + 40, icon_y)
        sh=self.sync_button.sizeHint(); sx=int((self.width()-sh.width())/2); sy=int(self.height()-sh.height()-55)
        self.sync_button.move(sx,sy)
        ss=self.loading_spinner.size(); spx=int((self.width()-ss.width())/2); spy=int(self.height()-ss.height()-55)
        self.loading_spinner.move(spx,spy)
        scs=self.success_container.sizeHint(); scx=int((self.width()-scs.width())/2); scy=int(self.height()-scs.height()-55)
        self.success_container.move(scx,scy)
    
    def update_overlay_visibility(self):
        is_fav = self.game_data.get("is_favorite", False)
        for w in [self.info_button, self.edit_button, self.delete_button]:
            w.setVisible(self.is_hovering)
        self.favorite_button.setVisible(self.is_hovering or is_fav)
        self.sync_button.hide()
        self.loading_spinner.hide()
        self.success_container.hide()
        if self.is_hovering:
            if self.is_syncing:
                self.loading_spinner.show()
            elif self.last_modified > self.last_upload:
                self.sync_button.show()
            else:
                self.success_container.show()

    def update_favorite_status(self):
        is_fav = self.game_data.get("is_favorite", False)
        self.favorite_button.default_color = "#E53935" if is_fav else "#FFFFFF"
        self.favorite_button.update_icon()
        self.update()
    
    def update_status(self, is_running, last_modified, last_upload):
        self.is_running = is_running
        self.last_modified = last_modified
        self.last_upload = last_upload
        QTimer.singleShot(0, self.update_overlay_visibility)

    def start_sync_animation(self):
        self.is_syncing = True
        self.loading_spinner.start()
        QTimer.singleShot(0, self.update_overlay_visibility)
    
    def stop_sync_animation(self):
        self.is_syncing = False
        self.loading_spinner.stop()
        QTimer.singleShot(0, self.update_overlay_visibility)
    
    def _update_dynamic_styles(self):
        if hasattr(self, 'sync_button'):
            self.sync_button.setStyleSheet(f"QPushButton{{background-color:rgba(20,20,20,0.7);color:white;border:1px solid {self.dominant_color.name()};padding:8px 14px;border-radius:5px;font-weight:bold;font-size:11px;}}QPushButton:hover{{background-color:rgba(35,35,35,0.9);border:1px solid {self.dominant_color.lighter(120).name()};}}")

class PageIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_count = 0
        self._current_page = 0
        self.setFixedHeight(12)

    def set_page_count(self, count):
        if self._page_count != count:
            self._page_count = count
            self.updateGeometry()
            self.update()

    def set_current_page(self, index):
        if self._current_page != index:
            self._current_page = index
            self.update()

    def sizeHint(self):
        if self._page_count <= 1:
            return QSize(0, 12)
        dot_diameter, dot_spacing = 8, 6
        width = self._page_count * dot_diameter + (self._page_count - 1) * dot_spacing
        return QSize(width, 12)

    def paintEvent(self, event):
        if self._page_count <= 1:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dot_diameter, dot_spacing = 8, 6
        y_pos = (self.height() - dot_diameter) / 2
        for i in range(self._page_count):
            painter.setBrush(QColor("#FFFFFF") if i == self._current_page else QColor(255, 255, 255, 80))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(i * (dot_diameter + dot_spacing)), int(y_pos), dot_diameter, dot_diameter)