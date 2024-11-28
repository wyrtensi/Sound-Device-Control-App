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

# Константы Windows для отправки сообщений
WM_APPCOMMAND = 0x319
APPCOMMAND_VOLUME_UP = 0x0a
APPCOMMAND_VOLUME_DOWN = 0x09
APPCOMMAND_MEDIA_PLAY_PAUSE = 0x0E
APPCOMMAND_MEDIA_NEXTTRACK = 0x0B
APPCOMMAND_MEDIA_PREVIOUSTRACK = 0x0C

# Определения для Windows Hook
WH_MOUSE_LL = 14
WM_MOUSEWHEEL = 0x020A
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208

# Структура для хука мыши
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('pt', wintypes.POINT),
        ('mouseData', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_void_p)
    ]

# Константы DirectInput
DIMOFS_Z = 8
DIMOUSESTATE2 = wintypes.LONG * 8

# Flask приложение
app = Flask(__name__)

# Файл для хранения настроек
SETTINGS_FILE = "settings.json"

# Обновляем дефолтные настройки с правильной структурой
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
        "mouse": "Нет"
    },
    "next_device": {
        "keyboard": "win+pagedown",
        "mouse": "Нет"
    },
    "media_play_pause": {
        "keyboard": "ctrl+space",
        "mouse": "Нет"
    },
    "media_next": {
        "keyboard": "ctrl+right",
        "mouse": "Нет"
    },
    "media_previous": {
        "keyboard": "ctrl+left",
        "mouse": "Нет"
    }
}

def create_default_settings():
    """Создает файл настроек по умолчанию"""
    try:
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(default_hotkeys, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Ошибка при создании файла настроек: {e}")
        return False

def load_settings():
    """Загружает настройки из файла"""
    try:
        # Пробуем загрузить существующие настройки
        with open('settings.json', 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
        # Проверяем структуру и исправляем если нужно
        fixed_settings = {}
        for action, combo in settings.items():
            if isinstance(combo, dict) and "keyboard" in combo and "mouse" in combo:
                # Структура правильная, копируем как есть
                fixed_settings[action] = combo
            elif isinstance(combo, dict):
                # Структура неправильная, исправляем
                keyboard_keys = []
                mouse_keys = []
                
                # Собираем все клавиши
                all_keys = []
                for field, value in combo.items():
                    if value and value.lower() != "нет":
                        all_keys.extend(value.lower().split('+'))
                
                # Распределяем клавиши
                for key in all_keys:
                    if ('scroll' in key or 'mouse' in key or 
                        key in ['лкм', 'пкм', 'скм', 'scrollup', 'scrolldown']):
                        if 'up' in key:
                            mouse_keys.append('scrollup')
                        elif 'down' in key:
                            mouse_keys.append('scrolldown')
                        elif 'left' in key or key == 'лкм':
                            mouse_keys.append('mouseleft')
                        elif 'right' in key or key == 'пкм':
                            mouse_keys.append('mouseright')
                        elif 'middle' in key or key == 'скм':
                            mouse_keys.append('mousemiddle')
                    else:
                        keyboard_keys.append(key)
                
                fixed_settings[action] = {
                    "keyboard": '+'.join(keyboard_keys) if keyboard_keys else "Нет",
                    "mouse": '+'.join(mouse_keys) if mouse_keys else "Нет"
                }
            else:
                # Если полностью неправильная структура, берем значения по умолчанию
                fixed_settings[action] = default_hotkeys.get(action, {
                    "keyboard": "Нет",
                    "mouse": "Нет"
                })
        
        # Сохраняем исправленные настройки
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(fixed_settings, f, ensure_ascii=False, indent=4)
        
        return fixed_settings
    except FileNotFoundError:
        # Если файл не существует, создаем новый
        create_default_settings()
        return default_hotkeys
    except Exception as e:
        print(f"Ошибка при загрузке настроек: {e}")
        return default_hotkeys

hotkeys = load_settings()

# Получение списка аудиоустройств
def get_audio_devices():
    # Указываем полный путь к PowerShell
    powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    
    ps_script = """
    # Проверяем наличие модуля
    if (-not (Get-Module -ListAvailable -Name AudioDeviceCmdlets)) {
        Write-Host "ERROR: AudioDeviceCmdlets не установлен"
        exit 1
    }
    
    try {
        $devices = Get-AudioDevice -List
        $devices | ForEach-Object { "$($_.Index),$($_.Name)" }
    } catch {
        Write-Host "Ошибка при получении списка устройств"
    }
    """
    
    try:
        result = subprocess.run(
            [powershell_path, "-Command", ps_script],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if "ERROR: AudioDeviceCmdlets не установлен" in result.stdout:
            print("Необходимо установить модуль AudioDeviceCmdlets. Установка...")
            install_script = """
            Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser
            """
            subprocess.run(
                [powershell_path, "-Command", install_script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Повторяем попытку получить устройства после установки
            result = subprocess.run(
                [powershell_path, "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        
        devices = result.stdout.strip().split('\n')
        devices = [device.split(',') for device in devices if device.strip() and "microphone" not in device.lower()]
        return devices
        
    except FileNotFoundError:
        print("Ошибка: PowerShell не найден по пути", powershell_path)
        return []

# Установка устройства по умолчанию
def set_default_audio_device(device_index):
    ps_script = f"""
    try {{
        Set-AudioDevice -Index {device_index}
    }} catch {{
        Write-Host "Ошибка при установке устройства по умолчаию: $_"
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
            print(f"Ошибка PowerShell: {result.stderr}")
        if result.stdout:
            print(f"Вывод PowerShell: {result.stdout}")
    except Exception as e:
        print(f"Ошибка при выполнении PowerShell: {e}")

# Уведомления о смене устройства
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
    label = tk.Label(root, text=f"Переключено на: {device_name}", font=("Arial", 12, "bold"), fg="white", bg="#333333")
    label.pack(expand=True)
    root.after(1000, root.destroy)
    root.mainloop()

# Отправка сообщений для регулировки громкости
def send_volume_message(app_command):
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.SendMessageW(hwnd, WM_APPCOMMAND, 0, app_command * 0x10000)

def send_media_message(app_command):
    """Отправляет команду управления медиа"""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.SendMessageW(hwnd, WM_APPCOMMAND, 0, app_command * 0x10000)

# Обновление горячих клавиш для регулировки громкости
def update_volume_hotkeys():
    # Удалим старые горячие клавиши, если они зарегистрированы
    if hotkeys["volume_up"] in keyboard._hotkeys:
        keyboard.remove_hotkey(hotkeys["volume_up"])
    if hotkeys["volume_down"] in keyboard._hotkeys:
        keyboard.remove_hotkey(hotkeys["volume_down"])

    # Добавим новые горячие клавиши
    keyboard.add_hotkey(hotkeys["volume_up"], lambda: send_volume_message(APPCOMMAND_VOLUME_UP))
    keyboard.add_hotkey(hotkeys["volume_down"], lambda: send_volume_message(APPCOMMAND_VOLUME_DOWN))

# Обработчик событий мыши
def on_scroll(x, y, dx, dy):
    if dy > 0:  # Прокрутка вверх
        send_volume_message(APPCOMMAND_VOLUME_UP)
    elif dy < 0:  # Прокрутка вниз
        send_volume_message(APPCOMMAND_VOLUME_DOWN)

# Добавьте эту глобальную переменную в начало файла после импортов
current_device_index = 0

keyboard_controller = KeyboardController()
mouse_controller = MouseController()

# Глобальные переменные для отслеживания состояния клавиш
pressed_keyboard_keys = set()
pressed_mouse_buttons = set()
scroll_direction = None
key_lock = Lock()

def normalize_key_name(key_str):
    """Нормализует названия клавиш"""
    key_mapping = {
        # Специальные клавиши
        'arrowup': 'up',
        'arrowdown': 'down',
        'arrowleft': 'left',
        'arrowright': 'right',
        'page_up': 'pageup',
        'page_down': 'pagedown',
        'нет': '',
        'space': 'space',
        # Стрелки
        'up': 'up',
        'down': 'down',
        'left': 'left',
        'right': 'right',
        # Модификаторы
        'ctrl_l': 'ctrl',
        'ctrl_r': 'ctrl',
        'alt_l': 'alt',
        'alt_r': 'alt',
        'shift_l': 'shift',
        'shift_r': 'shift',
        'cmd': 'win',
        'cmd_r': 'win',
        # Мышь
        'mouseleft': 'mouseleft',
        'mouseright': 'mouseright',
        'mousemiddle': 'mousemiddle',
        'scrollup': 'scrollup',
        'scrolldown': 'scrolldown',
        'лкм': 'mouseleft',
        'пкм': 'mouseright',
        'скм': 'mousemiddle',
        # Кириллица -> латиница
        'ф': 'a', 'и': 'b', 'с': 'c', 'в': 'd', 'у': 'e',
        'а': 'f', 'п': 'g', 'р': 'h', 'ш': 'i', 'о': 'j',
        'л': 'k', 'д': 'l', 'ь': 'm', 'т': 'n', 'щ': 'o',
        'з': 'p', 'й': 'q', 'к': 'r', 'ы': 's', 'е': 't',
        'г': 'u', 'м': 'v', 'ц': 'w', 'ч': 'x', 'н': 'y',
        'я': 'z'
    }
    
    # Удаляем префикс 'key.' если он есть
    if key_str.lower().startswith('key.'):
        key_str = key_str[4:]
    
    # Проверяем наличие ключа в маппинге
    normalized = key_mapping.get(key_str.lower(), key_str.lower())
    
    return normalized

def on_key_press(key):
    with key_lock:
        try:
            # Получаем строковое представление клавиши
            if isinstance(key, KeyCode) and key.char is not None:
                key_str = normalize_key_name(key.char.lower())
            else:
                key_str = str(key).lower().replace('key.', '')
                special_keys = {
                    'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'cmd': 'win', 'cmd_r': 'win',
                    'page_up': 'pageup', 'page_down': 'pagedown'
                }
                key_str = special_keys.get(key_str, key_str)
            
            pressed_keyboard_keys.add(key_str)
            print(f"Pressed keys: {pressed_keyboard_keys}")
            
        except Exception as e:
            print(f"Error in on_key_press: {e}")

def on_key_release(key):
    with key_lock:
        try:
            if isinstance(key, KeyCode) and key.char is not None:
                key_str = normalize_key_name(key.char.lower())
            else:
                key_str = str(key).lower().replace('key.', '')
                special_keys = {
                    'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'cmd': 'win', 'cmd_r': 'win',
                    'page_up': 'pageup', 'page_down': 'pagedown'
                }
                key_str = special_keys.get(key_str, key_str)
            
            pressed_keyboard_keys.discard(key_str)
            
        except Exception as e:
            print(f"Error in on_key_release: {e}")

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
        
        # Инициализация слушателя клавиатуры
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        
        # Устанавливаем обработчик событий мыши
        mouse.hook(self._on_mouse_event)
        print("KeyboardMouseTracker initialized")
        
        self.state_cache = None
        self.last_state_update = 0
        self.state_cache_lifetime = 0.008  # 8мс кэширование состояния
    
    def _on_mouse_event(self, event):
        """Обработчик событий мыши"""
        try:
            # Прорем наличие атрибута delta (кк в работающем коде)
            if hasattr(event, 'delta'):
                with self.lock:
                    if event.delta > 0:
                        self.scroll_direction = 'scrollup'
                        Thread(target=self._reset_scroll, daemon=True).start()
                    elif event.delta < 0:
                        self.scroll_direction = 'scrolldown'
                        Thread(target=self._reset_scroll, daemon=True).start()
                return
            
            # Игнорируем события движения мыши
            if getattr(event, 'event_type', None) == 'move':
                return

        except Exception as e:
            print(f"Error in mouse event handler: {e}")

    def _on_key_press(self, key):
        """Обработчик нажатия клавиш"""
        try:
            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                key_str = key.char.lower()
            else:
                key_str = str(key).lower().replace('key.', '')
            
            # Нормализуем название клавиши
            key_str = normalize_key_name(key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.add(key_str)
                
        except Exception as e:
            print(f"Error in key press handler: {e}")

    def _on_key_release(self, key):
        """Обработчик отпускания клавиш"""
        try:
            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                key_str = key.char.lower()
            else:
                key_str = str(key).lower().replace('key.', '')
            
            # Нормализуем название клавиши
            key_str = normalize_key_name(key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.discard(key_str)
                
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _track_mouse_buttons(self):
        """Отслеживает состояние кнопок мыши"""
        while not self.stop_event.is_set():
            try:
                time.sleep(0.008)  # Уменьшаем частоту опроса состояния мыши
                
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
                    
                    # Сбрасываем кэш только если состояние изменилось
                    if changed:
                        self.state_cache = None

            except Exception as e:
                print(f"Error tracking mouse buttons: {e}")
                time.sleep(0.1)

    def _reset_scroll(self):
        """Сбрасывает направление скролла"""
        time.sleep(0.2)
        with self.lock:
            self.scroll_direction = None

    def start(self):
        """Запускает отслеживание"""
        self.keyboard_listener.start()
        self.mouse_thread = Thread(target=self._track_mouse_buttons, daemon=True)
        self.mouse_thread.start()
        print("Tracking started")

    def stop(self):
        """Останавливает отслеживание"""
        self.stop_event.set()
        self.keyboard_listener.stop()
        mouse.unhook_all()
        if hasattr(self, 'mouse_thread'):
            self.mouse_thread.join(timeout=1.0)

    def get_state(self):
        """Возвращает текущее остояние с кэшированием"""
        current_time = time.time()
        
        # Используем кэшированное состояние, если оно достаточно свежее
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

def handle_hotkeys(tracker):
    """Обработчик горячих клавиш"""
    last_action_time = {}  # Словарь для отслеживания времени последнего действия
    
    while True:
        try:
            # Добавляем небольшую задержку для снижения нагрузки на CPU
            time.sleep(0.008)  # 8мс задержка - компромисс между отзывчивостью и нагрузкой
            
            state = tracker.get_state()
            current_time = time.time()
            
            for action, combo in hotkeys.items():
                # Проверяем, прошло ли достаточно времени с последнего действия
                if current_time - last_action_time.get(action, 0) < 0.1:  # Минимум 100мс между действиями
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
    """Проверяет комбинацию клавиш"""
    try:
        # Проверяем клавиши клавиатуры
        keyboard_keys = set(k.strip().lower() for k in hotkey['keyboard'].split('+') 
                          if k.strip() and k.strip().lower() != 'нет')
        keyboard_match = all(key in state['keyboard'] for key in keyboard_keys)

        # Проверяем клавиши мыши
        mouse_keys = set(m.strip().lower() for m in hotkey['mouse'].split('+') 
                        if m.strip() and m.strip().lower() != 'нет')
        mouse_match = True
        if mouse_keys:
            for mouse_key in mouse_keys:
                if mouse_key in ['scrollup', 'scrolldown']:
                    mouse_match = mouse_match and state['mouse']['scroll'] == mouse_key
                else:
                    mouse_match = mouse_match and mouse_key in state['mouse']['buttons']

        return keyboard_match and (not mouse_keys or mouse_match)

    except Exception as e:
        print(f"Error checking hotkey combination: {e}")
        return False

def save_settings(settings):
    """Сохраняет настройки в файл"""
    try:
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Ошибка при сохранении настроек: {e}")
        return False

# Маршруты Flask
@app.route("/")
def index():
    return render_template("index.html", hotkeys=hotkeys)

@app.route("/update_hotkey", methods=["POST"])
def update_hotkey():
    try:
        data = request.json
        print("Received data:", data)  # Отладка
        
        action = data["action"]
        keyboard_keys = data.get("keyboard", "Нет")
        mouse_keys = data.get("mouse", "Нет")
        
        print(f"Action: {action}")  # Отладка
        print(f"Keyboard keys: {keyboard_keys}")  # Отладка
        print(f"Mouse keys: {mouse_keys}")  # Отладка

        # Загружаем текущие настройки
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                current_hotkeys = json.load(f)
        except FileNotFoundError:
            current_hotkeys = default_hotkeys

        # Обновляем настройки
        current_hotkeys[action] = {
            "keyboard": keyboard_keys,
            "mouse": mouse_keys
        }

        print(f"Updated hotkeys: {current_hotkeys[action]}")  # Отладка

        # Сохраняем настройки
        if save_settings(current_hotkeys):
            # Обновляем глобальные настройки
            global hotkeys
            hotkeys = current_hotkeys
            return jsonify({"status": "success", "hotkeys": current_hotkeys})
        else:
            return jsonify({"status": "error", "message": "Ошибка при сохранении настроек"})

    except Exception as e:
        print(f"Error in update_hotkey: {e}")
        import traceback
        print(traceback.format_exc())  # Полный стек ошибки
        return jsonify({"status": "error", "message": str(e)})

@app.route("/save_settings", methods=["POST"])
def save_settings_endpoint():
    try:
        data = request.json
        # Проверяем формат данных
        for action, combo in data.items():
            if not isinstance(combo, dict) or "keyboard" not in combo or "mouse" not in combo:
                return jsonify({
                    "status": "error",
                    "message": f"Неверный формат данных для действия {action}"
                })

        # Сохраняем настройки
        if save_settings(data):
            # Обновляем глобальные настройки
            global hotkeys
            hotkeys = data
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Ошибка при сохранении настроек"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

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
        
        # Показываем уведомление о переключении
        device_name = devices[current_device_index][1]
        Thread(target=show_notification, args=(f"Переключено на: {device_name}",)).start()
        
    except Exception as e:
        print(f"Ошибка при переключении устройства: {e}")

def create_icon():
    """Создает розово-черно-бирюзовую иконку"""
    width = 128
    height = 128
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Розовый круг (Deep Pink)
    draw.ellipse([10, 10, width-40, height-40], fill=(255, 20, 147, 255))
    # Черный круг
    draw.ellipse([30, 30, width-20, height-20], fill=(0, 0, 0, 255))
    # Бирюзовый круг (Turquoise)
    draw.ellipse([50, 50, width, height], fill=(64, 224, 208, 255))
    
    image = image.resize((32, 32), Image.Resampling.LANCZOS)
    return image

def open_settings(icon, item):
    """Открывает настройки в браузере"""
    webbrowser.open('http://127.0.0.1:5000')

def exit_app(icon, item):
    """Закрывает приложение"""
    icon.stop()
    global running
    running = False

def setup_tray():
    """Настраивает иконку в трее"""
    icon = pystray.Icon(
        "Audio Device Switcher",
        icon=create_icon(),
        menu=pystray.Menu(
            pystray.MenuItem("Настройи", open_settings, default=True),
            pystray.MenuItem("Выход", exit_app)
        )
    )
    return icon

def run_flask():
    """Запускает Flask сервер"""
    app.run(host='127.0.0.1', port=5000, debug=False)

def main():
    global running, devices, current_device_index
    running = True
    
    # Получаем список устройств
    devices = get_audio_devices()
    if not devices:
        print("No audio devices found!")
    else:
        print(f"Found {len(devices)} audio devices")
    
    # Запускаем Flask сервер в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask server started")
    
    # Создаем и запускаем трекер
    tracker = KeyboardMouseTracker()
    tracker.start()
    print("Mouse and keyboard tracking started")

    # Запускаем обработчик горячих клавиш
    hotkey_thread = Thread(target=lambda: handle_hotkeys(tracker), daemon=True)
    hotkey_thread.start()
    print("Hotkey handler started")

    # Создаем и запускаем иконку в трее
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

# Инициализация глобальных переменных в начале файла
pressed_keyboard_keys = set()
pressed_mouse_buttons = set()
scroll_direction = None
key_lock = Lock()
current_device_index = 0
mouse_listener = None

# Загрузка сохраненных настроек при запуске
try:
    with open('settings.json', 'r', encoding='utf-8') as f:
        hotkeys = json.load(f)
    print(f"Loaded hotkeys: {hotkeys}")
except FileNotFoundError:
    hotkeys = default_hotkeys
    print(f"Using default hotkeys: {hotkeys}")

# Глобальные переменные
devices = []
current_device_index = 0
running = False

if __name__ == "__main__":
    main()
