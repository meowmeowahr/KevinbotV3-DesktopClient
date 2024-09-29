import pyqtgraph as pg

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
        self.getAxis('bottom').setStyle(showValues=False)
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
