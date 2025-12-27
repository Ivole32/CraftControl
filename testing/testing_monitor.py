import mido
from datetime import datetime

print("Recognized MIDI-Inputs:")
options = {}
option_number = 0
for name in mido.get_input_names():
    option_number += 1
    print(f"{str(option_number)}) {name}")
    options[str(option_number)] = name

PORT_NAME = options[input("Choose MIDI Number: ")]


print(f"Connecting with: {PORT_NAME}")
print("Press buttons or move fader...\n")

with mido.open_input(PORT_NAME) as port:
    for msg in port:
        time = datetime.now().strftime("%H:%M:%S")

        if msg.type in ["note_on", "note_off"]:
            print(
                f"[{time}] NOTE | "
                f"Type={msg.type:<8} "
                f"Note={msg.note:<3} "
                f"Velocity={msg.velocity:<3} "
                f"Channel={msg.channel}"
            )

        elif msg.type == "control_change":
            print(
                f"[{time}] CC   | "
                f"Control={msg.control:<3} "
                f"Value={msg.value:<3} "
                f"Channel={msg.channel}"
            )

        else:
            print(f"[{time}] OTHER | {msg}")