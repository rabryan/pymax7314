import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QColorDialog, QSpinBox, QSlider, QGridLayout, QLabel
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt
from PyQt5.QtGui import QColor

from functools import partial
import time

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
        self.setMinimum(1)
        self.setMaximum(15)

class App(QWidget):

    def __init__(self, port=None):
        super().__init__()
        self.title = 'TF96 LED Color Util'
        self.left = 10
        self.top = 10
        self.width = 320
        self.height = 200
        self.port = port
        self.initUI()

        for i in range(16):
            self._setChannelIntensity(i, 5)

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        controlsLayout = QGridLayout()

        controlsLayout.addWidget(QLabel("Global"), 0, 0)
        self.slider_master_int = IntensitySlider(Qt.Horizontal)
        self.slider_master_int.valueChanged.connect(self._updateMasterIntensity)
        controlsLayout.addWidget(self.slider_master_int, 0, 1)

        for i in range(16):
            row = i + 1
            controlsLayout.addWidget(QLabel(str(i)), row, 0)
            slider = IntensitySlider(Qt.Horizontal)
            slider.valueChanged.connect(partial(self._channelUpdateCallback, slider, i))
            controlsLayout.addWidget(slider, row, 1)

        self.setLayout(controlsLayout)
        self.show()


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


    def _channelUpdateCallback(self, slider, channel):
        i = slider.value()
        self._setChannelIntensity(channel, i)

    def _bright_update(self, val):
        cmd = "EL{}\n".format(val)
        self.port.write(cmd.encode())

if __name__ == '__main__':
    import serial
    TTY="/dev/ttyACM0"
    port = serial.Serial(TTY)
    app = QApplication(sys.argv)
    ex = App(port=port)
    sys.exit(app.exec_())
