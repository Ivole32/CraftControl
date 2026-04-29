import asyncio

class MidiRouter:
    def __init__(self):
        # Stores normal keyboard bindings
        self.keyboard_routes = {}

        # stores mouse bindings
        self.mouse_routes = {}

        # Stores key pairs for MSB + LSB value
        self.mouse_key_combinations = []

        # Temporary value cache
        self.mouse_cache = {}

    def register_keyboard_binding(self, msg_type, key, channel, value, func):
        # Register binfing with or without value filter
        if value == None:
            self.keyboard_routes[(msg_type, key, channel)] = func
        else:
            self.keyboard_routes[(msg_type, key, channel, value)] = func

    def register_mouse_binding(self, msg_type, keys: tuple, channel, value, action, func):
        # Save key pair
        self.mouse_key_combinations.append(keys)

        # register both keys to same callback
        if value == None:
            for key in keys:
                self.mouse_routes[(msg_type, key, channel)] = [func, action]
        else:
            for key in keys:
                self.mouse_routes[(msg_type, key, channel, value)] = [func, action]


    def handle(self, msg):
        key = None

        # Detect note or control number
        if msg.type.startswith("note"):
            key = msg.note
        elif msg.type == "control_change":
            key = msg.control

        # Get MIDI value
        try:
            value = msg.value
        except:
            value = msg.velocity

        channel = msg.channel

        # Search matching keyboard callback
        keyboard_route = (
            self.keyboard_routes.get((msg.type, key, channel))
            or self.keyboard_routes.get((msg.type, key, channel, value))
            or None
        )

        # Search matching mouse callback
        mouse_route, mouse_action = (
            self.mouse_routes.get((msg.type, key, channel))
            or self.mouse_routes.get((msg.type, key, channel, value)) 
            or (None, None)
        )

        if keyboard_route:
            function = keyboard_route(msg)
            asyncio.create_task(function)

        elif mouse_route:
            click_action = False

            # Save value until second key arrives
            self.mouse_cache[key] = value

            # Check if full key pair exists
            for key_1, key_2 in self.mouse_key_combinations:
                if key_1 in self.mouse_cache and key_2 in self.mouse_cache:
                    try:
                        # Read MSB + LSB values
                        msb = self.mouse_cache.pop(key_2)
                        lsb = self.mouse_cache.pop(key_1)
                    except:
                        click_action = True
                    finally:
                        # Call with fader coordniates or click only
                        if click_action:
                            function = mouse_route(mouse_action)
                        else:
                            function = mouse_route(mouse_action, (msb, lsb))
                        asyncio.create_task(function)
                        break