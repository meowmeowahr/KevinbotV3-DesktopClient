"""
Controller interface for Kevinbot v3 Desktop Client
Uses a pyglet backend and qtpy for frontend
"""

import sys
import typing
import threading
import uuid

from qtpy.QtWidgets import (QApplication, QWidget, QPushButton, QListWidget,
                            QHBoxLayout, QVBoxLayout, QListWidgetItem)
from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QFont, QRgba64, QColor

import pyglet # Controller backend

from ui.delegates import NoFocusDelegate
from .uuid_manager import UuidManager


def begin_controller_backend():
    """
    Spin up the pyglet backend for detecting controllers
    :return:
    """
    return threading.Thread(target=pyglet.app.run, daemon=True).start()


def map_press(controller: pyglet.input.Controller, action: typing.Callable):
    """
    Adds a new mapping to an existing Controller while keeping all old mappings
    :param controller: pyglet controller to map
    :param action: callable function that handles all button presses
    :return:
    """
    previous_mapping = controller.on_button_press
    def handler(c: pyglet.input.Controller, button):
        previous_mapping(c, button)
        action(c, button)

    controller.on_button_press = handler

class ControllerManagerWidget(QWidget):
    on_disconnected = Signal(pyglet.input.Controller)
    on_connected = Signal(pyglet.input.Controller)

    def __init__(self, slots=2):
        super().__init__()

        self.slots = slots

        # ConMan
        self._controller_manager = pyglet.input.ControllerManager()
        self._controller_manager.on_disconnect = self.controller_disconnect
        self._controller_manager.on_connect = self.controller_reconnect
        self.controllers = self._controller_manager.get_controllers()
        self.controller_store = UuidManager()

        # Layout
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        # Connected Controllers List
        self.controller_source_layout = QVBoxLayout()
        self.layout.addLayout(self.controller_source_layout)

        self.refresh_button = QPushButton("Refresh Controllers")
        self.refresh_button.clicked.connect(self.refresh_controllers)
        self.controller_source_layout.addWidget(self.refresh_button)

        self.connected_list = QListWidget()
        self.connected_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.connected_list.setItemDelegate(NoFocusDelegate())
        self.connected_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.controller_source_layout.addWidget(self.connected_list)

        self.timers: list[QTimer] = []

        # Refresh controllers on startup
        self.refresh_controllers()


    def refresh_controllers(self):
        self.connected_list.clear()
        self.controller_store.clear()
        for controller in self.controllers:
            self.controller_store.add_item(controller)
            item = QListWidgetItem(controller.name)
            item.setFont(QFont(app.font().families(), 11))
            item.setData(Qt.ItemDataRole.UserRole, self.controller_store.get_uuid(controller))
            if not controller.device.is_open:
                controller.open()
            controller.on_button_press = self.controller_press
            controller.on_button_release = self.controller_release
            self.connected_list.addItem(item)

    def controller_press(self, controller, _):
        for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard):
            if controller == self.controller_store.get_item(item.data(Qt.ItemDataRole.UserRole)):
                item.setBackground(QColor(QRgba64().fromRgba(76, 175, 80,127)))

    def controller_release(self, controller, _):
        for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard):
            if controller == self.controller_store.get_item(item.data(Qt.ItemDataRole.UserRole)):
                item.setBackground(Qt.GlobalColor.transparent)

    def controller_disconnect(self, controller: pyglet.input.Controller):
        self.controllers.remove(controller)
        self.on_disconnected.emit(controller)


    def controller_reconnect(self, controller: pyglet.input.Controller):
        self.controllers.append(controller)
        self.on_connected.emit(controller)

    def get_controller_ids(self) -> list[uuid.UUID]:
        ids = []
        for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard):
            ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def get_controllers(self) -> list[pyglet.input.Controller | None]:
        """
        Get controllers in the visual order
        :return: pyglet Controllers
        """
        ids = []
        for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard):
            ids.append(self.controller_store.get_item(item.data(Qt.ItemDataRole.UserRole)))
        return ids + [None] * max(0, self.slots - len(ids))

if __name__ == "__main__":
    class ExampleWindow(QWidget):
        def __init__(self):
            super().__init__()

            self.vlayout = QVBoxLayout()
            self.setLayout(self.vlayout)

            self.manager = ControllerManagerWidget()
            self.manager.on_connected.connect(lambda x: print("Connect", x))
            self.manager.on_disconnected.connect(lambda x: print("Disconnect", x))
            self.vlayout.addWidget(self.manager)

            self.uuid_button = QPushButton("Get UUIDs")
            self.uuid_button.clicked.connect(lambda: print(self.manager.get_controller_ids()))
            self.vlayout.addWidget(self.uuid_button)

            self.con_button = QPushButton("Get Controllers")
            self.con_button.clicked.connect(lambda: print(self.manager.get_controllers()))
            self.vlayout.addWidget(self.con_button)

            self.map_button = QPushButton("Map Controller 0 Buttons")
            self.map_button.clicked.connect(self.map_controller)
            self.vlayout.addWidget(self.map_button)

            self.show()

        def map_controller(self):
            c = self.manager.get_controllers()[0]
            if c:
                map_press(c, self.press)
            else:
                print("List empty")

        @staticmethod
        def press(controller, button):
            print("press", controller, button)

    app = QApplication(sys.argv)
    window = ExampleWindow()
    begin_controller_backend()
    sys.exit(app.exec())
