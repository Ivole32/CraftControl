from pynput.keyboard import Key, Controller
import time

keyboard = Controller()

time.sleep(3)

for c in "Hello World!":
    keyboard.press(c)
    keyboard.release(c)

time.sleep(1)

keyboard.press(Key.enter)
keyboard.release(Key.enter)

keyboard.press(Key.ctrl)
keyboard.press('c')
keyboard.release('c')
keyboard.release(Key.ctrl)