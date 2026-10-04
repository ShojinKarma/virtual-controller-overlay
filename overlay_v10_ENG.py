import sys
import time
import ctypes
import pygame
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, 
    QLabel, QSlider, QInputDialog, QMainWindow, QColorDialog, QDialog, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QCursor
from pynput.mouse import Controller, Button

mouse = Controller()

# --- GESTOR DE CURSOR GLOBAL DEL SISTEMA (WINDOWS) ---

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
                # Crear máscara transparente (16x16)
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
                # Restaurar cursores nativos del sistema
                self.user32.SystemParametersInfoW(self.SPI_SETCURSORS, 0, None, 0)
            except Exception:
                pass
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.is_hidden = False

cursor_mgr = SystemCursorManager()

# --- INDIVIDUAL CONFIGURATION DIALOG ---

class ConfigurationDialog(QDialog):
    def __init__(self, parent, widget_elem, is_joystick=False):
        super().__init__(parent)
        self.widget_elem = widget_elem
        self.is_joystick = is_joystick
        
        title_text = widget_elem.name if is_joystick else widget_elem.text
        self.setWindowTitle(f"Settings: {title_text}")
        self.setFixedSize(320, 400 if is_joystick else 320)

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

        if self.is_joystick:
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
        if self.is_joystick:
            self.widget_elem.name = text
        else:
            self.widget_elem.text = text
        self.setWindowTitle(f"Settings: {text}")
        self.widget_elem.update()

    def apply_changes(self):
        self.widget_elem.base_size = self.size_slider.value()
        self.widget_elem.opacity = self.opacity_slider.value()
        
        if self.is_joystick:
            self.widget_elem.max_drag = self.distance_slider.value()
            self.widget_elem.speed = self.speed_slider.value() / 100.0
            self.widget_elem.update_style()
        else:
            self.widget_elem.update_style()

    def change_color(self):
        color = QColorDialog.getColor(initial=self.widget_elem.color, parent=self, title="Select Color")
        if color.isValid():
            self.widget_elem.color = color
            self.widget_elem.update()

    def delete_element(self):
        self.widget_elem.delete_widget()
        self.close()

# --- VIRTUAL WIDGETS ---

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
            dlg = ConfigurationDialog(self, self, is_joystick=False)
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def delete_widget(self):
        if self in self.parent_overlay.buttons:
            self.parent_overlay.buttons.remove(self)
        self.deleteLater()

    def get_center(self):
        global_pos = self.mapToGlobal(QPoint(self.base_size // 2, self.base_size // 2))
        return (global_pos.x(), global_pos.y())


class VirtualJoystick(QWidget):
    def __init__(self, parent_overlay, name, axis_x_id, axis_y_id, color_qcolor, x, y):
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
        
        self.total_size = self.base_size * 2
        self.setGeometry(x, y, self.total_size, self.total_size)
        self.dragging = False
        self.offset = QPoint()
        self.is_active = False
        self.current_mouse_pos = (0, 0)

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

        text_color = QColor(255, 255, 255, self.opacity)
        painter.setPen(text_color)
        font = QFont("Arial", int(self.total_size / 7), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = ConfigurationDialog(self, self, is_joystick=True)
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def delete_widget(self):
        if self in self.parent_overlay.joysticks:
            self.parent_overlay.joysticks.remove(self)
        self.deleteLater()

    def get_center(self):
        global_pos = self.mapToGlobal(QPoint(self.total_size // 2, self.total_size // 2))
        return (global_pos.x(), global_pos.y())

# --- TRANSPARENT OVERLAY ---

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        virtual_geometry = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_geometry)
        
        self.panel = None
        self.buttons = []
        self.joysticks = []
        self.button_states = {}
        
        # Posición del ratón que el programa gestiona (para compararla con el movimiento físico)
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

        if not self.physical_joystick:
            return

        # --- VIRTUAL BUTTONS EXECUTION ---
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
            
            if is_pressed and not previous_state:
                self.press_virtual_button(b)
            elif not is_pressed and previous_state:
                self.release_virtual_button(b)
                
            self.button_states[b.btn_id] = is_pressed

        # --- VIRTUAL JOYSTICKS EXECUTION ---
        DEADZONE = 0.2
        for j in self.joysticks:
            if j.axis_x_id < self.physical_joystick.get_numaxes() and j.axis_y_id < self.physical_joystick.get_numaxes():
                val_x = self.physical_joystick.get_axis(j.axis_x_id)
                val_y = self.physical_joystick.get_axis(j.axis_y_id)
                
                if abs(val_x) > DEADZONE or abs(val_y) > DEADZONE:
                    cx, cy = j.get_center()
                    target_x = cx + (val_x * j.max_drag)
                    target_y = cy + (val_y * j.max_drag)

                    if not j.is_active:
                        j.is_active = True
                        cursor_mgr.hide()
                        self.hide()
                        QApplication.processEvents()
                        mouse.position = (cx, cy)
                        self.expected_mouse_pos = (cx, cy)
                        mouse.press(Button.left)
                        j.current_mouse_pos = (cx, cy)
                        self.show()
                    
                    curr_x, curr_y = j.current_mouse_pos
                    next_x = curr_x + (target_x - curr_x) * j.speed
                    next_y = curr_y + (target_y - curr_y) * j.speed
                    
                    mouse.position = (next_x, next_y)
                    self.expected_mouse_pos = (int(next_x), int(next_y))
                    j.current_mouse_pos = (next_x, next_y)
                else:
                    if j.is_active:
                        mouse.release(Button.left)
                        j.is_active = False
                        cx, cy = j.get_center()
                        mouse.position = (cx, cy)
                        self.expected_mouse_pos = (cx, cy)
                        j.current_mouse_pos = (cx, cy)

        # --- DETECCIÓN DE MOVIMIENTO FÍSICO DEL RATÓN ---
        if cursor_mgr.is_hidden and self.expected_mouse_pos:
            curr_pos = QCursor.pos()
            exp_x, exp_y = self.expected_mouse_pos
            # Si el ratón real está a más de 10 píxeles de donde lo dejó nuestro script, 
            # significa que el usuario ha movido el ratón físico intencionadamente.
            if abs(curr_pos.x() - exp_x) > 10 or abs(curr_pos.y() - exp_y) > 10:
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
        # NOTA: Ya no llamamos a cursor_mgr.show() aquí.
        # Se quedará oculto hasta que muevas el ratón.

# --- CONTROL PANEL ---

class ControlPanel(QMainWindow):
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.overlay.panel = self 
        
        self.setWindowTitle("Controller Configurator v5")
        self.setFixedSize(380, 370)

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

        layout.addWidget(QLabel("💡 <i>Use the monitor above to find the ID.<br>RIGHT-CLICK any button to adjust it.</i>"))

        btn_add_button = QPushButton("➕ Add New Button")
        btn_add_button.clicked.connect(self.create_button)
        layout.addWidget(btn_add_button)

        btn_add_jl = QPushButton("🕹️ Add Left Joystick (L)")
        btn_add_jl.clicked.connect(lambda: self.create_joystick("Stick L", 0, 1))
        layout.addWidget(btn_add_jl)

        btn_add_jr = QPushButton("🕹️ Add Right Joystick (R)")
        btn_add_jr.clicked.connect(lambda: self.create_joystick("Stick R", 2, 3))
        layout.addWidget(btn_add_jr)

        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def update_controller_name(self):
        controller_name = self.overlay.physical_joystick.get_name() if self.overlay.physical_joystick else "No controller detected"
        self.lbl_controller.setText(f"🎮 Controller: <b>{controller_name}</b>")

    def create_button(self):
        text, ok1 = QInputDialog.getText(self, "New Button", "On-screen name:")
        if not ok1 or not text: return
        
        btn_id, ok2 = QInputDialog.getInt(self, "Controller ID", "Button ID (Check the blue box while pressing it):", 0, 0, 300)
        if not ok2: return

        color = QColorDialog.getColor(initial=QColor("#4cd137"), parent=self, title="Select Button Color")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        new_button = VirtualButton(self.overlay, text, btn_id, color, pos.x() - 30, pos.y() - 30)
        new_button.show()
        self.overlay.buttons.append(new_button)

    def create_joystick(self, name, axis_x, axis_y):
        color = QColorDialog.getColor(initial=QColor("#00a8ff"), parent=self, title=f"Select color for {name}")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        new_joy = VirtualJoystick(self.overlay, name, axis_x, axis_y, color, pos.x() - 60, pos.y() - 60)
        new_joy.show()
        self.overlay.joysticks.append(new_joy)

def on_quit():
    # Medida de seguridad vital: Restaurar el cursor al cerrar el programa
    cursor_mgr.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(on_quit)  # Conectar el cierre a la restauración del cursor
    overlay = Overlay()
    overlay.show()
    panel = ControlPanel(overlay)
    panel.show()
    sys.exit(app.exec())