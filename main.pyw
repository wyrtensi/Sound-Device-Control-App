from flask import Flask, render_template, request, jsonify
from threading import Thread, Lock, Event
from pynput import mouse, keyboard
from pynput.keyboard import Key, Controller as KeyboardController, KeyCode
from pynput.mouse import Button, Controller as MouseController
import json
import time
import subprocess
import ctypes
from ctypes import cast, POINTER, wintypes
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import win32api
import win32con
import win32gui
import win32com.client
import pythoncom
import mouse
import tkinter as tk
from tkinter import font
import pystray
from PIL import Image, ImageDraw
import webbrowser

# Windows constants
WM_APPCOMMAND = 0x319
APPCOMMAND_VOLUME_UP = 0x0a
APPCOMMAND_VOLUME_DOWN = 0x09
APPCOMMAND_MEDIA_PLAY_PAUSE = 0x0E
APPCOMMAND_MEDIA_NEXTTRACK = 0x0B
APPCOMMAND_MEDIA_PREVIOUSTRACK = 0x0C

app = Flask(__name__)

# Default hotkeys
default_hotkeys = {
    "volume_up": {
        "keyboard": "ctrl",
        "mouse": "scrollup"
    },
    "volume_down": {
        "keyboard": "ctrl",
        "mouse": "scrolldown"
    },
    "prev_device": {
        "keyboard": "win+pageup",
        "mouse": "None"
    },
    "next_device": {
        "keyboard": "win+pagedown",
        "mouse": "None"
    },
    "prev_input_device": {
        "keyboard": "win+home",
        "mouse": "None"
    },
    "next_input_device": {
        "keyboard": "win+end",
        "mouse": "None"
    },
    "media_play_pause": {
        "keyboard": "ctrl+space",
        "mouse": "None"
    },
    "media_next": {
        "keyboard": "ctrl+right",
        "mouse": "None"
    },
    "media_previous": {
        "keyboard": "ctrl+left",
        "mouse": "None"
    }
}

class KeyboardMouseTracker:
    def __init__(self):
        self.pressed_buttons = set()
        self.pressed_keyboard_keys = set()
        self.scroll_direction = None
        self.lock = Lock()
        self.stop_event = Event()
        
        self._left_pressed = False
        self._right_pressed = False
        self._middle_pressed = False
        
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        
        mouse.hook(self._on_mouse_event)
        
        self.state_cache = None
        self.last_state_update = 0
        self.state_cache_lifetime = 0.008
    
    def _on_mouse_event(self, event):
        try:
            if hasattr(event, 'delta'):
                with self.lock:
                    if event.delta > 0:
                        self.scroll_direction = 'scrollup'
                        Thread(target=self._reset_scroll, daemon=True).start()
                    elif event.delta < 0:
                        self.scroll_direction = 'scrolldown'
                        Thread(target=self._reset_scroll, daemon=True).start()
                return
            
            if getattr(event, 'event_type', None) == 'move':
                return

        except Exception as e:
            print(f"Error in mouse event handler: {e}")

    def _on_key_press(self, key):
        try:
            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                key_str = key.char.lower()
            else:
                key_str = str(key).lower().replace('key.', '')
            
            key_str = normalize_key_name(key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.add(key_str)
                
        except Exception as e:
            print(f"Error in key press handler: {e}")

    def _on_key_release(self, key):
        try:
            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                key_str = key.char.lower()
            else:
                key_str = str(key).lower().replace('key.', '')
            
            key_str = normalize_key_name(key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.discard(key_str)
                
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _track_mouse_buttons(self):
        while not self.stop_event.is_set():
            try:
                time.sleep(0.008)
                
                left = win32api.GetKeyState(win32con.VK_LBUTTON) < 0
                right = win32api.GetKeyState(win32con.VK_RBUTTON) < 0
                middle = win32api.GetKeyState(win32con.VK_MBUTTON) < 0

                with self.lock:
                    changed = False
                    
                    if left != self._left_pressed:
                        if left:
                            self.pressed_buttons.add('mouseleft')
                        else:
                            self.pressed_buttons.discard('mouseleft')
                        self._left_pressed = left
                        changed = True

                    if right != self._right_pressed:
                        if right:
                            self.pressed_buttons.add('mouseright')
                        else:
                            self.pressed_buttons.discard('mouseright')
                        self._right_pressed = right
                        changed = True

                    if middle != self._middle_pressed:
                        if middle:
                            self.pressed_buttons.add('mousemiddle')
                        else:
                            self.pressed_buttons.discard('mousemiddle')
                        self._middle_pressed = middle
                        changed = True
                    
                    if changed:
                        self.state_cache = None

            except Exception as e:
                print(f"Error tracking mouse buttons: {e}")
                time.sleep(0.1)

    def _reset_scroll(self):
        time.sleep(0.2)
        with self.lock:
            self.scroll_direction = None

    def start(self):
        self.keyboard_listener.start()
        self.mouse_thread = Thread(target=self._track_mouse_buttons, daemon=True)
        self.mouse_thread.start()

    def stop(self):
        self.stop_event.set()
        self.keyboard_listener.stop()
        mouse.unhook_all()
        if hasattr(self, 'mouse_thread'):
            self.mouse_thread.join(timeout=1.0)

    def get_state(self):
        current_time = time.time()
        
        if self.state_cache and (current_time - self.last_state_update) < self.state_cache_lifetime:
            return self.state_cache
            
        with self.lock:
            self.state_cache = {
                'keyboard': self.pressed_keyboard_keys.copy(),
                'mouse': {
                    'buttons': self.pressed_buttons.copy(),
                    'scroll': self.scroll_direction
                }
            }
            self.last_state_update = current_time
            return self.state_cache

def normalize_key_name(key_str):
    key_mapping = {
        'arrowup': 'up',
        'arrowdown': 'down',
        'arrowleft': 'left',
        'arrowright': 'right',
        'page_up': 'pageup',
        'page_down': 'pagedown',
        'none': '',
        'space': 'space',
        'up': 'up',
        'down': 'down',
        'left': 'left',
        'right': 'right',
        'ctrl_l': 'ctrl',
        'ctrl_r': 'ctrl',
        'alt_l': 'alt',
        'alt_r': 'alt',
        'shift_l': 'shift',
        'shift_r': 'shift',
        'cmd': 'win',
        'cmd_r': 'win',
        'mouseleft': 'mouseleft',
        'mouseright': 'mouseright',
        'mousemiddle': 'mousemiddle',
        'scrollup': 'scrollup',
        'scrolldown': 'scrolldown',
        'lmb': 'mouseleft',
        'rmb': 'mouseright',
        'mmb': 'mousemiddle'
    }
    
    if key_str.lower().startswith('key.'):
        key_str = key_str[4:]
    
    return key_mapping.get(key_str.lower(), key_str.lower())

def handle_hotkeys(tracker):
    last_action_time = {}
    
    while True:
        try:
            time.sleep(0.008)
            
            state = tracker.get_state()
            current_time = time.time()
            
            for action, combo in hotkeys.items():
                if current_time - last_action_time.get(action, 0) < 0.1:
                    continue
                
                if combo['keyboard'].lower() == 'none' and combo['mouse'].lower() == 'none':
                    continue
                    
                if check_hotkey_combination(combo, state):
                    if action == 'volume_up':
                        send_volume_message(APPCOMMAND_VOLUME_UP)
                    elif action == 'volume_down':
                        send_volume_message(APPCOMMAND_VOLUME_DOWN)
                    elif action == 'prev_device':
                        switch_audio_device('prev')
                    elif action == 'next_device':
                        switch_audio_device('next')
                    elif action == 'prev_input_device':
                        switch_input_device('prev')
                    elif action == 'next_input_device':
                        switch_input_device('next')
                    elif action == 'media_play_pause':
                        send_media_message(APPCOMMAND_MEDIA_PLAY_PAUSE)
                    elif action == 'media_next':
                        send_media_message(APPCOMMAND_MEDIA_NEXTTRACK)
                    elif action == 'media_previous':
                        send_media_message(APPCOMMAND_MEDIA_PREVIOUSTRACK)
                    
                    last_action_time[action] = current_time
                    
        except Exception as e:
            print(f"Error in handle_hotkeys: {e}")
            time.sleep(0.1)

def check_hotkey_combination(hotkey, state):
    try:
        # Если обе комбинации None - сразу возвращаем False
        if (hotkey['keyboard'].lower() == 'none' and 
            hotkey['mouse'].lower() == 'none'):
            return False

        # Проверяем клавиатурные клавиши
        keyboard_keys = set(k.strip().lower() for k in hotkey['keyboard'].split('+') 
                          if k.strip() and k.strip().lower() != 'none')
        
        # Проверяем клавиши мыши
        mouse_keys = set(m.strip().lower() for m in hotkey['mouse'].split('+') 
                        if m.strip() and m.strip().lower() != 'none')

        # Если нет ни клавиатурных, ни мышиных клавиш - возвращаем False
        if not keyboard_keys and not mouse_keys:
            return False

        # Проверяем совпадение клавиатурных клавиш
        keyboard_match = True
        if keyboard_keys:
            keyboard_match = all(key in state['keyboard'] for key in keyboard_keys)
            if not keyboard_match:
                return False

        # Проверяем совпадение мышиных клавиш
        mouse_match = True
        if mouse_keys:
            for mouse_key in mouse_keys:
                if mouse_key in ['scrollup', 'scrolldown']:
                    mouse_match = mouse_match and state['mouse']['scroll'] == mouse_key
                else:
                    mouse_match = mouse_match and mouse_key in state['mouse']['buttons']
            if not mouse_match:
                return False

        # Возвращаем True только если все необходимые клавиши совпали
        return True

    except Exception as e:
        print(f"Error checking hotkey combination: {e}")
        return False

def send_volume_message(app_command):
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.SendMessageW(hwnd, WM_APPCOMMAND, 0, app_command * 0x10000)

def send_media_message(app_command):
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.SendMessageW(hwnd, WM_APPCOMMAND, 0, app_command * 0x10000)

def get_audio_devices():
    """Получает список устройств вывода звука"""
    powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    
    ps_script = """
    if (-not (Get-Module -ListAvailable -Name AudioDeviceCmdlets)) {
        Write-Host "ERROR: AudioDeviceCmdlets not installed"
        exit 1
    }
    
    try {
        $devices = Get-AudioDevice -List | Where-Object { $_.Type -eq 'Playback' }
        $devices | ForEach-Object { "$($_.Index),$($_.Name)" }
    } catch {
        Write-Host "Error getting output device list"
    }
    """
    
    try:
        result = subprocess.run(
            [powershell_path, "-Command", ps_script],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if "ERROR: AudioDeviceCmdlets not installed" in result.stdout:
            print("AudioDeviceCmdlets module needs to be installed. Installing...")
            install_script = """
            Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser
            """
            subprocess.run(
                [powershell_path, "-Command", install_script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            result = subprocess.run(
                [powershell_path, "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        
        devices = result.stdout.strip().split('\n')
        devices = [device.split(',') for device in devices if device.strip()]
        return devices
        
    except Exception as e:
        print(f"Error getting output devices: {e}")
        return []

def set_default_audio_device(device_index):
    ps_script = f"""
    try {{
        Set-AudioDevice -Index {device_index}
    }} catch {{
        Write-Host "Error setting default device: $_"
    }}
    """
    
    try:
        result = subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-Command", ps_script],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.stderr:
            print(f"PowerShell error: {result.stderr}")
        if result.stdout:
            print(f"PowerShell output: {result.stdout}")
    except Exception as e:
        print(f"Error executing PowerShell: {e}")

def show_notification(device_name):
    root = tk.Tk()
    root.overrideredirect(True)
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 350
    window_height = 60
    x_position = screen_width - window_width - 10
    y_position = screen_height - window_height - 80
    root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
    root.attributes("-topmost", 1)
    root.configure(bg="#333333")
    label = tk.Label(root, text=device_name, font=("Arial", 12, "bold"), fg="white", bg="#333333")
    label.pack(expand=True)
    root.after(1000, root.destroy)
    root.mainloop()

def switch_audio_device(direction):
    global current_device_index, devices
    try:
        if not devices:
            return
            
        if direction == 'prev':
            current_device_index = (current_device_index - 1) % len(devices)
        else:
            current_device_index = (current_device_index + 1) % len(devices)
        
        device_index = devices[current_device_index][0]
        set_default_audio_device(device_index)
        
        device_name = devices[current_device_index][1]
        Thread(target=show_notification, args=(f"Switched to: {device_name}",)).start()
        
    except Exception as e:
        print(f"Error switching device: {e}")

def create_icon():
    width = 128
    height = 128
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for i in range(40):
        alpha = int(255 * (1 - i/40))
        color = (0, 123, 255, alpha)
        draw.ellipse([i, i, width-i, height-i], fill=color)

    speaker_color = (255, 255, 255, 255)
    draw.rectangle([35, 44, 55, 84], fill=speaker_color)
    
    points_left = [(55, 44), (85, 24), (85, 104), (55, 84)]
    draw.polygon(points_left, fill=speaker_color)

    wave_color = (255, 255, 255, 200)
    draw.arc([70, 34, 100, 94], 300, 60, fill=wave_color, width=4)
    draw.arc([85, 24, 115, 104], 300, 60, fill=wave_color, width=4)

    bar_colors = [(0, 255, 255, 200), (0, 255, 200, 200), (0, 200, 255, 200)]
    bar_width = 4
    for i, color in enumerate(bar_colors):
        height = 20 + i * 10
        x = 95 + i * 8
        y = 64 - height//2
        draw.rectangle([x, y, x+bar_width, y+height], fill=color)

    return image

def open_settings(icon, item):
    webbrowser.open('http://127.0.0.1:5000')

def exit_app(icon, item):
    icon.stop()
    global running
    running = False

def setup_tray():
    """Sets up the tray icon"""
    icon = pystray.Icon(
        "Sound Device Control App",
        icon=create_icon(),
        menu=pystray.Menu(
            pystray.MenuItem("Settings", open_settings, default=True),
            pystray.MenuItem("Exit", exit_app)
        )
    )
    return icon

@app.route("/")
def index():
    return render_template("index.html", hotkeys=hotkeys)

def save_settings(settings):
    """Сохраняет настройки в файл"""
    try:
        # Проверяем валидность JSON перед сохранением
        json.dumps(settings)
        
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def update_settings_structure(settings):
    """Обновляет структуру настроек, добавляя недостающие действия"""
    updated = False
    for action, combo in default_hotkeys.items():
        if action not in settings:
            settings[action] = combo.copy()
            updated = True
    return settings, updated

# Загрузка настроек при запуске
try:
    with open('settings.json', 'r', encoding='utf-8') as f:
        hotkeys = json.load(f)
    # Обновляем структуру если нужно
    hotkeys, was_updated = update_settings_structure(hotkeys)
    if was_updated:
        save_settings(hotkeys)
    print(f"Loaded hotkeys: {hotkeys}")
except FileNotFoundError:
    hotkeys = default_hotkeys.copy()
    save_settings(hotkeys)
    print(f"Using default hotkeys: {hotkeys}")
except json.JSONDecodeError:
    print("Error reading settings.json, using default hotkeys")
    hotkeys = default_hotkeys.copy()
    save_settings(hotkeys)

@app.route("/update_hotkey", methods=["POST"])
def update_hotkey():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"})
            
        action = data.get("action")
        if not action:
            return jsonify({"status": "error", "message": "No action specified"})
            
        keyboard_keys = data.get("keyboard", "None")
        mouse_keys = data.get("mouse", "None")
        
        print(f"Updating hotkey - Action: {action}, Keyboard: {keyboard_keys}, Mouse: {mouse_keys}")

        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                current_hotkeys = json.load(f)
        except FileNotFoundError:
            current_hotkeys = default_hotkeys.copy()
        except json.JSONDecodeError:
            current_hotkeys = default_hotkeys.copy()

        # Обновляем структуру если нужно
        current_hotkeys, _ = update_settings_structure(current_hotkeys)
        
        current_hotkeys[action] = {
            "keyboard": keyboard_keys,
            "mouse": mouse_keys
        }

        if save_settings(current_hotkeys):
            global hotkeys
            hotkeys = current_hotkeys
            return jsonify({"status": "success", "hotkeys": current_hotkeys})
        else:
            return jsonify({"status": "error", "message": "Error saving settings"})

    except Exception as e:
        print(f"Error in update_hotkey: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)})

def run_flask():
    app.run(host='127.0.0.1', port=5000, debug=False)

def main():
    global running, devices, input_devices, current_device_index, current_input_device_index
    running = True
    
    # Получаем списки устройств
    devices = get_audio_devices()
    input_devices = get_input_devices()
    
    if not devices:
        print("No audio output devices found!")
    else:
        print(f"Found {len(devices)} audio output devices")
        
    if not input_devices:
        print("No audio input devices found!")
    else:
        print(f"Found {len(input_devices)} audio input devices")
    
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask server started")
    
    tracker = KeyboardMouseTracker()
    tracker.start()
    print("Mouse and keyboard tracking started")

    hotkey_thread = Thread(target=lambda: handle_hotkeys(tracker), daemon=True)
    hotkey_thread.start()
    print("Hotkey handler started")

    tray_icon = setup_tray()
    tray_thread = Thread(target=lambda: tray_icon.run(), daemon=True)
    tray_thread.start()
    print("Tray icon started")

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        tracker.stop()
        if hasattr(tray_icon, '_icon') and tray_icon._icon:
            tray_icon.stop()

@app.route("/save_settings", methods=["POST"])
def save_settings_endpoint():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"})

        # Проверяем формат данных
        for action, combo in data.items():
            if not isinstance(combo, dict) or "keyboard" not in combo or "mouse" not in combo:
                return jsonify({
                    "status": "error",
                    "message": f"Invalid data format for action {action}"
                })

        # Обновляем структуру если нужно
        data, _ = update_settings_structure(data)

        # Сохраняем настройки
        if save_settings(data):
            global hotkeys
            hotkeys = data
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Error saving settings"})
    except Exception as e:
        print(f"Error in save_settings_endpoint: {e}")
        return jsonify({"status": "error", "message": str(e)})

devices = []
current_device_index = 0
running = False

# Добавляем глобальные переменные для устройств ввода
input_devices = []
current_input_device_index = 0

def get_input_devices():
    """Получает список устройств ввода (микрофонов)"""
    powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    
    ps_script = """
    if (-not (Get-Module -ListAvailable -Name AudioDeviceCmdlets)) {
        Write-Host "ERROR: AudioDeviceCmdlets not installed"
        exit 1
    }
    
    try {
        $devices = Get-AudioDevice -List | Where-Object { $_.Type -eq 'Recording' }
        $devices | ForEach-Object { "$($_.Index),$($_.Name)" }
    } catch {
        Write-Host "Error getting input device list"
    }
    """
    
    try:
        result = subprocess.run(
            [powershell_path, "-Command", ps_script],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if "ERROR: AudioDeviceCmdlets not installed" in result.stdout:
            print("AudioDeviceCmdlets module needs to be installed. Installing...")
            install_script = """
            Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser
            """
            subprocess.run(
                [powershell_path, "-Command", install_script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            result = subprocess.run(
                [powershell_path, "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        
        devices = result.stdout.strip().split('\n')
        devices = [device.split(',') for device in devices if device.strip()]
        return devices
        
    except Exception as e:
        print(f"Error getting input devices: {e}")
        return []

def switch_input_device(direction):
    """Переключает устройство ввода"""
    global current_input_device_index, input_devices
    try:
        if not input_devices:
            return
            
        if direction == 'prev':
            current_input_device_index = (current_input_device_index - 1) % len(input_devices)
        else:
            current_input_device_index = (current_input_device_index + 1) % len(input_devices)
        
        device_index = input_devices[current_input_device_index][0]
        
        # PowerShell скрипт для установки устройства ввода по умолчанию
        ps_script = f"""
        try {{
            Set-AudioDevice -Index {device_index}
        }} catch {{
            Write-Host "Error setting default input device: $_"
        }}
        """
        
        subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        # Показываем уведомление
        device_name = input_devices[current_input_device_index][1]
        Thread(target=show_notification, args=(f"Input switched to: {device_name}",)).start()
        
    except Exception as e:
        print(f"Error switching input device: {e}")

if __name__ == "__main__":
    main()
