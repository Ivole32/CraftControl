import asyncio
import json
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
import keyboard
import mido
import pyautogui
from tkinter import messagebox

from midi_router import MidiRouter


class MidiMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CraftControl MIDI Monitor")
        self.geometry("1200x700")
        self.minsize(980, 600)

        self.default_config_path = Path(__file__).resolve().with_name("config.json")
        self.config_path = self._resolve_config_path()
        self.config = self._load_config()

        self.monitor_thread = None
        self.stop_event = threading.Event()
        self.log_queue = queue.Queue()
        self.port = None
        self.router = None

        self.x_position = 0.0
        self.y_position = 0.0
        self.last_x_position = 0.0
        self.last_y_position = 0.0

        screen_width, screen_height = pyautogui.size()
        ss = 0.5 * 0.6 + 0.2
        sensitivity_mod = ss * ss * ss
        self.mouse_sensitivity = sensitivity_mod * 8
        self.x_fader_screen_ratio = 16383 / max(screen_width, 1)
        self.y_fader_screen_ratio = 16383 / max(screen_height, 1)

        self._build_layout()
        self._refresh_devices()
        self._refresh_binding_lists()

        self.after(100, self._drain_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(self)
        controls.grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 6), sticky="nsew")
        controls.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(controls, text="MIDI Device").grid(row=0, column=0, padx=(12, 8), pady=10, sticky="w")

        self.device_combo = ctk.CTkComboBox(controls, values=["No devices found"], state="readonly")
        self.device_combo.grid(row=0, column=1, padx=(0, 8), pady=10, sticky="ew")

        self.refresh_btn = ctk.CTkButton(controls, text="Refresh", width=90, command=self._refresh_devices)
        self.refresh_btn.grid(row=0, column=2, padx=4, pady=10)

        self.start_btn = ctk.CTkButton(controls, text="Start", width=90, command=self._start_monitor)
        self.start_btn.grid(row=0, column=3, padx=4, pady=10)

        self.stop_btn = ctk.CTkButton(controls, text="Stop", width=90, command=self._stop_monitor)
        self.stop_btn.grid(row=0, column=4, padx=4, pady=10)

        self.restart_btn = ctk.CTkButton(controls, text="Restart", width=90, command=self._restart_monitor)
        self.restart_btn.grid(row=0, column=5, padx=(4, 12), pady=10)

        self.status_label = ctk.CTkLabel(controls, text="Status: stopped", text_color="#a22")
        self.status_label.grid(row=0, column=6, padx=(8, 12), pady=10, sticky="e")

        monitor_frame = ctk.CTkFrame(self)
        monitor_frame.grid(row=1, column=0, padx=(12, 6), pady=(6, 12), sticky="nsew")
        monitor_frame.grid_rowconfigure(1, weight=1)
        monitor_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(monitor_frame, text="MIDI Monitor Output", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 6), sticky="w"
        )

        text_frame = ctk.CTkFrame(monitor_frame)
        text_frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self.monitor_text = tk.Text(text_frame, wrap="none", bg="#212121", fg="#e0e0e0", font=("monospace", 10))
        self.monitor_text.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ctk.CTkScrollbar(text_frame, command=self.monitor_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.monitor_text.configure(yscrollcommand=scrollbar.set)

        self.monitor_text.tag_configure("midi_message", foreground="#64b5f6", underline=False)
        self.monitor_text.tag_configure("midi_message_hover", foreground="#42a5f5", underline=True, background="#333333")

        self.monitor_text.bind("<Motion>", self._on_message_hover)
        self.monitor_text.bind("<Leave>", self._on_message_leave)
        self.monitor_text.tag_bind("midi_message", "<Button-1>", self._on_message_click)
        
        self.last_hovered_message = None
        self.message_data = {}

        bindings_frame = ctk.CTkFrame(self)
        bindings_frame.grid(row=1, column=1, padx=(6, 12), pady=(6, 12), sticky="nsew")
        bindings_frame.grid_rowconfigure(1, weight=1)
        bindings_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bindings_frame, text="Bindings", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=12, pady=(12, 8), sticky="w"
        )

        tabs = ctk.CTkTabview(bindings_frame)
        tabs.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        tabs.add("Keyboard")
        tabs.add("Mouse")

        keyboard_tab = tabs.tab("Keyboard")
        keyboard_tab.grid_rowconfigure(7, weight=1)
        keyboard_tab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(keyboard_tab, text="Message Type").grid(row=0, column=0, padx=(12, 8), pady=(12, 4), sticky="w")
        self.kb_msg_type_combo = ctk.CTkComboBox(
            keyboard_tab,
            values=["note_on", "note_off", "control_change"],
            state="readonly",
        )
        self.kb_msg_type_combo.set("note_on")
        self.kb_msg_type_combo.grid(row=0, column=1, padx=(0, 12), pady=(12, 4), sticky="ew")

        ctk.CTkLabel(keyboard_tab, text="Key/Control").grid(row=1, column=0, padx=(12, 8), pady=4, sticky="w")
        self.kb_key_entry = ctk.CTkEntry(keyboard_tab, placeholder_text="e.g. 65")
        self.kb_key_entry.grid(row=1, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(keyboard_tab, text="Channel").grid(row=2, column=0, padx=(12, 8), pady=4, sticky="w")
        self.kb_channel_entry = ctk.CTkEntry(keyboard_tab, placeholder_text="e.g. 0")
        self.kb_channel_entry.grid(row=2, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(keyboard_tab, text="Value (optional)").grid(row=3, column=0, padx=(12, 8), pady=4, sticky="w")
        self.kb_value_entry = ctk.CTkEntry(keyboard_tab, placeholder_text="e.g. 127")
        self.kb_value_entry.grid(row=3, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(keyboard_tab, text="Action Key").grid(row=4, column=0, padx=(12, 8), pady=4, sticky="w")
        self.kb_action_entry = ctk.CTkEntry(keyboard_tab, placeholder_text="e.g. space")
        self.kb_action_entry.grid(row=4, column=1, padx=(0, 12), pady=4, sticky="ew")

        keyboard_actions = ctk.CTkFrame(keyboard_tab, fg_color="transparent")
        keyboard_actions.grid(row=5, column=0, columnspan=2, padx=12, pady=(6, 8), sticky="ew")
        keyboard_actions.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(keyboard_actions, text="Add", command=self._add_keybind).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(keyboard_actions, text="Update Selected", command=self._update_selected_keybind).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ctk.CTkButton(keyboard_actions, text="Remove Selected", command=self._remove_selected_keybind).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        ctk.CTkButton(keyboard_actions, text="Save", command=self._save_config_from_ui).grid(
            row=0, column=3, padx=4, sticky="ew"
        )

        keyboard_list_frame = ctk.CTkFrame(keyboard_tab)
        keyboard_list_frame.grid(row=7, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="nsew")
        keyboard_list_frame.grid_rowconfigure(0, weight=1)
        keyboard_list_frame.grid_columnconfigure(0, weight=1)

        self.keyboard_listbox = tk.Listbox(keyboard_list_frame, selectmode=tk.SINGLE)
        self.keyboard_listbox.grid(row=0, column=0, sticky="nsew")
        self.keyboard_listbox.bind("<<ListboxSelect>>", self._fill_keyboard_form_from_selection)

        keyboard_scrollbar = ctk.CTkScrollbar(keyboard_list_frame, command=self.keyboard_listbox.yview)
        keyboard_scrollbar.grid(row=0, column=1, sticky="ns")
        self.keyboard_listbox.configure(yscrollcommand=keyboard_scrollbar.set)

        mouse_tab = tabs.tab("Mouse")
        mouse_tab.grid_rowconfigure(7, weight=1)
        mouse_tab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(mouse_tab, text="Message Type").grid(row=0, column=0, padx=(12, 8), pady=(12, 4), sticky="w")
        self.mouse_msg_type_combo = ctk.CTkComboBox(
            mouse_tab,
            values=["note_on", "note_off", "control_change"],
            state="readonly",
        )
        self.mouse_msg_type_combo.set("control_change")
        self.mouse_msg_type_combo.grid(row=0, column=1, padx=(0, 12), pady=(12, 4), sticky="ew")

        ctk.CTkLabel(mouse_tab, text="Key 1").grid(row=1, column=0, padx=(12, 8), pady=4, sticky="w")
        self.mouse_key1_entry = ctk.CTkEntry(mouse_tab, placeholder_text="e.g. 51")
        self.mouse_key1_entry.grid(row=1, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(mouse_tab, text="Key 2").grid(row=2, column=0, padx=(12, 8), pady=4, sticky="w")
        self.mouse_key2_entry = ctk.CTkEntry(mouse_tab, placeholder_text="e.g. 19")
        self.mouse_key2_entry.grid(row=2, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(mouse_tab, text="Channel").grid(row=3, column=0, padx=(12, 8), pady=4, sticky="w")
        self.mouse_channel_entry = ctk.CTkEntry(mouse_tab, placeholder_text="e.g. 0")
        self.mouse_channel_entry.grid(row=3, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(mouse_tab, text="Value (optional)").grid(row=4, column=0, padx=(12, 8), pady=4, sticky="w")
        self.mouse_value_entry = ctk.CTkEntry(mouse_tab, placeholder_text="e.g. 127")
        self.mouse_value_entry.grid(row=4, column=1, padx=(0, 12), pady=4, sticky="ew")

        ctk.CTkLabel(mouse_tab, text="Action").grid(row=5, column=0, padx=(12, 8), pady=4, sticky="w")
        self.mouse_action_combo = ctk.CTkComboBox(
            mouse_tab,
            values=[
                "mouse_move_x",
                "mouse_move_y",
                "mouse_click_left",
                "mouse_release_left",
                "mouse_click_right",
                "mouse_release_right",
                "mouse_click_middle",
            ],
            state="readonly",
            command=self._sync_mouse_value_state,
        )
        self.mouse_action_combo.set("mouse_move_x")
        self.mouse_action_combo.grid(row=5, column=1, padx=(0, 12), pady=4, sticky="ew")

        mouse_actions = ctk.CTkFrame(mouse_tab, fg_color="transparent")
        mouse_actions.grid(row=6, column=0, columnspan=2, padx=12, pady=(6, 8), sticky="ew")
        mouse_actions.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(mouse_actions, text="Add", command=self._add_mouse_bind).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(mouse_actions, text="Update Selected", command=self._update_selected_mouse_bind).grid(
            row=0, column=1, padx=4, sticky="ew"
        )
        ctk.CTkButton(mouse_actions, text="Remove Selected", command=self._remove_selected_mouse_bind).grid(
            row=0, column=2, padx=4, sticky="ew"
        )
        ctk.CTkButton(mouse_actions, text="Save", command=self._save_config_from_ui).grid(row=0, column=3, padx=4, sticky="ew")

        mouse_list_frame = ctk.CTkFrame(mouse_tab)
        mouse_list_frame.grid(row=7, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="nsew")
        mouse_list_frame.grid_rowconfigure(0, weight=1)
        mouse_list_frame.grid_columnconfigure(0, weight=1)

        self.mouse_listbox = tk.Listbox(mouse_list_frame, selectmode=tk.SINGLE)
        self.mouse_listbox.grid(row=0, column=0, sticky="nsew")
        self.mouse_listbox.bind("<<ListboxSelect>>", self._fill_mouse_form_from_selection)

        mouse_scrollbar = ctk.CTkScrollbar(mouse_list_frame, command=self.mouse_listbox.yview)
        mouse_scrollbar.grid(row=0, column=1, sticky="ns")
        self.mouse_listbox.configure(yscrollcommand=mouse_scrollbar.set)

        self._sync_mouse_value_state(self.mouse_action_combo.get())

    def _resolve_config_path(self):
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent / "config.json"
        return self.default_config_path

    @staticmethod
    def _read_json(path):
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return None

    def _load_config(self):
        config = self._read_json(self.config_path)

        # In bundled mode, prefill with packaged config once when local config is missing.
        if config is None and getattr(sys, "frozen", False):
            bundled_root = Path(getattr(sys, "_MEIPASS", ""))
            if str(bundled_root):
                config = self._read_json(bundled_root / "config.json")

        if config is None:
            config = self._read_json(self.default_config_path)

        if config is None:
            config = {"keyboard_bindings": [], "mouse_bindings": []}

        config.setdefault("keyboard_bindings", [])
        config.setdefault("mouse_bindings", [])

        if not self.config_path.exists():
            try:
                with self.config_path.open("w", encoding="utf-8") as file:
                    json.dump(config, file, indent=4)
            except OSError:
                pass

        return config

    def _save_config(self):
        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(self.config, file, indent=4)

    def _refresh_devices(self):
        devices = mido.get_input_names()
        if not devices:
            devices = ["No devices found"]

        self.device_combo.configure(values=devices)
        self.device_combo.set(devices[0])

    def _refresh_binding_lists(self):
        self._refresh_keyboard_bind_list()
        self._refresh_mouse_bind_list()

    def _refresh_keyboard_bind_list(self):
        self.keyboard_listbox.delete(0, tk.END)
        for index, bind in enumerate(self.config["keyboard_bindings"], start=1):
            msg_type = bind.get("msg_type")
            key = bind.get("key")
            channel = bind.get("channel")
            value = bind.get("value")
            action = bind.get("action")
            text = f"{index:02d}. {msg_type} key={key} ch={channel} val={value} -> {action}"
            self.keyboard_listbox.insert(tk.END, text)

    def _refresh_mouse_bind_list(self):
        self.mouse_listbox.delete(0, tk.END)
        for index, bind in enumerate(self.config["mouse_bindings"], start=1):
            msg_type = bind.get("msg_type")
            keys = bind.get("keys", [])
            channel = bind.get("channel")
            value = bind.get("value")
            action = bind.get("action")
            text = f"{index:02d}. {msg_type} keys={keys} ch={channel} val={value} -> {action}"
            self.mouse_listbox.insert(tk.END, text)

    @staticmethod
    def _entry_set(entry, value):
        entry.delete(0, "end")
        if value is None:
            return
        entry.insert(0, str(value))

    def _fill_keyboard_form_from_selection(self, _event=None):
        selection = self.keyboard_listbox.curselection()
        if not selection:
            return

        bind = self.config["keyboard_bindings"][selection[0]]
        self.kb_msg_type_combo.set(bind.get("msg_type", "note_on"))
        self._entry_set(self.kb_key_entry, bind.get("key"))
        self._entry_set(self.kb_channel_entry, bind.get("channel"))
        self._entry_set(self.kb_value_entry, bind.get("value"))
        self._entry_set(self.kb_action_entry, bind.get("action"))

    def _fill_mouse_form_from_selection(self, _event=None):
        selection = self.mouse_listbox.curselection()
        if not selection:
            return

        bind = self.config["mouse_bindings"][selection[0]]
        keys = bind.get("keys", [])
        key_1 = keys[0] if len(keys) > 0 else None
        key_2 = keys[1] if len(keys) > 1 else None

        action = bind.get("action", "mouse_move_x")
        self.mouse_msg_type_combo.set(bind.get("msg_type", "control_change"))
        self._entry_set(self.mouse_key1_entry, key_1)
        self._entry_set(self.mouse_key2_entry, key_2)
        self._entry_set(self.mouse_channel_entry, bind.get("channel"))
        self.mouse_action_combo.set(action)
        self._sync_mouse_value_state(action)
        self._entry_set(self.mouse_value_entry, bind.get("value"))

    def _sync_mouse_value_state(self, selected_action):
        if selected_action.startswith("mouse_move"):
            self.mouse_value_entry.delete(0, "end")
            self.mouse_value_entry.configure(state="disabled")
        else:
            self.mouse_value_entry.configure(state="normal")

    def _queue_log(self, text):
        try:
            self.log_queue.put_nowait(text)
        except queue.Full:
            pass

    def _parse_midi_message(self, msg_str):
        msg_str = msg_str.strip()
        data = {}

        parts = msg_str.split()
        if not parts:
            return None
        
        msg_type = parts[0]
        data["msg_type"] = msg_type

        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                try:
                    data[key] = int(value)
                except ValueError:
                    data[key] = value
        
        if msg_type.startswith("note"):
            if "note" in data and "channel" in data:
                return data
        elif msg_type == "control_change":
            if "control" in data and "channel" in data:
                data["key"] = data["control"]
                return data
        
        return None

    def _on_message_hover(self, event):
        index = self.monitor_text.index(f"@{event.x},{event.y}")
        if "midi_message" not in self.monitor_text.tag_names(index):
            if self.last_hovered_message:
                self.monitor_text.tag_remove(
                    "midi_message_hover", self.last_hovered_message, f"{self.last_hovered_message} lineend"
                )
                self.last_hovered_message = None
            return

        line_start = f"{index} linestart"
        line_end = f"{index} lineend"
        
        if self.last_hovered_message == line_start:
            return
        
        if self.last_hovered_message:
            self.monitor_text.tag_remove("midi_message_hover", self.last_hovered_message, f"{self.last_hovered_message} lineend")

        self.monitor_text.tag_add("midi_message_hover", line_start, line_end)
        self.last_hovered_message = line_start

    def _on_message_leave(self, event):
        if self.last_hovered_message:
            self.monitor_text.tag_remove("midi_message_hover", self.last_hovered_message, f"{self.last_hovered_message} lineend")
            self.last_hovered_message = None

    def _on_message_click(self, event):
        index = self.monitor_text.index(f"@{event.x},{event.y}")
        line_start = f"{index} linestart"
        line_end = f"{index} lineend"
        
        message_text = self.monitor_text.get(line_start, line_end)
        parsed = self._parse_midi_message(message_text)
        
        if parsed:
            self._show_quick_binding_dialog(parsed, message_text)

    def _show_quick_binding_dialog(self, parsed_data, original_message):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Create Binding from Message")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Create Keyboard Binding", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=12, pady=(12, 6), anchor="w")

        ctk.CTkLabel(dialog, text=f"Message: {original_message}", text_color="#888", wraplength=350).pack(padx=12, pady=(0, 12), anchor="w")

        ctk.CTkLabel(dialog, text="Action Key:").pack(padx=12, pady=(6, 3), anchor="w")
        keyboard_action_entry = ctk.CTkEntry(dialog, placeholder_text="e.g. space, a, ctrl+s")
        keyboard_action_entry.insert(0, "space")
        keyboard_action_entry.pack(padx=12, pady=(0, 12), anchor="w", fill="x", expand=False)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(padx=12, pady=(12, 12), anchor="e")
        
        ctk.CTkButton(button_frame, text="Cancel", width=80, command=dialog.destroy).pack(side="left", padx=4)
        ctk.CTkButton(button_frame, text="Create", width=80, 
                     command=lambda: self._create_binding_from_dialog(parsed_data, dialog, keyboard_action_entry)).pack(side="left", padx=4)
    
    def _create_binding_from_dialog(self, parsed_data, dialog, keyboard_action_entry):
        try:
            action = keyboard_action_entry.get().strip()
            if not action:
                raise ValueError("Action cannot be empty")
            
            binding = {
                "msg_type": parsed_data.get("msg_type"),
                "key": parsed_data.get("key") or parsed_data.get("note"),
                "channel": parsed_data.get("channel"),
                "value": parsed_data.get("velocity") or parsed_data.get("value"),
                "action": action
            }
            self.config["keyboard_bindings"].append(binding)
            binding_desc = f"{binding['msg_type']} key={binding['key']} ch={binding['channel']} val={binding['value']} -> {action}"
            
            self._refresh_keyboard_bind_list()
            self._save_config()
            self._rebuild_router_if_running()
            self._queue_log(f"Created binding: {binding_desc}")
            dialog.destroy()
            messagebox.showinfo("Success", f"Binding created:\n{binding_desc}")
        
        except Exception as error:
            messagebox.showerror("Error", f"Failed to create binding: {error}")

    def _drain_log_queue(self):
        self.monitor_text.configure(state="normal")

        auto_scroll = self.monitor_text.yview()[1] >= 0.99

        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()
            
            insert_pos = self.monitor_text.index("end - 1 chars")
            line_num = insert_pos.split(".")[0]

            self.monitor_text.insert("end", f"{message}\n")

            parsed = self._parse_midi_message(message)
            if parsed:
                line_start = f"{line_num}.0"
                line_end = f"{line_num}.end"
                self.monitor_text.tag_add("midi_message", line_start, line_end)
        if auto_scroll:
            self.monitor_text.see("end")
        self.monitor_text.configure(state="disabled")
        self.after(100, self._drain_log_queue)

    def _set_status(self, running):
        if running:
            self.status_label.configure(text="Status: running", text_color="#2a2")
        else:
            self.status_label.configure(text="Status: stopped", text_color="#a22")

    @staticmethod
    def _parse_int_or_none(value_text, field_name):
        raw = value_text.strip()
        if raw == "":
            return None

        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer") from exc

    def _add_keybind(self):
        try:
            msg_type = self.kb_msg_type_combo.get()
            key = self._parse_int_or_none(self.kb_key_entry.get(), "Key/Control")
            channel = self._parse_int_or_none(self.kb_channel_entry.get(), "Channel")
            value = self._parse_int_or_none(self.kb_value_entry.get(), "Value")
            action = self.kb_action_entry.get().strip()

            if key is None:
                raise ValueError("Key/Control is required")
            if channel is None:
                raise ValueError("Channel is required")
            if action == "":
                raise ValueError("Action key is required")

            self.config["keyboard_bindings"].append(
                {
                    "msg_type": msg_type,
                    "key": key,
                    "channel": channel,
                    "value": value,
                    "action": action,
                }
            )
            self._refresh_keyboard_bind_list()
            self._save_config()
            self._rebuild_router_if_running()
            self._queue_log(f"Added keybind: {msg_type} key={key} ch={channel} val={value} -> {action}")

            self.kb_key_entry.delete(0, "end")
            self.kb_channel_entry.delete(0, "end")
            self.kb_value_entry.delete(0, "end")
            self.kb_action_entry.delete(0, "end")

        except ValueError as error:
            messagebox.showerror("Invalid keybind", str(error))

    def _remove_selected_keybind(self):
        selection = self.keyboard_listbox.curselection()
        if not selection:
            messagebox.showinfo("No selection", "Select a keybind to remove.")
            return

        index = selection[0]
        removed = self.config["keyboard_bindings"].pop(index)
        self._refresh_keyboard_bind_list()
        self._save_config()
        self._rebuild_router_if_running()
        self._queue_log(
            f"Removed keybind: {removed.get('msg_type')} key={removed.get('key')} "
            f"ch={removed.get('channel')} val={removed.get('value')} -> {removed.get('action')}"
        )

    def _update_selected_keybind(self):
        selection = self.keyboard_listbox.curselection()
        if not selection:
            messagebox.showinfo("No selection", "Select a keybind to update.")
            return

        try:
            msg_type = self.kb_msg_type_combo.get()
            key = self._parse_int_or_none(self.kb_key_entry.get(), "Key/Control")
            channel = self._parse_int_or_none(self.kb_channel_entry.get(), "Channel")
            value = self._parse_int_or_none(self.kb_value_entry.get(), "Value")
            action = self.kb_action_entry.get().strip()

            if key is None:
                raise ValueError("Key/Control is required")
            if channel is None:
                raise ValueError("Channel is required")
            if action == "":
                raise ValueError("Action key is required")

            index = selection[0]
            self.config["keyboard_bindings"][index] = {
                "msg_type": msg_type,
                "key": key,
                "channel": channel,
                "value": value,
                "action": action,
            }
            self._refresh_keyboard_bind_list()
            self.keyboard_listbox.selection_set(index)
            self._save_config()
            self._rebuild_router_if_running()
            self._queue_log(f"Updated keybind #{index + 1}: {msg_type} key={key} ch={channel} val={value} -> {action}")

        except ValueError as error:
            messagebox.showerror("Invalid keybind", str(error))

    def _add_mouse_bind(self):
        try:
            msg_type = self.mouse_msg_type_combo.get()
            key_1 = self._parse_int_or_none(self.mouse_key1_entry.get(), "Key 1")
            key_2 = self._parse_int_or_none(self.mouse_key2_entry.get(), "Key 2")
            channel = self._parse_int_or_none(self.mouse_channel_entry.get(), "Channel")
            action = self.mouse_action_combo.get()

            if key_1 is None:
                raise ValueError("Key 1 is required")
            if key_2 is None:
                raise ValueError("Key 2 is required")
            if channel is None:
                raise ValueError("Channel is required")

            value = None
            if not action.startswith("mouse_move"):
                value = self._parse_int_or_none(self.mouse_value_entry.get(), "Value")

            self.config["mouse_bindings"].append(
                {
                    "msg_type": msg_type,
                    "keys": [key_1, key_2],
                    "channel": channel,
                    "value": value,
                    "action": action,
                }
            )
            self._refresh_mouse_bind_list()
            self._save_config()
            self._rebuild_router_if_running()
            self._queue_log(f"Added mouse bind: {msg_type} keys={[key_1, key_2]} ch={channel} val={value} -> {action}")

            self.mouse_key1_entry.delete(0, "end")
            self.mouse_key2_entry.delete(0, "end")
            self.mouse_channel_entry.delete(0, "end")
            self.mouse_value_entry.delete(0, "end")

        except ValueError as error:
            messagebox.showerror("Invalid mouse bind", str(error))

    def _remove_selected_mouse_bind(self):
        selection = self.mouse_listbox.curselection()
        if not selection:
            messagebox.showinfo("No selection", "Select a mouse bind to remove.")
            return

        index = selection[0]
        removed = self.config["mouse_bindings"].pop(index)
        self._refresh_mouse_bind_list()
        self._save_config()
        self._rebuild_router_if_running()
        self._queue_log(
            f"Removed mouse bind: {removed.get('msg_type')} keys={removed.get('keys')} "
            f"ch={removed.get('channel')} val={removed.get('value')} -> {removed.get('action')}"
        )

    def _update_selected_mouse_bind(self):
        selection = self.mouse_listbox.curselection()
        if not selection:
            messagebox.showinfo("No selection", "Select a mouse bind to update.")
            return

        try:
            msg_type = self.mouse_msg_type_combo.get()
            key_1 = self._parse_int_or_none(self.mouse_key1_entry.get(), "Key 1")
            key_2 = self._parse_int_or_none(self.mouse_key2_entry.get(), "Key 2")
            channel = self._parse_int_or_none(self.mouse_channel_entry.get(), "Channel")
            action = self.mouse_action_combo.get()

            if key_1 is None:
                raise ValueError("Key 1 is required")
            if key_2 is None:
                raise ValueError("Key 2 is required")
            if channel is None:
                raise ValueError("Channel is required")

            value = None
            if not action.startswith("mouse_move"):
                value = self._parse_int_or_none(self.mouse_value_entry.get(), "Value")

            index = selection[0]
            self.config["mouse_bindings"][index] = {
                "msg_type": msg_type,
                "keys": [key_1, key_2],
                "channel": channel,
                "value": value,
                "action": action,
            }
            self._refresh_mouse_bind_list()
            self.mouse_listbox.selection_set(index)
            self._save_config()
            self._rebuild_router_if_running()
            self._queue_log(
                f"Updated mouse bind #{index + 1}: {msg_type} keys={[key_1, key_2]} ch={channel} val={value} -> {action}"
            )

        except ValueError as error:
            messagebox.showerror("Invalid mouse bind", str(error))

    def _save_config_from_ui(self):
        self._save_config()
        self._rebuild_router_if_running()
        self._queue_log("Config saved.")

    def _is_running(self):
        return self.monitor_thread is not None and self.monitor_thread.is_alive()

    def _start_monitor(self):
        if self._is_running():
            self._queue_log("Monitor is already running.")
            return

        device = self.device_combo.get()
        if not device or device == "No devices found":
            messagebox.showerror("No MIDI device", "No valid MIDI input device selected.")
            return

        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_worker, args=(device,), daemon=True)
        self.monitor_thread.start()
        self._set_status(True)
        self._queue_log(f"Started monitor on device: {device}")

    def _stop_monitor(self):
        if not self._is_running():
            self._set_status(False)
            self._queue_log("Monitor is already stopped.")
            return

        self.stop_event.set()
        if self.port is not None:
            try:
                self.port.close()
            except OSError:
                pass

        self.monitor_thread.join(timeout=2.0)
        self.monitor_thread = None
        self._set_status(False)
        self._queue_log("Monitor stopped.")

    def _restart_monitor(self):
        current_device = self.device_combo.get()
        self._stop_monitor()
        if current_device and current_device != "No devices found":
            self.device_combo.set(current_device)
        self._start_monitor()

    def _rebuild_router_if_running(self):
        if self._is_running():
            self.router = self._build_router()
            self._queue_log("Router reloaded from config.")

    def _build_router(self):
        router = MidiRouter()

        for bind in self.config.get("keyboard_bindings", []):
            try:
                msg_type = bind.get("msg_type")
                key = bind.get("key")
                channel = bind.get("channel")
                value = bind.get("value")
                action = bind.get("action")
                router.register_keyboard_binding(
                    msg_type,
                    key,
                    channel,
                    value,
                    lambda _msg, action=action: self._perform_keyboard_action(action),
                )
            except Exception as error:
                self._queue_log(f"Could not register keyboard binding: {error}")

        for bind in self.config.get("mouse_bindings", []):
            try:
                msg_type = bind.get("msg_type")
                keys = tuple(bind.get("keys", []))
                channel = bind.get("channel")
                value = bind.get("value")
                action = bind.get("action")

                if action and action.startswith("mouse_move"):
                    router.register_mouse_binding(msg_type, keys, channel, None, action, self._perform_mouse_movement_action)
                else:
                    router.register_mouse_binding(msg_type, keys, channel, value, action, self._perform_mouse_click_action)
            except Exception as error:
                self._queue_log(f"Could not register mouse binding: {error}")

        return router

    async def _perform_keyboard_action(self, key):
        loop = asyncio.get_running_loop()
        normalized_key = key.strip().lower() if isinstance(key, str) else key
        if normalized_key in ("spacebar", " "):
            normalized_key = "space"

        def trigger_key_action():
            # keyboard.send handles combos like ctrl+s more reliably than press/release.
            if isinstance(normalized_key, str) and "+" in normalized_key:
                keyboard.send(normalized_key)
                return

            keyboard.press(normalized_key)
            time.sleep(0.08)
            keyboard.release(normalized_key)

        await loop.run_in_executor(None, trigger_key_action)

    async def _perform_mouse_click_action(self, action):
        if action == "mouse_click_left":
            function = lambda: pyautogui.mouseDown(button="left")
        elif action == "mouse_release_left":
            function = lambda: pyautogui.mouseUp(button="left")
        elif action == "mouse_click_right":
            function = lambda: pyautogui.mouseDown(button="right")
        elif action == "mouse_release_right":
            function = lambda: pyautogui.mouseUp(button="right")
        elif action == "mouse_click_middle":
            function = lambda: pyautogui.click(button="middle")
        else:
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, function)

    async def _perform_mouse_movement_action(self, action, fader_position):
        msb, lsb = fader_position
        fader_value = (msb << 7) | lsb

        if action == "mouse_move_x":
            self.x_position = fader_value / self.x_fader_screen_ratio
        elif action == "mouse_move_y":
            self.y_position = fader_value / self.y_fader_screen_ratio
        else:
            return

        dx = (self.x_position - self.last_x_position) * self.mouse_sensitivity
        dy = (self.y_position - self.last_y_position) * self.mouse_sensitivity

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: pyautogui.moveRel(dx, dy, duration=0))

        self.last_x_position = self.x_position
        self.last_y_position = self.y_position

    def _monitor_worker(self, device):
        try:
            asyncio.run(self._monitor_loop(device))
        except Exception as error:
            self._queue_log(f"Monitor crashed: {error}")
            self.after(0, lambda: self._set_status(False))

    async def _monitor_loop(self, device):
        self.router = self._build_router()

        with mido.open_input(device) as port:
            self.port = port
            while not self.stop_event.is_set():
                for message in port.iter_pending():
                    self._queue_log(str(message))
                    try:
                        self.router.handle(message)
                    except Exception as error:
                        self._queue_log(f"Router error: {error}")

                await asyncio.sleep(0.001)

        self.port = None

    def _on_close(self):
        self._stop_monitor()
        self.destroy()


def launch_app():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = MidiMonitorApp()
    app.mainloop()