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
from PIL import Image, ImageDraw, ImageTk
import webbrowser
import math

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
    "toggle_mic_volume": {
        "keyboard": "ctrl+m",
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
            if isinstance(key, keyboard.KeyCode):
                if key.char is not None:
                    key_str = key.char.lower()
                else:
                    # Обработка специальных символов по vk коду
                    vk = key.vk if hasattr(key, 'vk') else None
                    if vk:
                        key_str = {
                            191: '/',  # Слеш
                            220: '\\', # Обратный слеш
                            188: ',',  # Запятая
                            190: '.',  # Точка
                            186: ';',  # Точка с запятой
                            222: "'",  # Кавычка
                            219: '[',  # Открывающая скобка
                            221: ']',  # Закрывающая скобка
                            189: '-',  # Минус
                            187: '=',  # Равно
                            192: '`',  # Обратный апостроф
                        }.get(vk, str(key).lower().replace('key.', ''))
                    else:
                        key_str = str(key).lower().replace('key.', '')
            else:
                key_str = str(key).lower().replace('key.', '')
            
            key_str = normalize_key_name(key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.add(key_str)
                
        except Exception as e:
            print(f"Error in key press handler: {e}")

    def _on_key_release(self, key):
        try:
            if isinstance(key, keyboard.KeyCode):
                if key.char is not None:
                    key_str = key.char.lower()
                else:
                    # Обработка специальных символов по vk коду
                    vk = key.vk if hasattr(key, 'vk') else None
                    if vk:
                        key_str = {
                            191: '/',  # Слеш
                            220: '\\', # Обратный слеш
                            188: ',',  # Запятая
                            190: '.',  # Точка
                            186: ';',  # Точка с запятой
                            222: "'",  # Кавычка
                            219: '[',  # Открывающая скобка
                            221: ']',  # Закрывающая скобка
                            189: '-',  # Минус
                            187: '=',  # Равно
                            192: '`',  # Обратный апостроф
                        }.get(vk, str(key).lower().replace('key.', ''))
                    else:
                        key_str = str(key).lower().replace('key.', '')
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
    """Нормализует названия клавиш"""
    key_mapping = {
        # Special keys
        'arrowup': 'up',
        'arrowdown': 'down',
        'arrowleft': 'left',
        'arrowright': 'right',
        'page_up': 'pageup',
        'page_down': 'pagedown',
        'none': '',
        'space': 'space',
        # Arrows
        'up': 'up',
        'down': 'down',
        'left': 'left',
        'right': 'right',
        # Modifiers
        'ctrl_l': 'ctrl',
        'ctrl_r': 'ctrl',
        'alt_l': 'alt',
        'alt_r': 'alt',
        'shift_l': 'shift',
        'shift_r': 'shift',
        'cmd': 'win',
        'cmd_r': 'win',
        # Mouse
        'mouseleft': 'mouseleft',
        'mouseright': 'mouseright',
        'mousemiddle': 'mousemiddle',
        'scrollup': 'scrollup',
        'scrolldown': 'scrolldown',
        'lmb': 'mouseleft',
        'rmb': 'mouseright',
        'mmb': 'mousemiddle',
        # Special characters
        '/': '/',
        '\\': '\\',
        ',': ',',
        '.': '.',
        ';': ';',
        "'": "'",
        '[': '[',
        ']': ']',
        '-': '-',
        '=': '=',
        '`': '`',
        # Fix for control characters
        '\x01': 'a',  # Ctrl+A
        '\x02': 'b',  # Ctrl+B
        '\x03': 'c',  # Ctrl+C
        '\x04': 'd',  # Ctrl+D
        '\x05': 'e',  # Ctrl+E
        '\x06': 'f',  # Ctrl+F
        '\x07': 'g',  # Ctrl+G
        '\x08': 'h',  # Ctrl+H
        '\x09': 'i',  # Ctrl+I (Tab)
        '\x0A': 'j',  # Ctrl+J
        '\x0B': 'k',  # Ctrl+K
        '\x0C': 'l',  # Ctrl+L
        '\x0D': 'm',  # Ctrl+M (Enter)
        '\x0E': 'n',  # Ctrl+N
        '\x0F': 'o',  # Ctrl+O
        '\x10': 'p',  # Ctrl+P
        '\x11': 'q',  # Ctrl+Q
        '\x12': 'r',  # Ctrl+R
        '\x13': 's',  # Ctrl+S
        '\x14': 't',  # Ctrl+T
        '\x15': 'u',  # Ctrl+U
        '\x16': 'v',  # Ctrl+V
        '\x17': 'w',  # Ctrl+W
        '\x18': 'x',  # Ctrl+X
        '\x19': 'y',  # Ctrl+Y
        '\x1A': 'z',  # Ctrl+Z
        '\r': 'm',    # Enter key
        '\n': 'n',    # Newline
        '\t': 'tab',  # Tab key
        # Letters and numbers
        'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e',
        'f': 'f', 'g': 'g', 'h': 'h', 'i': 'i', 'j': 'j',
        'k': 'k', 'l': 'l', 'm': 'm', 'n': 'n', 'o': 'o',
        'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't',
        'u': 'u', 'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y',
        'z': 'z',
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
        '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    }
    
    # Remove 'key.' prefix if it exists
    if key_str.lower().startswith('key.'):
        key_str = key_str[4:]
    
    # Convert to lowercase for consistency
    key_str = key_str.lower()
    
    # Check if key is in mapping
    return key_mapping.get(key_str, key_str)

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
                    elif action == 'toggle_mic_volume':
                        toggle_microphone_volume()
                    elif action == 'media_play_pause':
                        send_media_message(APPCOMMAND_MEDIA_PLAY_PAUSE)
                    elif action == 'media_next':
                        send_media_message(APPCOMMAND_MEDIA_NEXTTRACK)
                    elif action == 'media_previous':
                        send_media_message(APPCOMMAND_MEDIA_PREVIOUSTRACK)
                    
                    last_action_time[action] = current_time

        except:
            time.sleep(0.1)

def check_hotkey_combination(hotkey, state):
    try:
        if (hotkey['keyboard'].lower() == 'none' and 
            hotkey['mouse'].lower() == 'none'):
            return False

        # Разделяем комбинации клавиш
        keyboard_keys = set()
        for k in hotkey['keyboard'].split('+'):
            k = k.strip().lower()
            if k and k != 'none':
                keyboard_keys.add(k)

        mouse_keys = set(m.strip().lower() for m in hotkey['mouse'].split('+') 
                        if m.strip() and m.strip().lower() != 'none')

        if not keyboard_keys and not mouse_keys:
            return False

        # Получаем текущие нажатые клавиши
        current_keys = state['keyboard']

        # Проверяем, что все необходимые клавиши нажаты
        keyboard_match = True
        if keyboard_keys:
            # Проверяем, что количество нажатых клавиш совпадает
            if len(keyboard_keys) != len(current_keys):
                return False
            
            # Проверяем, что все необходимые клавиши нажаты
            keyboard_match = all(key in current_keys for key in keyboard_keys)
            if not keyboard_match:
                return False

        mouse_match = True
        if mouse_keys:
            for mouse_key in mouse_keys:
                if mouse_key in ['scrollup', 'scrolldown']:
                    mouse_match = mouse_match and state['mouse']['scroll'] == mouse_key
                else:
                    mouse_match = mouse_match and mouse_key in state['mouse']['buttons']
            if not mouse_match:
                return False

        return True

    except Exception as e:
        print(f"Error in check_hotkey_combination: {e}")
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
        $OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
        $devices = Get-AudioDevice -List | Where-Object { $_.Type -eq 'Playback' }
        Write-Host "Found devices:"
        $devices | ForEach-Object {
            Write-Host ("Device: Index={0}, Name={1}" -f $_.Index, $_.Name)
            Write-Output ("DEVICE:{0}|{1}" -f $_.Index, $_.Name)
        }
    } catch {
        Write-Host "Error getting output device list: $_"
    }
    """
    
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            [powershell_path, "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        
        print("PowerShell output:", result.stdout)
        if result.stderr:
            print("PowerShell error:", result.stderr)
        
        devices = []
        for line in result.stdout.split('\n'):
            if line.strip().startswith('DEVICE:'):
                try:
                    _, device_info = line.strip().split('DEVICE:', 1)
                    index, name = device_info.split('|', 1)
                    devices.append([index.strip(), name.strip()])
                except ValueError as e:
                    print(f"Error parsing line '{line}': {e}")
                    continue
        
        print(f"Found devices: {devices}")
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
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        if result.stderr:
            print("PowerShell error:", result.stderr)
    except Exception as e:
        print(f"Error executing PowerShell: {e}")

notification_queue = []
notification_root = None
current_notification = None

def create_round_rectangle(width, height, radius, fill):
    """Создает изображение со скругленными углами"""
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    draw.rounded_rectangle([(0, 0), (width-1, height-1)], radius, fill=fill)
    return image

def create_notification_window():
    """Создает основное окно для уведомлений"""
    global notification_root
    notification_root = tk.Tk()
    notification_root.withdraw()  # Скрываем основное окно
    
    def check_queue():
        if notification_queue:
            message = notification_queue.pop(0)
            show_notification_message(message)
        notification_root.after(100, check_queue)
    
    check_queue()
    notification_root.mainloop()

def show_notification(message):
    """Добавляет сообщение в очередь уведомлений"""
    notification_queue.append(message)

def show_notification_message(message):
    """Показывает уведомление"""
    global current_notification
    
    try:
        # Создаем новое окно только если нет активного или оно уже не существует
        if not current_notification or not current_notification.winfo_exists():
            root = tk.Toplevel(notification_root)
            current_notification = root
        else:
            root = current_notification
            # Очищаем предыдущее содержимое
            for widget in root.winfo_children():
                widget.destroy()
        
        root.overrideredirect(True)
        root.attributes('-alpha', 0.0)
        root.attributes("-topmost", True)
        
        # Настройка размеров и позиции
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = 300
        window_height = 80
        x_position = screen_width - window_width - 20
        y_position = screen_height - window_height - 40
        
        root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        
        # Создаем скругленную рамку
        frame = tk.Frame(root, bg='#2C2C2C', highlightthickness=0)
        frame.place(relwidth=1, relheight=1)
        
        # Создаем фон со скругленными углами
        bg_image = create_round_rectangle(300, 80, 15, '#2C2C2C')
        bg_photo = ImageTk.PhotoImage(bg_image, master=root)
        
        # Создаем и размещаем фоновую метку
        bg_label = tk.Label(frame, image=bg_photo, bg='#2C2C2C')
        bg_label.image = bg_photo
        bg_label.place(relwidth=1, relheight=1)
        
        # Иконка звука
        icon_size = 24
        icon_image = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon_image)
        
        # Рисуем иконку звука
        speaker_color = '#4A9EFF'
        draw.rectangle([4, 8, 10, 16], fill=speaker_color)
        points = [(10, 8), (16, 4), (16, 20), (10, 16)]
        draw.polygon(points, fill=speaker_color)
        
        # Звуковые волны
        for i in range(2):
            x = 18 + i * 4
            draw.arc([x, 6, x+6, 18], -60, 60, fill=speaker_color, width=2)
        
        icon_photo = ImageTk.PhotoImage(icon_image, master=root)
        icon_label = tk.Label(frame, image=icon_photo, bg='#2C2C2C')
        icon_label.image = icon_photo
        icon_label.place(x=15, y=28)
        
        # Текст уведомления
        custom_font = font.Font(family="Segoe UI", size=10, weight="normal")
        label = tk.Label(frame, 
                        text=message,
                        font=custom_font,
                        fg='#FFFFFF',
                        bg='#2C2C2C',
                        justify=tk.LEFT)
        label.place(x=50, y=30)
        
        def fade_in():
            alpha = root.attributes('-alpha')
            if alpha < 1.0:
                root.attributes('-alpha', alpha + 0.1)
                root.after(20, fade_in)
            else:
                root.after(2000, fade_out)
                
        def fade_out():
            if not root.winfo_exists():
                return
                
            alpha = root.attributes('-alpha')
            if alpha > 0:
                root.attributes('-alpha', alpha - 0.1)
                root.after(20, fade_out)
            else:
                root.destroy()
        
        fade_in()
        
    except Exception as e:
        print(f"Error showing notification: {e}")

def run_notification_window():
    """Запускает главный цикл Tkinter для уведомлений"""
    root = tk.Tk()
    root.withdraw()  # Скрываем основное окно
    root.mainloop()

# Добавляем глобальную переменную для хранения активных устройств
enabled_devices = set()

def load_enabled_devices():
    """Загружает список активных устройств из файла"""
    global enabled_devices
    try:
        with open('enabled_devices.json', 'r') as f:
            enabled_devices = set(json.load(f))
    except FileNotFoundError:
        # Если файл не существует, все устройства активны по умолчанию
        enabled_devices = set(device[0] for device in devices)
        save_enabled_devices()

def save_enabled_devices():
    """Сохраняет список активных устройств в файл"""
    try:
        with open('enabled_devices.json', 'w') as f:
            json.dump(list(enabled_devices), f)
    except Exception as e:
        print(f"Error saving enabled devices: {e}")

@app.route("/set_device_enabled", methods=["POST"])
def set_device_enabled():
    """Включает/выключает устройство в списке активных"""
    try:
        data = request.json
        device_index = data.get("device_index")
        enabled = data.get("enabled", True)
        
        if enabled:
            enabled_devices.add(device_index)
        else:
            enabled_devices.discard(device_index)
        
        save_enabled_devices()
        
        return jsonify({
            "status": "success"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def switch_audio_device(direction):
    """Переключает устройство вывода звука"""
    global current_device_index, devices, enabled_devices
    try:
        print(f"\nSwitching device {direction}")
        print(f"Current device index: {current_device_index}")
        print(f"All devices: {devices}")
        print(f"Enabled devices: {enabled_devices}")
        
        if not devices:
            # Обновляем список устройств, если он пуст
            devices = get_audio_devices()
            if not devices:
                print("No devices available")
                return
        
        # Если enabled_devices пуст, добавляем все устройства
        if not enabled_devices:
            enabled_devices.update(device[0] for device in devices)
            save_enabled_devices()
            
        # Получаем список активных устройств
        active_devices = [device for device in devices if device[0] in enabled_devices]
        print(f"Active devices: {active_devices}")
        
        if not active_devices:
            print("No active devices")
            return
            
        # Если текущий индекс некорректный, устанавливаем его на первое активное устройство
        if current_device_index >= len(devices) or current_device_index < 0:
            current_device_index = 0
            
        # Находим текущее устройство в списке активных
        try:
            current_device = next((device for device in active_devices 
                                if device[0] == devices[current_device_index][0]), 
                                active_devices[0])
            print(f"Current device: {current_device}")
            
            # Находим индекс текущего устройства в списке активных
            current_active_index = active_devices.index(current_device)
            print(f"Current active index: {current_active_index}")
            
            # Определяем следующее устройство
            if direction == 'prev':
                next_active_index = (current_active_index - 1) % len(active_devices)
            else:
                next_active_index = (current_active_index + 1) % len(active_devices)
            print(f"Next active index: {next_active_index}")
            
            # Получаем следующее устройство
            next_device = active_devices[next_active_index]
            print(f"Next device: {next_device}")
            
            # Обновляем текущий индекс в общем списке устройств
            current_device_index = next(i for i, device in enumerate(devices) 
                                    if device[0] == next_device[0])
            print(f"New current device index: {current_device_index}")
            
            # Устанавливаем новое устройство
            print(f"Setting default audio device to: {next_device[0]}")
            set_default_audio_device(next_device[0])
            
            # Показываем уведомление
            Thread(target=show_notification, args=(f"Switched to: {next_device[1]}",)).start()
            
        except Exception as e:
            print(f"Error during device switching: {e}")
            # Если произошла ошибка, пробуем установить первое активное устройство
            if active_devices:
                current_device_index = next(i for i, device in enumerate(devices) 
                                        if device[0] == active_devices[0][0])
                set_default_audio_device(active_devices[0][0])
        
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
    """Сохраяет настройки в файл"""
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

# Добавлем глобальные переменные для устройств ввода
enabled_input_devices = set()

def load_enabled_input_devices():
    """Загружает список активных устройств ввода из файла"""
    global enabled_input_devices
    try:
        with open('enabled_input_devices.json', 'r') as f:
            enabled_input_devices = set(json.load(f))
    except FileNotFoundError:
        # Если файл не существует, все устройства активны по умолчанию
        enabled_input_devices = set(device[0] for device in input_devices)
        save_enabled_input_devices()

def save_enabled_input_devices():
    """Сохраняет список активных устройств ввода в файл"""
    try:
        with open('enabled_input_devices.json', 'w') as f:
            json.dump(list(enabled_input_devices), f)
    except Exception as e:
        print(f"Error saving enabled input devices: {e}")

@app.route("/get_input_devices")
def get_input_devices_route():
    """Возвращает список устройств ввода"""
    try:
        devices = get_input_devices()
        return jsonify({
            "status": "success",
            "devices": devices
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/set_input_device_enabled", methods=["POST"])
def set_input_device_enabled():
    """Включает/выключает устройство ввода в списке активных"""
    try:
        data = request.json
        device_index = data.get("device_index")
        enabled = data.get("enabled", True)
        
        if enabled:
            enabled_input_devices.add(device_index)
        else:
            enabled_input_devices.discard(device_index)
        
        save_enabled_input_devices()
        
        return jsonify({
            "status": "success"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def get_input_devices():
    """Получает список устройств ввода звука"""
    powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    
    ps_script = """
    if (-not (Get-Module -ListAvailable -Name AudioDeviceCmdlets)) {
        Write-Host "ERROR: AudioDeviceCmdlets not installed"
        exit 1
    }
    
    try {
        $OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
        $devices = Get-AudioDevice -List | Where-Object { $_.Type -eq 'Recording' }
        $devices | ForEach-Object {
            $index = $_.Index
            $name = $_.Name
            Write-Output "$index|$name"
        }
    } catch {
        Write-Host "Error getting input device list: $_"
    }
    """
    
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            [powershell_path, "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        
        devices = []
        for line in result.stdout.split('\n'):
            if '|' in line:
                try:
                    index, name = line.strip().split('|', 1)
                    devices.append([index.strip(), name.strip()])
                except ValueError as e:
                    print(f"Error parsing line '{line}': {e}")
                    continue
        
        print(f"Found input devices: {devices}")
        return devices
        
    except Exception as e:
        print(f"Error getting input devices: {e}")
        return []

def switch_input_device(direction):
    """Переключает устройство ввода звука"""
    global current_input_device_index, input_devices, enabled_input_devices
    try:
        print(f"\nSwitching input device {direction}")
        print(f"Current input device index: {current_input_device_index}")
        print(f"All input devices: {input_devices}")
        print(f"Enabled input devices: {enabled_input_devices}")
        
        if not input_devices:
            # Обновляем список устройств, если он пуст
            input_devices = get_input_devices()
            if not input_devices:
                print("No input devices available")
                return
            
        # Получаем список активных устройств
        active_devices = [device for device in input_devices if device[0] in enabled_input_devices]
        print(f"Active input devices: {active_devices}")
        
        if not active_devices:
            print("No active input devices")
            return
            
        # Находим текущее устройство в списке активных
        try:
            current_device = next((device for device in active_devices 
                                if device[0] == input_devices[current_input_device_index][0]), 
                                active_devices[0])
            print(f"Current input device: {current_device}")
            
            # Находим индекс текущего устройства в списке активных
            current_active_index = active_devices.index(current_device)
            print(f"Current active index: {current_active_index}")
            
            # Определяем следующее устройство
            if direction == 'prev':
                next_active_index = (current_active_index - 1) % len(active_devices)
            else:
                next_active_index = (current_active_index + 1) % len(active_devices)
            print(f"Next active index: {next_active_index}")
            
            # Получаем следующее устройство
            next_device = active_devices[next_active_index]
            print(f"Next input device: {next_device}")
            
            # Обновляем текущий индекс в общем списке устройств
            current_input_device_index = next(i for i, device in enumerate(input_devices) 
                                          if device[0] == next_device[0])
            print(f"New current input device index: {current_input_device_index}")
            
            # Устанавливаем новое устройство
            print(f"Setting default input device to: {next_device[0]}")
            set_default_input_device(next_device[0])
            
            # Показываем уведомление
            Thread(target=show_notification, args=(f"Input switched to: {next_device[1]}",)).start()
            
        except Exception as e:
            print(f"Error during input device switching: {e}")
        
    except Exception as e:
        print(f"Error switching input device: {e}")

def set_default_input_device(device_index):
    """Устанавливает устройство ввода по умолчанию"""
    ps_script = f"""
    try {{
        Set-AudioDevice -Index {device_index}
    }} catch {{
        Write-Host "Error setting default input device: $_"
    }}
    """
    
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        if result.stderr:
            print("PowerShell error:", result.stderr)
    except Exception as e:
        print(f"Error executing PowerShell: {e}")

def toggle_microphone_volume():
    """Переключает громкость микрофона между 0% и 100%"""
    try:
        pythoncom.CoInitialize()
        devices = AudioUtilities.GetMicrophone()
        
        if not devices:
            return

        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        if volume.GetMute():
            volume.SetMute(0, None)
            volume.SetMasterVolumeLevelScalar(1.0, None)
            Thread(target=show_notification, args=("Microphone: ON",)).start()
        else:
            volume.SetMute(1, None)
            volume.SetMasterVolumeLevelScalar(0.0, None)
            Thread(target=show_notification, args=("Microphone: OFF",)).start()
    except:
        pass
    finally:
        pythoncom.CoUninitialize()

@app.route("/get_output_devices")
def get_output_devices():
    """Возвращает список устройств вывода звука"""
    try:
        devices = get_audio_devices()
        return jsonify({
            "status": "success",
            "devices": devices
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

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

# Добавляем глобальные переменные, если они были удалены
devices = []
current_device_index = 0
running = False

# Добавляем глобальные переменные для устройств ввода
input_devices = []
current_input_device_index = 0

@app.route("/get_enabled_devices")
def get_enabled_devices():
    """Возвращает список активных устройств вывода"""
    try:
        return jsonify({
            "status": "success",
            "enabled_devices": list(enabled_devices)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/get_enabled_input_devices")
def get_enabled_input_devices():
    """Возвращает список активных устройств ввода"""
    try:
        return jsonify({
            "status": "success",
            "enabled_devices": list(enabled_input_devices)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def main():
    global running, devices, input_devices, current_device_index, current_input_device_index
    running = True
    
    # Выводим текущие настройки
    print("\nCurrent hotkey settings:")
    for action, combo in hotkeys.items():
        print(f"{action}: keyboard='{combo['keyboard']}', mouse='{combo['mouse']}'")
    print()
    
    # Получаем списки устройств
    devices = get_audio_devices()
    input_devices = get_input_devices()
    
    # Загружаем списки активных устройств
    load_enabled_devices()
    load_enabled_input_devices()
    
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

    # Запускаем поток для уведомлений
    notification_thread = Thread(target=create_notification_window, daemon=True)
    notification_thread.start()
    
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        tracker.stop()
        if hasattr(tray_icon, '_icon') and tray_icon._icon:
            tray_icon.stop()

if __name__ == "__main__":
    main()
