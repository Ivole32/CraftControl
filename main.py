import mido
from pynput.keyboard import Controller
import threading
import queue
import time

keyboard = Controller()
event_queue = queue.Queue()

# ---------------- MIDI THREAD ----------------
def midi_listener(port_name):
    with mido.open_input(port_name) as port:
        print("🎹 MIDI listening...")
        for msg in port:
            event_queue.put(msg)

# ------------- KEYBOARD THREAD ---------------
def keyboard_worker():
    while True:
        msg = event_queue.get()

        # Beispiel: jede Note triggert "a"
        if msg.type == "control_change":
            if msg.channel == 0:
                if msg.value == 65:
                    key = "a"
                elif msg.value == 63:
                    key = "d"
                else:
                    continue
            if msg.channel == 1:
                if msg.value == 65:
                    key = "w"
                elif msg.value == 63:
                    key = "s"
                else: 
                    continue

            keyboard.press(key)
            time.sleep(0.00000001)
            keyboard.release(key)

        event_queue.task_done()

# ------------- MIDI PORT AUSWAHL --------------
print("Recognized MIDI-Inputs:")
options = {}
for i, name in enumerate(mido.get_input_names(), start=1):
    print(f"{i}) {name}")
    options[str(i)] = name

PORT_NAME = options[input("Choose MIDI Number: ")]

# ---------------- THREADS START ---------------
threading.Thread(
    target=midi_listener,
    args=(PORT_NAME,),
    daemon=True
).start()

threading.Thread(
    target=keyboard_worker,
    daemon=True
).start()

# ---------------- MAIN LOOP -------------------
print("✅ Ready. Press Ctrl+C to exit.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("❌ Stopped.")
