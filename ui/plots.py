from PySide6.QtWidgets import QWidget, QProgressBar, QGridLayout, QLabel
from ui.widgets import ColorBlock

import pyqtgraph as pg

import enums


class BatteryGraph(pg.PlotWidget):
    def __init__(self):
        super().__init__()

        self.showGrid(x=False, y=True)
        self.setYRange(0, 20)
        self.hideButtons()
        self.setBackground("transparent")
        self.setMenuEnabled(False)
        self.setMouseTracking(False)
        self.setMouseEnabled(x=False, y=False)
        self.getAxis("bottom").setStyle(showValues=False)
        self.time = list(range(10))
        self.values = [0.0 for _ in range(10)]
        # Get a line reference
        self.line = self.plot(
            self.time,
            self.values,
            name="Battery Voltage #1",
            symbolSize=0,
            fillLevel=-0,
            brush="#9c27b0",
            symbolBrush="b",
        )

    def add(self, voltage: float) -> None:
        self.time = self.time[1:]
        self.time.append(self.time[-1] + 1)
        self.values = self.values[1:]
        self.values.append(voltage)
        self.line.setData(self.time, self.values)

    def set_voltage_range(self, min_voltage: float, max_voltage: float):
        self.setYRange(min_voltage, max_voltage)


class StickVisual(QWidget):
    def __init__(self):
        super().__init__()

        self._root_layout = QGridLayout()
        self.setLayout(self._root_layout)

        self.x_label = QLabel("X")
        self._root_layout.addWidget(self.x_label, 0, 0)

        self.y_label = QLabel("Y")
        self._root_layout.addWidget(self.y_label, 1, 0)

        self.x_progress_bar = QProgressBar()
        self.x_progress_bar.setRange(-100, 100)
        self._root_layout.addWidget(self.x_progress_bar, 0, 1)

        self.y_progress_bar = QProgressBar()
        self.y_progress_bar.setRange(-100, 100)
        self._root_layout.addWidget(self.y_progress_bar, 1, 1)

    def plot(self, x, y):
        self.x_progress_bar.setValue((x)*100)
        self.y_progress_bar.setValue((y)*100)

class PovVisual(QWidget):
    def __init__(self):
        super().__init__()

        self._root_layout = QGridLayout()
        self.setLayout(self._root_layout)

        self.pov_nw = QProgressBar()
        self.pov_nw.setValue(0)
        self.pov_nw.setRange(0, 1)
        self.pov_nw.setTextVisible(False)
        self._root_layout.addWidget(self.pov_nw, 0, 0)

        self.pov_n = QProgressBar()
        self.pov_n.setValue(0)
        self.pov_n.setRange(0, 1)
        self.pov_n.setTextVisible(False)
        self._root_layout.addWidget(self.pov_n, 0, 1)

        self.pov_ne = QProgressBar()
        self.pov_ne.setValue(0)
        self.pov_ne.setRange(0, 1)
        self.pov_ne.setTextVisible(False)
        self._root_layout.addWidget(self.pov_ne, 0, 2)

        self.pov_w = QProgressBar()
        self.pov_w.setValue(0)
        self.pov_w.setRange(0, 1)
        self.pov_w.setTextVisible(False)
        self._root_layout.addWidget(self.pov_w, 1, 0)

        self.pov_c = QProgressBar()
        self.pov_c.setValue(0)
        self.pov_c.setRange(0, 1)
        self.pov_c.setTextVisible(False)
        self._root_layout.addWidget(self.pov_c, 1, 1)

        self.pov_e = QProgressBar()
        self.pov_e.setValue(0)
        self.pov_e.setRange(0, 1)
        self.pov_e.setTextVisible(False)
        self._root_layout.addWidget(self.pov_e, 1, 2)

        self.pov_sw = QProgressBar()
        self.pov_sw.setValue(0)
        self.pov_sw.setRange(0, 1)
        self.pov_sw.setTextVisible(False)
        self._root_layout.addWidget(self.pov_sw, 2, 0)

        self.pov_s = QProgressBar()
        self.pov_s.setValue(0)
        self.pov_s.setRange(0, 1)
        self.pov_s.setTextVisible(False)
        self._root_layout.addWidget(self.pov_s, 2, 1)

        self.pov_se = QProgressBar()
        self.pov_se.setValue(0)
        self.pov_se.setRange(0, 1)
        self.pov_se.setTextVisible(False)
        self._root_layout.addWidget(self.pov_se, 2, 2)


    def plot(self, pov: enums.Cardinal):
        direction_map = {
            enums.Cardinal.NORTH: self.pov_n,
            enums.Cardinal.NORTHEAST: self.pov_ne,
            enums.Cardinal.EAST: self.pov_e,
            enums.Cardinal.SOUTHEAST: self.pov_se,
            enums.Cardinal.SOUTH: self.pov_s,
            enums.Cardinal.SOUTHWEST: self.pov_sw,
            enums.Cardinal.WEST: self.pov_w,
            enums.Cardinal.NORTHWEST: self.pov_nw,
            enums.Cardinal.CENTER: self.pov_c
        }
        
        for direction, attr in direction_map.items():
            attr.setValue(1 if pov == direction else 0)