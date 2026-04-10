import asyncio

class MidiRouter:
    def __init__(self):
        self.routes = {}

    def register(self, msg_type, key, value, func):
        if not value:
            self.routes[(msg_type, key)] = func
        else:
            self.routes[(msg_type, key, value)] = func 

    def handle(self, msg):
        key = None

        if msg.type.startswith("note"):
            key = msg.note
        elif msg.type == "control_change":
            key = msg.control

        try:
            value = msg.value
        except:
            value = msg.velocity

        route = self.routes.get((msg.type, key)) or self.routes.get((msg.type, key, value))
        if route:
            function = route(msg)
            asyncio.create_task(function)