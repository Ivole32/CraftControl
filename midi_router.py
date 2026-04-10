import asyncio

class MidiRouter:
    def __init__(self):
        self.routes = {}

    def register(self, msg_type, key, channel, value, func):
        if value == None:
            self.routes[(msg_type, key, channel)] = func
        else:
            self.routes[(msg_type, key, channel, value)] = func 

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

        channel = msg.channel

        route = self.routes.get((msg.type, key, channel)) or self.routes.get((msg.type, key, channel, value))
        if route:
            function = route(msg)
            asyncio.create_task(function)   