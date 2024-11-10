"""
Unit tests for plotting widgets
"""


from kevinbot_desktopclient.ui.plots import BatteryGraph


def test_battery_graph(qtbot):
    widget = BatteryGraph()
    widget.set_voltage_range(0, 100)
    widget.add(50.2)
    assert widget.values[9] == 50.2
