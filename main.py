from midi_router import MidiRouter
import mido
import json
import keyboard
import asyncio

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

async def press_key(key: str) -> None:
    print(key)
    keyboard.press(key)
    await asyncio.sleep(0.1)
    keyboard.release(key)

with open("config.json", "r") as file:
    config = json.load(file)

for bind in config["bindings"]:
    msg_type = bind.get("msg_type")
    print(msg_type)
    key = bind.get("key")
    print(key)
    channel = bind.get("channel")
    print(channel)
    value = bind.get("value")
    print(value)
    action = bind.get("action")
    print(action)
    print("\n")

    router.register(msg_type, key, channel, value, lambda _msg, action=action: press_key(action))

print("Listening...")

async def main():
    while True:
        for message in port.iter_pending():
            print(message)
            router.handle(message)

        await asyncio.sleep(0.001)

asyncio.run(main())