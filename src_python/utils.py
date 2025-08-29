import os
import sys
import datetime
import psutil
import winreg
import subprocess
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QByteArray, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtSvg import QSvgRenderer

def is_steam_running():
    return "steam.exe" in (p.name().lower() for p in psutil.process_iter(['name']))

def launch_steam():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
        steam_exe = os.path.join(steam_path, "steam.exe")
        winreg.CloseKey(key)
        
        if os.path.exists(steam_exe):
            subprocess.Popen([steam_exe])
            return True
        else:
            return False
    except (FileNotFoundError, OSError):
        return False

def render_svg_to_pixmap(path: str, size: int, color_override: str = None) -> QPixmap:
    if not os.path.exists(path):
        placeholder = QPixmap(size, size)
        placeholder.fill(QColor("magenta"))
        return placeholder

    with open(path, 'r', encoding='utf-8') as f:
        svg_data = f.read()

    if color_override:
        svg_data = svg_data.replace('currentColor', color_override)
        svg_data = svg_data.replace('#FFFFFF', color_override)
        svg_data = svg_data.replace('white', color_override)
        svg_data = svg_data.replace('#000000', color_override)
        svg_data = svg_data.replace('black', color_override)

    renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
    
    app = QApplication.instance()
    dpr = app.devicePixelRatio() if app else 1.0
    
    pixel_size = int(size * dpr)
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(dpr)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter, QRectF(pixmap.rect()))
    painter.end()
    
    return pixmap

def load_svg_data(path: str, color_override: str = None) -> QByteArray:
    if not os.path.exists(path):
        svg_error = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="magenta"><path d="M0 0h24v24H0z"/></svg>'
        return QByteArray(svg_error.encode('utf-8'))

    with open(path, 'r', encoding='utf-8') as f:
        svg_data = f.read()

    if color_override:
        svg_data = svg_data.replace('currentColor', color_override)
        svg_data = svg_data.replace('#FFFFFF', color_override)
        svg_data = svg_data.replace('white', color_override)
        svg_data = svg_data.replace('#000000', color_override)
        svg_data = svg_data.replace('black', color_override)
    
    return QByteArray(svg_data.encode('utf-8'))


def format_bytes(byte_count):
    if byte_count is None: return "N/A"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while byte_count >= power and n < len(power_labels):
        byte_count /= power
        n += 1
    return f"{byte_count:.2f} {power_labels[n]}"

def format_timestamp(ts):
    if not ts or ts == 0: return "Nunca"
    try:
        return datetime.datetime.fromtimestamp(ts).strftime('%d/%m/%Y às %H:%M')
    except (TypeError, ValueError):
        return "Data inválida"