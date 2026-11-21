import os
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import urllib.request
from pynput import mouse
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, KeyCode, Controller as KeyboardController, Listener as KeyboardListener


# Version & Update Configuration
APP_VERSION = "1.0.1"
GITHUB_API_URL = "https://api.github.com/repos/RealGubby/Update/contents/Macro.py?ref=main"
UPDATE_URL = "https://raw.githubusercontent.com/RealGubby/Update/refs/heads/main/Macro.py"

# Shared Monochrome Palette
BG_MAIN = "#080808"
BG_CARD = "#111111"
BG_INPUT = "#161616"
BG_HOVER = "#222222"
BORDER_SUBTLE = "#262626"
FG_PRIMARY = "#FFFFFF"
FG_SECONDARY = "#9A9A9A"
FG_MUTED = "#555555"


def parse_version(version_str: str) -> tuple:
    try:
        return tuple(int(x) for x in version_str.strip().split("."))
    except ValueError:
        return (0, 0, 0)


def center_window(win: tk.Tk | tk.Toplevel, width: int, height: int):
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")


def make_draggable(widget, target_window):
    def start_move(event):
        target_window._drag_x = event.x
        target_window._drag_y = event.y

    def on_move(event):
        x = target_window.winfo_x() + (event.x - target_window._drag_x)
        y = target_window.winfo_y() + (event.y - target_window._drag_y)
        target_window.geometry(f"+{x}+{y}")

    widget.bind("<Button-1>", start_move)
    widget.bind("<B1-Motion>", on_move)


def bind_hover(btn: tk.Button, normal_bg: str, hover_bg: str, normal_fg: str = None, hover_fg: str = None):
    def on_enter(_):
        if btn["state"] != "disabled":
            btn.config(bg=hover_bg)
            if hover_fg:
                btn.config(fg=hover_fg)

    def on_leave(_):
        if btn["state"] != "disabled":
            btn.config(bg=normal_bg)
            if normal_fg:
                btn.config(fg=normal_fg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)


def format_key(key) -> str:
    if isinstance(key, Key):
        return key.name.upper()
    if isinstance(key, KeyCode):
        if key.char:
            return key.char.upper()
        if key.vk:
            return f"KEY_{key.vk}"
    return str(key).replace("Key.", "").upper()


def keys_match(pressed_key, target_key) -> bool:
    if pressed_key == target_key:
        return True
    if isinstance(pressed_key, KeyCode) and isinstance(target_key, KeyCode):
        if pressed_key.char and target_key.char:
            return pressed_key.char.lower() == target_key.char.lower()
        if pressed_key.vk and target_key.vk:
            return pressed_key.vk == target_key.vk
    return False


class AutoSellMacroWindow:
    def __init__(self, root: tk.Tk, on_back_callback, on_exit_callback):
        self.root = root
        self.on_back_callback = on_back_callback
        self.on_exit_callback = on_exit_callback

        self.win = tk.Toplevel(self.root)
        self.win.title("Auto Sell Macro")
        self.win.configure(bg=BORDER_SUBTLE)
        self.win.attributes("-topmost", True)
        self.win.overrideredirect(True)
        center_window(self.win, 340, 286)

        # Default Settings
        self.is_running = False
        self.is_binding_key = False
        self.target_x = 0
        self.target_y = 0
        self.step_interval = 0.25
        self.sell_amount = "3"
        self.hotkey = Key.f7
        self.hotkey_name = "F7"
        self.settings_window = None

        # Controllers
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()

        self._build_ui()
        self._start_global_hotkey_listener()

    def get_command_text(self) -> str:
        return f"/ah sell {self.sell_amount}k"

    def _start_global_hotkey_listener(self):
        def on_press(key):
            if self.is_binding_key:
                return
            if keys_match(key, self.hotkey):
                self.win.after(0, self.toggle_macro)

        self.global_listener = KeyboardListener(on_press=on_press)
        self.global_listener.daemon = True
        self.global_listener.start()

    def _minimize_window(self):
        self.win.overrideredirect(False)
        self.win.iconify()
        self.win.after(200, self._check_restore)

    def _check_restore(self):
        try:
            if self.win.winfo_exists() and self.win.state() == "normal":
                self.win.overrideredirect(True)
                self.win.attributes("-topmost", True)
            elif self.win.winfo_exists():
                self.win.after(200, self._check_restore)
        except tk.TclError:
            pass

    def _build_ui(self):
        container = tk.Frame(self.win, bg=BG_MAIN)
        container.pack(fill="both", expand=True, padx=1, pady=1)

        # Custom Title Bar with Back Arrow
        title_bar = tk.Frame(container, bg=BG_CARD, height=34)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        make_draggable(title_bar, self.win)

        back_btn = tk.Button(
            title_bar,
            text="←",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            bd=0,
            width=4,
            cursor="hand2",
            command=self.go_back,
        )
        back_btn.pack(side="left", fill="y")
        bind_hover(back_btn, BG_CARD, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

        title_lbl = tk.Label(
            title_bar,
            text="◆  AUTO SELL MACRO",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        title_lbl.pack(side="left", padx=4)
        make_draggable(title_lbl, self.win)

        close_btn = tk.Button(
            title_bar,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            bd=0,
            width=4,
            cursor="hand2",
            command=self.close_app,
        )
        close_btn.pack(side="right", fill="y")
        bind_hover(close_btn, BG_CARD, "#FFFFFF", FG_SECONDARY, "#000000")

        min_btn = tk.Button(
            title_bar,
            text="—",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            bd=0,
            width=4,
            cursor="hand2",
            command=self._minimize_window,
        )
        min_btn.pack(side="right", fill="y")
        bind_hover(min_btn, BG_CARD, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

        tk.Frame(container, bg=BORDER_SUBTLE, height=1).pack(fill="x")

        # Main Body
        body = tk.Frame(container, bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        info_card = tk.Frame(
            body,
            bg=BG_CARD,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        info_card.pack(fill="x", pady=(0, 12))

        status_top = tk.Frame(info_card, bg=BG_CARD)
        status_top.pack(fill="x", pady=(0, 8))

        self.status_dot = tk.Label(
            status_top,
            text="●",
            font=("Segoe UI", 10),
            bg=BG_CARD,
            fg=FG_MUTED,
        )
        self.status_dot.pack(side="left")

        self.status_label = tk.Label(
            status_top,
            text="IDLE",
            font=("Consolas", 11, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
        )
        self.status_label.pack(side="left", padx=(6, 0))

        self.hotkey_badge = tk.Label(
            status_top,
            text=f" {self.hotkey_name} ",
            font=("Consolas", 9, "bold"),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
        )
        self.hotkey_badge.pack(side="right")

        tk.Frame(info_card, bg=BORDER_SUBTLE, height=1).pack(fill="x", pady=(0, 6))

        row_cmd = tk.Frame(info_card, bg=BG_CARD)
        row_cmd.pack(fill="x", pady=2)
        tk.Label(row_cmd, text="COMMAND", font=("Consolas", 8, "bold"), bg=BG_CARD, fg=FG_MUTED).pack(side="left")
        self.cmd_val_label = tk.Label(
            row_cmd,
            text=self.get_command_text(),
            font=("Consolas", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        self.cmd_val_label.pack(side="right")

        row_pos = tk.Frame(info_card, bg=BG_CARD)
        row_pos.pack(fill="x", pady=2)
        tk.Label(row_pos, text="TARGET POS", font=("Consolas", 8, "bold"), bg=BG_CARD, fg=FG_MUTED).pack(side="left")
        self.pos_val_label = tk.Label(
            row_pos,
            text=f"X: {self.target_x}  Y: {self.target_y}",
            font=("Consolas", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        self.pos_val_label.pack(side="right")

        row_int = tk.Frame(info_card, bg=BG_CARD)
        row_int.pack(fill="x", pady=2)
        tk.Label(row_int, text="INTERVAL", font=("Consolas", 8, "bold"), bg=BG_CARD, fg=FG_MUTED).pack(side="left")
        self.int_val_label = tk.Label(
            row_int,
            text=f"{self.step_interval}s",
            font=("Consolas", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        self.int_val_label.pack(side="right")

        self.toggle_btn = tk.Button(
            body,
            text=f"▶  START  [{self.hotkey_name}]",
            font=("Consolas", 10, "bold"),
            height=2,
            bg=BG_CARD,
            fg=FG_PRIMARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.toggle_macro,
        )
        self.toggle_btn.pack(fill="x", pady=(0, 8))
        bind_hover(self.toggle_btn, BG_CARD, BG_HOVER)

        self.settings_btn = tk.Button(
            body,
            text="⚙  CONFIGURE SETTINGS",
            font=("Consolas", 10, "bold"),
            height=2,
            bg=BG_CARD,
            fg=FG_PRIMARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.open_settings,
        )
        self.settings_btn.pack(fill="x")
        bind_hover(self.settings_btn, BG_CARD, BG_HOVER)

    def refresh_main_ui(self):
        if not self.win.winfo_exists():
            return
        self.cmd_val_label.config(text=self.get_command_text())
        self.pos_val_label.config(text=f"X: {self.target_x}  Y: {self.target_y}")
        self.int_val_label.config(text=f"{self.step_interval}s")
        self.hotkey_badge.config(text=f" {self.hotkey_name} ")
        if self.is_running:
            self.toggle_btn.config(text=f"■  STOP  [{self.hotkey_name}]")
            self.status_dot.config(fg=FG_PRIMARY)
            self.status_label.config(text="RUNNING", fg=FG_PRIMARY)
        else:
            self.toggle_btn.config(text=f"▶  START  [{self.hotkey_name}]")
            self.status_dot.config(fg=FG_MUTED)
            self.status_label.config(text="IDLE", fg=FG_SECONDARY)

    def toggle_macro(self):
        self.is_running = not self.is_running
        self.refresh_main_ui()
        if self.is_running:
            threading.Thread(target=self.macro_loop, daemon=True).start()

    def sleep_interruptible(self, duration):
        end_time = time.time() + duration
        while time.time() < end_time and self.is_running:
            time.sleep(min(0.05, end_time - time.time()))

    def macro_loop(self):
        while self.is_running:
            self.keyboard_controller.press('t')
            self.keyboard_controller.release('t')
            self.sleep_interruptible(self.step_interval)
            if not self.is_running:
                break

            self.keyboard_controller.type(self.get_command_text())
            self.sleep_interruptible(self.step_interval)
            if not self.is_running:
                break

            self.keyboard_controller.press(Key.enter)
            self.keyboard_controller.release(Key.enter)
            self.sleep_interruptible(self.step_interval)
            if not self.is_running:
                break

            self.mouse_controller.position = (self.target_x, self.target_y)
            self.mouse_controller.click(Button.left, 1)
            self.sleep_interruptible(self.step_interval)

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus()
            return

        self.settings_window = tk.Toplevel(self.win)
        self.settings_window.title("Auto Sell Settings")
        self.settings_window.configure(bg=BORDER_SUBTLE)
        self.settings_window.attributes("-topmost", True)
        self.settings_window.overrideredirect(True)
        center_window(self.settings_window, 340, 414)

        def on_settings_close():
            self.is_binding_key = False
            if self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.destroy()

        wrapper = tk.Frame(self.settings_window, bg=BG_MAIN)
        wrapper.pack(fill="both", expand=True, padx=1, pady=1)

        s_title = tk.Frame(wrapper, bg=BG_CARD, height=34)
        s_title.pack(fill="x")
        s_title.pack_propagate(False)
        make_draggable(s_title, self.settings_window)

        s_lbl = tk.Label(
            s_title,
            text="  ⚙  AUTO SELL SETTINGS",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        s_lbl.pack(side="left", padx=6)
        make_draggable(s_lbl, self.settings_window)

        s_close = tk.Button(
            s_title,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            bd=0,
            width=4,
            cursor="hand2",
            command=on_settings_close,
        )
        s_close.pack(side="right", fill="y")
        bind_hover(s_close, BG_CARD, "#FFFFFF", FG_SECONDARY, "#000000")

        tk.Frame(wrapper, bg=BORDER_SUBTLE, height=1).pack(fill="x")

        form = tk.Frame(wrapper, bg=BG_MAIN)
        form.pack(fill="both", expand=True, padx=18, pady=14)

        # Section 1: Sell Value
        price_card = tk.Frame(form, bg=BG_CARD, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        price_card.pack(fill="x", pady=(0, 9))

        tk.Label(
            price_card,
            text="SELL VALUE",
            font=("Consolas", 8, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 2))

        price_row = tk.Frame(price_card, bg=BG_CARD)
        price_row.pack(fill="x", padx=10, pady=(0, 7))

        self.amount_var = tk.StringVar(value=self.sell_amount)
        amount_entry = tk.Entry(
            price_row,
            textvariable=self.amount_var,
            font=("Consolas", 11, "bold"),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            relief="flat",
            bd=4,
        )
        amount_entry.pack(side="left", fill="x", expand=True)

        tk.Label(price_row, text="K", font=("Consolas", 8), bg=BG_CARD, fg=FG_MUTED, width=5, anchor="e").pack(side="right")

        # Section 2: Step Interval
        int_card = tk.Frame(form, bg=BG_CARD, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        int_card.pack(fill="x", pady=(0, 9))

        tk.Label(
            int_card,
            text="STEP INTERVAL",
            font=("Consolas", 8, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 2))

        int_row = tk.Frame(int_card, bg=BG_CARD)
        int_row.pack(fill="x", padx=10, pady=(0, 7))

        self.interval_var = tk.StringVar(value=str(self.step_interval))
        interval_entry = tk.Entry(
            int_row,
            textvariable=self.interval_var,
            font=("Consolas", 11, "bold"),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            relief="flat",
            bd=4,
        )
        interval_entry.pack(side="left", fill="x", expand=True)

        tk.Label(int_row, text="SEC", font=("Consolas", 8), bg=BG_CARD, fg=FG_MUTED, width=5, anchor="e").pack(side="right")

        # Section 3: Mouse Position
        pos_card = tk.Frame(form, bg=BG_CARD, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        pos_card.pack(fill="x", pady=(0, 9))

        self.pos_label = tk.Label(
            pos_card,
            text=f"MOUSE POSITION  —  X: {self.target_x}  Y: {self.target_y}",
            font=("Consolas", 8, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            anchor="w",
        )
        self.pos_label.pack(fill="x", padx=10, pady=(6, 4))

        self.record_btn = tk.Button(
            pos_card,
            text="CAPTURE MOUSE CLICK",
            font=("Consolas", 9, "bold"),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            relief="flat",
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.start_mouse_capture,
        )
        self.record_btn.pack(fill="x", padx=10, pady=(0, 8))
        bind_hover(self.record_btn, BG_INPUT, BG_HOVER)

        # Section 4: Global Toggle Hotkey
        hk_card = tk.Frame(form, bg=BG_CARD, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        hk_card.pack(fill="x", pady=(0, 12))

        tk.Label(
            hk_card,
            text="GLOBAL TOGGLE HOTKEY",
            font=("Consolas", 8, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 4))

        self.bind_btn = tk.Button(
            hk_card,
            text=f"[ {self.hotkey_name} ]  —  CLICK TO REBIND",
            font=("Consolas", 9, "bold"),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            relief="flat",
            bd=0,
            pady=6,
            cursor="hand2",
            command=self.start_hotkey_capture,
        )
        self.bind_btn.pack(fill="x", padx=10, pady=(0, 8))
        bind_hover(self.bind_btn, BG_INPUT, BG_HOVER)

        # Bottom Buttons
        btn_row = tk.Frame(form, bg=BG_MAIN)
        btn_row.pack(fill="x")

        cancel_btn = tk.Button(
            btn_row,
            text="CANCEL",
            font=("Consolas", 9, "bold"),
            height=2,
            width=12,
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=on_settings_close,
        )
        cancel_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        bind_hover(cancel_btn, BG_CARD, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

        save_btn = tk.Button(
            btn_row,
            text="SAVE CHANGES",
            font=("Consolas", 9, "bold"),
            height=2,
            width=16,
            bg="#FFFFFF",
            fg="#000000",
            activebackground="#E6E6E6",
            activeforeground="#000000",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.save_settings,
        )
        save_btn.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def start_mouse_capture(self):
        self.record_btn.config(text="LEFT CLICK ANYWHERE...", bg="#FFFFFF", fg="#000000")

        def on_click(x, y, button, pressed):
            if pressed and button == Button.left:
                self.target_x = int(x)
                self.target_y = int(y)
                self.win.after(0, self.finish_mouse_capture)
                return False

        mouse.Listener(on_click=on_click).start()

    def finish_mouse_capture(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.pos_label.config(text=f"MOUSE POSITION  —  X: {self.target_x}  Y: {self.target_y}")
            self.record_btn.config(text="CAPTURE MOUSE CLICK", bg=BG_INPUT, fg=FG_PRIMARY)
            self.settings_window.attributes("-topmost", True)
            self.settings_window.lift()
        self.refresh_main_ui()

    def start_hotkey_capture(self):
        if self.is_binding_key:
            return
        self.is_binding_key = True
        self.bind_btn.config(text="PRESS ANY KEY ON KEYBOARD...", bg="#FFFFFF", fg="#000000")

        def on_press(key):
            self.hotkey = key
            self.hotkey_name = format_key(key)
            self.win.after(0, self.finish_hotkey_capture)
            return False

        KeyboardListener(on_press=on_press).start()

    def finish_hotkey_capture(self):
        self.is_binding_key = False
        if self.settings_window and self.settings_window.winfo_exists():
            self.bind_btn.config(text=f"[ {self.hotkey_name} ]  —  CLICK TO REBIND", bg=BG_INPUT, fg=FG_PRIMARY)
            self.settings_window.attributes("-topmost", True)
            self.settings_window.lift()
        self.refresh_main_ui()

    def save_settings(self):
        if self.is_binding_key:
            return
        new_amount = self.amount_var.get().strip()
        if new_amount:
            self.sell_amount = new_amount
        try:
            val = float(self.interval_var.get().replace(",", "."))
            if val >= 0:
                self.step_interval = val
        except ValueError:
            pass
        self.refresh_main_ui()
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()

    def cleanup(self):
        self.is_running = False
        self.is_binding_key = False
        if hasattr(self, "global_listener"):
            self.global_listener.stop()
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        if self.win and self.win.winfo_exists():
            self.win.destroy()

    def go_back(self):
        self.cleanup()
        self.on_back_callback()

    def close_app(self):
        self.cleanup()
        self.on_exit_callback()


class AutoKillMacroWindow:
    def __init__(self, root: tk.Tk, on_back_callback, on_exit_callback):
        self.root = root
        self.on_back_callback = on_back_callback
        self.on_exit_callback = on_exit_callback

        self.win = tk.Toplevel(self.root)
        self.win.title("Auto Kill Macro")
        self.win.configure(bg=BORDER_SUBTLE)
        self.win.attributes("-topmost", True)
        self.win.overrideredirect(True)
        center_window(self.win, 340, 286)

        # Default Settings
        self.left_interval = 1.0
        self.clicks_before_right = 30
        self.right_hold_duration = 3.0
        self.toggle_hotkey = Key.f7

        # Runtime State
        self.is_running = False
        self.is_rebinding = False
        self.current_clicks = 0
        self.is_holding_right = False
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.mouse = MouseController()
        self.settings_window = None

        self._build_ui()
        self._start_hotkey_listener()

    def _start_hotkey_listener(self):
        self.kb_listener = KeyboardListener(on_press=self._on_global_key_press)
        self.kb_listener.daemon = True
        self.kb_listener.start()

    def _on_global_key_press(self, key):
        if self.is_rebinding:
            return
        if keys_match(key, self.toggle_hotkey):
            self.win.after(0, self.toggle_clicker)

    def _minimize_window(self):
        self.win.overrideredirect(False)
        self.win.iconify()
        self.win.after(200, self._check_restore)

    def _check_restore(self):
        try:
            if self.win.winfo_exists() and self.win.state() == "normal":
                self.win.overrideredirect(True)
                self.win.attributes("-topmost", True)
            elif self.win.winfo_exists():
                self.win.after(200, self._check_restore)
        except tk.TclError:
            pass

    def _build_ui(self):
        container = tk.Frame(self.win, bg=BG_MAIN)
        container.pack(fill="both", expand=True, padx=1, pady=1)

        # Custom Title Bar with Back Arrow
        title_bar = tk.Frame(container, bg=BG_CARD, height=34)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        make_draggable(title_bar, self.win)

        back_btn = tk.Button(
            title_bar,
            text="←",
            font=("Segoe UI", 11, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            bd=0,
            width=4,
            cursor="hand2",
            command=self.go_back,
        )
        back_btn.pack(side="left", fill="y")
        bind_hover(back_btn, BG_CARD, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

        title_lbl = tk.Label(
            title_bar,
            text="◆  AUTO KILL MACRO",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        title_lbl.pack(side="left", padx=4)
        make_draggable(title_lbl, self.win)

        close_btn = tk.Button(
            title_bar,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            bd=0,
            width=4,
            cursor="hand2",
            command=self.close_app,
        )
        close_btn.pack(side="right", fill="y")
        bind_hover(close_btn, BG_CARD, "#FFFFFF", FG_SECONDARY, "#000000")

        min_btn = tk.Button(
            title_bar,
            text="—",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            bd=0,
            width=4,
            cursor="hand2",
            command=self._minimize_window,
        )
        min_btn.pack(side="right", fill="y")
        bind_hover(min_btn, BG_CARD, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

        tk.Frame(container, bg=BORDER_SUBTLE, height=1).pack(fill="x")

        # Main Body
        body = tk.Frame(container, bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        status_card = tk.Frame(
            body,
            bg=BG_CARD,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
        )
        status_card.pack(fill="x", pady=(0, 10))

        status_top = tk.Frame(status_card, bg=BG_CARD)
        status_top.pack(fill="x", padx=12, pady=(8, 3))

        self.status_dot = tk.Label(
            status_top,
            text="●",
            font=("Segoe UI", 10),
            bg=BG_CARD,
            fg=FG_MUTED,
        )
        self.status_dot.pack(side="left")

        self.status_label = tk.Label(
            status_top,
            text="IDLE",
            font=("Consolas", 11, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
        )
        self.status_label.pack(side="left", padx=(6, 0))

        self.hotkey_badge = tk.Label(
            status_top,
            text=f" {format_key(self.toggle_hotkey)} ",
            font=("Consolas", 9, "bold"),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
        )
        self.hotkey_badge.pack(side="right")

        self.progress_label = tk.Label(
            status_card,
            text=f"CYCLE: 0 / {self.clicks_before_right} LEFT CLICKS",
            font=("Consolas", 8),
            bg=BG_CARD,
            fg=FG_MUTED,
            anchor="w",
        )
        self.progress_label.pack(fill="x", padx=12, pady=(2, 5))

        self.progress_canvas = tk.Canvas(
            status_card,
            height=4,
            bg=BG_INPUT,
            highlightthickness=0,
        )
        self.progress_canvas.pack(fill="x", padx=12, pady=(0, 10))
        self.progress_bar = self.progress_canvas.create_rectangle(
            0, 0, 0, 4, fill=FG_PRIMARY, width=0
        )

        config_strip = tk.Frame(
            body,
            bg=BG_CARD,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
        )
        config_strip.pack(fill="x", pady=(0, 10))

        self.summary_label = tk.Label(
            config_strip,
            text=self._get_summary_text(),
            font=("Consolas", 8),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            pady=6,
        )
        self.summary_label.pack(fill="x")

        self.toggle_btn = tk.Button(
            body,
            text=f"▶  START  [{format_key(self.toggle_hotkey)}]",
            font=("Consolas", 10, "bold"),
            height=2,
            bg=BG_CARD,
            fg=FG_PRIMARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.toggle_clicker,
        )
        self.toggle_btn.pack(fill="x", pady=(0, 8))
        bind_hover(self.toggle_btn, BG_CARD, BG_HOVER)

        self.settings_btn = tk.Button(
            body,
            text="⚙  CONFIGURE SETTINGS",
            font=("Consolas", 10, "bold"),
            height=2,
            bg=BG_CARD,
            fg=FG_PRIMARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.open_settings,
        )
        self.settings_btn.pack(fill="x")
        bind_hover(self.settings_btn, BG_CARD, BG_HOVER)

    def _get_summary_text(self) -> str:
        return (
            f"INT: {self.left_interval}s   |   "
            f"COUNT: {self.clicks_before_right}   |   "
            f"HOLD: {self.right_hold_duration}s"
        )

    def _update_progress_ui(self, count: int, holding: bool = False):
        if not self.win.winfo_exists():
            return
        self.progress_canvas.update_idletasks()
        total_w = self.progress_canvas.winfo_width()
        if holding:
            self.status_label.config(text="HOLDING RIGHT CLICK", fg=FG_PRIMARY)
            self.progress_label.config(
                text=f"RIGHT BUTTON HELD ({self.right_hold_duration}s)...",
                fg=FG_PRIMARY,
            )
            self.progress_canvas.coords(self.progress_bar, 0, 0, total_w, 4)
        else:
            if self.is_running:
                self.status_label.config(text="RUNNING", fg=FG_PRIMARY)
            ratio = min(count / max(self.clicks_before_right, 1), 1.0)
            self.progress_label.config(
                text=f"CYCLE: {count} / {self.clicks_before_right} LEFT CLICKS",
                fg=FG_SECONDARY if self.is_running else FG_MUTED,
            )
            self.progress_canvas.coords(self.progress_bar, 0, 0, int(total_w * ratio), 4)

    def _refresh_ui_labels(self):
        if not self.win.winfo_exists():
            return
        key_name = format_key(self.toggle_hotkey)
        self.hotkey_badge.config(text=f" {key_name} ")
        self.summary_label.config(text=self._get_summary_text())
        if self.is_running:
            self.toggle_btn.config(text=f"■  STOP  [{key_name}]")
        else:
            self.toggle_btn.config(text=f"▶  START  [{key_name}]")
        self._update_progress_ui(self.current_clicks, self.is_holding_right)

    def toggle_clicker(self):
        if not self.is_running:
            self.is_running = True
            self.current_clicks = 0
            self.is_holding_right = False
            self.stop_event.clear()

            self.status_dot.config(fg=FG_PRIMARY)
            self.status_label.config(text="RUNNING", fg=FG_PRIMARY)
            self._refresh_ui_labels()

            self.worker_thread = threading.Thread(target=self._click_loop, daemon=True)
            self.worker_thread.start()
        else:
            self.stop_clicker()

    def stop_clicker(self):
        self.is_running = False
        self.is_holding_right = False
        self.current_clicks = 0
        self.stop_event.set()

        if self.win.winfo_exists():
            self.status_dot.config(fg=FG_MUTED)
            self.status_label.config(text="IDLE", fg=FG_SECONDARY)
            self._refresh_ui_labels()

    def _click_loop(self):
        click_counter = 0
        try:
            while not self.stop_event.is_set():
                self.mouse.click(Button.left, 1)
                click_counter += 1
                self.current_clicks = click_counter
                self.win.after(0, lambda c=click_counter: self._update_progress_ui(c, False))

                if click_counter >= self.clicks_before_right:
                    click_counter = 0
                    self.current_clicks = 0
                    self.is_holding_right = True
                    self.win.after(0, lambda: self._update_progress_ui(self.clicks_before_right, True))

                    self.mouse.press(Button.right)
                    try:
                        if self.stop_event.wait(self.right_hold_duration):
                            break
                    finally:
                        self.mouse.release(Button.right)
                        self.is_holding_right = False

                    self.win.after(0, lambda: self._update_progress_ui(0, False))

                if self.stop_event.wait(self.left_interval):
                    break
        except Exception as e:
            self.win.after(0, self.stop_clicker)
            self.win.after(0, lambda: messagebox.showerror("Error", str(e)))

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        self.settings_window = tk.Toplevel(self.win)
        self.settings_window.title("Auto Kill Settings")
        self.settings_window.configure(bg=BORDER_SUBTLE)
        self.settings_window.attributes("-topmost", True)
        self.settings_window.overrideredirect(True)
        center_window(self.settings_window, 340, 414)

        pending_hotkey = [self.toggle_hotkey]
        rebind_listener = [None]

        def on_settings_close():
            self.is_rebinding = False
            if rebind_listener[0] is not None:
                rebind_listener[0].stop()
            if self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.destroy()

        wrapper = tk.Frame(self.settings_window, bg=BG_MAIN)
        wrapper.pack(fill="both", expand=True, padx=1, pady=1)

        s_title = tk.Frame(wrapper, bg=BG_CARD, height=34)
        s_title.pack(fill="x")
        s_title.pack_propagate(False)
        make_draggable(s_title, self.settings_window)

        s_lbl = tk.Label(
            s_title,
            text="  ⚙  AUTO KILL SETTINGS",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        s_lbl.pack(side="left", padx=6)
        make_draggable(s_lbl, self.settings_window)

        s_close = tk.Button(
            s_title,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            bd=0,
            width=4,
            cursor="hand2",
            command=on_settings_close,
        )
        s_close.pack(side="right", fill="y")
        bind_hover(s_close, BG_CARD, "#FFFFFF", FG_SECONDARY, "#000000")

        tk.Frame(wrapper, bg=BORDER_SUBTLE, height=1).pack(fill="x")

        form = tk.Frame(wrapper, bg=BG_MAIN)
        form.pack(fill="both", expand=True, padx=18, pady=14)

        def create_field(label_text: str, unit_text: str, default_val: str) -> tk.Entry:
            card = tk.Frame(form, bg=BG_CARD, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
            card.pack(fill="x", pady=(0, 9))

            tk.Label(
                card,
                text=label_text,
                font=("Consolas", 8, "bold"),
                bg=BG_CARD,
                fg=FG_SECONDARY,
                anchor="w",
            ).pack(fill="x", padx=10, pady=(6, 2))

            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", padx=10, pady=(0, 7))

            entry = tk.Entry(
                row,
                font=("Consolas", 11, "bold"),
                bg=BG_INPUT,
                fg=FG_PRIMARY,
                insertbackground=FG_PRIMARY,
                relief="flat",
                bd=4,
            )
            entry.insert(0, default_val)
            entry.pack(side="left", fill="x", expand=True)

            tk.Label(
                row,
                text=unit_text,
                font=("Consolas", 8),
                bg=BG_CARD,
                fg=FG_MUTED,
                width=7,
                anchor="e",
            ).pack(side="right")

            return entry

        interval_entry = create_field("LEFT CLICK INTERVAL", "SEC", str(self.left_interval))
        count_entry = create_field("LEFT CLICKS BEFORE RIGHT HOLD", "CLICKS", str(self.clicks_before_right))
        hold_entry = create_field("RIGHT CLICK HOLD DURATION", "SEC", str(self.right_hold_duration))

        hk_card = tk.Frame(form, bg=BG_CARD, highlightbackground=BORDER_SUBTLE, highlightthickness=1)
        hk_card.pack(fill="x", pady=(0, 12))

        tk.Label(
            hk_card,
            text="GLOBAL TOGGLE HOTKEY",
            font=("Consolas", 8, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(6, 4))

        hotkey_btn = tk.Button(
            hk_card,
            text=f"[ {format_key(pending_hotkey[0])} ]  —  CLICK TO REBIND",
            font=("Consolas", 9, "bold"),
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            relief="flat",
            bd=0,
            pady=6,
            cursor="hand2",
        )
        hotkey_btn.pack(fill="x", padx=10, pady=(0, 8))

        def start_rebind():
            if self.is_rebinding:
                return
            self.is_rebinding = True
            hotkey_btn.config(text="PRESS ANY KEY ON KEYBOARD...", bg="#FFFFFF", fg="#000000")

            def on_capture(key):
                pending_hotkey[0] = key
                self.is_rebinding = False
                self.win.after(
                    0,
                    lambda: hotkey_btn.config(
                        text=f"[ {format_key(key)} ]  —  CLICK TO REBIND",
                        bg=BG_INPUT,
                        fg=FG_PRIMARY,
                    ),
                )
                return False

            rebind_listener[0] = KeyboardListener(on_press=on_capture)
            rebind_listener[0].daemon = True
            rebind_listener[0].start()

        hotkey_btn.config(command=start_rebind)

        btn_row = tk.Frame(form, bg=BG_MAIN)
        btn_row.pack(fill="x")

        cancel_btn = tk.Button(
            btn_row,
            text="CANCEL",
            font=("Consolas", 9, "bold"),
            height=2,
            width=12,
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=on_settings_close,
        )
        cancel_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        bind_hover(cancel_btn, BG_CARD, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

        def save_settings():
            if self.is_rebinding:
                messagebox.showwarning(
                    "Pending Key",
                    "Please press a key to finish binding the hotkey first.",
                    parent=self.settings_window,
                )
                return
            try:
                new_interval = float(interval_entry.get())
                new_count = int(count_entry.get())
                new_hold = float(hold_entry.get())

                if new_interval <= 0 or new_count <= 0 or new_hold <= 0:
                    raise ValueError("All values must be greater than 0.")

                self.left_interval = new_interval
                self.clicks_before_right = new_count
                self.right_hold_duration = new_hold
                self.toggle_hotkey = pending_hotkey[0]
                self._refresh_ui_labels()
                on_settings_close()
            except ValueError:
                messagebox.showerror(
                    "Invalid Input",
                    "Please enter valid positive numbers.\n(Click count must be an integer.)",
                    parent=self.settings_window,
                )

        save_btn = tk.Button(
            btn_row,
            text="SAVE CHANGES",
            font=("Consolas", 9, "bold"),
            height=2,
            width=16,
            bg="#FFFFFF",
            fg="#000000",
            activebackground="#E6E6E6",
            activeforeground="#000000",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=save_settings,
        )
        save_btn.pack(side="right", fill="x", expand=True, padx=(6, 0))

    def cleanup(self):
        self.stop_clicker()
        self.is_rebinding = False
        if hasattr(self, "kb_listener"):
            self.kb_listener.stop()
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        if self.win and self.win.winfo_exists():
            self.win.destroy()

    def go_back(self):
        self.cleanup()
        self.on_back_callback()

    def close_app(self):
        self.cleanup()
        self.on_exit_callback()


class MacroLauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Macro Selector")
        self.root.configure(bg=BORDER_SUBTLE)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        center_window(self.root, 340, 214)

        self.active_macro = None
        self.is_checking_update = False
        self._build_launcher_ui()

        # Automatically scan for updates on startup
        self.check_for_updates(manual=False)

    def _minimize_window(self):
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.after(200, self._check_restore)

    def _check_restore(self):
        try:
            if self.root.state() == "normal":
                self.root.overrideredirect(True)
                self.root.attributes("-topmost", True)
            else:
                self.root.after(200, self._check_restore)
        except tk.TclError:
            pass

    def _build_launcher_ui(self):
        container = tk.Frame(self.root, bg=BG_MAIN)
        container.pack(fill="both", expand=True, padx=1, pady=1)

        # Title Bar
        title_bar = tk.Frame(container, bg=BG_CARD, height=34)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        make_draggable(title_bar, self.root)

        title_lbl = tk.Label(
            title_bar,
            text=f"  ◆  SELECT MACRO  v{APP_VERSION}",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
        )
        title_lbl.pack(side="left", padx=6)
        make_draggable(title_lbl, self.root)

        close_btn = tk.Button(
            title_bar,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            bd=0,
            width=4,
            cursor="hand2",
            command=self.exit_app,
        )
        close_btn.pack(side="right", fill="y")
        bind_hover(close_btn, BG_CARD, "#FFFFFF", FG_SECONDARY, "#000000")

        min_btn = tk.Button(
            title_bar,
            text="—",
            font=("Segoe UI", 9),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_HOVER,
            activeforeground=FG_PRIMARY,
            bd=0,
            width=4,
            cursor="hand2",
            command=self._minimize_window,
        )
        min_btn.pack(side="right", fill="y")
        bind_hover(min_btn, BG_CARD, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

        tk.Frame(container, bg=BORDER_SUBTLE, height=1).pack(fill="x")

        # Selection Buttons Body
        body = tk.Frame(container, bg=BG_MAIN)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        auto_sell_btn = tk.Button(
            body,
            text="▶  AUTO SELL",
            font=("Consolas", 11, "bold"),
            height=2,
            bg=BG_CARD,
            fg=FG_PRIMARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.open_auto_sell,
        )
        auto_sell_btn.pack(fill="x", pady=(0, 8))
        bind_hover(auto_sell_btn, BG_CARD, BG_HOVER)

        auto_kill_btn = tk.Button(
            body,
            text="▶  AUTO KILL",
            font=("Consolas", 11, "bold"),
            height=2,
            bg=BG_CARD,
            fg=FG_PRIMARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.open_auto_kill,
        )
        auto_kill_btn.pack(fill="x", pady=(0, 8))
        bind_hover(auto_kill_btn, BG_CARD, BG_HOVER)

        self.update_btn = tk.Button(
            body,
            text="↻  SEARCH FOR UPDATES",
            font=("Consolas", 9, "bold"),
            height=2,
            bg=BG_INPUT,
            fg=FG_SECONDARY,
            activebackground="#FFFFFF",
            activeforeground="#000000",
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.check_for_updates(manual=True),
        )
        self.update_btn.pack(fill="x")
        bind_hover(self.update_btn, BG_INPUT, BG_HOVER, FG_SECONDARY, FG_PRIMARY)

    def _fetch_remote_code(self) -> str:
        # 1) Try GitHub Contents API first (bypasses 5-minute raw CDN cache)
        try:
            api_req = urllib.request.Request(
                GITHUB_API_URL,
                headers={
                    "User-Agent": "MacroUpdater/1.0",
                    "Accept": "application/vnd.github.v3.raw",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(api_req, timeout=6) as response:
                return response.read().decode("utf-8")
        except Exception:
            # 2) Fallback to raw.githubusercontent.com
            raw_req = urllib.request.Request(
                f"{UPDATE_URL}?t={int(time.time())}",
                headers={
                    "User-Agent": "MacroUpdater/1.0",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with urllib.request.urlopen(raw_req, timeout=6) as response:
                return response.read().decode("utf-8")

    def check_for_updates(self, manual: bool = False):
        if self.is_checking_update:
            return
        self.is_checking_update = True

        if manual and self.update_btn.winfo_exists():
            self.update_btn.config(text="↻  CHECKING FOR UPDATES...", fg=FG_PRIMARY)

        def worker():
            try:
                remote_code = self._fetch_remote_code()
                match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', remote_code)
                remote_version = match.group(1) if match else None

                if remote_version and parse_version(remote_version) > parse_version(APP_VERSION):
                    self.root.after(0, lambda: self._prompt_update(remote_version, remote_code))
                else:
                    self.root.after(0, lambda: self._on_up_to_date(manual))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._on_update_error(manual, str(e)))
            finally:
                self.is_checking_update = False

        threading.Thread(target=worker, daemon=True).start()

    def _on_up_to_date(self, manual: bool):
        if not self.update_btn.winfo_exists():
            return
        if manual:
            self.update_btn.config(text=f"✓  UP TO DATE (v{APP_VERSION})", fg=FG_PRIMARY)
            self.root.after(2500, self._reset_update_btn)
        else:
            self._reset_update_btn()

    def _on_update_error(self, manual: bool, err: str):
        if not self.update_btn.winfo_exists():
            return
        if manual:
            self.update_btn.config(text="✕  UPDATE CHECK FAILED", fg=FG_SECONDARY)
            messagebox.showerror(
                "Update Error",
                f"Could not reach GitHub update server.\n\nDetails: {err}",
                parent=self.root,
            )
            self._reset_update_btn()

    def _reset_update_btn(self):
        if self.update_btn.winfo_exists():
            self.update_btn.config(text="↻  SEARCH FOR UPDATES", fg=FG_SECONDARY)

    def _prompt_update(self, remote_version: str, remote_code: str):
        self._reset_update_btn()
        answer = messagebox.askyesno(
            "Update Available",
            f"A new version (v{remote_version}) is available!\n"
            f"Current version: v{APP_VERSION}\n\n"
            "Do you want to download and install it now?",
            parent=self.root,
        )
        if answer:
            self._apply_update(remote_code)

    def _apply_update(self, remote_code: str):
        try:
            current_file = os.path.abspath(__file__)
            with open(current_file, "w", encoding="utf-8") as f:
                f.write(remote_code)

            if self.active_macro is not None:
                self.active_macro.cleanup()
            self.root.destroy()
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            messagebox.showerror(
                "Installation Failed",
                f"Failed to overwrite script file:\n{exc}",
                parent=self.root,
            )

    def open_auto_sell(self):
        self.root.withdraw()
        self.active_macro = AutoSellMacroWindow(
            self.root,
            on_back_callback=self.show_launcher,
            on_exit_callback=self.exit_app,
        )

    def open_auto_kill(self):
        self.root.withdraw()
        self.active_macro = AutoKillMacroWindow(
            self.root,
            on_back_callback=self.show_launcher,
            on_exit_callback=self.exit_app,
        )

    def show_launcher(self):
        self.active_macro = None
        center_window(self.root, 340, 214)
        self.root.deiconify()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.lift()

    def exit_app(self):
        if self.active_macro is not None:
            self.active_macro.cleanup()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MacroLauncherApp(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()
