import sys
import time
import pygame
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, 
    QLabel, QSlider, QInputDialog, QMainWindow, QColorDialog, QDialog, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QCursor
from pynput.mouse import Controller, Button

mouse = Controller()

# --- DIÁLOGO DE CONFIGURACIÓN INDIVIDUAL ---

class DialogoConfiguracion(QDialog):
    def __init__(self, parent, widget_elem, es_joystick=False):
        super().__init__(parent)
        self.widget_elem = widget_elem
        self.es_joystick = es_joystick
        self.setWindowTitle(f"Ajustes: {widget_elem.nombre if es_joystick else widget_elem.texto}")
        self.setFixedSize(320, 360 if es_joystick else 280)

        layout = QVBoxLayout()
        form = QFormLayout()

        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(20, 200)
        self.slider_size.setValue(widget_elem.size_base)
        self.slider_size.valueChanged.connect(self.aplicar_cambios)
        form.addRow("📏 Tamaño:", self.slider_size)

        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(10, 255)
        self.slider_opacity.setValue(widget_elem.opacity)
        self.slider_opacity.valueChanged.connect(self.aplicar_cambios)
        form.addRow("👻 Opacidad:", self.slider_opacity)

        if self.es_joystick:
            self.slider_distancia = QSlider(Qt.Orientation.Horizontal)
            self.slider_distancia.setRange(50, 400)
            self.slider_distancia.setValue(widget_elem.max_drag)
            self.slider_distancia.valueChanged.connect(self.aplicar_cambios)
            form.addRow("📐 Distancia Arrastre:", self.slider_distancia)

            self.slider_velocidad = QSlider(Qt.Orientation.Horizontal)
            self.slider_velocidad.setRange(1, 100)
            self.slider_velocidad.setValue(int(widget_elem.velocidad * 100))
            self.slider_velocidad.valueChanged.connect(self.aplicar_cambios)
            form.addRow("⚡ Velocidad Arrastre:", self.slider_velocidad)

        layout.addLayout(form)

        btn_color = QPushButton("🎨 Cambiar Color")
        btn_color.clicked.connect(self.cambiar_color)
        layout.addWidget(btn_color)

        btn_borrar = QPushButton("❌ Eliminar este Elemento")
        btn_borrar.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        btn_borrar.clicked.connect(self.eliminar)
        layout.addWidget(btn_borrar)

        self.setLayout(layout)
        
        # Mueve la ventana emergente directamente a la posición del cursor
        self.move(QCursor.pos())

    def aplicar_cambios(self):
        self.widget_elem.size_base = self.slider_size.value()
        self.widget_elem.opacity = self.slider_opacity.value()
        
        if self.es_joystick:
            self.widget_elem.max_drag = self.slider_distancia.value()
            self.widget_elem.velocidad = self.slider_velocidad.value() / 100.0
            self.widget_elem.actualizar_estilo()
        else:
            self.widget_elem.actualizar_estilo()

    def cambiar_color(self):
        color = QColorDialog.getColor(initial=self.widget_elem.color, parent=self, title="Selecciona Color")
        if color.isValid():
            self.widget_elem.color = color
            self.widget_elem.update()

    def eliminar(self):
        self.widget_elem.borrar()
        self.close()

# --- WIDGETS VIRTUALES ---

class BotonVirtual(QWidget):
    def __init__(self, parent_overlay, texto, btn_id, color_qcolor, x, y):
        super().__init__(parent_overlay)
        self.parent_overlay = parent_overlay
        self.texto = texto
        self.btn_id = btn_id
        self.color = color_qcolor
        self.size_base = 60
        self.opacity = 180
        self.setGeometry(x, y, self.size_base, self.size_base)
        self.dragging = False
        self.offset = QPoint()

    def actualizar_estilo(self):
        self.setGeometry(self.x(), self.y(), self.size_base, self.size_base)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self.color)
        c.setAlpha(self.opacity)
        painter.setBrush(c)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.size_base, self.size_base)
        
        text_color = QColor(255, 255, 255, self.opacity)
        painter.setPen(text_color)
        font = QFont("Arial", int(self.size_base / 2.5), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.texto)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = DialogoConfiguracion(self, self, es_joystick=False)
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def borrar(self):
        if self in self.parent_overlay.botones:
            self.parent_overlay.botones.remove(self)
        self.deleteLater()

    def obtener_centro(self):
        global_pos = self.mapToGlobal(QPoint(self.size_base // 2, self.size_base // 2))
        return (global_pos.x(), global_pos.y())


class JoystickVirtual(QWidget):
    def __init__(self, parent_overlay, nombre, axis_x_id, axis_y_id, color_qcolor, x, y):
        super().__init__(parent_overlay)
        self.parent_overlay = parent_overlay
        self.nombre = nombre
        self.axis_x_id = axis_x_id
        self.axis_y_id = axis_y_id
        self.color = color_qcolor
        self.size_base = 60
        self.opacity = 180
        self.max_drag = 150
        self.velocidad = 1.0
        
        self.size_total = self.size_base * 2
        self.setGeometry(x, y, self.size_total, self.size_total)
        self.dragging = False
        self.offset = QPoint()
        self.is_active = False
        self.pos_actual_mouse = (0, 0)

    def actualizar_estilo(self):
        self.size_total = self.size_base * 2
        self.setGeometry(self.x(), self.y(), self.size_total, self.size_total)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        c_base = QColor(self.color)
        c_base.setAlpha(int(self.opacity * 0.4))
        painter.setBrush(c_base)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.size_total, self.size_total)
        
        c_pomo = QColor(self.color)
        c_pomo.setAlpha(self.opacity)
        painter.setBrush(c_pomo)
        pomo_size = self.size_total // 2
        painter.drawEllipse(self.size_total // 4, self.size_total // 4, pomo_size, pomo_size)

        text_color = QColor(255, 255, 255, self.opacity)
        painter.setPen(text_color)
        font = QFont("Arial", int(self.size_total / 7), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.nombre)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = DialogoConfiguracion(self, self, es_joystick=True)
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def borrar(self):
        if self in self.parent_overlay.joysticks:
            self.parent_overlay.joysticks.remove(self)
        self.deleteLater()

    def obtener_centro(self):
        global_pos = self.mapToGlobal(QPoint(self.size_total // 2, self.size_total // 2))
        return (global_pos.x(), global_pos.y())

# --- CAPA TRANSPARENTE ---

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        virtual_geometry = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_geometry)
        
        self.panel = None
        self.botones = []
        self.joysticks = []
        self.estado_botones = {}
        
        pygame.init()
        pygame.joystick.init()
        self.joystick_fisico = None
        self.conectar_mando()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.procesar_mando)
        self.timer.start(16)

    def conectar_mando(self):
        if pygame.joystick.get_count() > 0:
            self.joystick_fisico = pygame.joystick.Joystick(0)
            self.joystick_fisico.init()

    def procesar_mando(self):
        pygame.event.pump()
        
        if not self.joystick_fisico:
            self.conectar_mando()
            if self.joystick_fisico and self.panel:
                self.panel.actualizar_nombre_mando()

        input_detectado = None

        if self.joystick_fisico:
            # 1. Detección de Botones Clásicos
            for i in range(self.joystick_fisico.get_numbuttons()):
                if self.joystick_fisico.get_button(i):
                    input_detectado = f"🎮 <b>Botón:</b> {i} (Usa el ID <b>{i}</b>)"
                    break

            # 2. Detección de Cruceta (Hats)
            if not input_detectado and self.joystick_fisico.get_numhats() > 0:
                hat_x, hat_y = self.joystick_fisico.get_hat(0)
                if hat_y == 1: input_detectado = "⬆️ <b>Cruceta Arriba</b> -> Usa el ID <b>101</b>"
                elif hat_y == -1: input_detectado = "⬇️ <b>Cruceta Abajo</b> -> Usa el ID <b>102</b>"
                elif hat_x == -1: input_detectado = "⬅️ <b>Cruceta Izquierda</b> -> Usa el ID <b>103</b>"
                elif hat_x == 1: input_detectado = "➡️ <b>Cruceta Derecha</b> -> Usa el ID <b>104</b>"

            # 3. Detección de Gatillos L2/R2 (Ignorando ejes de joystick 0,1,2,3)
            if not input_detectado:
                for i in range(self.joystick_fisico.get_numaxes()):
                    if i in (0, 1, 2, 3): continue # Excluir sticks del monitor
                    val = self.joystick_fisico.get_axis(i)
                    if val > 0.5: # Si se presiona más de la mitad
                        input_detectado = f"🔫 <b>Gatillo (Eje {i}):</b> -> Usa el ID <b>{200 + i}</b>"
                        break

        # Actualización del Monitor
        if self.panel:
            if not self.joystick_fisico:
                self.panel.lbl_detector.setText("⚠️ <b>Sin mando detectado</b>")
            elif input_detectado:
                self.panel.lbl_detector.setText(f"📡 {input_detectado}")
            else:
                self.panel.lbl_detector.setText("📡 <b>Detectado:</b> (Pulsa un botón del mando para saber su valor)")

        if not self.joystick_fisico:
            return

        # --- EJECUCIÓN DE BOTONES VIRTUALES ---
        for b in self.botones:
            presionado = False
            
            if b.btn_id < 100:
                # Botón normal
                if b.btn_id < self.joystick_fisico.get_numbuttons():
                    presionado = self.joystick_fisico.get_button(b.btn_id)
            elif 100 <= b.btn_id < 200:
                # Cruceta (D-Pad)
                if self.joystick_fisico.get_numhats() > 0:
                    hx, hy = self.joystick_fisico.get_hat(0)
                    if b.btn_id == 101 and hy == 1: presionado = True
                    elif b.btn_id == 102 and hy == -1: presionado = True
                    elif b.btn_id == 103 and hx == -1: presionado = True
                    elif b.btn_id == 104 and hx == 1: presionado = True
            elif b.btn_id >= 200:
                # Gatillos L2/R2 convertidos en botón
                eje_real = b.btn_id - 200
                if eje_real < self.joystick_fisico.get_numaxes():
                    if self.joystick_fisico.get_axis(eje_real) > 0.5:
                        presionado = True

            estado_anterior = self.estado_botones.get(b.btn_id, False)
            if presionado and not estado_anterior:
                self.simular_clic(b)
            self.estado_botones[b.btn_id] = presionado

        # --- EJECUCIÓN DE JOYSTICKS VIRTUALES ---
        DEADZONE = 0.2
        for j in self.joysticks:
            if j.axis_x_id < self.joystick_fisico.get_numaxes() and j.axis_y_id < self.joystick_fisico.get_numaxes():
                val_x = self.joystick_fisico.get_axis(j.axis_x_id)
                val_y = self.joystick_fisico.get_axis(j.axis_y_id)
                
                if abs(val_x) > DEADZONE or abs(val_y) > DEADZONE:
                    cx, cy = j.obtener_centro()
                    target_x = cx + (val_x * j.max_drag)
                    target_y = cy + (val_y * j.max_drag)

                    if not j.is_active:
                        self.hide()
                        QApplication.processEvents()
                        mouse.position = (cx, cy)
                        mouse.press(Button.left)
                        j.is_active = True
                        j.pos_actual_mouse = (cx, cy)
                        self.show()
                    
                    curr_x, curr_y = j.pos_actual_mouse
                    next_x = curr_x + (target_x - curr_x) * j.velocidad
                    next_y = curr_y + (target_y - curr_y) * j.velocidad
                    
                    mouse.position = (next_x, next_y)
                    j.pos_actual_mouse = (next_x, next_y)
                else:
                    if j.is_active:
                        mouse.release(Button.left)
                        j.is_active = False
                        cx, cy = j.obtener_centro()
                        mouse.position = (cx, cy)
                        j.pos_actual_mouse = (cx, cy)

    def simular_clic(self, widget):
        cx, cy = widget.obtener_centro()
        self.hide()
        QApplication.processEvents()
        time.sleep(0.03)
        mouse.position = (cx, cy)
        mouse.click(Button.left)
        self.show()

# --- PANEL DE CONTROL ---

class PanelControl(QMainWindow):
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.overlay.panel = self 
        
        self.setWindowTitle("Configurador Mando v5")
        self.setFixedSize(380, 370)

        widget = QWidget()
        layout = QVBoxLayout()
        
        self.lbl_mando = QLabel()
        self.actualizar_nombre_mando()
        layout.addWidget(self.lbl_mando)
        
        self.lbl_detector = QLabel("📡 <b>Detectado:</b> (Pulsa un botón del mando para saber su valor)")
        self.lbl_detector.setStyleSheet("background-color: #192a56; color: #00a8ff; padding: 15px; border-radius: 6px; font-size: 13px;")
        self.lbl_detector.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_detector.setWordWrap(True)
        layout.addWidget(self.lbl_detector)

        layout.addWidget(QLabel("💡 <i>Usa el monitor de arriba para saber el ID.<br>Click DERECHO en cualquier botón para ajustarlo.</i>"))

        btn_add_boton = QPushButton("➕ Añadir Botón Nuevo")
        btn_add_boton.clicked.connect(self.crear_boton)
        layout.addWidget(btn_add_boton)

        btn_add_jl = QPushButton("🕹️ Añadir Joystick Izquierdo (L)")
        btn_add_jl.clicked.connect(lambda: self.crear_joystick("Stick L", 0, 1))
        layout.addWidget(btn_add_jl)

        btn_add_jr = QPushButton("🕹️ Añadir Joystick Derecho (R)")
        btn_add_jr.clicked.connect(lambda: self.crear_joystick("Stick R", 2, 3))
        layout.addWidget(btn_add_jr)

        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def actualizar_nombre_mando(self):
        mando_nombre = self.overlay.joystick_fisico.get_name() if self.overlay.joystick_fisico else "Ningún mando detectado"
        self.lbl_mando.setText(f"🎮 Mando: <b>{mando_nombre}</b>")

    def crear_boton(self):
        texto, ok1 = QInputDialog.getText(self, "Nuevo Botón", "Nombre en pantalla:")
        if not ok1 or not texto: return
        
        # Aumentamos el límite de 30 a 300 para permitir los IDs virtuales de Gatillos y Cruceta
        btn_id, ok2 = QInputDialog.getInt(self, "ID del Mando", "ID del botón (Mira la caja azul mientras lo pulsas):", 0, 0, 300)
        if not ok2: return

        color = QColorDialog.getColor(initial=QColor("#4cd137"), parent=self, title="Selecciona el color del Botón")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        nuevo_boton = BotonVirtual(self.overlay, texto, btn_id, color, pos.x() - 30, pos.y() - 30)
        nuevo_boton.show()
        self.overlay.botones.append(nuevo_boton)

    def crear_joystick(self, nombre, eje_x, eje_y):
        color = QColorDialog.getColor(initial=QColor("#00a8ff"), parent=self, title=f"Selecciona el color para {nombre}")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        nuevo_joy = JoystickVirtual(self.overlay, nombre, eje_x, eje_y, color, pos.x() - 60, pos.y() - 60)
        nuevo_joy.show()
        self.overlay.joysticks.append(nuevo_joy)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.show()
    panel = PanelControl(overlay)
    panel.show()
    sys.exit(app.exec())