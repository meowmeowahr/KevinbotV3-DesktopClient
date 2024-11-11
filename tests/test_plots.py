"""
Unit tests for plotting widgets
"""

import pytest

from kevinbot_desktopclient.ui.plots import BatteryGraph


@pytest.mark.usefixtures("qtbot")
def test_battery_graph():
    widget = BatteryGraph()
    widget.set_voltage_range(0, 100)
    widget.add(50.2)
    assert widget.values[9] == 50.2
