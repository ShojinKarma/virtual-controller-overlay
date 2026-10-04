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

# --- GESTOR DE CURSOR GLOBAL DEL SISTEMA (WINDOWS) ---

class GestorCursorSistema:
    def __init__(self):
        self.esta_oculto = False
        self.es_windows = sys.platform == 'win32'
        if self.es_windows:
            self.user32 = ctypes.windll.user32
            self.OCR_NORMAL = 32512
            self.SPI_SETCURSORS = 0x0057

    def ocultar(self):
        if self.esta_oculto: return
        if self.es_windows:
            try:
                # Crear máscara transparente (16x16)
                and_mask = (ctypes.c_ubyte * 32)(*([0xFF] * 32))
                xor_mask = (ctypes.c_ubyte * 32)(*([0x00] * 32))
                blank_cursor = self.user32.CreateCursor(None, 0, 0, 16, 16, and_mask, xor_mask)
                self.user32.SetSystemCursor(blank_cursor, self.OCR_NORMAL)
            except Exception:
                pass
        QApplication.setOverrideCursor(Qt.BlankCursor)
        self.esta_oculto = True

    def mostrar(self):
        if not self.esta_oculto: return
        if self.es_windows:
            try:
                # Restaurar cursores nativos del sistema
                self.user32.SystemParametersInfoW(self.SPI_SETCURSORS, 0, None, 0)
            except Exception:
                pass
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.esta_oculto = False

gestor_cursor = GestorCursorSistema()

# --- DIÁLOGO DE CONFIGURACIÓN INDIVIDUAL ---

class DialogoConfiguracion(QDialog):
    def __init__(self, parent, widget_elem, tipo_elem="boton"):
        super().__init__(parent)
        self.widget_elem = widget_elem
        self.tipo_elem = tipo_elem
        
        titulo_texto = widget_elem.nombre if hasattr(widget_elem, 'nombre') else widget_elem.texto
        self.setWindowTitle(f"Ajustes: {titulo_texto}")
        self.setFixedSize(320, 430 if tipo_elem == "joystick_raton" else 320)

        layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_nombre = QLineEdit()
        self.edit_nombre.setText(titulo_texto)
        self.edit_nombre.textChanged.connect(self.cambiar_nombre)
        form.addRow("✏️ Nombre:", self.edit_nombre)

        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(20, 200)
        self.slider_size.setValue(widget_elem.size_base)
        self.slider_size.valueChanged.connect(self.aplicar_cambios)
        form.addRow("📏 Tamaño:", self.slider_size)

        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 255)
        self.slider_opacity.setValue(widget_elem.opacity)
        self.slider_opacity.valueChanged.connect(self.aplicar_cambios)
        form.addRow("👻 Opacidad:", self.slider_opacity)

        if self.tipo_elem == "joystick_raton":
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

            self.checkbox_desbloqueado = QCheckBox("Modo Cámara / Desbloqueado")
            self.checkbox_desbloqueado.setChecked(widget_elem.desbloqueado)
            self.checkbox_desbloqueado.toggled.connect(self.aplicar_cambios)
            form.addRow("📷 Modo Cámara:", self.checkbox_desbloqueado)

        layout.addLayout(form)

        btn_color = QPushButton("🎨 Cambiar Color")
        btn_color.clicked.connect(self.cambiar_color)
        layout.addWidget(btn_color)

        btn_borrar = QPushButton("❌ Eliminar este Elemento")
        btn_borrar.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        btn_borrar.clicked.connect(self.eliminar)
        layout.addWidget(btn_borrar)

        self.setLayout(layout)
        self.move(QCursor.pos())

    def cambiar_nombre(self, texto):
        if hasattr(self.widget_elem, 'nombre'):
            self.widget_elem.nombre = texto
        else:
            self.widget_elem.texto = texto
        self.setWindowTitle(f"Ajustes: {texto}")
        self.widget_elem.update()

    def aplicar_cambios(self):
        self.widget_elem.size_base = self.slider_size.value()
        self.widget_elem.opacity = self.slider_opacity.value()
        if self.tipo_elem == "joystick_raton":
            self.widget_elem.max_drag = self.slider_distancia.value()
            self.widget_elem.velocidad = self.slider_velocidad.value() / 100.0
            self.widget_elem.desbloqueado = self.checkbox_desbloqueado.isChecked()
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
        if self.opacity == 0: return
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
            dlg = DialogoConfiguracion(self, self, tipo_elem="boton")
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

class JoystickRatonVirtual(QWidget):
    def __init__(self, parent_overlay, nombre, axis_x_id, axis_y_id, color_qcolor, x, y, desbloqueado=False):
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
        self.desbloqueado = desbloqueado
        self.size_total = self.size_base * 2
        self.setGeometry(x, y, self.size_total, self.size_total)
        self.dragging = False
        self.offset = QPoint()
        
        self.is_active = False
        self.pos_actual_mouse = (0.0, 0.0)
        self.fase_reset = 0 # 0: Normal, 1: Mover en el aire, 2: Volver a hacer clic

    def actualizar_estilo(self):
        self.size_total = self.size_base * 2
        self.setGeometry(self.x(), self.y(), self.size_total, self.size_total)
        self.update()

    def paintEvent(self, event):
        if self.opacity == 0: return
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
        painter.setPen(QColor(255, 255, 255, self.opacity))
        font = QFont("Arial", int(self.size_total / 7), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.nombre)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = DialogoConfiguracion(self, self, tipo_elem="joystick_raton")
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def borrar(self):
        if self in self.parent_overlay.joysticks_raton:
            self.parent_overlay.joysticks_raton.remove(self)
        self.deleteLater()

    def obtener_centro(self):
        global_pos = self.mapToGlobal(QPoint(self.size_total // 2, self.size_total // 2))
        return (global_pos.x(), global_pos.y())

class JoystickWASDVirtual(QWidget):
    def __init__(self, parent_overlay, nombre, axis_x_id, axis_y_id, color_qcolor, x, y):
        super().__init__(parent_overlay)
        self.parent_overlay = parent_overlay
        self.nombre = nombre
        self.axis_x_id = axis_x_id
        self.axis_y_id = axis_y_id
        self.color = color_qcolor
        self.size_base = 60
        self.opacity = 180
        self.size_total = self.size_base * 2
        self.setGeometry(x, y, self.size_total, self.size_total)
        self.dragging = False
        self.offset = QPoint()
        self.pos_pomo = QPoint(self.size_total // 4, self.size_total // 4)
        
        self.estado_teclas = {'w': False, 'a': False, 's': False, 'd': False}

    def actualizar_teclas(self, w, a, s, d):
        if w and not self.estado_teclas['w']: kb.press('w'); self.estado_teclas['w'] = True
        elif not w and self.estado_teclas['w']: kb.release('w'); self.estado_teclas['w'] = False
        
        if a and not self.estado_teclas['a']: kb.press('a'); self.estado_teclas['a'] = True
        elif not a and self.estado_teclas['a']: kb.release('a'); self.estado_teclas['a'] = False
        
        if s and not self.estado_teclas['s']: kb.press('s'); self.estado_teclas['s'] = True
        elif not s and self.estado_teclas['s']: kb.release('s'); self.estado_teclas['s'] = False
        
        if d and not self.estado_teclas['d']: kb.press('d'); self.estado_teclas['d'] = True
        elif not d and self.estado_teclas['d']: kb.release('d'); self.estado_teclas['d'] = False

    def soltar_todas(self):
        for tecla in self.estado_teclas:
            if self.estado_teclas[tecla]:
                kb.release(tecla)
                self.estado_teclas[tecla] = False

    def actualizar_estilo(self):
        self.size_total = self.size_base * 2
        self.setGeometry(self.x(), self.y(), self.size_total, self.size_total)
        self.pos_pomo = QPoint(self.size_total // 4, self.size_total // 4)
        self.update()

    def paintEvent(self, event):
        if self.opacity == 0: return
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
        painter.drawEllipse(self.pos_pomo.x(), self.pos_pomo.y(), pomo_size, pomo_size)
        
        painter.setPen(QColor(255, 255, 255, self.opacity))
        font = QFont("Arial", int(self.size_total / 8), QFont.Weight.Bold)
        painter.setFont(font)
        # ELIMINADO EL TEXTO (WASD) - Solo dibuja el nombre
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.nombre)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            dlg = DialogoConfiguracion(self, self, tipo_elem="joystick_wasd")
            dlg.exec()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.position().toPoint() - self.offset))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def borrar(self):
        self.soltar_todas()
        if self in self.parent_overlay.joysticks_wasd:
            self.parent_overlay.joysticks_wasd.remove(self)
        self.deleteLater()

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
        self.joysticks_raton = []
        self.joysticks_wasd = []
        self.estado_botones = {}
        
        self.pos_esperada_mouse = None
        
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
            for i in range(self.joystick_fisico.get_numbuttons()):
                if self.joystick_fisico.get_button(i):
                    input_detectado = f"🎮 <b>Botón:</b> {i} (Usa el ID <b>{i}</b>)"
                    break

            if not input_detectado and self.joystick_fisico.get_numhats() > 0:
                hat_x, hat_y = self.joystick_fisico.get_hat(0)
                if hat_y == 1: input_detectado = "⬆️ <b>Cruceta Arriba</b> -> Usa el ID <b>101</b>"
                elif hat_y == -1: input_detectado = "⬇️ <b>Cruceta Abajo</b> -> Usa el ID <b>102</b>"
                elif hat_x == -1: input_detectado = "⬅️ <b>Cruceta Izquierda</b> -> Usa el ID <b>103</b>"
                elif hat_x == 1: input_detectado = "➡️ <b>Cruceta Derecha</b> -> Usa el ID <b>104</b>"

            if not input_detectado:
                for i in range(self.joystick_fisico.get_numaxes()):
                    if i in (0, 1, 2, 3): continue
                    val = self.joystick_fisico.get_axis(i)
                    if val > 0.5:
                        input_detectado = f"🔫 <b>Gatillo (Eje {i}):</b> -> Usa el ID <b>{200 + i}</b>"
                        break

        if self.panel:
            if not self.joystick_fisico:
                self.panel.lbl_detector.setText("⚠️ <b>Sin mando detectado</b>")
            elif input_detectado:
                self.panel.lbl_detector.setText(f"📡 {input_detectado}")
            else:
                self.panel.lbl_detector.setText("📡 <b>Detectado:</b> (Pulsa un botón del mando para saber su valor)")

        if not self.joystick_fisico: return

        # --- BOTONES VIRTUALES ---
        for b in self.botones:
            presionado = False
            if b.btn_id < 100:
                if b.btn_id < self.joystick_fisico.get_numbuttons():
                    presionado = self.joystick_fisico.get_button(b.btn_id)
            elif 100 <= b.btn_id < 200:
                if self.joystick_fisico.get_numhats() > 0:
                    hx, hy = self.joystick_fisico.get_hat(0)
                    if b.btn_id == 101 and hy == 1: presionado = True
                    elif b.btn_id == 102 and hy == -1: presionado = True
                    elif b.btn_id == 103 and hx == -1: presionado = True
                    elif b.btn_id == 104 and hx == 1: presionado = True
            elif b.btn_id >= 200:
                eje_real = b.btn_id - 200
                if eje_real < self.joystick_fisico.get_numaxes():
                    if self.joystick_fisico.get_axis(eje_real) > 0.5:
                        presionado = True

            estado_anterior = self.estado_botones.get(b.btn_id, False)
            if presionado and not estado_anterior: self.presionar_boton_virtual(b)
            elif not presionado and estado_anterior: self.soltar_boton_virtual(b)
            self.estado_botones[b.btn_id] = presionado

        # --- JOYSTICK WASD (TECLADO PARA MOVIMIENTO) ---
        KB_DEADZONE = 0.25
        for kj in self.joysticks_wasd:
            if kj.axis_x_id < self.joystick_fisico.get_numaxes() and kj.axis_y_id < self.joystick_fisico.get_numaxes():
                val_x = self.joystick_fisico.get_axis(kj.axis_x_id)
                val_y = self.joystick_fisico.get_axis(kj.axis_y_id)
                
                center_offset = kj.size_total // 4
                kj.pos_pomo = QPoint(int(center_offset + (val_x * center_offset)), int(center_offset + (val_y * center_offset)))
                kj.update()
                
                w = val_y < -KB_DEADZONE
                s = val_y > KB_DEADZONE
                a = val_x < -KB_DEADZONE
                d = val_x > KB_DEADZONE
                kj.actualizar_teclas(w, a, s, d)

        # --- JOYSTICK DE RATÓN (CÁMARA CON SISTEMA DE RESET ANTI-TIRÓN) ---
        DEADZONE = 0.15
        for j in self.joysticks_raton:
            if j.axis_x_id < self.joystick_fisico.get_numaxes() and j.axis_y_id < self.joystick_fisico.get_numaxes():
                val_x = self.joystick_fisico.get_axis(j.axis_x_id)
                val_y = self.joystick_fisico.get_axis(j.axis_y_id)
                
                raw_mag = math.hypot(val_x, val_y)

                if raw_mag > DEADZONE:
                    
                    # SISTEMA DE RETRASO DE FOTOGRAMAS PARA EVITAR EL SNAP-BACK (TIRÓN DE CÁMARA)
                    if j.fase_reset > 0:
                        cx, cy = j.obtener_centro()
                        if j.fase_reset == 1:
                            # Fotograma 2: Tras soltar el ratón, lo movemos en el aire al centro
                            mouse.position = (cx, cy)
                            self.pos_esperada_mouse = (cx, cy)
                            j.pos_actual_mouse = (float(cx), float(cy))
                            j.fase_reset = 2
                        elif j.fase_reset == 2:
                            # Fotograma 3: Con el ratón en el centro, volvemos a pulsar
                            mouse.press(Button.left)
                            j.fase_reset = 0
                        continue # Evitamos ejecutar movimiento normal mientras hacemos reset

                    scaled_mag = min(1.0, (raw_mag - DEADZONE) / (1.0 - DEADZONE))
                    dir_x = val_x / raw_mag
                    dir_y = val_y / raw_mag
                    
                    move_x = dir_x * scaled_mag
                    move_y = dir_y * scaled_mag

                    cx, cy = j.obtener_centro()

                    if j.desbloqueado:
                        if not j.is_active:
                            j.is_active = True
                            gestor_cursor.ocultar()
                            self.hide()
                            QApplication.processEvents()
                            self.pos_esperada_mouse = (cx, cy)
                            mouse.position = (cx, cy)
                            mouse.press(Button.left)
                            j.pos_actual_mouse = (float(cx), float(cy))

                        curr_x, curr_y = j.pos_actual_mouse
                        step_x = move_x * (j.velocidad * 18.0)
                        step_y = move_y * (j.velocidad * 18.0)
                        next_x = curr_x + step_x
                        next_y = curr_y + step_y

                        dist_from_center = math.hypot(next_x - cx, next_y - cy)

                        if dist_from_center >= j.max_drag:
                            # Fotograma 1: Soltamos el clic y entramos en fase de reset
                            mouse.release(Button.left)
                            j.fase_reset = 1
                        else:
                            self.pos_esperada_mouse = (int(next_x), int(next_y))
                            mouse.position = (next_x, next_y)
                            j.pos_actual_mouse = (next_x, next_y)
                    else:
                        target_x = cx + (move_x * j.max_drag)
                        target_y = cy + (move_y * j.max_drag)

                        if not j.is_active:
                            j.is_active = True
                            gestor_cursor.ocultar()
                            self.hide()
                            QApplication.processEvents()
                            self.pos_esperada_mouse = (cx, cy)
                            mouse.position = (cx, cy)
                            mouse.press(Button.left)
                            j.pos_actual_mouse = (float(cx), float(cy))

                        curr_x, curr_y = j.pos_actual_mouse
                        next_x = curr_x + (target_x - curr_x) * j.velocidad
                        next_y = curr_y + (target_y - curr_y) * j.velocidad
                        
                        self.pos_esperada_mouse = (int(next_x), int(next_y))
                        mouse.position = (next_x, next_y)
                        j.pos_actual_mouse = (next_x, next_y)

                else:
                    if j.is_active:
                        if j.fase_reset == 0:
                            mouse.release(Button.left)
                        j.is_active = False
                        j.fase_reset = 0
                        self.show()

        # Evitar interrupciones con el ratón físico solo si hay joysticks de ratón activos
        any_active_mouse_joy = any(j.is_active for j in self.joysticks_raton)
        if gestor_cursor.esta_oculto and self.pos_esperada_mouse and not any_active_mouse_joy:
            curr_pos = QCursor.pos()
            exp_x, exp_y = self.pos_esperada_mouse
            if abs(curr_pos.x() - exp_x) > 15 or abs(curr_pos.y() - exp_y) > 15:
                gestor_cursor.mostrar()
                self.pos_esperada_mouse = None

    def presionar_boton_virtual(self, widget):
        cx, cy = widget.obtener_centro()
        gestor_cursor.ocultar()
        self.hide()
        QApplication.processEvents()
        mouse.position = (cx, cy)
        self.pos_esperada_mouse = (cx, cy)
        mouse.press(Button.left)

    def soltar_boton_virtual(self, widget):
        mouse.release(Button.left)
        self.show()

# --- PANEL DE CONTROL ---

class PanelControl(QMainWindow):
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        self.overlay.panel = self 
        
        self.setWindowTitle("Configurador Mando v7 - Corrección de Cámara")
        self.setFixedSize(380, 420)

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

        layout.addWidget(QLabel("💡 <i>Usa esto para jugar en PC o Emuladores sin problemas.</i>"))

        btn_add_boton = QPushButton("➕ Añadir Botón Nuevo")
        btn_add_boton.clicked.connect(self.crear_boton)
        layout.addWidget(btn_add_boton)

        btn_add_jl = QPushButton("⌨️ Añadir Joystick Izquierdo (Movimiento WASD)")
        btn_add_jl.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        btn_add_jl.clicked.connect(lambda: self.crear_joystick_wasd("Mover", 0, 1))
        layout.addWidget(btn_add_jl)

        btn_add_jr = QPushButton("🖱️️ Añadir Joystick Derecho (Cámara Ratón)")
        btn_add_jr.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        btn_add_jr.clicked.connect(lambda: self.crear_joystick_raton("Cámara", 2, 3, desbloqueado=True))
        layout.addWidget(btn_add_jr)

        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def actualizar_nombre_mando(self):
        mando_nombre = self.overlay.joystick_fisico.get_name() if self.overlay.joystick_fisico else "Ningún mando detectado"
        self.lbl_mando.setText(f"🎮 Mando: <b>{mando_nombre}</b>")

    def crear_boton(self):
        texto, ok1 = QInputDialog.getText(self, "Nuevo Botón", "Nombre en pantalla:")
        if not ok1 or not texto: return
        
        btn_id, ok2 = QInputDialog.getInt(self, "ID del Mando", "ID del botón (Mira la caja azul mientras lo pulsas):", 0, 0, 300)
        if not ok2: return

        color = QColorDialog.getColor(initial=QColor("#4cd137"), parent=self, title="Selecciona el color del Botón")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        nuevo_boton = BotonVirtual(self.overlay, texto, btn_id, color, pos.x() - 30, pos.y() - 30)
        nuevo_boton.show()
        self.overlay.botones.append(nuevo_boton)

    def crear_joystick_wasd(self, nombre, eje_x, eje_y):
        color = QColorDialog.getColor(initial=QColor("#27ae60"), parent=self, title=f"Color para {nombre}")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        nuevo_joy = JoystickWASDVirtual(self.overlay, nombre, eje_x, eje_y, color, pos.x() - 60, pos.y() - 60)
        nuevo_joy.show()
        self.overlay.joysticks_wasd.append(nuevo_joy)

    def crear_joystick_raton(self, nombre, eje_x, eje_y, desbloqueado=False):
        color = QColorDialog.getColor(initial=QColor("#2980b9"), parent=self, title=f"Color para {nombre}")
        if not color.isValid(): return

        pos = self.overlay.mapFromGlobal(QCursor.pos())
        nuevo_joy = JoystickRatonVirtual(self.overlay, nombre, eje_x, eje_y, color, pos.x() - 60, pos.y() - 60, desbloqueado=desbloqueado)
        nuevo_joy.show()
        self.overlay.joysticks_raton.append(nuevo_joy)

def al_cerrar():
    gestor_cursor.mostrar()
    for kj in overlay.joysticks_wasd:
        kj.soltar_todas()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(al_cerrar)
    overlay = Overlay()
    overlay.show()
    panel = PanelControl(overlay)
    panel.show()
    sys.exit(app.exec())