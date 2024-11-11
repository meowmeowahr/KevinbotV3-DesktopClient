"""
Main components for the Kevinbot v3 Desktop Client
"""

from kevinbot_desktopclient.components.controllers import ControllerManagerWidget, begin_controller_backend
from kevinbot_desktopclient.components.ping import PingWidget, PingWorker
from kevinbot_desktopclient.components.uuid_manager import UuidManager

__all__ = [
    "ControllerManagerWidget",
    "begin_controller_backend",
    "PingWidget",
    "PingWorker",
    "UuidManager",
]
