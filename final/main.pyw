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

# Горячие клавиши по умолчанию
default_hotkeys = {
    "volume_up": "ctrl+up",
    "volume_down": "ctrl+down",
    "prev_device": "win+page up",
    "next_device": "win+page down"
}

# Загрузка настроек
def load_settings():
    try:
        with open('settings.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default_hotkeys
    except Exception as e:
        print(f"Ошибка при загрузке настроек: {e}")
        return default_hotkeys

# Сохранение настроек
def save_settings(hotkeys):
    try:
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(hotkeys, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Ошибка при сохранении настроек: {e}")
        return False

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
        Write-Host "Ошибка при установке устройства по умолчанию: $_"
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
        # Кириллица -> латиница
        'ф': 'a', 'и': 'b', 'с': 'c', 'в': 'd', 'у': 'e',
        'а': 'f', 'п': 'g', 'р': 'h', 'ш': 'i', 'о': 'j',
        'л': 'k', 'д': 'l', 'ь': 'm', 'т': 'n', 'щ': 'o',
        'з': 'p', 'й': 'q', 'к': 'r', 'ы': 's', 'е': 't',
        'г': 'u', 'м': 'v', 'ц': 'w', 'ч': 'x', 'н': 'y',
        'я': 'z'
    }
    return key_mapping.get(key_str.lower(), key_str.lower())

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

    def _on_mouse_event(self, event):
        """Обработчик событий мыши"""
        try:
            # Проверяем наличие атрибута delta (как в работающем коде)
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
                # Расширенный словарь специальных клавиш
                special_keys = {
                    'ctrl_l': 'ctrl', 
                    'ctrl_r': 'ctrl',
                    'alt_l': 'alt', 
                    'alt_r': 'alt',
                    'shift_l': 'shift', 
                    'shift_r': 'shift',
                    'cmd': 'win',  # Windows key (левый)
                    'cmd_r': 'win',  # Windows key (правый)
                    'page_up': 'pageup',
                    'page_down': 'pagedown'
                }
                key_str = special_keys.get(key_str, key_str)
            
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
                # Тот же словарь специальных клавиш
                special_keys = {
                    'ctrl_l': 'ctrl', 
                    'ctrl_r': 'ctrl',
                    'alt_l': 'alt', 
                    'alt_r': 'alt',
                    'shift_l': 'shift', 
                    'shift_r': 'shift',
                    'cmd': 'win',  # Windows key (левый)
                    'cmd_r': 'win',  # Windows key (правый)
                    'page_up': 'pageup',
                    'page_down': 'pagedown'
                }
                key_str = special_keys.get(key_str, key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.discard(key_str)
                
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _track_mouse_buttons(self):
        """Отслеживает состояние кнопок мыши"""
        while not self.stop_event.is_set():
            try:
                left = win32api.GetKeyState(win32con.VK_LBUTTON) < 0
                right = win32api.GetKeyState(win32con.VK_RBUTTON) < 0
                middle = win32api.GetKeyState(win32con.VK_MBUTTON) < 0

                with self.lock:
                    if left != self._left_pressed:
                        if left:
                            self.pressed_buttons.add('mouseleft')
                        else:
                            self.pressed_buttons.discard('mouseleft')
                        self._left_pressed = left

                    if right != self._right_pressed:
                        if right:
                            self.pressed_buttons.add('mouseright')
                        else:
                            self.pressed_buttons.discard('mouseright')
                        self._right_pressed = right

                    if middle != self._middle_pressed:
                        if middle:
                            self.pressed_buttons.add('mousemiddle')
                        else:
                            self.pressed_buttons.discard('mousemiddle')
                        self._middle_pressed = middle

                time.sleep(0.001)
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
        """Возвращает текущее состояние"""
        with self.lock:
            return {
                'keyboard': self.pressed_keyboard_keys.copy(),
                'mouse': {
                    'buttons': self.pressed_buttons.copy(),
                    'scroll': self.scroll_direction
                }
            }

def handle_hotkeys(tracker):
    """Обработчик горячих клавиш"""
    while True:
        try:
            state = tracker.get_state()
            print(f"\rCurrent state: {state}", end='')  # Отладочный вывод
            
            for action, combo in hotkeys.items():
                if check_hotkey_combination(combo, state):
                    print(f"\nExecuting action: {action}")  # Отладочный вывод
                    
                    # Выполняем действие
                    if action == 'volume_up':
                        send_volume_message(APPCOMMAND_VOLUME_UP)
                    elif action == 'volume_down':
                        send_volume_message(APPCOMMAND_VOLUME_DOWN)
                    elif action == 'prev_device':
                        switch_audio_device('prev')
                    elif action == 'next_device':
                        switch_audio_device('next')
                    
                    time.sleep(0.2)
            
            time.sleep(0.01)
            
        except Exception as e:
            print(f"Error in handle_hotkeys: {e}")
            time.sleep(0.1)

def check_hotkey_combination(hotkey, state):
    """Проверяет комбинацию клавиш"""
    try:
        required_keyboard = set(k.strip().lower() for k in hotkey['keyboard'].split('+') if k.strip() and k.strip().lower() != 'нет')
        required_mouse = set(m.strip().lower() for m in hotkey['mouse'].split('+') if m.strip() and m.strip().lower() != 'нет')

        keyboard_match = all(key in state['keyboard'] for key in required_keyboard)
        
        mouse_match = True
        if required_mouse:
            for mouse_key in required_mouse:
                if mouse_key in ['scrollup', 'scrolldown']:
                    mouse_match = mouse_match and state['mouse']['scroll'] == mouse_key
                else:
                    mouse_match = mouse_match and mouse_key in state['mouse']['buttons']

        return keyboard_match and (not required_mouse or mouse_match)

    except Exception as e:
        print(f"Error checking hotkey combination: {e}")
        return False

# Маршруты Flask
@app.route("/")
def index():
    return render_template("index.html", hotkeys=hotkeys)

@app.route("/update_hotkey", methods=["POST"])
def update_hotkey():
    try:
        data = request.json
        action = data["action"]
        keyboard_keys = data["keyboard"]
        mouse_keys = data["mouse"]
        
        # Нормализуем клавиши перед сохранением
        keyboard_keys = '+'.join(normalize_key_name(k) for k in keyboard_keys.split('+') if k.strip())
        mouse_keys = '+'.join(normalize_key_name(m) for m in mouse_keys.split('+') if m.strip())
        
        hotkeys[action] = {
            "keyboard": keyboard_keys or "Нет",
            "mouse": mouse_keys or "Нет"
        }
        
        save_settings(hotkeys)
        return jsonify({"status": "success", "hotkeys": hotkeys})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/save_settings", methods=["POST"])
def save_settings_endpoint():
    try:
        global hotkeys
        hotkeys = request.json
        save_settings(hotkeys)
        return jsonify({"status": "success"})
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
            pystray.MenuItem("Настройки", open_settings, default=True),
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
