from midi_router import MidiRouter
import mido
import json
import keyboard
import asyncio
import pyautogui

def choose_device(devices: list = mido.get_input_names()) -> str | None:
    i = 0
    for device in devices:
        i +=1
        print(f"{i}) {device}\n")
    
    try:
        i = int(input("Device: "))
        return devices[i - 1]
    except:
        return None

device = choose_device()
port = mido.open_input(device)
router = MidiRouter()

screen_width, screen_height = pyautogui.size()

async def perform_keyboard_action(key: str) -> None:
    print(key)
    keyboard.press(key)
    await asyncio.sleep(0.1)
    keyboard.release(key)

x_position = 0
y_position = 0
last_x_position = 0
last_y_position = 0

ss = 0.5 * 0.6 + 0.2
sensitivityMod = ss * ss * ss
sens = sensitivityMod * 8

x_fader_screen_ratio = 16383 / screen_width
y_fader_screen_ratio = 16383 / screen_height

async def perform_mouse_click_action(action: str):
    if action == "mouse_click_left":
        function = lambda: pyautogui.mouseDown(button="left")
    elif action == "mouse_release_left":
        function = lambda: pyautogui.mouseUp(button="left")
    elif action == "mouse_click_right":
        function = lambda: pyautogui.mouseDown(button="right")
    elif action == "mouse_release_right":
        function = lambda: pyautogui.mouseUp(button="right")
    elif action == "mouse_click_middle":
        function = lambda: pyautogui.click(button="middle")
    else:
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        function
    )

async def perform_mouse_movement_action(action: str, fader_position: tuple):
    global x_position
    global y_position
    global last_x_position
    global last_y_position

    msb = fader_position[0]
    lsb = fader_position[1]
    fader_value = (msb << 7) | lsb

    if action == "mouse_move_x":
        x_position = fader_value / x_fader_screen_ratio
    elif action == "mouse_move_y":
        y_position = fader_value / y_fader_screen_ratio
    else:
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: pyautogui.moveRel((x_position - last_x_position) * sens, (y_position - last_y_position) * sens, duration=0)
    )

    last_x_position = x_position
    last_y_position = y_position

with open("config.json", "r") as file:
    config = json.load(file)

for bind in config["keyboard_bindings"]:
    try:
        msg_type = bind.get("msg_type")
        key = bind.get("key")
        channel = bind.get("channel")
        value = bind.get("value")
        action = bind.get("action")

        print(f"Registerd keyboard binding:\n    msg_type: {msg_type}, key: {key}, channel: {channel}, value: {value}, action: {action}")
        router.register_keyboard_binding(msg_type, key, channel, value, lambda _msg, action=action: perform_keyboard_action(action))
    except Exception as e:
        print(f"Could not register keyboard binding: {e}")

for bind in config["mouse_bindings"]:
    try:
        msg_type = bind.get("msg_type")
        keys = bind.get("keys")
        channel = bind.get("channel")
        value = bind.get("value")
        action = bind.get("action")

        print(f"Registerd mouse binding:\n    msg_type: {msg_type}, keys: {keys}, channel: {channel}, action: {action}")
        if action.startswith("mouse_move"):
            router.register_mouse_binding(msg_type, keys, channel, None, action, perform_mouse_movement_action)
        else:
            router.register_mouse_binding(msg_type, keys, channel, value, action, perform_mouse_click_action)
    except Exception as e:
        print(f"Could not register mouse binding: {e}")

print("Listening...")

async def main():
    while True:
        for message in port.iter_pending():
            print(message)
            router.handle(message)

        await asyncio.sleep(0.001)

asyncio.run(main())