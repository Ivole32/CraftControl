from midi_router import MidiRouter
import mido
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

router.register('control_change', 33, 0, 63, lambda key: press_key("s"))
router.register('control_change', 33, 0, 65, lambda key: press_key("w"))

router.register('control_change', 33, 1, 63, lambda key: press_key("d"))
router.register('control_change', 33, 1, 65, lambda key: press_key("a"))

router.register('note_on', 65, 6, 127, lambda key: press_key("space"))
print("Listening...")

async def main():
    while True:
        for message in port.iter_pending():
            print(message)
            router.handle(message)

        await asyncio.sleep(0.001)

asyncio.run(main())