from typing import Dict, List, Callable, Optional
import sys
import random
import math
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QCheckBox, QLabel, QGroupBox, QPushButton,
    QSpinBox, QFrame
)
from PySide6.QtCore import QTimer, SignalInstance

from desktopclient.ui.widgets import ColorBlock

def color_string_to_hex(color_str):
    # Map of shorthand color strings to their hex codes
    color_map = {
        'w': '#FFFFFF',  # White
        'r': '#FF0000',  # Red
        'g': '#00FF00',  # Green
        'b': '#0000FF',  # Blue
        'c': '#00FFFF',  # Cyan
        'm': '#FF00FF',  # Magenta
        'y': '#FFFF00',  # Yellow
        'k': '#000000',  # Black
        'gray': '#808080' # Gray
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
        self.color.set_color(color_string_to_hex(color))

class LivePlot(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        
        # Initialize data structures for dynamic sources
        self.data_sources: Dict[str, Callable[[float], float]] = {}
        self.source_checkboxes: Dict[str, DataSourceCheckBox] = {}
        self.data_y: Dict[str, List[float]] = {}
        self.plot_data_items: Dict[str, pg.PlotDataItem] = {}
        
        self._setup_ui()
        
        # Initialize the data series for real-time updates
        self.data_x: List[float] = []
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

        # Data sources group
        self.source_group = QGroupBox("Data Sources")
        self.source_layout = QVBoxLayout(self.source_group)
        sidebar_layout.addWidget(self.source_group)

        # Data to Graph group
        self.graph_group = QGroupBox("Data to Graph")
        graph_layout = QVBoxLayout(self.graph_group)
        self.graph_data_label = QLabel("Current Sources: None")
        graph_layout.addWidget(self.graph_data_label)
        sidebar_layout.addWidget(self.graph_group)

        # Add sidebar to main layout
        main_layout.addWidget(sidebar)

        # Initialize the plot widget
        self.plot_widget = pg.PlotWidget()
        main_layout.addWidget(self.plot_widget)

        # Set plot ranges and labels
        self.plot_widget.setLabel('left', 'Value')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
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

    def add_data_source(self, name: str, func: Callable[[float], float], color: str = 'w') -> None:
        """
        Add a new data source to the plot.
        
        Args:
            name: The name of the data source
            func: A function that takes a float x value and returns a float y value
            color: The color to use for plotting (default: white)
        """
        if name in self.data_sources:
            raise ValueError(f"Data source '{name}' already exists")
            
        # Add the source function
        self.data_sources[name] = func
        
        # Create a checkbox for the source
        checkbox = DataSourceCheckBox(name, color)
        checkbox.stateChanged.connect(self.select_sources)
        self.source_checkboxes[name] = checkbox
        self.source_layout.addWidget(checkbox)
        
        # Initialize data structures for the new source
        self.data_y[name] = []
        self.plot_data_items[name] = self.plot_widget.plot(pen=color)

    def remove_data_source(self, name: str) -> None:
        """
        Remove a data source from the plot.
        
        Args:
            name: The name of the data source to remove
        """
        if name not in self.data_sources:
            raise ValueError(f"Data source '{name}' does not exist")
            
        # Remove the checkbox
        self.source_checkboxes[name].deleteLater()
        del self.source_checkboxes[name]
        
        # Remove the data
        del self.data_sources[name]
        del self.data_y[name]
        
        # Remove the plot item
        self.plot_widget.removeItem(self.plot_data_items[name])
        del self.plot_data_items[name]
        
        # Update the display
        self.select_sources()


    def update_plot(self) -> None:
        """Update the plot with new data points."""
        # Add new x value
        self.data_x.append(self.plot_x)

        # Update each data source
        for name, func in self.data_sources.items():
            # Generate the y-value using the source function
            y_value = func(self.plot_x)
            self.data_y[name].append(y_value)

            # Update the plot data item, but set visibility based on selection
            self.plot_data_items[name].setData(self.data_x, self.data_y[name])
            self.plot_data_items[name].setVisible(self.source_checkboxes[name].isChecked())

        self.plot_x += 0.1  # Increment x-value by 0.1

    def select_sources(self) -> None:
        """Update the sources to graph based on selected checkboxes."""
        selected_sources = [
            name for name, checkbox in self.source_checkboxes.items()
            if checkbox.isChecked()
        ]

        # Update the label to show selected sources
        sources_text = ', '.join(selected_sources) if selected_sources else 'None'
        self.graph_data_label.setText(f"Current Sources: {sources_text}")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LivePlot()

    # Add default sources
    window.add_data_source("sin", math.sin, 'c')  # Cyan for sine wave
    window.add_data_source("cos", math.cos, 'r')  # Red for cosine wave
    window.add_data_source("tan", math.tan, 'm')  # Magenta for tangent wave
    window.add_data_source("exp", lambda x: math.exp(x), 'b')  # Blue for exponential data
    window.add_data_source("sqrt", lambda x: math.sqrt(x), 'y')  # Yellow for square root data
    window.add_data_source("rand", lambda x: random.randint(-100, 100) / 100, 'g')  # Green for random data

    window.show()
    sys.exit(app.exec())