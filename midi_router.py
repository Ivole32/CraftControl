import asyncio

class MidiRouter:
    def __init__(self):
        self.routes = {}

    def register(self, msg_type, key, func):
        self.routes[(msg_type, key)] = func

    def handle(self, msg):
        key = None

        if msg.type.startswith("note"):
            key = msg.note
        elif msg.type == "control_change":
            key = msg.control

        route = self.routes.get((msg.type, key))
        if route:
            function = route(msg)
            asyncio.create_task(function)