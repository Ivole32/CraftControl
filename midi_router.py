import asyncio

class MidiRouter:
    def __init__(self):
        self.keyboard_routes = {}
        self.mouse_routes = {}
        self.mouse_key_combinations = []
        self.mouse_cache = {}

    def register_keyboard_binding(self, msg_type, key, channel, value, func):
        if value == None:
            self.keyboard_routes[(msg_type, key, channel)] = func
        else:
            self.keyboard_routes[(msg_type, key, channel, value)] = func

    def register_mouse_binding(self, msg_type, keys: tuple, channel, action, func):
        self.mouse_key_combinations.append(keys)
        print(self.mouse_key_combinations)
        for key in keys:
            self.mouse_routes[(msg_type, key, channel)] = [func, action]

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

        keyboard_route = self.keyboard_routes.get((msg.type, key, channel)) or self.keyboard_routes.get((msg.type, key, channel, value)) or None
        mouse_route, mouse_action = self.mouse_routes.get((msg.type, key, channel)) or (None, None)

        if keyboard_route:
            function = keyboard_route(msg)
            asyncio.create_task(function)

        elif mouse_route:
            self.mouse_cache[key] = value
            print(self.mouse_cache)

            for key_1, key_2 in self.mouse_key_combinations:
                if key_1 in self.mouse_cache and key_2 in self.mouse_cache:
                    msb = self.mouse_cache.pop(key_2)
                    lsb = self.mouse_cache.pop(key_1)

                    function = mouse_route(mouse_action, (msb, lsb))
                    asyncio.create_task(function)
                    break