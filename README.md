<p align="center">
  <img src="assets/icons/icon.svg" alt="Kevinbot v3 logo" width=120/>
</p>

# Kevinbot v3 Desktop Client

[![codecov](https://codecov.io/gh/meowmeowahr/KevinbotV3-DesktopClient/graph/badge.svg?token=7Y1GZD15MH)](https://codecov.io/gh/meowmeowahr/KevinbotV3-DesktopClient)
[![Github Version](https://img.shields.io/github/v/release/meowmeowahr/KevinbotV3-DesktopClient?display_name=tag&include_prereleases)](https://github.com/meowmeowahr/KevinbotV3-DesktopClient/releases)

> [!WARNING]
> This application is still being developed and is not fully functional yet. Do not expect it to work!

Home to the new Kevinbot v3 Desktop Client. This is intended to be a replacement for the [Remote](https://github.com/meowmeowahr/KevinbotV3-Remote).

Drive and operate Kevinbot using a regular PC, gaming controllers, and a USB-connected XBee. Get rid of the need for custom, hard to debug, and slow Raspberry Pi hardware.

## Features

* Modern PySide6 GUI with dark theme
* pyglet backend for controllers
* Support Escaped/Unescaped XBee API modes
* Support all XBee-supported baud rates and flow control
* Unit and coverage testing
* Cross-platform compatibility (Mac support hasn't been tested)
* GNU GPLv3 license

## Known Issues

### Q: App crashes on launch with PySide 6.8.0

This is related to star imports being broken again.

https://bugreports.qt.io/browse/PYSIDE-2888
<br>
https://github.com/spyder-ide/qtpy/issues/494

### A: Update your PySide6 version to 6.8.0.1