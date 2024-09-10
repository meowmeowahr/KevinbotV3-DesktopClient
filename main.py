import sys

from qtpy.QtCore import QSize, QSettings
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QVBoxLayout, QHBoxLayout, QMainWindow, QWidget, QApplication, QTabWidget, QToolBox, QLabel, QRadioButton
import qtawesome as qta
import qdarktheme as qtd

from ui.util import add_tabs
from ui.widgets import WarningBar

__version__ = "v0.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Kevinbot Desktop Client {__version__}")

        # Settings Manager
        self.settings = QSettings("meowmeowahr", "KevinbotDesktopClient", self)

        # Theme
        theme = self.settings.value("window/theme", "dark")
        if theme == "dark":
            qtd.setup_theme("dark", additional_qss="#warning_bar_text{color: #050505;}")
            qta.dark(app)
        elif theme == "light":
            qtd.setup_theme("light")
            qta.light(app)
        else:
            qtd.setup_theme("auto")

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
            ["About", qta.icon("mdi6.information-slab-circle")],
        ]
        self.main, self.controller, self.debug, self.settings_widget, self.about_widget = add_tabs(self.tabs, tabs)

        self.settings_widget.setLayout(self.settings_layout(self.settings))

        self.show()

    def settings_layout(self, settings: QSettings):
        layout = QVBoxLayout()

        toolbox = QToolBox()
        layout.addWidget(toolbox)

        theme_widget = QWidget()
        toolbox.addItem(theme_widget, "Theme and Appearance")


        theme_layout = QVBoxLayout()
        theme_widget.setLayout(theme_layout)

        theme_warning = WarningBar("Restart required to apply theme")
        theme_layout.addWidget(theme_warning)

        dark_mode_layout = QHBoxLayout()
        theme_layout.addLayout(dark_mode_layout)

        dark_mode_label = QLabel("Style")
        dark_mode_layout.addWidget(dark_mode_label)

        theme_dark = QRadioButton("Dark")
        dark_mode_layout.addWidget(theme_dark)

        theme_light = QRadioButton("Light")
        dark_mode_layout.addWidget(theme_light)

        theme_system = QRadioButton("System")
        dark_mode_layout.addWidget(theme_system)

        if settings.value("window/theme", "dark") == "dark":
            theme_dark.setChecked(True)
        elif settings.value("window/theme", "dark") == "light":
            theme_light.setChecked(True)
        else:
            theme_system.setChecked(True)

        theme_dark.clicked.connect(lambda: self.set_theme("dark"))
        theme_light.clicked.connect(lambda: self.set_theme("light"))
        theme_system.clicked.connect(lambda: self.set_theme("system"))

        return layout

    def set_theme(self, theme: str):
        self.settings.setValue("window/theme", theme)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationVersion(__version__)
    app.setApplicationName("Kevinbot Desktop Client")
    win = MainWindow()
    app.exec()