import sys
import ctypes
import threading
import time
import winreg
from PyQt5.QtWidgets import (QApplication, QLabel, QCheckBox, QSlider, QVBoxLayout, QHBoxLayout, QWidget, 
                             QMenu, QAction, QSystemTrayIcon, QMessageBox)
from PyQt5.QtGui import QPixmap, QImage, QCursor, QIcon, QColor
from PyQt5.QtCore import Qt, QTimer, QObject
import pygame
import random
import os

class OverlayWindow(QWidget):
    def __init__(self, image_path):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.X11BypassWindowManagerHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(0, 0, 0, 0)  # Initial size (will be updated)
        
        # Load the image
        self.image = QImage(image_path)
        self.pixmap = QPixmap.fromImage(self.image)
        self.label = QLabel(self)
        self.label.setPixmap(self.pixmap)
        self.label.setAttribute(Qt.WA_TranslucentBackground)

    def update_position(self, x, y):
        self.resize(self.pixmap.size())
        self.move(x - self.pixmap.width() // 2, y - self.pixmap.height() // 2)
        self.show()

    def hide_overlay(self):
        self.hide()

class ColorChanger(QObject):
    def __init__(self, label):
        super().__init__()
        self.label = label
        self.timer = QTimer()
        self.timer.timeout.connect(self.change_color)
        self.timer.start(2000)  # Change color every 2 seconds
        self.colors = [
            QColor(255, 0, 0),    # Red
            QColor(255, 127, 0),  # Orange
            QColor(255, 255, 0),  # Yellow
            QColor(0, 255, 0),    # Green
            QColor(0, 0, 255),    # Blue
            QColor(75, 0, 130),   # Indigo
            QColor(148, 0, 211)   # Violet
        ]

    def change_color(self):
        color = random.choice(self.colors)
        self.label.setStyleSheet(f"color: {color.name()}; font-size: 22px; font-weight: bold; padding: 10px;")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hitmarker MLG Edition")
        self.setGeometry(100, 100, 600, 300)
        
        # Set application icon
        self.setWindowIcon(QIcon('icon.ico'))

        # Initialize pygame for audio
        pygame.mixer.init()
        self.sound_enabled = True
        self.volume = 1.0  # Default volume (1.0 means 100%)

        # Load the sound
        self.sound = pygame.mixer.Sound('hm.mp3')
        self.sound.set_volume(self.volume)

        # Create layout and widgets
        main_layout = QHBoxLayout()
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)

        # Apply Windows 11-like styling
        self.setStyleSheet("""
            QWidget {
                background-color: #F3F3F3;
                color: #000000;
                font-family: Segoe UI, Arial, sans-serif;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: #000000;
                border: none;
            }
            QCheckBox {
                color: #000000;
                spacing: 5px;
            }
            QSlider {
                background-color: #E1E1E1;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #0078D4;
                border: 1px solid #0056A0;
                width: 20px;
                height: 20px;
                margin: -6px 0;
                border-radius: 10px;
            }
            QSlider::groove:horizontal {
                background: #D6D6D6;
                height: 6px;
                border-radius: 3px;
            }
        """)

        # Title
        title_label = QLabel("Hitmarker MLG Edition")
        title_label.setAlignment(Qt.AlignCenter)
        settings_layout.addWidget(title_label)

        # Color changer for title label
        self.color_changer = ColorChanger(title_label)

        # Sound checkbox
        self.sound_checkbox = QCheckBox("Enable Sound")
        self.sound_checkbox.setChecked(True)
        self.sound_checkbox.stateChanged.connect(self.update_sound_enabled)
        settings_layout.addWidget(self.sound_checkbox)

        # Volume controls
        volume_layout = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.update_volume)
        
        self.volume_label = QLabel("100%")
        self.volume_label.setFixedWidth(50)
        
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        
        settings_layout.addLayout(volume_layout)

        # Graphic checkbox
        self.graphic_checkbox = QCheckBox("Enable Graphic")
        self.graphic_checkbox.setChecked(True)
        settings_layout.addWidget(self.graphic_checkbox)

        # Startup checkbox
        self.startup_checkbox = QCheckBox("Launch at Startup")
        self.startup_checkbox.setChecked(self.is_startup())
        self.startup_checkbox.stateChanged.connect(self.toggle_startup)
        settings_layout.addWidget(self.startup_checkbox)

        # Image display
        image_label = QLabel()
        self.image_pixmap = QPixmap('doritos.png')
        scaled_pixmap = self.image_pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        image_label.setPixmap(scaled_pixmap)
        image_label.setFixedSize(64, 64)  # Fixed size for the image

        main_layout.addLayout(settings_layout)
        main_layout.addWidget(image_label)

        self.setLayout(main_layout)

        # Create the overlay window
        self.overlay = OverlayWindow('hm.png')

        # Timer for periodically checking mouse click
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_mouse_click)
        self.timer.start(10)  # Check every 10 ms

        # Debounce settings
        self.last_click_time = 0
        self.debounce_interval = 0.1  # 100 ms debounce interval

        self.is_running = True
        self.track_thread = threading.Thread(target=self.track_mouse)
        self.track_thread.daemon = True
        self.track_thread.start()

        # System tray icon setup
        self.tray_icon = QSystemTrayIcon(QIcon('icon.ico'), self)
        self.tray_icon_menu = QMenu()
        
        self.restore_action = QAction("Restore")
        self.restore_action.triggered.connect(self.restore_window)
        self.tray_icon_menu.addAction(self.restore_action)
        
        self.quit_action = QAction("Exit")
        self.quit_action.triggered.connect(self.quit_application)
        self.tray_icon_menu.addAction(self.quit_action)

        self.tray_icon.setContextMenu(self.tray_icon_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

        # Start the application in minimized state if specified
        if self.is_startup():
            self.showMinimized()
        else:
            self.show()

    def update_sound_enabled(self, state):
        self.sound_enabled = (state == Qt.Checked)

    def update_volume(self):
        self.volume = self.volume_slider.value() / 100.0
        self.sound.set_volume(self.volume)
        self.volume_label.setText(f"{int(self.volume * 100)}%")

    def check_mouse_click(self):
        if self.graphic_checkbox.isChecked() and self.is_mouse_button_down():
            current_time = time.time()
            if current_time - self.last_click_time > self.debounce_interval:
                x, y = self.get_mouse_position()
                self.overlay.update_position(x, y)
                QTimer.singleShot(50, self.overlay.hide_overlay)  # Hide after 50 ms
                if self.sound_enabled:
                    self.sound.play()
                self.last_click_time = current_time

    def is_mouse_button_down(self):
        # Check if the left mouse button is down
        return ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000 != 0

    def get_mouse_position(self):
        # Get the global mouse position using QCursor
        pos = QCursor.pos()
        return pos.x(), pos.y()

    def track_mouse(self):
        while self.is_running:
            # Mouse tracking logic can be placed here if needed
            pass

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.restore_window()

    def restore_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_application(self):
        self.is_running = False
        self.close()
        QApplication.quit()

    def set_startup_status(self, enable):
        """Set the application to start on Windows boot"""
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "HitmarkerMLG"
        executable_path = os.path.abspath(sys.argv[0])
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(registry_key, value_name, 0, winreg.REG_SZ, executable_path)
            else:
                try:
                    winreg.DeleteValue(registry_key, value_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(registry_key)
        except Exception as e:
            print(f"Failed to modify registry: {e}")

    def toggle_startup(self, state):
        """Toggle the startup status and show a message box"""
        enable = (state == Qt.Checked)
        self.set_startup_status(enable)
        message = "The program will start automatically on Windows boot." if enable else "The program will not start automatically on Windows boot."
        QMessageBox.information(self, "Startup Status", message)

    def is_startup(self):
        """Checks if the application is set to start on Windows boot"""
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        value_name = "HitmarkerMLG"
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ)
            try:
                value, regtype = winreg.QueryValueEx(registry_key, value_name)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(registry_key)
        except Exception as e:
            print(f"Failed to read registry: {e}")
            return False

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Check if started from startup folder
    minimized_on_startup = len(sys.argv) > 1 and sys.argv[1] == 'minimized'
    
    window = MainWindow()
    if minimized_on_startup:
        window.showMinimized()
    else:
        window.show()
        
    sys.exit(app.exec_())
