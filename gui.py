import sys
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QColorDialog, QSpinBox, QSlider, QGridLayout, QLabel, QCheckBox, QLineEdit, QGroupBox, QVBoxLayout, QHBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor

from functools import partial
import time
import numpy as np

class ColorCircle(QtWidgets.QWidget):
    colorChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.radius = 125.
        self.setFixedSize(250, 250)
        default_color = QtGui.QColor(255, 255, 255, 255)
        self.selected_color = default_color.name()
        self.colors = [[default_color for x in range(250)] for y in range(250)]

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QtGui.QPainter(self)
        for i in range(self.width()):
            for j in range(self.height()):
                color = QtGui.QColor(255, 255, 255, 255)
                h = (np.arctan2(i-self.radius, j-self.radius)+np.pi)/(2.*np.pi)
                s = np.sqrt(np.power(i-self.radius, 2)+np.power(j-self.radius, 2))/self.radius
                v = 1.0
                if s < 1.0:
                    color.setHsvF(h, s, v, 1.0)
                p.setPen(color)
                p.drawPoint(i, j)
                self.colors[i][j] = color

    def mousePressEvent(self, QMouseEvent):
        x = QMouseEvent.x()
        y = QMouseEvent.y()
        self.selected_color = self.colors[x][y].name()
        self.colorChanged.emit()

class QColorButton(QPushButton):
    '''
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color-chooser, while
    right-clicking resets the color to None (no-color).
    '''

    colorChanged = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(QColorButton, self).__init__(*args, **kwargs)

        self._color = None
        self.setMaximumWidth(32)
        self.pressed.connect(self.onColorPicker)

    def setColor(self, color):
        if color != self._color:
            self._color = color
            self.colorChanged.emit()

        if self._color:
            self.setStyleSheet("background-color: %s;" % self._color)
        else:
            self.setStyleSheet("")

    def color(self):
        return self._color

    def onColorPicker(self):
        '''
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.

        '''
        dlg = QColorDialog(self)
        if self._color:
            dlg.setCurrentColor(QColor(self._color))

        if dlg.exec_():
            self.setColor(dlg.currentColor().name())

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.setColor(None)

        return super(QColorButton, self).mousePressEvent(e)

def color_to_int(c):
    """colors are hex strings of format #aabbcc"""
    return int(c[1:], 16)

class IntensitySlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimum(0)
        self.setMaximum(15)
class BlinkSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimum(0)
        self.setMaximum(10)

TIMER_INTERVAL_MS = 10
class App(QWidget):

    def __init__(self, port=None):
        super().__init__()
        self.title = 'TF96 LED Color Util'
        self.left = 10
        self.top = 10
        self.width = 525
        self.height = 200
        self.port = port
        self.registers = []
        self.colorCircle = ColorCircle()
        self.sliders = [IntensitySlider(Qt.Horizontal) for x in range(16)]
        self.converted_color = [16,16,16]
        self.phase_addr = ['' for x in range(4)]
        self.initUI()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tic)
        for i in range(16):
            self._setChannelIntensity(i, 2)
            self._read_register(i)

        self.timer.start(TIMER_INTERVAL_MS)
        self._last_tic_s = 0
        self._last_blink_update = 0
        self._blink_on = False
        self.blinking_enabled = False
        self.blink_time_s = 1

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        controlsLayout = QGridLayout()

        controlsLayout.addWidget(self._create_led_group("led1",2,0,1), 0,0,1,4)
        controlsLayout.addWidget(self._create_led_group("led2",5,4,3), 0,4,1,4)
        controlsLayout.addWidget(self._create_led_group("signal",8,9,10),1,0,1,4)
        controlsLayout.addWidget(self._create_led_group("led3",14,13,15),1,4,1,4)

        controlsLayout.addWidget(QLabel("Global"), 2, 0, 1, 2)
        self.slider_master_int = IntensitySlider(Qt.Horizontal)
        self.slider_master_int.valueChanged.connect(self._updateMasterIntensity)
        controlsLayout.addWidget(self.slider_master_int, 2, 2, 1, 6)

        blink_checkBox = QCheckBox("blink")
        blink_checkBox.stateChanged.connect(self._blinkOnClick)
        controlsLayout.addWidget(blink_checkBox, 3,0,1,2)

        blink_slider = BlinkSlider(Qt.Horizontal)
        blink_slider.valueChanged.connect(partial(self._set_blink_time_s, blink_slider))
        controlsLayout.addWidget(blink_slider,3,2,1,6)

        self.colorCircle.colorChanged.connect(self._onColorChange)
        controlsLayout.addWidget(self.colorCircle, 4,4,4,4)

        controlsLayout.addWidget(QLabel("color: "), 4,0,1,1)
        self.curr_color = QLineEdit()
        self.curr_color.setText(self.colorCircle.selected_color)
        controlsLayout.addWidget(self.curr_color, 4,2,1,1)

        self.curr_color_btn = QColorButton()
        self.curr_color_btn.setColor(self.colorCircle.selected_color)
        controlsLayout.addWidget(self.curr_color_btn, 4,1,1,1)

        self.leds = ["led1", "led2", "signal", "led3", "all"]
        led1_button = QPushButton(self.leds[0])
        led1_button.clicked.connect(partial(self._ledOnClick, self.leds[0]))
        led2_button = QPushButton(self.leds[1])
        led2_button.clicked.connect(partial(self._ledOnClick, self.leds[1]))
        signal_button = QPushButton(self.leds[2])
        signal_button.clicked.connect(partial(self._ledOnClick, self.leds[2]))
        led3_button = QPushButton(self.leds[3])
        led3_button.clicked.connect(partial(self._ledOnClick, self.leds[3]))
        all_button = QPushButton(self.leds[4])
        all_button.clicked.connect(partial(self._ledOnClick, self.leds[4]))
        controlsLayout.addWidget(led1_button,5,0,1,2)
        controlsLayout.addWidget(led2_button,5,2,1,1)
        controlsLayout.addWidget(signal_button,6,0,1,2)
        controlsLayout.addWidget(led3_button,6,2,1,1)
        controlsLayout.addWidget(all_button,7,0,1,2)

        controlsLayout.addWidget(QLabel("Phase0"), 9,0,1,2)
        self.phase0_addr0_input = QLineEdit(self)
        self.phase0_addr0_input.setText(self.phase_addr[0])
        controlsLayout.addWidget(QLabel("0x02:"), 9,2,1,1)
        controlsLayout.addWidget(self.phase0_addr0_input, 9,3,1,1)
        controlsLayout.addWidget(QLabel("0x03:"), 9,4,1,1)
        self.phase0_addr1_input = QLineEdit(self)
        self.phase0_addr1_input.setText(self.phase_addr[1])
        controlsLayout.addWidget(self.phase0_addr1_input, 9,5,1,1)
        phase0_confirm_btn = QPushButton("confirm")
        phase0_confirm_btn.clicked.connect(partial(self._update_blink_phase, 0))
        controlsLayout.addWidget(phase0_confirm_btn, 9,6,1,1)

        controlsLayout.addWidget(QLabel("Phase1"), 10,0,1,2)
        self.phase1_addr0_input = QLineEdit()
        self.phase1_addr0_input.setText(self.phase_addr[2])
        controlsLayout.addWidget(QLabel("0x0A:"), 10,2,1,1)
        controlsLayout.addWidget(self.phase1_addr0_input, 10,3,1,1)
        controlsLayout.addWidget(QLabel("0x0B:"), 10,4,1,1)
        self.phase1_addr1_input = QLineEdit()
        self.phase1_addr1_input.setText(self.phase_addr[3])
        controlsLayout.addWidget(self.phase1_addr1_input, 10,5,1,1)
        phase0_confirm_btn = QPushButton("confirm")
        phase0_confirm_btn.clicked.connect(partial(self._update_blink_phase, 1))
        controlsLayout.addWidget(phase0_confirm_btn, 10,6,1,1)

        self.setLayout(controlsLayout)
        self.show()

    def _update_blink_phase(self, phase):
        if phase == 0:
            self.phase_addr[0] = self.phase0_addr0_input.text()
            self.phase_addr[1] = self.phase0_addr1_input.text()
            add0_hex = int(self.phase_addr[0], 16)
            add1_hex = int(self.phase_addr[1], 16)
            self._write_register(0x02, add0_hex)
            self._write_register(0x03, add1_hex)
            print("writing {}, {} to address 0x02, 0x03".format(self.phase_addr[0],self.phase_addr[1]))
        if phase == 1:
            self.phase_addr[2] = self.phase1_addr0_input.text()
            self.phase_addr[3] = self.phase1_addr1_input.text()
            add0_hex = int(self.phase_addr[2], 16)
            add1_hex = int(self.phase_addr[3], 16)
            self._write_register(0x0A, add0_hex)
            self._write_register(0x0B, add1_hex)
            print("writing {}, {} to address 0x0A, 0x0B".format(self.phase_addr[2],self.phase_addr[3]))

    def _toggle_port_bit(self, port, state):
        # enable the port, set port bit to 0
        if port <= 7:
            bit_pos = int(port)
            reg_addr = 6
        else:
            bit_pos = int(port) - 8
            reg_addr = 7
        reg_val = self._read_register(reg_addr)
        if state == QtCore.Qt.Checked:
            print("enabling port {}, setting bit {} to 0".format(port, bit_pos))
            new_val = reg_val ^ (1 << bit_pos)
            print("reg {} : {} => {}".format(hex(reg_addr), bin(reg_val), bin(new_val)))
            self._write_register(reg_addr, new_val)
        # disable the port, set port bit to 1
        else:
            print("disabling port {}, setting bit {} to 1".format(port, bit_pos))
            new_val = reg_val | (1 << bit_pos)
            print("reg {} : {} => {}".format(hex(reg_addr), bin(reg_val), bin(new_val)))
            self._write_register(reg_addr, new_val)

    def _check_enabled(self, port):
        if port <= 7:
            bit_pos = int(port)
            reg_addr = 6
        else:
            bit_pos = int(port) - 8
            reg_addr = 7
        reg_val = self._read_register(reg_addr)
        if reg_val & (1 << bit_pos) == 0:
            return True
        else:
            return False

    def _create_led_group(self, led_label, red_port, green_port, blue_port):
        led_group = QGroupBox(led_label)
        red_select_checkbox = QCheckBox()
        if self._check_enabled(red_port):
            red_select_checkbox.setChecked(True)
        red_select_checkbox.stateChanged.connect(partial(self._toggle_port_bit, red_port))
        green_select_checkbox = QCheckBox()
        if self._check_enabled(green_port):
            green_select_checkbox.setChecked(True)
        green_select_checkbox.stateChanged.connect(partial(self._toggle_port_bit, green_port))
        blue_select_checkbox = QCheckBox()
        if self._check_enabled(blue_port):
            blue_select_checkbox.setChecked(True)
        blue_select_checkbox.stateChanged.connect(partial(self._toggle_port_bit, blue_port))
        red_slider = IntensitySlider(Qt.Horizontal)
        red_slider.valueChanged.connect(partial(self._channelUpdateCallback, red_slider, red_port))
        green_slider = IntensitySlider(Qt.Horizontal)
        green_slider.valueChanged.connect(partial(self._channelUpdateCallback, green_slider, green_port))
        blue_slider = IntensitySlider(Qt.Horizontal)
        blue_slider.valueChanged.connect(partial(self._channelUpdateCallback, blue_slider, blue_port))
        self.sliders[red_port] = red_slider
        self.sliders[green_port] = green_slider
        self.sliders[blue_port] = blue_slider
        vBox = QVBoxLayout()

        hBoxRed = QHBoxLayout()
        hBoxRed.addWidget(red_select_checkbox)
        hBoxRed.addWidget(red_slider)
        vBox.addLayout(hBoxRed)

        hBoxGreen = QHBoxLayout()
        hBoxGreen.addWidget(green_select_checkbox)
        hBoxGreen.addWidget(green_slider)
        vBox.addLayout(hBoxGreen)

        hBoxBlue = QHBoxLayout()
        hBoxBlue.addWidget(blue_select_checkbox)
        hBoxBlue.addWidget(blue_slider)
        vBox.addLayout(hBoxBlue)

        vBox.addStretch(1)
        led_group.setLayout(vBox)
        return led_group

    def _set_rgb(self, sliders, converted_rgb, red_port, green_port, blue_port):
        red = converted_rgb[0]
        green = converted_rgb[1]
        blue = converted_rgb[2]
        sliders[red_port].setValue(red)
        sliders[green_port].setValue(green)
        sliders[blue_port].setValue(blue)


    def _ledOnClick(self, selected_led):
        if selected_led == "led1":
            print("updating port 2, 0, 1")
            self._set_rgb(self.sliders, self.converted_color, 2, 0, 1)
        elif selected_led == "led2":
            print("updating port 5, 4, 3")
            self._set_rgb(self.sliders, self.converted_color, 5, 4, 3)
        elif selected_led == "signal":
            print("updating port 8, 9, 10")
            self._set_rgb(self.sliders, self.converted_color, 8, 9, 10)
        elif selected_led == "led3":
            print("updating port 14, 13, 15")
            self._set_rgb(self.sliders, self.converted_color, 14, 13, 15)
        elif selected_led == "all":
            print("updating all port")
            self._set_rgb(self.sliders, self.converted_color, 2, 0, 1)
            self._set_rgb(self.sliders, self.converted_color, 5, 4, 3)
            self._set_rgb(self.sliders, self.converted_color, 8, 9, 10)
            self._set_rgb(self.sliders, self.converted_color, 14, 13, 15)

    def _onColorChange(self):
        self.curr_color.setText(self.colorCircle.selected_color)
        self.curr_color_btn.setColor(self.colorCircle.selected_color)
        self.converted_color = self._colorMapper(self.colorCircle.selected_color)

    def tic(self):
        dt = time.time() - self._last_blink_update
        if self.blinking_enabled:
            if dt > self.blink_time_s:
                if self._blink_on:
                    self._write_register(0x0F, 0x41)
                    self._blink_on = False
                else:
                    self._write_register(0x0F, 0x43)
                    self._blink_on = True

                self._last_blink_update = time.time()


        self._last_tic_s = time.time()

    def _blinkOnClick(self, state):
        if state == QtCore.Qt.Checked:
            self.blinking_enabled = True
        else:
            self.blinking_enabled = False

    #convert hex value to port scaled value
    def _colorMapper(self, hexVal):
        h = hexVal.lstrip('#')
        rgb = [int(h[i:i+2], 16) for i in (0, 2, 4)]
        converted = []
        for val in rgb:
           converted.append(int(round(15*val/255)))
        return converted

    def _updateMasterIntensity(self):
        i = self.slider_master_int.value()
        cmd = "CG{}\n".format(int(i))
        self.port.write(cmd.encode())
        print("Master intensity now {}".format(i))

    def _setChannelIntensity(self, channel, intensity):
        cmd = "CL{}\n".format(int(channel))
        cmd+= "CI{}\n".format(int(intensity))
        self.port.write(cmd.encode())
        print(cmd)

    def _read_register(self, reg_addr):
        cmd = "Cr{}\n".format(int(reg_addr))
        self.port.write(cmd.encode())
        resp = self.port.read_until(b"\n")
        """parse reponse into value"""
        val = int(resp.decode().split(':')[-1].strip("\n"), 16)
        print('reg 0x{:02x} : 0x{:02x}\n'.format(reg_addr, val))
        return val

    def _write_register(self, reg_addr, value):
        cmd = "CA{}\nCW{}\n".format(int(reg_addr), int(value))
        self.port.write(cmd.encode())

    def _channelUpdateCallback(self, slider, channel):
        i = slider.value()
        self._setChannelIntensity(channel, i)



    def _set_blink_time_s(self, slider):
        self.blink_time_s = 1 - (slider.value() / 10)
        print("blink time interval is now {}".format(self.blink_time_s))

    def _bright_update(self, val):
        cmd = "EL{}\n".format(val)
        self.port.write(cmd.encode())

if __name__ == '__main__':
    import serial
    TTY="/dev/ttyACM0"
    port = serial.Serial(TTY, timeout=1)
    port.close()
    port.open()
    app = QApplication(sys.argv)
    ex = App(port=port)
    sys.exit(app.exec_())
