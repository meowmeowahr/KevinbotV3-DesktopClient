"""
Controller interface for Kevinbot v3 Desktop Client
Uses a pyglet backend and PySide6 for frontend
"""

import sys
import typing
import uuid

import pyglet
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QRgba64
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from kevinbot_desktopclient.components.uuid_manager import UuidManager
from kevinbot_desktopclient.ui.delegates import NoFocusDelegate


def begin_controller_backend():  # pragma: no cover
    """
    Blocking loop - pyglet backend for detecting controllers
    :return:
    """
    return pyglet.app.run()


def map_press(controller: pyglet.input.Controller, action: typing.Callable):
    """
    Adds a new mapping to an existing Controller while keeping all old mappings
    :param controller: pyglet controller to map
    :param action: callable function that handles all button presses
    :return:
    """
    previous_mapping = controller.on_button_press

    def handler(controller: pyglet.input.Controller, button: str):
        previous_mapping(controller, button)
        action(controller, button)

    controller.on_button_press = handler


def map_stick(controller: pyglet.input.Controller, action: typing.Callable):
    """
    Adds a new mapping to an existing Controller while keeping all old mappings
    :param controller: pyglet controller to map
    :param action: callable function that handles all stick values
    :return:
    """
    previous_mapping = controller.on_stick_motion

    def handler(controller: pyglet.input.Controller, stick: str, xvalue: float, yvalue: float):
        previous_mapping(controller, stick, xvalue, yvalue)
        action(controller, stick, xvalue, yvalue)

    controller.on_stick_motion = handler


def map_pov(controller: pyglet.input.Controller, action: typing.Callable):
    """
    Adds a new mapping to an existing Controller while keeping all old mappings
    :param controller: pyglet controller to map
    :param action: callable function that handles all dpad presses
    :return:
    """
    previous_mapping = controller.on_dpad_motion

    def handler(
        controller: pyglet.input.Controller,
        dpleft: bool,  # noqa: FBT001
        dpright: bool,  # noqa: FBT001
        dpup: bool,  # noqa: FBT001
        dpdown: bool,  # noqa: FBT001
    ):
        previous_mapping(controller, dpleft, dpright, dpup, dpdown)
        action(controller, dpleft, dpright, dpup, dpdown)

    controller.on_dpad_motion = handler


class ControllerManagerWidget(QWidget):
    on_disconnected = Signal(pyglet.input.Controller)
    on_connected = Signal(pyglet.input.Controller)
    on_refresh = Signal(list)

    def __init__(self, slots=2):
        super().__init__()

        self.slots = slots

        # ConMan
        self._controller_manager = pyglet.input.ControllerManager()
        self._controller_manager.on_disconnect = self.controller_disconnect
        self._controller_manager.on_connect = self.controller_reconnect
        self.controllers: list[pyglet.input.Controller] = self._controller_manager.get_controllers()
        self.controller_store = UuidManager()

        # Layout
        self.root_layout = QHBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.root_layout)

        # Connected Controllers List
        self.controller_source_layout = QVBoxLayout()
        self.controller_source_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addLayout(self.controller_source_layout)

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
        for controller in self.controller_store.get_items():
            controller.close()

        self.connected_list.clear()
        self.controller_store.clear()
        self.controllers: list[pyglet.input.Controller] = self._controller_manager.get_controllers()
        for controller in self.controllers:
            self.controller_store.add_item(controller)
            item = QListWidgetItem(controller.name)
            item.setToolTip(f"{controller.name}; GUID: {controller.guid}")
            item.setFont(QFont(self.font().families(), 11))
            item.setData(Qt.ItemDataRole.UserRole, self.controller_store.get_uuid(controller))
            if not controller.device.is_open:
                controller.open()
            controller.rumble_play_weak(1, 0.1)
            controller.on_button_press = self.controller_press
            controller.on_button_release = self.controller_release
            controller.on_stick_motion = self.controller_stick_motion
            self.connected_list.addItem(item)
        self.on_refresh.emit(self.controller_store.get_items())

    def controller_press(self, controller: pyglet.input.Controller, _button: str):
        for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard):
            if controller == self.controller_store.get_item(item.data(Qt.ItemDataRole.UserRole)):
                item.setBackground(QColor(QRgba64().fromRgba(76, 175, 80, 127)))

    def controller_release(self, controller: pyglet.input.Controller, _button: str):
        for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard):
            if controller == self.controller_store.get_item(item.data(Qt.ItemDataRole.UserRole)):
                item.setBackground(Qt.GlobalColor.transparent)

    def controller_stick_motion(
        self,
        controller: pyglet.input.Controller,
        stick: str,
        xvalue: float,
        yvalue: float,
    ):
        pass

    def controller_disconnect(self, controller: pyglet.input.Controller):
        if controller in self.controllers:
            self.controllers.remove(controller)
        self.on_disconnected.emit(controller)
        return controller

    def controller_reconnect(self, controller: pyglet.input.Controller):
        self.controllers.append(controller)
        self.on_connected.emit(controller)
        return controller

    def get_controller_ids(self) -> list[uuid.UUID]:
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard)
        ]

    def get_controllers(self) -> list[pyglet.input.Controller | None]:
        """
        Get controllers in the visual order
        :return: pyglet Controllers
        """
        ids = []
        ids = [
            self.controller_store.get_item(item.data(Qt.ItemDataRole.UserRole))
            for item in self.connected_list.findItems("*", Qt.MatchFlag.MatchWildcard)
        ]

        return ids + [None] * max(0, self.slots - len(ids))


if __name__ == "__main__":  # pragma: no cover

    class ExampleWindow(QWidget):
        def __init__(self):
            super().__init__()

            self.vlayout = QVBoxLayout()
            self.setLayout(self.vlayout)

            self.manager = ControllerManagerWidget()
            self.manager.on_connected.connect(lambda x: print("Connect", x))  # noqa: T201
            self.manager.on_disconnected.connect(lambda x: print("Disconnect", x))  # noqa: T201
            self.vlayout.addWidget(self.manager)

            self.uuid_button = QPushButton("Get UUIDs")
            self.uuid_button.clicked.connect(
                lambda: print(self.manager.get_controller_ids())  # noqa: T201
            )
            self.vlayout.addWidget(self.uuid_button)

            self.con_button = QPushButton("Get Controllers")
            self.con_button.clicked.connect(
                lambda: print(self.manager.get_controllers())  # noqa: T201
            )
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
                print("List empty")  # noqa: T201

        @staticmethod
        def press(controller, button):
            print("press", controller, button)  # noqa: T201

    app = QApplication(sys.argv)
    window = ExampleWindow()
    begin_controller_backend()
    sys.exit(app.exec())
