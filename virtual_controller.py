import vgamepad as vg
import time

gamepad = vg.VX360Gamepad()
time.sleep(5)
# press a button to wake the device up
gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gamepad.update()
time.sleep(0.5)
gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gamepad.update()
time.sleep(0.5)

# press buttons and things
gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
gamepad.left_trigger_float(value_float=0.5)
gamepad.right_trigger_float(value_float=0.5)
gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.2)
gamepad.right_joystick_float(x_value_float=-1.0, y_value_float=1.0)

gamepad.update()

time.sleep(1.0)

# release buttons and things
gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)
gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
gamepad.right_trigger_float(value_float=0.0)
gamepad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)

gamepad.update()

time.sleep(1.0)

gamepad.update()

while True:
    # gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    # gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.2)
    # gamepad.update()
    # time.sleep(0.2)
    # gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
    # gamepad.left_joystick_float(x_value_float=0.0, y_value_float=0.0)
    # gamepad.update()
    # time.sleep(0.2)
    # Sweep left stick
    for i in range(0, 101, 10):
        gamepad.left_joystick_float(x_value_float=i / 100.0, y_value_float=0.0)
        gamepad.right_joystick_float(x_value_float=i / 100.0 - 1, y_value_float=0.0)
        gamepad.update()
        time.sleep(0.01)
    for i in range(100, -1, -10):
        gamepad.left_joystick_float(x_value_float=i / 100.0, y_value_float=0.0)
        gamepad.right_joystick_float(x_value_float=i / 100.0 - 1, y_value_float=0.0)
        gamepad.update()
        time.sleep(0.01)
