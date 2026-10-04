import sys
import time
import ctypes
import math
import pygame
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, 
    QLabel, QSlider, QInputDialog, QMainWindow, QColorDialog, QDialog, QFormLayout, QLineEdit, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QCursor
from pynput.mouse import Controller as MController, Button
from pynput.keyboard import Controller as KController

mouse = MController()
kb = KController()

# --- GESTOR DE CURSOR GLOBAL DEL SISTEMA ---
class SystemCursorManager:
    def __init__(self):
        self.is_hidden = False
        self.is_windows = sys.platform == 'win32'
        if self.is_windows:
            self.user32 = ctypes.windll.user32
            self.OCR_NORMAL = 32512
            self.SPI_SETCURSORS = 0x0057

    def hide(self):
        if self.is_hidden: return
        if self.is_windows:
            try:
                and_mask = (ctypes.c_ubyte * 32)(*([0xFF] * 32))
                xor_mask = (ctypes.c_ubyte * 32)(*([0x00] * 32))
                blank_cursor = self.user32.CreateCursor(None, 0, 0, 16, 16, and_mask, xor_mask)
                self.user32.SetSystemCursor(blank_cursor, self.OCR_NORMAL)
            except Exception:
                pass
        QApplication.setOverrideCursor(Qt.BlankCursor)
        self.is_hidden = True

    def show(self):
        if not self.is_hidden: return
        if self.is_windows:
            try:
                self.user32.SystemParametersInfoW(self.SPI_SETCURSORS, 0, None, 0)
            except Exception:
                pass
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.is_hidden = False

cursor_mgr = SystemCursorManager()

# --- DIÁLOGO DE CONFIGURACIÓN ---
class ConfigurationDialog(QDialog):
    def __init__(self, parent, widget_elem, elem_type="button"):
        super().__init__(parent)
        self.widget_elem = widget_elem
        self.elem_type = elem_type
        
        title_text = widget_elem.name if hasattr(widget_elem, 'name') else widget_elem.text
        self.setWindowTitle(f"Settings: {title_text}")
        self.setFixedSize(320, 430 if elem_type == "mouse_joy" else 320)

        layout = QVBoxLayout()
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setText(title_text)
        self.name_edit.textChanged.connect(self.change_name)
        form.addRow("✏️ Name:", self.name_edit)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(20, 200)
        self.size_slider.setValue(widget_elem.base_size)
        self.size_slider.valueChanged.connect(self.apply_changes)
        form.addRow("📏 Size:", self.size_slider)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 255)
        self.opacity_slider.setValue(widget_elem.opacity)
        self.opacity_slider.valueChanged.connect(self.apply_changes)
        form.addRow("👻 Opacity:", self.opacity_slider)

        if self.elem_type == "mouse_joy":
            self.distance_slider = QSlider(Qt.Orientation.Horizontal)
            self.distance_slider.setRange(50, 400)
            self.distance_slider.setValue(widget_elem.max_drag)
            self.distance_slider.valueChanged.connect(self.apply_changes)
            form.addRow("📐 Drag Distance:", self.distance_slider)

            self.speed_slider = QSlider(Qt.Orientation.Horizontal)
            self.speed_slider.setRange(1, 100)
            self.speed_slider.setValue(int(widget_elem.speed * 100))
            self.speed_slider.valueChanged.connect(self.apply_changes)
            form.addRow("⚡ Drag Speed:", self.speed_slider)

            self.unlocked_checkbox = QCheckBox("Unlocked / Camera Mode")
            self.unlocked_checkbox.setChecked(widget_elem.unlocked)
            self.unlocked_checkbox.toggled.connect(self.apply_changes)
            form.addRow("📷 Camera Mode:", self.unlocked_checkbox)

        layout.addLayout(form)

        btn_color = QPushButton("🎨 Change Color")
        btn_color.clicked.connect(self.change_color)
        layout.addWidget(btn_color)

        btn_delete = QPushButton("❌ Delete this Element")
        btn_delete.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        btn_delete.clicked.connect(self.delete_element)
        layout.addWidget(btn_delete)

        self.setLayout(layout)
        self.move(QCursor.pos())

    def change_name(self, text):
        if hasattr(self.widget_elem, 'name'):
            self.widget_elem.name = text
        else:
            self.widget_elem.text = text
        self.setWindowTitle(f"Settings: {text}")
        self.widget_elem.update()

    def apply_changes(self):
        self.widget_elem.base_size = self.size_slider.value()
        self.widget_elem.opacity = self.opacity_slider.value()
        if self.elem_type == "mouse_joy":
            self.widget_elem.max_drag = self.distance_slider.value()
            self.widget_elem.speed = self.speed_slider.value() / 100.0
            self.widget_elem.unlocked = self.unlocked_checkbox.isChecked()
        self.widget_elem.update_style()

    def change_color(self):
        color = QColorDialog.getColor(initial=self.widget_elem.color, parent=self, title="Select Color")
        if color.isValid():
            self.widget_elem.color = color
            self.widget_elem.update()

    def delete_element(self):
        self.widget_elem.delete_widget()
        self.close()

# --- ELEMENTOS VIRTUALES ---

class VirtualButton(QWidget):
    def __init__(self, parent_overlay, text, btn_id, color_qcolor, x, y):
        super().__init__(parent_overlay)
        self.parent_overlay = parent_overlay
        self.text = text
        self.btn_id = btn_id
        self.color = color_qcolor
        self.base_size = 60
        self.opacity = 180
        self.setGeometry(x, y, self.base_size, self.base_size)
        self.dragging = False
        self.offset = QPoint()

    def update_style(self):
        self.setGeometry(self.x(), self.y(), self.base_size, self.base_size)
        self.update()

    def paintEvent(self, event):
        if self.opacity == 0: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self.color)
        c.setAlpha(self.opacity)
        painter.setBrush(c)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.base_size, self.base_size)
        text_color = QColor(255, 255, 255, self.opacity)
        painter.setPen(text_color)
        font = QFont("Arial", int(self.base_size / 2.5), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = ConfigurationDialog(self, self, "button")
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging: self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.dragging = False

    def delete_widget(self):
        if self in self.parent_overlay.buttons:
            self.parent_overlay.buttons.remove(self)
        self.deleteLater()

    def get_center(self):
        global_pos = self.mapToGlobal(QPoint(self.base_size // 2, self.base_size // 2))
        return (global_pos.x(), global_pos.y())

class VirtualMouseJoystick(QWidget):
    def __init__(self, parent_overlay, name, axis_x_id, axis_y_id, color_qcolor, x, y, unlocked=False):
        super().__init__(parent_overlay)
        self.parent_overlay = parent_overlay
        self.name = name
        self.axis_x_id = axis_x_id
        self.axis_y_id = axis_y_id
        self.color = color_qcolor
        self.base_size = 60
        self.opacity = 180
        self.max_drag = 150
        self.speed = 1.0
        self.unlocked = unlocked
        self.total_size = self.base_size * 2
        self.setGeometry(x, y, self.total_size, self.total_size)
        self.dragging = False
        self.offset = QPoint()
        
        self.is_active = False
        self.current_mouse_pos = (0.0, 0.0)
        self.reset_phase = 0 # 0: Normal, 1: Esperar movimiento, 2: Esperar click

    def update_style(self):
        self.total_size = self.base_size * 2
        self.setGeometry(self.x(), self.y(), self.total_size, self.total_size)
        self.update()

    def paintEvent(self, event):
        if self.opacity == 0: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c_base = QColor(self.color)
        c_base.setAlpha(int(self.opacity * 0.4))
        painter.setBrush(c_base)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.total_size, self.total_size)
        c_knob = QColor(self.color)
        c_knob.setAlpha(self.opacity)
        painter.setBrush(c_knob)
        knob_size = self.total_size // 2
        painter.drawEllipse(self.total_size // 4, self.total_size // 4, knob_size, knob_size)
        painter.setPen(QColor(255, 255, 255, self.opacity))
        font = QFont("Arial", int(self.total_size / 7), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = ConfigurationDialog(self, self, "mouse_joy")
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging: self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.dragging = False

    def delete_widget(self):
        if self in self.parent_overlay.mouse_joysticks:
            self.parent_overlay.mouse_joysticks.remove(self)
        self.deleteLater()

    def get_center(self):
        global_pos = self.mapToGlobal(QPoint(self.total_size // 2, self.total_size // 2))
        return (global_pos.x(), global_pos.y())

class VirtualWASDJoystick(QWidget):
    def __init__(self, parent_overlay, name, axis_x_id, axis_y_id, color_qcolor, x, y):
        super().__init__(parent_overlay)
        self.parent_overlay = parent_overlay
        self.name = name
        self.axis_x_id = axis_x_id
        self.axis_y_id = axis_y_id
        self.color = color_qcolor
        self.base_size = 60
        self.opacity = 180
        self.total_size = self.base_size * 2
        self.setGeometry(x, y, self.total_size, self.total_size)
        self.dragging = False
        self.offset = QPoint()
        self.knob_pos = QPoint(self.total_size // 4, self.total_size // 4)
        
        self.keys_state = {'w': False, 'a': False, 's': False, 'd': False}

    def update_keys(self, w, a, s, d):
        if w and not self.keys_state['w']: kb.press('w'); self.keys_state['w'] = True
        elif not w and self.keys_state['w']: kb.release('w'); self.keys_state['w'] = False
        
        if a and not self.keys_state['a']: kb.press('a'); self.keys_state['a'] = True
        elif not a and self.keys_state['a']: kb.release('a'); self.keys_state['a'] = False
        
        if s and not self.keys_state['s']: kb.press('s'); self.keys_state['s'] = True
        elif not s and self.keys_state['s']: kb.release('s'); self.keys_state['s'] = False
        
        if d and not self.keys_state['d']: kb.press('d'); self.keys_state['d'] = True
        elif not d and self.keys_state['d']: kb.release('d'); self.keys_state['d'] = False

    def release_all(self):
        for key in self.keys_state:
            if self.keys_state[key]:
                kb.release(key)
                self.keys_state[key] = False

    def update_style(self):
        self.total_size = self.base_size * 2
        self.setGeometry(self.x(), self.y(), self.total_size, self.total_size)
        self.knob_pos = QPoint(self.total_size // 4, self.total_size // 4)
        self.update()

    def paintEvent(self, event):
        if self.opacity == 0: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c_base = QColor(self.color)
        c_base.setAlpha(int(self.opacity * 0.4))
        painter.setBrush(c_base)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.total_size, self.total_size)
        
        c_knob = QColor(self.color)
        c_knob.setAlpha(self.opacity)
        painter.setBrush(c_knob)
        knob_size = self.total_size // 2
        painter.drawEllipse(self.knob_pos.x(), self.knob_pos.y(), knob_size, knob_size)
        
        painter.setPen(QColor(255, 255, 255, self.opacity))
        font = QFont("Arial", int(self.total_size / 8), QFont.Weight.Bold)
        painter.setFont(font)
        # TEXTO (WASD) ELIMINADO
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = ConfigurationDialog(self, self, "kb_joy")
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging: self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.dragging = False

    def delete_widget(self):
        self.release_all()
        if self in self.parent_overlay.kb_joysticks:
            self.parent_overlay.kb_joysticks.remove(self)
        self.deleteLater()

# --- OVERLAY TRANSPARENTE ---

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        virtual_geometry = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_geometry)
        
        self.panel = None
        self.buttons = []
        self.mouse_joysticks = []
        self.kb_joysticks = []
        self.button_states = {}
        
        self.expected_mouse_pos = None
        
        pygame.init()
        pygame.joystick.init()
        self.physical_joystick = None
        self.connect_controller()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_controller)
        self.timer.start(16)

    def connect_controller(self):
        if pygame.joystick.get_count() > 0:
            self.physical_joystick = pygame.joystick.Joystick(0)
            self.physical_joystick.init()

    def process_controller(self):
        pygame.event.pump()
        
        if not self.physical_joystick:
            self.connect_controller()
            if self.physical_joystick and self.panel:
                self.panel.update_controller_name()

        detected_input = None

        if self.physical_joystick:
            for i in range(self.physical_joystick.get_numbuttons()):
                if self.physical_joystick.get_button(i):
                    detected_input = f"🎮 <b>Button:</b> {i} (Use ID <b>{i}</b>)"
                    break

            if not detected_input and self.physical_joystick.get_numhats() > 0:
                hat_x, hat_y = self.physical_joystick.get_hat(0)
                if hat_y == 1: detected_input = "⬆️ <b>D-Pad Up</b> -> Use ID <b>101</b>"
                elif hat_y == -1: detected_input = "⬇️ <b>D-Pad Down</b> -> Use ID <b>102</b>"
                elif hat_x == -1: detected_input = "⬅️ <b>D-Pad Left</b> -> Use ID <b>103</b>"
                elif hat_x == 1: detected_input = "➡️ <b>D-Pad Right</b> -> Use ID <b>104</b>"

            if not detected_input:
                for i in range(self.physical_joystick.get_numaxes()):
                    if i in (0, 1, 2, 3): continue
                    val = self.physical_joystick.get_axis(i)
                    if val > 0.5:
                        detected_input = f"🔫 <b>Trigger (Axis {i}):</b> -> Use ID <b>{200 + i}</b>"
                        break

        if self.panel:
            if not self.physical_joystick:
                self.panel.lbl_detector.setText("⚠ <b>No controller detected</b>")
            elif detected_input:
                self.panel.lbl_detector.setText(f"📡 {detected_input}")
            else:
                self.panel.lbl_detector.setText("📡 <b>Detected:</b> (Press a controller button to see its value)")

        if not self.physical_joystick: return

        # --- BOTONES VIRTUALES ---
        for b in self.buttons:
            is_pressed = False
            if b.btn_id < 100:
                if b.btn_id < self.physical_joystick.get_numbuttons():
                    is_pressed = self.physical_joystick.get_button(b.btn_id)
            elif 100 <= b.btn_id < 200:
                if self.physical_joystick.get_numhats() > 0:
                    hx, hy = self.physical_joystick.get_hat(0)
                    if b.btn_id == 101 and hy == 1: is_pressed = True
                    elif b.btn_id == 102 and hy == -1: is_pressed = True
                    elif b.btn_id == 103 and hx == -1: is_pressed = True
                    elif b.btn_id == 104 and hx == 1: is_pressed = True
            elif b.btn_id >= 200:
                real_axis = b.btn_id - 200
                if real_axis < self.physical_joystick.get_numaxes():
                    if self.physical_joystick.get_axis(real_axis) > 0.5:
                        is_pressed = True

            previous_state = self.button_states.get(b.btn_id, False)
            if is_pressed and not previous_state: self.press_virtual_button(b)
            elif not is_pressed and previous_state: self.release_virtual_button(b)
            self.button_states[b.btn_id] = is_pressed

        # --- JOYSTICK WASD (TECLADO) ---
        KB_DEADZONE = 0.25
        for kj in self.kb_joysticks:
            if kj.axis_x_id < self.physical_joystick.get_numaxes() and kj.axis_y_id < self.physical_joystick.get_numaxes():
                val_x = self.physical_joystick.get_axis(kj.axis_x_id)
                val_y = self.physical_joystick.get_axis(kj.axis_y_id)
                
                center_offset = kj.total_size // 4
                kj.knob_pos = QPoint(int(center_offset + (val_x * center_offset)), int(center_offset + (val_y * center_offset)))
                kj.update()
                
                w = val_y < -KB_DEADZONE
                s = val_y > KB_DEADZONE
                a = val_x < -KB_DEADZONE
                d = val_x > KB_DEADZONE
                kj.update_keys(w, a, s, d)

        # --- JOYSTICK DE RATÓN (CÁMARA) ---
        DEADZONE = 0.15
        for j in self.mouse_joysticks:
            if j.axis_x_id < self.physical_joystick.get_numaxes() and j.axis_y_id < self.physical_joystick.get_numaxes():
                val_x = self.physical_joystick.get_axis(j.axis_x_id)
                val_y = self.physical_joystick.get_axis(j.axis_y_id)
                
                raw_mag = math.hypot(val_x, val_y)

                if raw_mag > DEADZONE:
                    
                    # SISTEMA DE RETRASO DE FOTOGRAMAS PARA EVITAR EL SNAP-BACK (TIRÓN)
                    if j.reset_phase > 0:
                        cx, cy = j.get_center()
                        if j.reset_phase == 1:
                            # Fotograma 2: Tras soltar el ratón, lo movemos en el aire
                            mouse.position = (cx, cy)
                            self.expected_mouse_pos = (cx, cy)
                            j.current_mouse_pos = (float(cx), float(cy))
                            j.reset_phase = 2
                        elif j.reset_phase == 2:
                            # Fotograma 3: Con el ratón en el centro, volvemos a pulsar
                            mouse.press(Button.left)
                            j.reset_phase = 0
                        continue # Evitamos ejecutar movimiento normal mientras hacemos reset

                    scaled_mag = min(1.0, (raw_mag - DEADZONE) / (1.0 - DEADZONE))
                    dir_x = val_x / raw_mag
                    dir_y = val_y / raw_mag
                    
                    move_x = dir_x * scaled_mag
                    move_y = dir_y * scaled_mag

                    cx, cy = j.get_center()

                    if j.unlocked:
                        if not j.is_active:
                            j.is_active = True
                            cursor_mgr.hide()
                            self.hide()
                            QApplication.processEvents()
                            self.expected_mouse_pos = (cx, cy)
                            mouse.position = (cx, cy)
                            mouse.press(Button.left)
                            j.current_mouse_pos = (float(cx), float(cy))

                        curr_x, curr_y = j.current_mouse_pos
                        step_x = move_x * (j.speed * 18.0)
                        step_y = move_y * (j.speed * 18.0)
                        next_x = curr_x + step_x
                        next_y = curr_y + step_y

                        dist_from_center = math.hypot(next_x - cx, next_y - cy)

                        if dist_from_center >= j.max_drag:
                            # Fotograma 1: Soltamos el clic y entramos en fase de reset
                            mouse.release(Button.left)
                            j.reset_phase = 1
                        else:
                            self.expected_mouse_pos = (int(next_x), int(next_y))
                            mouse.position = (next_x, next_y)
                            j.current_mouse_pos = (next_x, next_y)
                    else:
                        target_x = cx + (move_x * j.max_drag)
                        target_y = cy + (move_y * j.max_drag)

                        if not j.is_active:
                            j.is_active = True
                            cursor_mgr.hide()
                            self.hide()
                            QApplication.processEvents()
                            self.expected_mouse_pos = (cx, cy)
                            mouse.position = (cx, cy)
                            mouse.press(Button.left)
                            j.current_mouse_pos = (float(cx), float(cy))

                        curr_x, curr_y = j.current_mouse_pos
                        next_x = curr_x + (target_x - curr_x) * j.speed
                        next_y = curr_y + (target_y - curr_y) * j.speed
                        
                        self.expected_mouse_pos = (int(next_x), int(next_y))
                        mouse.position = (next_x, next_y)
                        j.current_mouse_pos = (next_x, next_y)

                else:
                    if j.is_active:
                        if j.reset_phase == 0:
                            mouse.release(Button.left)
                        j.is_active = False
                        j.reset_phase = 0
                        self.show()

        # Evitar interrupciones con el ratón físico solo si hay joysticks de ratón activos
        any_active_mouse_joy = any(j.is_active for j in self.mouse_joysticks)
        if cursor_mgr.is_hidden and self.expected_mouse_pos and not any_active_mouse_joy:
            curr_pos = QCursor.pos()
            exp_x, exp_y = self.expected_mouse_pos
            if abs(curr_pos.x() - exp_x) > 15 or abs(curr_pos.y() - exp_y) > 15:
                cursor_mgr.show()
                self.expected_mouse_pos = None

    def press_virtual_button(self, widget):
        cx, cy = widget.get_center()
        cursor_mgr.hide()
        self.hide()
        QApplication.processEvents()
        mouse.position = (cx, cy)
        self.expected_mouse_pos = (cx, cy)
        mouse.press(Button.left)

    def release_virtual_button(self, widget):
        mouse.release(Button.left)
        self.show()

# --- PANEL DE CONTROL ---

class ControlPanel(QMainWindow):
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.overlay.panel = self 
        
        self.setWindowTitle("Controller Configurator v7 - Camera Fix")
        self.setFixedSize(380, 420)

        widget = QWidget()
        layout = QVBoxLayout()
        
        self.lbl_controller = QLabel()
        self.update_controller_name()
        layout.addWidget(self.lbl_controller)
        
        self.lbl_detector = QLabel("📡 <b>Detected:</b> (Press a controller button to see its value)")
        self.lbl_detector.setStyleSheet("background-color: #192a56; color: #00a8ff; padding: 15px; border-radius: 6px; font-size: 13px;")
        self.lbl_detector.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_detector.setWordWrap(True)
        layout.addWidget(self.lbl_detector)

        layout.addWidget(QLabel("💡 <i>Use this to play PC games or Emulators flawlessly.</i>"))

        btn_add_button = QPushButton("➕ Add New Mouse Button")
        btn_add_button.clicked.connect(self.create_button)
        layout.addWidget(btn_add_button)

        btn_add_kb_jl = QPushButton("⌨️ Add Left Stick (Movement)")
        btn_add_kb_jl.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        btn_add_kb_jl.clicked.connect(lambda: self.create_kb_joystick("Move", 0, 1))
        layout.addWidget(btn_add_kb_jl)

        btn_add_ms_jr = QPushButton("🖱️ Add Right Stick (Camera)")
        btn_add_ms_jr.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        btn_add_ms_jr.clicked.connect(lambda: self.create_mouse_joystick("Camera", 2, 3, unlocked=True))
        layout.addWidget(btn_add_ms_jr)

        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def update_controller_name(self):
        controller_name = self.overlay.physical_joystick.get_name() if self.overlay.physical_joystick else "No controller detected"
        self.lbl_controller.setText(f"🎮 Controller: <b>{controller_name}</b>")

    def create_button(self):
        text, ok = QInputDialog.getText(self, "New Button", "On-screen name:")
        if not ok or not text: return
        btn_id, ok = QInputDialog.getInt(self, "Controller ID", "Button ID (Check the blue box while pressing it):", 0, 0, 300)
        if not ok: return
        color = QColorDialog.getColor(initial=QColor("#4cd137"), parent=self, title="Select Color")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        new_button = VirtualButton(self.overlay, text, btn_id, color, pos.x() - 30, pos.y() - 30)
        new_button.show()
        self.overlay.buttons.append(new_button)

    def create_kb_joystick(self, name, axis_x, axis_y):
        color = QColorDialog.getColor(initial=QColor("#27ae60"), parent=self, title=f"Color for {name}")
        if not color.isValid(): return
        pos = self.overlay.mapFromGlobal(QCursor.pos())
        new_joy = VirtualWASDJoystick(self.overlay, name, axis_x, axis_y, color, pos.x() - 60, pos.y() - 60)
        new_joy.show()
        self.overlay.kb_joysticks.append(new_joy)

    def create_mouse_joystick(self, name, axis_x, axis_y, unlocked=False):
        color = QColorDialog.getColor(initial=QColor("#2980b9"), parent=self, title=f"Color for {name}")
        if not color.isValid(): return
        pos = self.overlay.mapFromGlobal(QCursor.pos())
        new_joy = VirtualMouseJoystick(self.overlay, name, axis_x, axis_y, color, pos.x() - 60, pos.y() - 60, unlocked=unlocked)
        new_joy.show()
        self.overlay.mouse_joysticks.append(new_joy)

def on_quit():
    cursor_mgr.show()
    for kj in overlay.kb_joysticks: kj.release_all()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(on_quit)
    overlay = Overlay()
    overlay.show()
    panel = ControlPanel(overlay)
    panel.show()
    sys.exit(app.exec())