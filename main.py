import sys

from qtpy.QtCore import QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QVBoxLayout, QMainWindow, QWidget, QApplication, QTabWidget
import qtawesome as qta

from ui.util import add_tabs

__version__ = "v0.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Kevinbot Desktop Client {__version__}")

        self.root_widget = QWidget()
        self.setCentralWidget(self.root_widget)

        self.root_layout = QVBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_widget.setLayout(self.root_layout)

        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(32, 32))
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.root_layout.addWidget(self.tabs)

        tabs: list[list[str | QIcon]] = [
            ["Main", qta.icon("mdi6.hub")],
            ["Controllers", qta.icon("mdi6.microsoft-xbox-controller")],
            ["Debug", qta.icon("mdi6.bug")],
            ["Settings", qta.icon("mdi6.cog")],
        ]
        self.main, self.controller, self.debug, self.settings = add_tabs(self.tabs, tabs)

        self.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationVersion(__version__)
    app.setApplicationName("Kevinbot Desktop Client")
    win = MainWindow()
    app.exec()