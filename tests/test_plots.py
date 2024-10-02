"""
Unit tests for plotting widgets
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QResizeEvent

from ui.plots import BatteryGraph


def test_battery_graph(qtbot):
    widget = BatteryGraph()
    widget.set_voltage_range(0, 100)
    widget.add(50.2)
    assert widget.values[9] == 50.2
