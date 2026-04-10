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

async def a(msg):
    print("a")
    keyboard.press("a")
    await asyncio.sleep(0.1)
    keyboard.release("a")

router.register('control_change', 33, a)
print("Listening...")

async def main():
    while True:
        for message in port.iter_pending():
            print(message)
            router.handle(message)

        await asyncio.sleep(0.001)

asyncio.run(main())