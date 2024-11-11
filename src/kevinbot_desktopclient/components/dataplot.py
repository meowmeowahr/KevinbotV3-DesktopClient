import math
import random
import sys
from collections.abc import Callable

import pyqtgraph as pg
from PySide6.QtCore import QSize, Qt, QTimer, Signal, SignalInstance
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from kevinbot_desktopclient.ui.delegates import ComboBoxNoTextDelegate
from kevinbot_desktopclient.ui.widgets import ColorBlock


def color_string_to_hex(color_str):
    # Map of shorthand color strings to their hex codes
    color_map = {
        "w": "#FFFFFF",  # White
        "r": "#FF0000",  # Red
        "g": "#00FF00",  # Green
        "b": "#0000FF",  # Blue
        "c": "#00FFFF",  # Cyan
        "m": "#FF00FF",  # Magenta
        "y": "#FFFF00",  # Yellow
        "k": "#000000",  # Black
        "gray": "#808080",  # Gray
    }

    # Return the hex code or None if the color is not recognized
    return color_map.get(color_str, color_str)


class DataSourceCheckBox(QFrame):
    def __init__(self, source_name: str, color: str) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("DataSourceCheckBoxFrame")

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.check = QCheckBox()
        layout.addWidget(self.check)

        self.clicked: SignalInstance = self.check.clicked
        self.stateChanged = self.check.stateChanged
        self.setChecked = self.check.setChecked
        self.isChecked = self.check.isChecked

        self.label = QLabel(source_name)
        layout.addWidget(self.label)

        self.color = ColorBlock()
        self.color.setMinimumSize(QSize(10, 10))
        self.color.setMaximumWidth(10)
        self.color.set_color(color_string_to_hex(color))
        layout.addWidget(self.color)

    def set_color(self, color: str):
        self.color.set_color(color_string_to_hex(color))


class DataSourceManagerItem(QFrame):
    color_changed = Signal(str, str)
    width_changed = Signal(str, int)
    def __init__(self, source_name: str, color: str, width: int) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("DataSourceCheckBoxFrame")

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.label = QLabel(source_name)
        layout.addWidget(self.label)

        self.width_select = QComboBox()
        for i in range(1, 6):
            self.width_select.addItem(str(i), i)
        self.width_select.setCurrentIndex(width - 1)
        self.width_select.currentIndexChanged.connect(self._width_changed_event)
        layout.addWidget(self.width_select)

        self.color = QComboBox()

        view = QTableView(
            self.color
        )
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.color.setView(view)

        view.verticalHeader().hide()
        view.horizontalHeader().hide()

        header = view.horizontalHeader()
        for i in range(header.count()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self.color.setFixedSize(QSize(48, 36))
        self.color.setItemDelegate(ComboBoxNoTextDelegate())

        for col in ["r", "g", "b", "m", "c", "y", "#e91e63", "#3f51b5", "#cddc39", "#ff9800", "#607d8b", "#03a9f4", "#ff5722", "#2196f3", "#8bc34a", "#673ab7", "#795548", "#009688"]:
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(color_string_to_hex(col)))
            self.color.addItem(QIcon(pixmap), col, col)
            self.color.setItemData(0, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)
        self.color.setCurrentText(str(color))
        self.color.currentIndexChanged.connect(self._color_changed_event)

        layout.addWidget(self.color)

    def _color_changed_event(self, _index: int) -> None:
        self.color_changed.emit(self.label.text(), self.color.currentText())

    def _width_changed_event(self, _index: int) -> None:
        self.width_changed.emit(self.label.text(), self.width_select.currentData())


class LivePlot(QMainWindow):
    on_data_source_selection_changed = Signal(str, bool)

    def __init__(self) -> None:
        super().__init__()

        # Initialize data structures for dynamic sources
        self.data_sources: dict[str, dict] = {}
        self.source_checkboxes: dict[str, DataSourceCheckBox] = {}
        self.data_y: dict[str, list[float]] = {}
        self.plot_data_items: dict[str, pg.PlotDataItem] = {}

        self._setup_ui()

        # Initialize the data series for real-time updates
        self.data_x: list[float] = []
        self.plot_x: float = 0

        # Timer to update data
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(100)  # 100ms default update rate

    def _setup_ui(self) -> None:
        """Set up the user interface components."""
        self.setWindowTitle("Live Data Plot with Multiple Sources")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)

        # Top controls
        controls_layout = QHBoxLayout()
        root_layout.addLayout(controls_layout)

        # Autoscale button
        autoscale_button = QPushButton("Autoscale")
        controls_layout.addWidget(autoscale_button)

        # Play/Pause button
        self.play_pause_button = QPushButton("Pause")
        self.play_pause_button.setCheckable(True)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.play_pause_button)

        # Clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_data)
        controls_layout.addWidget(clear_button)

        # Update rate control
        rate_layout = QHBoxLayout()
        rate_label = QLabel("Update Rate (ms):")
        self.rate_spinbox = QSpinBox()
        self.rate_spinbox.setRange(10, 1000)
        self.rate_spinbox.setValue(100)
        self.rate_spinbox.setSingleStep(10)
        self.rate_spinbox.valueChanged.connect(self.update_timer_interval)
        rate_layout.addWidget(rate_label)
        rate_layout.addWidget(self.rate_spinbox)
        controls_layout.addLayout(rate_layout)

        # Add stretch to push controls to the left
        controls_layout.addStretch()

        main_layout = QHBoxLayout()
        root_layout.addLayout(main_layout)

        # Sidebar layout
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        # Data sources
        self.source_group = QGroupBox("Data Sources")
        sidebar_layout.addWidget(self.source_group, 3)

        self.source_root_layout = QVBoxLayout()
        self.source_root_layout.setContentsMargins(0, 4, 0, 0)
        self.source_group.setLayout(self.source_root_layout)

        self.source_scroll = QScrollArea()
        self.source_scroll.setWidgetResizable(True)
        self.source_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.source_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.source_root_layout.addWidget(self.source_scroll)

        self.source_scroll_widget = QWidget()
        self.source_scroll.setWidget(self.source_scroll_widget)

        self.source_layout = QVBoxLayout()
        self.source_scroll_widget.setLayout(self.source_layout)

        # Add sidebar to main layout
        main_layout.addWidget(sidebar)

        # Initialize the plot widget
        self.plot_widget = pg.PlotWidget()
        main_layout.addWidget(self.plot_widget, 5)

        # Set plot ranges and labels
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.setLabel("bottom", "Time", units="s")
        self.plot_widget.setMouseEnabled(x=True, y=False)
        self.plot_widget.showGrid(x=True, y=True)
        pg.setConfigOptions(antialias=True)

        # Controls
        autoscale_button.clicked.connect(self.plot_widget.setAutoVisible)
        autoscale_button.clicked.connect(self.plot_widget.enableAutoRange)

    def toggle_play_pause(self) -> None:
        """Toggle between playing and pausing the plot updates."""
        if self.play_pause_button.isChecked():
            self.timer.stop()
            self.play_pause_button.setText("Resume")
        else:
            self.timer.start()
            self.play_pause_button.setText("Pause")

    def clear_data(self) -> None:
        """Clear all plotted data."""
        self.data_x.clear()
        for name in self.data_sources:
            self.data_y[name].clear()
            self.plot_data_items[name].clear()
        self.plot_x = 0

    def update_timer_interval(self, value: int) -> None:
        """Update the timer interval for data updates.

        Args:
            value: New interval in milliseconds
        """
        was_active = self.timer.isActive()
        if was_active:
            self.timer.stop()
        self.timer.setInterval(value)
        if was_active:
            self.timer.start()

    def add_data_source(self, name: str, func: Callable[[float], float], color: str = "w", width: int = 2, *, enabled = False) -> None:
        """
        Add a new data source to the plot.

        Args:
            name: The name of the data source
            func: A function that takes a float x value and returns a float y value
            color: The color to use for plotting (default: white)
        """
        if name in self.data_sources:
            msg = f"Data source '{name}' already exists"
            raise ValueError(msg)

        # Add the source function
        self.data_sources[name] = {"func": func, "color": color, "width": width, "enabled": enabled}

        # Create a checkbox for the source
        checkbox = DataSourceCheckBox(name, color)
        if enabled:
            checkbox.setChecked(True)
        checkbox.stateChanged.connect(lambda: self._update_selected_source(name))
        self.source_checkboxes[name] = checkbox
        self.source_layout.addWidget(checkbox)

        # Initialize data structures for the new source
        self.data_y[name] = []
        self.plot_data_items[name] = self.plot_widget.plot(pen=pg.mkPen(color, width=width))

        self.source_group.setFixedWidth(self.source_group.sizeHint().width() + 28)

    def _update_selected_source(self, name: str) -> None:
        """Update the visibility of a data source."""
        self.data_sources[name]["enabled"] = self.source_checkboxes[name].isChecked()
        self.on_data_source_selection_changed.emit(name, self.source_checkboxes[name].isChecked())

    def get_data_sources(self):
        return self.data_sources

    def edit_pen_color(self, name: str, color: str = "w"):
        """
        Edit the color of a data source's pen.

        Args:
            name: The name of the data source
            color: The new color to use for plotting (default: white)
        """
        self.data_sources[name]["color"] = color
        self.plot_data_items[name].setPen(pg.mkPen(color, width=self.data_sources[name]["width"]))
        self.source_checkboxes[name].set_color(color)

    def edit_pen_width(self, name: str, width: int):
        """
        Edit the width of a data source's pen.

        Args:
            name: The name of the data source
            width: The new width to use for plotting
        """
        self.data_sources[name]["width"] = width
        self.plot_data_items[name].setPen(pg.mkPen(self.data_sources[name]["color"], width=width))


    def remove_data_source(self, name: str) -> None:
        """
        Remove a data source from the plot.

        Args:
            name: The name of the data source to remove
        """
        if name not in self.data_sources:
            msg = f"Data source '{name}' does not exist"
            raise ValueError(msg)

        # Remove the checkbox
        self.source_checkboxes[name].deleteLater()
        del self.source_checkboxes[name]

        # Remove the data
        del self.data_sources[name]
        del self.data_y[name]

        # Remove the plot item
        self.plot_widget.removeItem(self.plot_data_items[name])
        del self.plot_data_items[name]

    def update_plot(self) -> None:
        """Update the plot with new data points."""
        # Add new x value
        self.data_x.append(self.plot_x)

        # Update each data source
        for name, data in self.data_sources.items():
            # Generate the y-value using the source function
            y_value = data["func"](self.plot_x)
            self.data_y[name].append(y_value)

            # Update the plot data item, but set visibility based on selection
            self.plot_data_items[name].setData(self.data_x, self.data_y[name])
            self.plot_data_items[name].setVisible(data["enabled"])

        self.plot_x += 0.1  # Increment x-value by 0.1


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LivePlot()

    # Add default sources
    window.add_data_source("sin", math.sin, "c")  # Cyan for sine wave
    window.add_data_source("cos", math.cos, "r")  # Red for cosine wave
    window.add_data_source("tan", math.tan, "m")  # Magenta for tangent wave
    window.add_data_source("exp", lambda x: math.exp(x), "b")  # Blue for exponential data
    window.add_data_source("sqrt", lambda x: math.sqrt(x), "y")  # Yellow for square root data
    window.add_data_source(
        "rand",
        lambda _: random.randint(-100, 100) / 100,  # noqa: S311
        "g",
    )  # Green for random data

    window.show()
    sys.exit(app.exec())
