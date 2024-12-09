from flask import Flask, render_template, request, jsonify, send_from_directory
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
import webbrowser
import math
import winreg
import os
import sys
from datetime import datetime, timedelta
from PIL import Image, ImageDraw
import pystray
import tempfile
import win32ui
import threading
import psutil
import tkinter as tk
from tkinter import filedialog
from urllib.parse import unquote

# Глобальные переменные
devices = []
input_devices = []
enabled_devices = set()
enabled_input_devices = set()
device_update_callbacks = []
running = False
current_device_index = 0
current_input_device_index = 0

# Добавляем в начало файла после импортов
device_lock = Lock()
input_device_lock = Lock()

# Инициализируем Flask приложение
app = Flask(__name__)
app.json.ensure_ascii = False

def check_powershell_module():
    """Проверяет наличие модуля AudioDeviceCmdlets"""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        ps_script = """
        if (Get-Module -ListAvailable -Name AudioDeviceCmdlets) {
            Write-Output "MODULE_INSTALLED"
        } else {
            Write-Output "MODULE_NOT_INSTALLED"
        }
        """
        
        result = subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        
        return "MODULE_INSTALLED" in result.stdout
    except Exception as e:
        print(f"Error checking PowerShell module: {e}")
        return False

def install_powershell_module():
    """Устанавливает модуль AudioDeviceCmdlets"""
    try:
        show_notification("Initializing AudioDeviceCmdlets module installation...", "speaker")
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        ps_script = """
        try {
            Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser
            if (Get-Module -ListAvailable -Name AudioDeviceCmdlets) {
                Write-Output "INSTALLATION_SUCCESS"
            } else {
                Write-Output "INSTALLATION_FAILED"
            }
        } catch {
            Write-Output "INSTALLATION_FAILED"
            Write-Output $_.Exception.Message
        }
        """
        
        result = subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        
        if "INSTALLATION_SUCCESS" in result.stdout:
            show_notification("AudioDeviceCmdlets module installed successfully!", "speaker")
            return True
        else:
            show_notification("Failed to install AudioDeviceCmdlets module", "speaker")
            return False
    except Exception as e:
        print(f"Error installing PowerShell module: {e}")
        show_notification("Error installing AudioDeviceCmdlets module", "speaker")
        return False

# Проверяем и устанавливаем модуль при запуске
if not check_powershell_module():
    install_powershell_module()

# Windows constants
WM_APPCOMMAND = 0x319
APPCOMMAND_VOLUME_UP = 0x0a
APPCOMMAND_VOLUME_DOWN = 0x09
APPCOMMAND_MEDIA_PLAY_PAUSE = 0x0E
APPCOMMAND_MEDIA_NEXTTRACK = 0x0B
APPCOMMAND_MEDIA_PREVIOUSTRACK = 0x0C

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
    "toggle_sound_volume": {
        "keyboard": "ctrl+alt+m",
        "mouse": "None"
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

# Добавляем константы для позиций уведомленй
NOTIFICATION_POSITIONS = {
    "top_right": "Top Right",
    "top_left": "Top Left", 
    "bottom_left": "Bottom Left",
    "bottom_right": "Bottom Right",
    "center": "Center"
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
            on_release=self._on_key_release,
            suppress=False  # Не блокируем клавиши
        )
        
        mouse.hook(self._on_mouse_event)
        
        self.state_cache = None
        self.last_state_update = 0
        self.state_cache_lifetime = 0.032  # Снижаем до ~30Hz для экономии CPU
    
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
            key_str = None
            
            # Обработка обчных клавиш
            if isinstance(key, keyboard.KeyCode):
                # Маппинг виртуальных кодов на английские буквы
                vk_to_eng = {
                    65: 'a', 66: 'b', 67: 'c', 68: 'd', 69: 'e',
                    70: 'f', 71: 'g', 72: 'h', 73: 'i', 74: 'j',
                    75: 'k', 76: 'l', 77: 'm', 78: 'n', 79: 'o',
                    80: 'p', 81: 'q', 82: 'r', 83: 's', 84: 't',
                    85: 'u', 86: 'v', 87: 'w', 88: 'x', 89: 'y', 90: 'z'
                }
                
                if hasattr(key, 'vk') and key.vk in vk_to_eng:
                    key_str = vk_to_eng[key.vk]
                elif hasattr(key, 'vk') and key.vk:
                    # Маппинг для специальных клавиш
                    key_str = {
                        191: '/', 220: '\\', 188: ',', 190: '.',
                        186: ';', 222: "'", 219: '[', 221: ']',
                        189: '-', 187: '=', 192: '`',
                        48: '0', 49: '1', 50: '2', 51: '3', 52: '4',
                        53: '5', 54: '6', 55: '7', 56: '8', 57: '9'
                    }.get(key.vk)
            
            # Обработка специальных клавиш
            if isinstance(key, keyboard.Key):
                key_str = str(key).replace('Key.', '').lower()
                # Нормализация имен клавиш
                key_str = {
                    'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'cmd': 'win', 'cmd_l': 'win', 'cmd_r': 'win',
                    'return': 'enter',
                    'space': 'space'
                }.get(key_str, key_str)
            
            # Если ключ не определен, используем строковое представление
            if not key_str:
                key_str = str(key).lower().replace('key.', '')
            
            key_str = normalize_key_name(key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.add(key_str)
                
        except Exception as e:
            print(f"Error in key press handler: {e}")

    def _on_key_release(self, key):
        try:
            key_str = None
            
            # Обработк обычных клавиш
            if isinstance(key, keyboard.KeyCode):
                # Маппинг виртуальных кодов на английские буквы
                vk_to_eng = {
                    65: 'a', 66: 'b', 67: 'c', 68: 'd', 69: 'e',
                    70: 'f', 71: 'g', 72: 'h', 73: 'i', 74: 'j',
                    75: 'k', 76: 'l', 77: 'm', 78: 'n', 79: 'o',
                    80: 'p', 81: 'q', 82: 'r', 83: 's', 84: 't',
                    85: 'u', 86: 'v', 87: 'w', 88: 'x', 89: 'y', 90: 'z'
                }
                
                if hasattr(key, 'vk') and key.vk in vk_to_eng:
                    key_str = vk_to_eng[key.vk]
                elif hasattr(key, 'vk') and key.vk:
                    # Маппинг для специальных клавиш
                    key_str = {
                        191: '/', 220: '\\', 188: ',', 190: '.',
                        186: ';', 222: "'", 219: '[', 221: ']',
                        189: '-', 187: '=', 192: '`',
                        48: '0', 49: '1', 50: '2', 51: '3', 52: '4',
                        53: '5', 54: '6', 55: '7', 56: '8', 57: '9'
                    }.get(key.vk)
            
            # Обработка специальных клавиш
            if isinstance(key, keyboard.Key):
                key_str = str(key).replace('Key.', '').lower()
                # Нормализация имен клавиш
                key_str = {
                    'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
                    'alt_l': 'alt', 'alt_r': 'alt',
                    'shift_l': 'shift', 'shift_r': 'shift',
                    'cmd': 'win', 'cmd_l': 'win', 'cmd_r': 'win',
                    'return': 'enter',
                    'space': 'space'
                }.get(key_str, key_str)
            
            # Если ключ не определен, используем строковое п��едставление
            if not key_str:
                key_str = str(key).lower().replace('key.', '')
            
            key_str = normalize_key_name(key_str)
            
            with self.lock:
                self.pressed_keyboard_keys.discard(key_str)
                
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _track_mouse_buttons(self):
        last_check_time = 0
        check_interval = 0.032  # Снижаем до ~30Hz
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                if current_time - last_check_time < check_interval:
                    time.sleep(0.001)  # Короткая пауза
                    continue
                    
                last_check_time = current_time
                
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
    """Нормализует ��азвани�� клавиш"""
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
    """Обработчик горячих клавиш"""
    global profile_manager
    last_action_time = {}
    last_check_time = 0
    check_interval = 0.032  # Снижаем до ~30Hz
    
    while True:
        try:
            current_time = time.time()
            
            # Проверяем, прошло ли достаточно времени с последней проверки
            if current_time - last_check_time < check_interval:
                time.sleep(0.002)  # Увеличиваем паузу
                continue
                
            last_check_time = current_time
            state = tracker.get_state()
            
            # Проверяем горячие клавиши профилей
            for profile in profile_manager.profiles:
                if not profile.get('hotkey') or not profile['hotkey'].get('keyboard'):
                    continue
                    
                profile_combo = {
                    'keyboard': profile['hotkey'].get('keyboard', 'None'),
                    'mouse': profile['hotkey'].get('mouse', 'None')
                }
                
                if current_time - last_action_time.get(f'profile_{profile["name"]}', 0) < 0.2:  # Задержка для профилей
                    continue
                    
                if check_hotkey_combination(profile_combo, state):
                    activate_profile(profile['name'])
                    last_action_time[f'profile_{profile["name"]}'] = current_time
                    continue
            
            # Проверяем осталь��ые горячие клавиши
            for action, combo in hotkeys.items():
                # Определяем задержку в зависимости от действия
                delay = 0.09 if action in ['volume_up', 'volume_down'] else 0.2
                
                if current_time - last_action_time.get(action, 0) < delay:
                    continue
                
                if combo['keyboard'].lower() == 'none' and combo['mouse'].lower() == 'none':
                    continue
                    
                if check_hotkey_combination(combo, state):
                    if action == 'volume_up':
                        send_volume_message(APPCOMMAND_VOLUME_UP)
                    elif action == 'volume_down':
                        send_volume_message(APPCOMMAND_VOLUME_DOWN)
                    elif action == 'toggle_sound_volume':
                        toggle_sound_volume()
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

        except Exception as e:
            print(f"Error in handle_hotkeys: {e}")
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
    devices = []
    
    try:
        pythoncom.CoInitialize()
        try:
            # 1. Основной метод через PowerShell
            try:
                powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
                
                ps_script = """
                try {
                    if (-not (Get-Module -ListAvailable -Name AudioDeviceCmdlets)) {
                        Write-Host "ERROR: AudioDeviceCmdlets not installed"
                        exit 1
                    }
                    
                    $OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
                    $devices = Get-AudioDevice -List | Where-Object { $_.Type -eq 'Playback' }
                    $devices | ForEach-Object {
                        Write-Output ("DEVICE:{0}|{1}" -f $_.Index, $_.Name)
                    }
                } catch {
                    Write-Host "Error getting output device list: $_"
                }
                """
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                result = subprocess.run(
                    [powershell_path, "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    startupinfo=startupinfo
                )
                
                for line in result.stdout.split('\n'):
                    if line.strip().startswith('DEVICE:'):
                        try:
                            _, device_info = line.strip().split('DEVICE:', 1)
                            index, name = device_info.split('|', 1)
                            devices.append([index.strip(), name.strip()])
                        except ValueError:
                            continue
                            
                if devices:
                    return devices
            except Exception as e:
                pass

            # 2. Резервный метод через pycaw
            if not devices:
                try:
                    deviceEnumerator = AudioUtilities.GetAllDevices()
                    index = 0
                    for device in deviceEnumerator:
                        if device.state == 1 and device.flow == 0:  # DEVICE_STATE_ACTIVE = 1, eRender = 0
                            devices.append([str(index), device.FriendlyName])
                            index += 1
                            
                    if devices:
                        return devices
                except Exception as e:
                    pass

            # 3. Резервный метод через MMDevice API в PowerShell
            if not devices:
                try:
                    ps_script = """
                    try {
                        Add-Type -TypeDefinition @"
                        using System.Runtime.InteropServices;
                        [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                        interface IMMDevice {
                            int Activate([MarshalAs(UnmanagedType.LPStruct)] Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
                        }
                        [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                        interface IMMDeviceEnumerator {
                            int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IMMDeviceCollection ppDevices);
                        }
                        [Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                        interface IMMDeviceCollection {
                            int GetCount(out int pcDevices);
                            int Item(int nDevice, out IMMDevice ppDevice);
                        }
"@
                        
                        $deviceEnumerator = New-Object -ComObject "MMDeviceEnumerator.MMDeviceEnumerator"
                        $devices = @()
                        $deviceCollection = $deviceEnumerator.EnumAudioEndpoints(0, 1)  # eRender = 0, DEVICE_STATE_ACTIVE = 1
                        
                        for ($i = 0; $i -lt $deviceCollection.Count; $i++) {
                            $device = $deviceCollection.Item($i)
                            $properties = $device.Properties
                            $name = $properties.GetValue("{a45c254e-df1c-4efd-8020-67d146a850e0},2").ToString()
                            Write-Output ("DEVICE:{0}|{1}" -f $i, $name)
                        }
                    } catch {
                        Write-Host "Error in MMDevice API: $_"
                        exit 1
                    }
                    """
                    
                    result = subprocess.run(
                        [powershell_path, "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        startupinfo=startupinfo
                    )
                    
                    for line in result.stdout.split('\n'):
                        if line.strip().startswith('DEVICE:'):
                            try:
                                _, device_info = line.strip().split('DEVICE:', 1)
                                index, name = device_info.split('|', 1)
                                devices.append([index.strip(), name.strip()])
                            except ValueError:
                                continue
                                
                    if devices:
                        return devices
                except Exception as e:
                    pass
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        pass

    # Если все методы не сработали, возвращаем хотя бы одно виртуальное устройство
    return [["0", "Default Audio Device"]]

def set_default_audio_device(device_index):
    """Устанавливает устройство вывода по умолчанию"""
    try:
        print(f"\nSetting default audio device with index: {device_index}")
        if not device_index:
            print("Error: device_index is empty")
            return
            
        if not isinstance(device_index, (str, int)):
            print(f"Error: invalid device_index type: {type(device_index)}")
            return
            
        pythoncom.CoInitialize()
        try:
            ps_script = f"""
            try {{
                Write-Host "Looking for device with index {device_index}"
                $devices = Get-AudioDevice -List
                Write-Host "Available devices:"
                $devices | ForEach-Object {{ Write-Host "Index: $($_.Index), Name: $($_.Name), ID: $($_.ID)" }}
                $device = $devices | Where-Object {{ $_.Index -eq {device_index} }}
                if ($device) {{
                    Write-Host "Found device: $($device.Name) (ID: $($device.ID))"
                    Write-Host "Setting as default device..."
                    Set-AudioDevice -ID $device.ID
                    Write-Host "Device set successfully"
                }} else {{
                    Write-Host "Device with index {device_index} not found"
                }}
            }} catch {{
                Write-Host "Error setting default device: $_"
                Write-Host $_.Exception.Message
                Write-Host $_.ScriptStackTrace
            }}
            """
            
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
            print(f"PowerShell output: {result.stdout}")
            if result.stderr:
                print(f"PowerShell error: {result.stderr}")
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error executing PowerShell: {e}")
        import traceback
        print(traceback.format_exc())

def set_default_communication_device(device_index):
    """Устанавливает устройство вывода для связи по умолчанию"""
    try:
        pythoncom.CoInitialize()
        try:
            ps_script = f"""
            try {{
                $device = Get-AudioDevice -List | Where-Object {{ $_.Index -eq {device_index} }}
                if ($device) {{
                    Write-Host "Setting communication device: $($device.Name)"
                    Set-AudioDevice -ID $device.ID -Communication
                }} else {{
                    Write-Host "Device with index {device_index} not found"
                }}
            }} catch {{
                Write-Host "Error setting communication device: $_"
            }}
            """
            
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
            print(f"PowerShell output: {result.stdout}")
            if result.stderr:
                print(f"PowerShell error: {result.stderr}")
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error executing PowerShell: {e}")

def set_default_input_device(device_index):
    """Устанавливает устройство ввода по умолчанию"""
    try:
        print(f"\nSetting default input device with index: {device_index}")
        if not device_index:
            print("Error: device_index is empty")
            return
            
        pythoncom.CoInitialize()
        try:
            ps_script = f"""
            try {{
                Write-Host "Looking for device with index {device_index}"
                $device = Get-AudioDevice -List | Where-Object {{ $_.Index -eq {device_index} }}
                if ($device) {{
                    Write-Host "Found device: $($device.Name) (ID: $($device.ID))"
                    Write-Host "Setting as default device..."
                    Set-AudioDevice -ID $device.ID
                    Write-Host "Device set successfully"
                }} else {{
                    Write-Host "Device with index {device_index} not found"
                }}
            }} catch {{
                Write-Host "Error setting default device: $_"
                Write-Host $_.Exception.Message
                Write-Host $_.ScriptStackTrace
            }}
            """
            
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
            print(f"PowerShell output: {result.stdout}")
            if result.stderr:
                print(f"PowerShell error: {result.stderr}")
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error executing PowerShell: {e}")
        import traceback
        print(traceback.format_exc())

def set_default_input_communication_device(device_index):
    """Утнавливает устройство ввода для связи по умолчанию"""
    try:
        pythoncom.CoInitialize()
        try:
            ps_script = f"""
            try {{
                $device = Get-AudioDevice -List | Where-Object {{ $_.Index -eq {device_index} }}
                if ($device) {{
                    Write-Host "Setting communication input device: $($device.Name)"
                    Set-AudioDevice -ID $device.ID -Communication
                }} else {{
                    Write-Host "Device with index {device_index} not found"
                }}
            }} catch {{
                Write-Host "Error setting communication input device: $_"
            }}
            """
            
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
            print(f"PowerShell output: {result.stdout}")
            if result.stderr:
                print(f"PowerShell error: {result.stderr}")
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error executing PowerShell: {e}")

def create_notification_icon(icon_type='speaker', size=64):
    """Создает красив��ю иконку для уведомлений"""
    # Создаем изображение болшего размера для лучшего сглаживания
    large_size = size * 4
    image = Image.new('RGBA', (large_size, large_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = large_size / 128

    # Рисуем градиентный круг с правильным расчетом координа
    gradient_steps = 20
    step_size = large_size / (2 * gradient_steps)
    for i in range(gradient_steps):
        alpha = int(255 * (1 - i/gradient_steps))
        color = (0, 123, 255, alpha)
        x0 = i * step_size
        y0 = i * step_size
        x1 = large_size - (i * step_size)
        y1 = large_size - (i * step_size)
        draw.ellipse([x0, y0, x1, y1], fill=color)

    if icon_type == 'speaker':
        # Рисуем динамик (беый)
        speaker_color = (255, 255, 255, 255)
        
        # Прямоугольник динамика
        draw.rectangle([
            int(35 * scale), int(44 * scale), 
            int(55 * scale), int(84 * scale)
        ], fill=speaker_color)
        
        # Треугольник динамика
        points = [
            (int(55 * scale), int(44 * scale)),
            (int(85 * scale), int(24 * scale)), 
            (int(85 * scale), int(104 * scale)),
            (int(55 * scale), int(84 * scale))
        ]
        draw.polygon(points, fill=speaker_color)
        
        # Звуквые волн с улучшенным сглаживанием
        wave_color = (255, 255, 255, 200)
        for i in range(3):
            offset = i * 15
            # Увеличиваем толщину линии для учшего сглживания
            draw.arc(
                [int((70 + offset) * scale), int((34 + offset) * scale),
                int((100 + offset) * scale), int((94 + offset) * scale)],
                300, 60, fill=wave_color, width=int(6 * scale))

    elif icon_type == 'microphone':
        mic_color = (255, 255, 255, 255)
        # Основной корпус микрофона (более округлый)
        draw.rounded_rectangle([
            int(52 * scale), int(24 * scale),
            int(76 * scale), int(64 * scale)
        ], radius=int(12 * scale), fill=mic_color)
        
        # Нижняя чась микрофона (подставка)
        base_width = int(40 * scale)
        base_height = int(4 * scale)
        base_x = int(64 * scale - base_width/2)
        base_y = int(84 * scale)
        
        # Ножка микрофона
        stand_width = int(4 * scale)
        stand_x = int(64 * scale - stand_width/2)
        stand_y1 = int(64 * scale)
        stand_y2 = base_y
        
        # Рисуем ножку с грдиентом
        steps = 20  # Увеличиваем коиество шагов для плавности
        for i in range(steps):
            alpha = int(255 * (1 - i/steps * 0.3))
            current_color = (255, 255, 255, alpha)
            current_y = stand_y1 + (stand_y2 - stand_y1) * i/steps
            draw.rectangle([
                stand_x, current_y,
                stand_x + stand_width, current_y + (stand_y2 - stand_y1)/steps
            ], fill=current_color)
        
        # Рисуем подставку с градиентом
        for i in range(steps):
            alpha = int(255 * (1 - i/steps * 0.3))
            current_color = (255, 255, 255, alpha)
            current_width = base_width * (1 - i/steps * 0.2)
            current_x = int(64 * scale - current_width/2)
            current_y = base_y + i * base_height/steps
            draw.rounded_rectangle([
                current_x, current_y,
                current_x + current_width, current_y + base_height/steps
            ], radius=int(2 * scale), fill=current_color)
        
        # Добавляем блики на корпусе
        highlight_color = (255, 255, 255, 30)
        draw.ellipse([
            int(54 * scale), int(26 * scale),
            int(62 * scale), int(34 * scale)
        ], fill=highlight_color)

    # Уменьшаем изобраение до нужного рзмера с использованием высококачественного ресемплинга
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    return image

class NotificationWindow:
    def __init__(self):
        self.notifications = []
        self.WINDOW_CLASS = "SoundDeviceControlNotification"
        
        # Цвета для темно темы
        self.DARK_THEME = {
            'bg': win32api.RGB(44, 44, 44),      # Темно-серый фон
            'text': win32api.RGB(255, 255, 255),  # Белый текст
            'accent': win32api.RGB(74, 158, 255)  # Голубй акцен
        }
        
        # Цвета для светлой темы
        self.LIGHT_THEME = {
            'bg': win32api.RGB(240, 240, 240),    # Светло-серый фон
            'text': win32api.RGB(0, 0, 0),        # Черный ткст
            'accent': win32api.RGB(0, 120, 215)   # Синий кцент
        }
        
        # По уолчанию темная тема
        self.current_theme = self.DARK_THEME

        # Регистрируем класс окна
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = self.WINDOW_CLASS
        wc.lpfnWndProc = self._window_proc
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32gui.GetStockObject(win32con.BLACK_BRUSH)
        wc.hInstance = win32api.GetModuleHandle(None)
        
        try:
            win32gui.RegisterClass(wc)
        except Exception as e:
            print(f"Failed to register window class: {e}")

        self.notification_position = self.load_notification_position()

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _create_rounded_region(self, hwnd, width, height, radius):
        """Сздает регио окна с скругленными углами"""
        try:
            region = win32gui.CreateRoundRectRgn(0, 0, width, height, radius, radius)
            win32gui.SetWindowRgn(hwnd, region, True)
        except Exception as e:
            print(f"Error creating rounded region: {e}")

    def set_theme(self, is_light):
        """Утанавливает тему уведомлений"""
        print(f"Setting theme to {'light' if is_light else 'dark'}")  # Отладочный вывод
        self.current_theme = self.LIGHT_THEME if is_light else self.DARK_THEME

    def show_notification(self, text, icon_type='speaker'):
        def _show():
            try:
                # Создаем окно уведомления
                width = 300
                height = 80
                screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                
                # Получем координаты в зависимости от выбранной позиции
                x, y = self.get_notification_position(width, height, screen_width, screen_height)

                # Добавляем WS_EX_TOPMOST к стилям окна
                hwnd = win32gui.CreateWindowEx(
                    win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TOPMOST,  # Добавляем WS_EX_TOPMOST
                    self.WINDOW_CLASS,
                    "Notification",
                    win32con.WS_POPUP | win32con.WS_VISIBLE,
                    x, y, width, height,
                    0, 0, win32api.GetModuleHandle(None), None
                )

                # Создаем скруленный регион для окна
                region = win32gui.CreateRoundRectRgn(0, 0, width, height, 15, 15)
                win32gui.SetWindowRgn(hwnd, region, True)

                # Устанавливаем окно поверх всех окон
                win32gui.SetWindowPos(
                    hwnd, 
                    win32con.HWND_TOPMOST,
                    x, y, width, height,
                    win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                )

                # Создаем DC для рисования
                hdc = win32gui.GetDC(hwnd)
                memdc = win32gui.CreateCompatibleDC(hdc)
                bitmap = win32gui.CreateCompatibleBitmap(hdc, width, height)
                win32gui.SelectObject(memdc, bitmap)

                # Заливаем фон
                brush = win32gui.CreateSolidBrush(self.current_theme['bg'])
                win32gui.FillRect(memdc, (0, 0, width, height), brush)
                win32gui.DeleteObject(brush)

                # Создаем иконку
                icon_image = create_notification_icon(icon_type, size=32)
                
                # Сохраняе как ICO
                icon_path = os.path.join(tempfile.gettempdir(), f'notification_icon_{icon_type}.ico')
                # Конвертируем в ICO формат
                icon_image.save(icon_path, format='ICO', sizes=[(32, 32)])
                
                # Загружаем иконку
                icon = win32gui.LoadImage(
                    0, icon_path, win32con.IMAGE_ICON,
                    32, 32, win32con.LR_LOADFROMFILE
                )
                
                # Рисуем иконк
                win32gui.DrawIconEx(
                    memdc, 15, 24,
                    icon, 32, 32,
                    0, None, win32con.DI_NORMAL
                )
                
                # Удаляем иконку
                win32gui.DestroyIcon(icon)
                
                try:
                    os.remove(icon_path)
                except:
                    pass

                # Рисуем текст
                lf = win32gui.LOGFONT()
                lf.lfFaceName = 'Segoe UI'
                lf.lfHeight = 15
                lf.lfWeight = win32con.FW_NORMAL
                lf.lfQuality = win32con.DEFAULT_QUALITY
                font = win32gui.CreateFontIndirect(lf)

                win32gui.SelectObject(memdc, font)
                win32gui.SetTextColor(memdc, self.current_theme['text'])
                win32gui.SetBkMode(memdc, win32con.TRANSPARENT)
                rect = (60, 0, width - 10, height)
                win32gui.DrawText(memdc, text, -1, rect, 
                                win32con.DT_LEFT | win32con.DT_VCENTER | win32con.DT_SINGLELINE)

                # Копируем из пмяти на экран напрямую
                win32gui.BitBlt(hdc, 0, 0, width, height, memdc, 0, 0, win32con.SRCCOPY)

                # Очищаем ресурсы
                win32gui.DeleteObject(bitmap)
                win32gui.DeleteDC(memdc)
                win32gui.ReleaseDC(hwnd, hdc)

                # Ждем перед закрытием
                time.sleep(2)
                
                win32gui.DestroyWindow(hwnd)

            except Exception as e:
                print(f"Error showing notification: {e}")
                import traceback
                print(traceback.format_exc())

        Thread(target=_show, daemon=True).start()

    def load_notification_position(self):
        try:
            with open('notification_settings.json', 'r') as f:
                settings = json.load(f)
                return settings.get('position', 'bottom_right')
        except FileNotFoundError:
            return 'bottom_right'

    def save_notification_position(self, position):
        try:
            with open('notification_settings.json', 'w') as f:
                json.dump({'position': position}, f)
        except Exception as e:
            print(f"Error saving notification position: {e}")

    def get_notification_position(self, width, height, screen_width, screen_height):
        padding = 20
        bottom_padding = 70  # величенный отступ снзу для нижних позиций (было 50, стало 70)
        
        positions = {
            'top_right': (screen_width - width - padding, padding),
            'top_left': (padding, padding),
            'bottom_left': (padding, screen_height - height - bottom_padding),
            'bottom_right': (screen_width - width - padding, screen_height - height - bottom_padding),
            'center': (screen_width//2 - width//2, screen_height//2 - height//2)
        }
        
        return positions.get(self.notification_position, positions['bottom_right'])

# Создаем глобальный объект для уведомлений
notification_window = NotificationWindow()

# Заменяем все вызовы show_notification на:
def show_notification(message, icon_type='speaker'):
    notification_window.show_notification(message, icon_type)

# Удаляем старый код создания окна уведомлений
# def create_notification_window():
#     ...

# В функции main() заменяем запуск старого notification_thread на:
# notification_thread = Thread(target=create_notification_window, daemon=True)
# notification_thread.start()

def load_enabled_devices():
    """Загружает список активных устройств из файла"""
    global enabled_devices
    with device_lock:
        try:
            if os.path.exists('enabled_devices.json'):
                print("Loading enabled devices from file...")
                with open('enabled_devices.json', 'r', encoding='utf-8') as f:
                    loaded_devices = json.load(f)
                    enabled_devices = set(str(device_id) for device_id in loaded_devices)
                print(f"Loaded {len(enabled_devices)} enabled devices")
            else:
                print("enabled_devices.json not found, creating new file with all devices enabled")
                # При первом запуске все устройства активны
                devices_list = get_audio_devices()
                if devices_list:
                    print(f"Found {len(devices_list)} devices, enabling all")
                    enabled_devices = set(str(device[0]) for device in devices_list)
                    # Сохраняем устройства в файл
                    with open('enabled_devices.json', 'w', encoding='utf-8') as f:
                        json.dump(list(enabled_devices), f, ensure_ascii=False, indent=4)
                        f.flush()
                        os.fsync(f.fileno())
                    print(f"Successfully saved {len(enabled_devices)} enabled devices")
                else:
                    print("No devices found, adding default device")
                    enabled_devices = {"0"}
                    with open('enabled_devices.json', 'w', encoding='utf-8') as f:
                        json.dump(["0"], f, ensure_ascii=False, indent=4)
                        f.flush()
                        os.fsync(f.fileno())
                    print("Successfully saved default device")
        except Exception as e:
            print(f"Error loading enabled devices: {e}")
            import traceback
            print(traceback.format_exc())
            # При ошибке создаем новый список с виртуальным устройством
            enabled_devices = {"0"}
            try:
                with open('enabled_devices.json', 'w', encoding='utf-8') as f:
                    json.dump(["0"], f, ensure_ascii=False, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                print("Created new enabled_devices.json with default device")
            except Exception as e:
                print(f"Error saving default device: {e}")
                print(traceback.format_exc())

def save_enabled_devices():
    """Сохраняет список активных устройств в файл"""
    with device_lock:
        try:
            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname('enabled_devices.json'), exist_ok=True)
            
            # Проверяем, что enabled_devices не пустой
            if not enabled_devices:
                devices_list = get_audio_devices()
                if devices_list:
                    enabled_devices.update(str(device[0]) for device in devices_list)
                else:
                    enabled_devices.add("0")  # Добавляем виртуальное устройство
            
            # Сохраняем в файл с принудительной син��ронизацией
            with open('enabled_devices.json', 'w', encoding='utf-8') as f:
                json.dump(list(enabled_devices), f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            
            print(f"Successfully saved enabled devices: {list(enabled_devices)}")
        except Exception as e:
            print(f"Error saving enabled devices: {e}")
            import traceback
            print(traceback.format_exc())

@app.route("/set_device_enabled", methods=["POST"])
def set_device_enabled():
    """Включает/выключает устройство в списке активных"""
    global enabled_devices
    try:
        data = request.json
        device_index = str(data.get("device_index"))
        enabled = data.get("enabled", False)
        
        # Обновляем состояние
        if enabled:
            enabled_devices.add(device_index)
        else:
            enabled_devices.discard(device_index)
        
        # Сразу сохраняем в файл
        with open('enabled_devices.json', 'w', encoding='utf-8') as f:
            json.dump(list(enabled_devices), f)
        
        # Возвращаем только необходимый минимум данных
        return jsonify({
            "status": "success",
            "device_index": device_index,
            "enabled": enabled
        })
    except Exception as e:
        print(f"Error in set_device_enabled: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def switch_audio_device(direction):
    """Переключает устройство вывода звука"""
    global current_device_index, devices
    try:
        pythoncom.CoInitialize()
        try:
            if not devices:
                devices = get_audio_devices()
                if not devices:
                    return
            
            # Получаем текущее устройство
            current_device = None
            if current_device_index < len(devices):
                current_device = devices[current_device_index]
            
            # Если текущ��е устройство отключено, добавляем его в список отключенных
            if current_device:
                device_name = current_device[1]
                if not is_device_connected(device_name, devices):
                    profile_manager.add_disconnected_device(device_name, current_device[0])
            
            # Получаем список всех устройств, включая отключенные
            all_device_names = []
            all_device_ids = []
            
            # Добавляем только устройства с активным чекбоксом
            for device in devices:
                if device[0] in enabled_devices:  # ро��еряем, активировао ли устройство
                    device_name = device[1]
                    all_device_names.append(device_name)
                    all_device_ids.append(device[0])
            
            if not all_device_names:
                show_notification("No enabled output devices found", "speaker")
                return
                
            # Находим текущее устройство в списке
            current_name = ""
            if current_device:
                current_name = current_device[1]
            
            try:
                current_index = all_device_names.index(current_name)
            except ValueError:
                current_index = 0
            
            # Определяем следующее устройство
            if direction == 'prev':
                next_index = (current_index - 1) % len(all_device_names)
            else:
                next_index = (current_index + 1) % len(all_device_names)
            
            next_device_name = all_device_names[next_index]
            next_device_id = all_device_ids[next_index]
            
            # Проверяем, подключено ли устройство
            is_disconnected = profile_manager.is_device_disconnected(next_device_name)
            
            # Если устройство подключено, переключаемся на нег
            if not is_disconnected:
                for i, device in enumerate(devices):
                    if device[1] == next_device_name:
                        current_device_index = i
                        set_default_audio_device(next_device_id)
                        break
            
            # Показываем уведомление
            status = " (Disconnected)" if is_disconnected else ""
            show_notification(f"Switched to: {next_device_name}{status}")
                
        finally:
            pythoncom.CoUninitialize()
            
    except Exception as e:
        print(f"Error switching audio device: {e}")

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

    return image

def open_settings(icon, item):
    webbrowser.open('http://127.0.0.1:5000')

def exit_app(icon, item):
    icon.stop()
    global running
    running = False

# Добавляем констану для отслеживания изменений устройств
WM_DEVICECHANGE = 0x0219

class SystemTray:
    def __init__(self):
        self.log("Initializing SystemTray...")
        self.flask_server = None  # Добавляем ссылку на сервер
        self.server_thread = None  # Добавляем ссылку на поток сервера
        
        try:
            icon_size = 64
            image = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)

            # Рисуем градиентный круг
            for i in range(20):
                alpha = int(255 * (1 - i/20))
                color = (0, 123, 255, alpha)
                draw.ellipse([i, i, icon_size-i, icon_size-i], fill=color)

            # Рисуем динамик (белый)
            speaker_color = (255, 255, 255, 255)
            scale = icon_size / 128  # Масштабируем координаты
            
            # Прямоугольник динамика
            draw.rectangle([
                int(35 * scale), int(44 * scale), 
                int(55 * scale), int(84 * scale)
            ], fill=speaker_color)
            
            # Треугольник динамика
            points = [
                (int(55 * scale), int(44 * scale)),
                (int(85 * scale), int(24 * scale)), 
                (int(85 * scale), int(104 * scale)),
                (int(55 * scale), int(84 * scale))
            ]
            draw.polygon(points, fill=speaker_color)

            # Создаем меню
            menu = (
                pystray.MenuItem('Settings', self._open_settings, default=True),
                pystray.MenuItem('Exit', self._exit_app)
            )

            # Создаем иконку
            self.icon = pystray.Icon(
                "SoundDeviceControl",
                image,
                "Sound Device Control",
                menu
            )

        except Exception as e:
            self.log(f"Ошибка при создании иконки: {str(e)}")
            return False

        self.running = True
        self.log("Initialization complete")

    def _open_settings(self, icon, item):
        try:
            self.log("Opening settings")
            webbrowser.open('http://127.0.0.1:5000')
        except Exception as e:
            self.log(f"Error opening settings: {e}")

    def _run_flask_server(self):
        """Запускает Flask сервер"""
        try:
            self.flask_server = app.run(host='127.0.0.1', port=5000, debug=False)
        except Exception as e:
            self.log(f"Error running Flask server: {e}")

    def stop_server(self):
        """Останавливает Flask сервер"""
        if self.flask_server:
            try:
                func = request.environ.get('werkzeug.server.shutdown')
                if func is None:
                    raise RuntimeError('Not running with the Werkzeug Server')
                func()
            except Exception as e:
                self.log(f"Error stopping server: {e}")

    def _exit_app(self, icon, item):
        try:
            self.log("Exiting application")
            global running
            self.stop()
            running = False
        except Exception as e:
            self.log(f"Error exiting: {e}")

    def stop(self):
        try:
            if hasattr(self, 'icon'):
                self.icon.stop()
            self.log("Stopped")
        except Exception as e:
            self.log(f"Error stopping: {e}")

    def run(self):
        self.log("Starting tray icon")
        self.icon.run()

    def log(self, message):
        """Логирование событий трея"""
        print(f"{message}")

    def create_tray_icon(self):
        """Создает иконку в трее"""
        self.server_thread = None  # Добавляем ссылку на поток сервера
        
        try:
            icon_size = 64
            image = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            
            # Настройки для рисования
            scale = 0.5
            speaker_color = (255, 255, 255, 255)  # Белый цвет
            
            # Основная часть динамика
            points = [
                (int(55 * scale), int(44 * scale)),
                (int(55 * scale), int(84 * scale)),
                (int(70 * scale), int(84 * scale)),
                (int(70 * scale), int(44 * scale))
            ]
            draw.polygon(points, fill=speaker_color)
            
            # Треугольник динамика
            points = [
                (int(55 * scale), int(44 * scale)),
                (int(85 * scale), int(24 * scale)),
                (int(85 * scale), int(104 * scale)),
                (int(55 * scale), int(84 * scale))
            ]
            draw.polygon(points, fill=speaker_color)
            
            # Сохраняем иконку во временный файл
            icon_path = os.path.join(tempfile.gettempdir(), 'speaker_icon.png')
            image.save(icon_path, 'PNG')
            
            return icon_path
        except Exception as e:
            print(f"Error creating tray icon: {e}")
            import traceback
            print(traceback.format_exc())

def setup_tray():
    """Sets up the system tray icon"""
    return SystemTray()

def exit_app(icon):
    global running
    running = False
    icon.stop()

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
def load_settings():
    global hotkeys
    try:
        print("Loading settings...")
        if os.path.exists('settings.json'):
            with open('settings.json', 'r', encoding='utf-8') as f:
                hotkeys = json.load(f)
            # Обновляем структуру если нужно
            hotkeys, was_updated = update_settings_structure(hotkeys)
            if was_updated:
                save_settings(hotkeys)
            print(f"Loaded hotkeys: {hotkeys}")
        else:
            print("Settings file not found, using defaults")
            hotkeys = default_hotkeys.copy()
            save_settings(hotkeys)
    except Exception as e:
        print(f"Error loading settings: {e}")
        print("Using default hotkeys")
        hotkeys = default_hotkeys.copy()
        try:
            save_settings(hotkeys)
        except Exception as e:
            print(f"Error saving default settings: {e}")

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

        # Обновляем стр��ктуру если нужно
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

def load_enabled_input_devices():
    """Загружает список активных устройств ввода из файла"""
    global enabled_input_devices
    with input_device_lock:
        try:
            if os.path.exists('enabled_input_devices.json'):
                print("Loading enabled input devices from file...")
                with open('enabled_input_devices.json', 'r', encoding='utf-8') as f:
                    loaded_devices = json.load(f)
                    enabled_input_devices = set(str(device_id) for device_id in loaded_devices)
                print(f"Loaded {len(enabled_input_devices)} enabled input devices")
            else:
                print("enabled_input_devices.json not found, creating new file with all devices enabled")
                # При первом запуске все устройства активны
                devices_list = get_input_devices()
                if devices_list:
                    print(f"Found {len(devices_list)} input devices, enabling all")
                    enabled_input_devices = set(str(device[0]) for device in devices_list)
                    # Сохраняем устройства в файл
                    with open('enabled_input_devices.json', 'w', encoding='utf-8') as f:
                        json.dump(list(enabled_input_devices), f, ensure_ascii=False, indent=4)
                        f.flush()
                        os.fsync(f.fileno())
                    print(f"Successfully saved {len(enabled_input_devices)} enabled input devices")
                else:
                    print("No input devices found, adding default device")
                    enabled_input_devices = {"0"}
                    with open('enabled_input_devices.json', 'w', encoding='utf-8') as f:
                        json.dump(["0"], f, ensure_ascii=False, indent=4)
                        f.flush()
                        os.fsync(f.fileno())
                    print("Successfully saved default input device")
        except Exception as e:
            print(f"Error loading enabled input devices: {e}")
            import traceback
            print(traceback.format_exc())
            # При ошибке создаем новый список с виртуальным устройством
            enabled_input_devices = {"0"}
            try:
                with open('enabled_input_devices.json', 'w', encoding='utf-8') as f:
                    json.dump(["0"], f, ensure_ascii=False, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                print("Created new enabled_input_devices.json with default device")
            except Exception as e:
                print(f"Error saving default input device: {e}")
                print(traceback.format_exc())

def save_enabled_input_devices():
    """Сохраняет список активных устройств ввода в файл"""
    with input_device_lock:
        try:
            with open('enabled_input_devices.json', 'w', encoding='utf-8') as f:
                json.dump(list(enabled_input_devices), f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"Error saving enabled input devices: {e}")

@app.route("/get_input_devices")
def get_input_devices_route():
    """Возвращает список устройств ввода"""
    try:
        devices = get_input_devices()
        device_list = []
        
        # Загружаем текущие enabled устройства
        load_enabled_input_devices()
        
        # Добавляем подключенные устройства
        for device in devices:
            device_list.append({
                'id': device[0],
                'name': device[1],
                'connected': True,
                'enabled': str(device[0]) in enabled_input_devices
            })
            
        # Добавляем отключенные устройства
        for device_name, device_info in profile_manager.disconnected_devices['input'].items():
            # Проверяем, нет ли уже такого устройства в списке
            if not any(d['name'] == device_name for d in device_list):
                device_list.append({
                    'id': device_info['id'],
                    'name': f"{device_name} (Disconnected)",
                    'connected': False,
                    'enabled': str(device_info['id']) in enabled_input_devices
                })
        
        return jsonify({
            "status": "success",
            "devices": device_list
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/set_input_device_enabled", methods=["POST"])
def set_input_device_enabled():
    """Включает/выключает устройство ввода в списке активных"""
    global enabled_input_devices
    try:
        data = request.json
        device_index = str(data.get("device_index"))
        enabled = data.get("enabled", False)
        
        # Обновляем состояние
        if enabled:
            enabled_input_devices.add(device_index)
        else:
            enabled_input_devices.discard(device_index)
        
        # Сразу сохраняем в файл
        with open('enabled_input_devices.json', 'w', encoding='utf-8') as f:
            json.dump(list(enabled_input_devices), f)
        
        # Возвращаем только необходимый минимум данных
        return jsonify({
            "status": "success",
            "device_index": device_index,
            "enabled": enabled
        })
    except Exception as e:
        print(f"Error in set_input_device_enabled: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def get_input_devices():
    """Получает список устройств ввода звука"""
    devices = []
    
    try:
        pythoncom.CoInitialize()
        try:
            # 1. Основной метод через PowerShell
            try:
                powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
                
                ps_script = """
                try {
                    if (-not (Get-Module -ListAvailable -Name AudioDeviceCmdlets)) {
                        Write-Host "ERROR: AudioDeviceCmdlets not installed"
                        exit 1
                    }
                    
                    $OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
                    $devices = Get-AudioDevice -List | Where-Object { $_.Type -eq 'Recording' }
                    $devices | ForEach-Object {
                        Write-Output ("DEVICE:{0}|{1}" -f $_.Index, $_.Name)
                    }
                } catch {
                    Write-Host "Error getting input device list: $_"
                    exit 1
                }
                """
                
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                result = subprocess.run(
                    [powershell_path, "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    startupinfo=startupinfo
                )
                
                for line in result.stdout.split('\n'):
                    if line.strip().startswith('DEVICE:'):
                        try:
                            _, device_info = line.strip().split('DEVICE:', 1)
                            index, name = device_info.split('|', 1)
                            devices.append([index.strip(), name.strip()])
                        except ValueError:
                            continue
                            
                if devices:
                    return devices
            except Exception as e:
                pass

            # 2. Резервный метод через pycaw
            if not devices:
                try:
                    deviceEnumerator = AudioUtilities.GetAllDevices()
                    index = 0
                    for device in deviceEnumerator:
                        if device.state == 1 and device.flow == 1:  # DEVICE_STATE_ACTIVE = 1, eCapture = 1
                            devices.append([str(index), device.FriendlyName])
                            index += 1
                            
                    if devices:
                        return devices
                except Exception as e:
                    pass

            # 3. Резервный метод через MMDevice API в PowerShell
            if not devices:
                try:
                    ps_script = """
                    try {
                        Add-Type -TypeDefinition @"
                        using System.Runtime.InteropServices;
                        [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                        interface IMMDevice {
                            int Activate([MarshalAs(UnmanagedType.LPStruct)] Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
                        }
                        [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                        interface IMMDeviceEnumerator {
                            int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IMMDeviceCollection ppDevices);
                        }
                        [Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                        interface IMMDeviceCollection {
                            int GetCount(out int pcDevices);
                            int Item(int nDevice, out IMMDevice ppDevice);
                        }
"@
                        
                        $deviceEnumerator = New-Object -ComObject "MMDeviceEnumerator.MMDeviceEnumerator"
                        $devices = @()
                        $deviceCollection = $deviceEnumerator.EnumAudioEndpoints(1, 1)  # eCapture = 1, DEVICE_STATE_ACTIVE = 1
                        
                        for ($i = 0; $i -lt $deviceCollection.Count; $i++) {
                            $device = $deviceCollection.Item($i)
                            $properties = $device.Properties
                            $name = $properties.GetValue("{a45c254e-df1c-4efd-8020-67d146a850e0},2").ToString()
                            Write-Output ("DEVICE:{0}|{1}" -f $i, $name)
                        }
                    } catch {
                        Write-Host "Error in MMDevice API: $_"
                        exit 1
                    }
                    """
                    
                    result = subprocess.run(
                        [powershell_path, "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        startupinfo=startupinfo
                    )
                    
                    for line in result.stdout.split('\n'):
                        if line.strip().startswith('DEVICE:'):
                            try:
                                _, device_info = line.strip().split('DEVICE:', 1)
                                index, name = device_info.split('|', 1)
                                devices.append([index.strip(), name.strip()])
                            except ValueError:
                                continue
                                
                    if devices:
                        return devices
                except Exception as e:
                    pass
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        pass

    # Если все методы не сработали, возвращаем хотя бы одно виртуальное устройство
    return [["0", "Default Input Device"]]

def switch_input_device(direction):
    """Переключает устройство ввода звука"""
    global current_input_device_index, input_devices
    try:
        pythoncom.CoInitialize()
        try:
            if not input_devices:
                input_devices = get_input_devices()
                if not input_devices:
                    return
            
            # Получаем текущее устройство
            current_device = None
            if current_input_device_index < len(input_devices):
                current_device = input_devices[current_input_device_index]
            
            # Если текущее устройство отключено, добавляем его в список отключенных
            if current_device:
                device_name = current_device[1]
                if not is_device_connected(device_name, input_devices):
                    profile_manager.add_disconnected_device(device_name, current_device[0], is_input=True)
            
            # Получаем список всех устройств, включая отключенные
            all_device_names = []
            all_device_ids = []
            
            # Добавляем только устройства с активным чекбоксом
            for device in input_devices:
                if device[0] in enabled_input_devices:  # Проверяем, активировано ли устройство
                    device_name = device[1]
                    all_device_names.append(device_name)
                    all_device_ids.append(device[0])
            
            if not all_device_names:
                show_notification("No enabled input devices found", "microphone")
                return
                
            # Находим текущее устройство в списке
            current_name = ""
            if current_device:
                current_name = current_device[1]
            
            try:
                current_index = all_device_names.index(current_name)
            except ValueError:
                current_index = 0
            
            # Определяем следующее уст��ойство
            if direction == 'prev':
                next_index = (current_index - 1) % len(all_device_names)
            else:
                next_index = (current_index + 1) % len(all_device_names)
            
            next_device_name = all_device_names[next_index]
            next_device_id = all_device_ids[next_index]
            
            # Проверяем, подключено ли устройство
            is_disconnected = profile_manager.is_device_disconnected(next_device_name, is_input=True)
            
            # Если устройство подключено, переключаеся на него
            if not is_disconnected:
                for i, device in enumerate(input_devices):
                    if device[1] == next_device_name:
                        current_input_device_index = i
                        set_default_input_device(next_device_id)
                        break
            
            # Показываем уведомление
            status = " (Disconnected)" if is_disconnected else ""
            show_notification(f"Input switched to: {next_device_name}{status}", "microphone")
                
        finally:
            pythoncom.CoUninitialize()
            
    except Exception as e:
        print(f"Error switching input device: {e}")

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
            Thread(target=show_notification, args=("Microphone: ON", 'microphone')).start()
        else:
            volume.SetMute(1, None)
            volume.SetMasterVolumeLevelScalar(0.0, None)
            Thread(target=show_notification, args=("Microphone: OFF", 'microphone')).start()
    except:
        pass
    finally:
        pythoncom.CoUninitialize()

@app.route("/get_output_devices")
def get_output_devices():
    """Возвращает список устройств вывода звука"""
    try:
        devices = get_audio_devices()
        device_list = []
        
        # Загружаем текущие enabled устройства
        load_enabled_devices()
        
        # Добавляем подключенные устройства
        for device in devices:
            device_list.append({
                'id': device[0],
                'name': device[1],
                'connected': True,
                'enabled': str(device[0]) in enabled_devices
            })
            
        # Добавляем отключенные устройства
        for device_name, device_info in profile_manager.disconnected_devices['output'].items():
            # Проверяем, нет ли уже такого устройства в списке
            if not any(d['name'] == device_name for d in device_list):
                device_list.append({
                    'id': device_info['id'],
                    'name': f"{device_name} (Disconnected)",
                    'connected': False,
                    'enabled': str(device_info['id']) in enabled_devices
                })
        
        return jsonify({
            "status": "success",
            "devices": device_list
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

@app.route("/get_enabled_devices")
def get_enabled_devices():
    """Возвращает список активных устройств вывода"""
    try:
        # Обновляем список перед отправкой
        load_enabled_devices()
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
        # Обновляем список перед отправкой
        load_enabled_input_devices()
        return jsonify({
            "status": "success",
            "enabled_devices": list(enabled_input_devices)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def get_autostart_status():
    """Проверяет, добавлено ли приложение в автозагрузку"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        try:
            value, _ = winreg.QueryValueEx(key, "SoundDeviceControl")
            return True
        except WindowsError:
            return False
        finally:
            winreg.CloseKey(key)
    except WindowsError:
        return False

def toggle_autostart(enable):
    """Включает или выключает автозагрузку приложения"""
    key = None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_ALL_ACCESS
        )
        
        app_path = sys.argv[0]
        if enable:
            if app_path.endswith('.py'):
                # Для Python файла
                python_path = sys.executable
                script_path = os.path.abspath(app_path)
                command = f'"{python_path}" "{script_path}"'
                winreg.SetValueEx(
                    key,
                    "SoundDeviceControl",
                    0,
                    winreg.REG_SZ,
                    command
                )
            else:
                # Для exe файла
                winreg.SetValueEx(
                    key,
                    "SoundDeviceControl",
                    0,
                    winreg.REG_SZ,
                    os.path.abspath(app_path)
                )
        else:
            try:
                winreg.DeleteValue(key, "SoundDeviceControl")
            except WindowsError:
                pass  # Значение уе удалено
        return True
    except WindowsError as e:
        print(f"Ошибка при работе с реестром: {e}")
        return False
    finally:
        if key:
            winreg.CloseKey(key)

@app.route("/get_autostart")
def get_autostart():
    """��озвращает статус автозагрузки"""
    try:
        return jsonify({
            "status": "success",
            "autostart": get_autostart_status()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/set_autostart", methods=["POST"])
def set_autostart_route():
    """Устанавливает статус автозагр��зки"""
    try:
        data = request.json
        enable = data.get("enable", False)
        
        success = toggle_autostart(enable)
        return jsonify({
            "status": "success" if success else "error"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/set_theme", methods=["POST"])
def set_theme():
    try:
        data = request.json
        is_light = data.get("is_light", False)
        notification_window.set_theme(is_light)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/get_notification_position")
def get_notification_position():
    """Возвращает текущую позицию уведомлений и список доступных позиций"""
    try:
        return jsonify({
            "status": "success",
            "current_position": notification_window.notification_position,
            "available_positions": NOTIFICATION_POSITIONS
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/set_notification_position", methods=["POST"])
def set_notification_position():
    """Устанавливает новую позицию уедомлений"""
    try:
        data = request.json
        position = data.get("position")
        
        if position not in NOTIFICATION_POSITIONS:
            return jsonify({
                "status": "error",
                "message": "Invalid position"
            })
            
        notification_window.notification_position = position
        notification_window.save_notification_position(position)
        
        return jsonify({
            "status": "success"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def register_device_callback(callback):
    """Регистрирует функцию обратного вызова для обновления устройств"""
    device_update_callbacks.append(callback)

def notify_device_changes():
    """Уведомляет все зарегистрированные функции об изменении устрйств"""
    global devices, input_devices
    try:
        # Обновляем ��писки ус��ро��ств
        new_devices = get_audio_devices()
        new_input_devices = get_input_devices()
        
        if new_devices is not None:
            devices = new_devices
        if new_input_devices is not None:
            input_devices = new_input_devices
        
        # Ув��до��ляем колбэ��и
        for callback in device_update_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in device update callback: {e}")
    except Exception as e:
        print(f"Error in notify_device_changes: {e}")

class DeviceChangeListener:
    def __init__(self):
        self.running = True
        self.last_check = 0
        self.check_interval = 5.0  # Увеличиваем интервал до 5 секунд
        self.device_states = {}  # Кэш состояний устройств
        
        # Создаем скрытое окно для получения сообщений Windows
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "DeviceChangeListener"
        wc.hInstance = win32api.GetModuleHandle(None)
        
        class_atom = win32gui.RegisterClass(wc)
        self.hwnd = win32gui.CreateWindow(
            class_atom,
            "DeviceChangeListener",
            0,
            0, 0, 0, 0,
            0,
            0,
            wc.hInstance,
            None
        )
        
        # Запускаем поток для периодической проверки
        self.check_thread = threading.Thread(target=self._check_devices, daemon=True)
        self.check_thread.start()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_DEVICECHANGE:  # Используем константу WM_DEVICECHANGE
            notify_device_changes()
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _check_devices(self):
        """Периодически проверяет устройства"""
        while self.running:
            current_time = time.time()
            if current_time - self.last_check >= self.check_interval:
                # Получаем текущие состояния устройств только если прошло достаточно времени
                current_states = self._get_device_states()
                
                # Сравниваем с предыдущими состоян��ями
                if current_states != self.device_states:
                    notify_device_changes()
                    self.device_states = current_states
                
                self.last_check = current_time
            time.sleep(2.0)  # Увеличиваем интервал сна до 2 секунды

    def _get_device_states(self):
        """Получает текущие состояния устройств"""
        states = {}
        try:
            # Получаем списки устройств
            output_devices = get_audio_devices()
            input_devices = get_input_devices()
            
            # Сохраняем состояния
            states['output'] = [(d[0], d[1]) for d in output_devices]
            states['input'] = [(d[0], d[1]) for d in input_devices]
        except Exception as e:
            print(f"Error getting device states: {e}")
        
        return states

    def stop(self):
        self.running = False
        if self.hwnd:
            win32gui.DestroyWindow(self.hwnd)

# Добавляем класс для работы с профилями
class DeviceProfile:
    def __init__(self, name):
        self.name = name
        self.input_default = None
        self.input_communication = None
        self.output_default = None
        self.output_communication = None
        self.hotkey = {
            'keyboard': 'None',
            'mouse': 'None'
        }
        self.trigger_app = None  # Путь к приложению-триггеру

def get_device_name_by_id(device_id, devices_list):
    """Получает имя устройства по его ID"""
    for device in devices_list:
        if device[0] == device_id:
            return device[1]
    return None

def get_device_id_by_name(device_name, devices_list):
    """Получает ID устройства по его имени"""
    for device in devices_list:
        if device[1] == device_name:
            return device[0]
    return None

class ProfileManager:
    def __init__(self):
        # Инициализируем базовые атрибуты
        self.profiles = []
        self.current_profile = None
        self.disconnected_devices = {
            'output': {},  # {'device_name': {'id': 'last_known_id', 'last_seen': timestamp}}
            'input': {}
        }
        
        # Загружаем данные
        try:
            self.load_profiles()
            self.load_disconnected_devices()
        except Exception as e:
            print(f"Error during initialization: {e}")
            # Убеждаемся, что disconnected_devices всегда инициализирован
            self.disconnected_devices = {
                'output': {},
                'input': {}
            }
            # Сохраняем начальное состояние
            try:
                self.save_disconnected_devices()
            except Exception as e:
                print(f"Error saving initial disconnected devices: {e}")

    def load_disconnected_devices(self):
        """Загружает список отключенных устройств из файла"""
        try:
            if os.path.exists('disconnected_devices.json'):
                with open('disconnected_devices.json', 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Проверяем структуру загруженных данных
                    if isinstance(loaded_data, dict) and 'output' in loaded_data and 'input' in loaded_data:
                        self.disconnected_devices = loaded_data
                    else:
                        raise ValueError("Invalid disconnected devices data structure")
            else:
                print("disconnected_devices.json not found, creating new file")
                self.disconnected_devices = {
                    'output': {},
                    'input': {}
                }
                self.save_disconnected_devices()
        except Exception as e:
            print(f"Error loading disconnected devices: {e}")
            # Сбрасываем к начальному состоянию при ошибке
            self.disconnected_devices = {
                'output': {},
                'input': {}
            }
            try:
                self.save_disconnected_devices()
            except Exception as e:
                print(f"Error saving initial disconnected devices: {e}")

    def save_disconnected_devices(self):
        """Сохраняет список отключенных устройств в файл"""
        try:
            with open('disconnected_devices.json', 'w', encoding='utf-8') as f:
                json.dump(self.disconnected_devices, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"Error saving disconnected devices: {e}")

    def activate_startup_profile(self):
        """Активирует профиль, помеченный для запуска при старте"""
        startup_profiles = [p for p in self.profiles if p.get('activate_on_startup', False)]
        if startup_profiles:
            # Если есть несколько профилей с activate_on_startup, берем первый
            profile_name = startup_profiles[0]['name']
            print(f"Activating startup profile: {profile_name}")
            # Используем self вместо глобальн��й переменной
            return self.activate_profile(profile_name)
        return False

    def save_profile(self, profile_data):
        """Сохраняет профиль"""
        try:
            profile_name = profile_data.get('name')
            if not profile_name:
                return {'status': 'error', 'message': 'Profile name is required'}

            print(f"\nSaving profile: {profile_name}")
            print(f"Raw profile data: {profile_data}")

            # Очищаем имена устройств от статуса (Disconnected)
            for key in ['output_default', 'output_communication', 'input_default', 'input_communication']:
                if profile_data.get(key):
                    profile_data[key] = profile_data[key].replace(" (Disconnected)", "")

            # Проверяем существование профиля
            existing_profile = next((p for p in self.profiles if p['name'] == profile_name), None)
            
            # Нормализуем путь к приложению-триггеру
            trigger_app = profile_data.get('trigger_app', '')
            print(f"Original trigger app path: {trigger_app}")
            
            if trigger_app and trigger_app != 'No application selected':
                trigger_app = os.path.normpath(trigger_app)
                print(f"Normalized trigger app path: {trigger_app}")
            else:
                trigger_app = ''
                print("No trigger app selected")
            
            # Создаем новый профиль с правильными значениями по умол��анию
            new_profile = {
                'name': profile_name,
                'output_default': profile_data.get('output_default', ''),
                'output_communication': profile_data.get('output_communication', ''),
                'input_default': profile_data.get('input_default', ''),
                'input_communication': profile_data.get('input_communication', ''),
                'hotkey': profile_data.get('hotkey', {'keyboard': 'None', 'mouse': 'None'}),
                'trigger_app': trigger_app,
                'activate_on_startup': bool(profile_data.get('activate_on_startup', False))
            }
            
            print(f"New profile data: {new_profile}")

            # Если профиль существует, обновляем его
            if existing_profile:
                index = self.profiles.index(existing_profile)
                self.profiles[index] = new_profile
                print("Updated existing profile")
            else:
                self.profiles.append(new_profile)
                print("Added new profile")

            # Сохраняем профили в файл
            self.save_profiles_to_file()
            print("Profiles saved to file")

            return {
                'status': 'success',
                'message': f"Profile '{profile_name}' saved successfully"
            }

        except Exception as e:
            print(f"Error saving profile: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def save_profiles_to_file(self):
        """Сохраняет профили в файл"""
        try:
            print("\nSaving profiles to file...")
            print(f"Profiles to save: {json.dumps(self.profiles, indent=2)}")
            
            with open('profiles.json', 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=4)
                
            print("Profiles saved successfully")
        except Exception as e:
            print(f"Error saving profiles to file: {e}")
            raise

    def load_profiles(self):
        """Загружает профили из файла"""
        try:
            print("\nLoading profiles from file...")
            if os.path.exists('profiles.json'):
                with open('profiles.json', 'r', encoding='utf-8') as f:
                    self.profiles = json.load(f)
                    print(f"Loaded profiles: {json.dumps(self.profiles, indent=2)}")
            else:
                print("No profiles file found, starting with empty list")
                self.profiles = []
                
            # Нормализуем пути к приложениям-триггерам
            for profile in self.profiles:
                if profile.get('trigger_app'):
                    original_path = profile['trigger_app']
                    normalized_path = os.path.normpath(original_path)
                    if original_path != normalized_path:
                        print(f"Normalizing path in profile {profile['name']}:")
                        print(f"  Original: {original_path}")
                        print(f"  Normalized: {normalized_path}")
                        profile['trigger_app'] = normalized_path
                        
            print("Profiles loaded successfully")
        except Exception as e:
            print(f"Error loading profiles: {e}")
            self.profiles = []
        
    def get_profile(self, name):
        """Получает профиль по имени"""
        for profile in self.profiles:
            if profile.get('name') == name:
                return profile
        return None
        
    def get_profiles(self):
        return self.profiles
        
    def add_profile(self, profile):
        """Добавляет новый профиль"""
        if any(p['name'] == profile['name'] for p in self.profiles):
            return False
            
        # Очищаем имена устройств от статуса (Disconnected)
        for key in ['output_default', 'output_communication', 'input_default', 'input_communication']:
            if profile.get(key) and " (Disconnected)" in profile[key]:
                profile[key] = profile[key].replace(" (Disconnected)", "")
        
        # Добавляем поле activate_on_startup со значением по умолчанию False
        if 'activate_on_startup' not in profile:
            profile['activate_on_startup'] = False
            
        self.profiles.append(profile)
        self.save_profiles_to_file()
        return True
        
    def update_profile(self, profile):
        """Обновляет существующий профиль"""
        # Очиаем имена устройств от статуса (Disconnected)
        for key in ['output_default', 'output_communication', 'input_default', 'input_communication']:
            if profile.get(key) and " (Disconnected)" in profile[key]:
                profile[key] = profile[key].replace(" (Disconnected)", "")
                
        for i, p in enumerate(self.profiles):
            if p['name'] == profile['name']:
                self.profiles[i] = profile
                self.save_profiles_to_file()
                return True
        return False
        
    def delete_profile(self, name):
        """Удаляет профиль"""
        # Удаляем профиль из списка
        self.profiles = [p for p in self.profiles if p['name'] != name]
        
        # Соханяем обновленный список с правильной кодировкой
        try:
            with open('profiles.json', 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving profiles after deletion: {e}")
            # Восстанавливаем список профилей
            self.load_profiles()

    def add_disconnected_device(self, device_name, device_id, is_input=False):
        """Добавляет устройство в список отключенных"""
        device_type = 'input' if is_input else 'output'
        if device_name not in self.disconnected_devices[device_type]:
            self.disconnected_devices[device_type][device_name] = {
                'id': device_id,
                'last_seen': time.time()
            }
        self.save_disconnected_devices()

    def is_device_disconnected(self, device_name, is_input=False):
        """Проверяет, является ли устройство отключенным"""
        if not device_name:
            return False
            
        device_type = 'input' if is_input else 'output'
        return device_name in self.disconnected_devices[device_type]

    def get_device_status(self, device_name, is_input=False):
        """Возвращает статус устройства и его ID"""
        if not device_name:
            return None
            
        device_type = 'input' if is_input else 'output'
        devices_list = get_input_devices() if is_input else get_audio_devices()
        
        # Проверяем текущие подключенные устройства
        for device in devices_list:
            if device[1] == device_name:
                return {
                    'connected': True,
                    'id': device[0]
                }
        
        # Проверяем отключенные устройства
        if device_name in self.disconnected_devices[device_type]:
            return {
                'connected': False,
                'id': self.disconnected_devices[device_type][device_name]['id']
            }
            
        return None

    def is_device_connected(self, device_name, devices_list):
        """Проверяет, подключено ли устройство"""
        if not device_name:
            return False
        return any(device[1] == device_name for device in devices_list)

    def get_device_id(self, device_name, is_input=False):
        """Получает ID устройства по им��ни"""
        if not device_name:
            return None
            
        # Проверяем текущие устройства
        devices_list = get_input_devices() if is_input else get_audio_devices()
        for device in devices_list:
            if device[1] == device_name:
                return device[0]
        
        # Проверяем отключенные устройства
        device_type = 'input' if is_input else 'output'
        if device_name in self.disconnected_devices[device_type]:
            return self.disconnected_devices[device_type][device_name]['id']
        
        return None

    def activate_profile(self, name):
        """Активирует профиль по имени"""
        try:
            profile = self.get_profile(name)
            if not profile:
                print(f"Profile not found: {name}")
                return False
                
            print(f"\nActivating profile with settings: {profile}")
            
            # Получаем текущие устройства
            current_audio_devices = get_audio_devices()
            current_input_devices = get_input_devices()
            
            print(f"Current audio devices: {current_audio_devices}")
            print(f"Current input devices: {current_input_devices}")
            
            # Обновляем статус устройств
            self.update_device_status()
            
            # Функция для проверки и установки устройства
            def set_device_if_available(device_name, setter_func, is_input=False):
                if not device_name:
                    print(f"Device name is empty, skipping")
                    return
                    
                print(f"\nProcessing device: {device_name}")
                print(f"Is input device: {is_input}")
                print(f"Setter function: {setter_func.__name__}")
                
                # Очищаем имя устройства от статуса (Disconnected)
                clean_name = device_name.replace(" (Disconnected)", "")
                print(f"Clean device name: {clean_name}")
                
                # Проверяем, подключено ли устройство
                devices_list = get_input_devices() if is_input else get_audio_devices()
                print(f"Available devices: {devices_list}")
                
                device_connected = False
                device_id = None
                
                # Сначала ищем среди подключенных устройств
                for device in devices_list:
                    print(f"Checking device: {device}")
                    if device[1] == clean_name:
                        device_connected = True
                        device_id = device[0]
                        print(f"Found matching device: {device}")
                        break
                
                # Если устройство не найдено среди подключенных, проверяем отключенные
                if not device_connected:
                    device_type = 'input' if is_input else 'output'
                    print(f"Device not connected, checking disconnected devices: {self.disconnected_devices[device_type]}")
                    if clean_name in self.disconnected_devices[device_type]:
                        device_id = self.disconnected_devices[device_type][clean_name]['id']
                        print(f"Found in disconnected devices with ID: {device_id}")
                
                # Если устройство найдено и подключено, активируем его
                if device_connected and device_id:
                    print(f"Setting device: {clean_name} (ID: {device_id})")
                    try:
                        print(f"Calling {setter_func.__name__} with device_id: {device_id}")
                        setter_func(device_id)
                        print(f"Successfully set device")
                    except Exception as e:
                        print(f"Error setting device: {e}")
                        import traceback
                        print(traceback.format_exc())
                else:
                    print(f"Device {clean_name} is disconnected or not found")
                    show_notification(f"Device {clean_name} is disconnected", "speaker" if not is_input else "microphone")
            
            print("\nApplying profile settings...")
            
            # Применяем настройки профиля
            if 'output_default' in profile:
                print("\nSetting output default device...")
                set_device_if_available(profile['output_default'], set_default_audio_device, False)
                
            if 'output_communication' in profile:
                print("\nSetting output communication device...")
                set_device_if_available(profile['output_communication'], set_default_communication_device, False)
                
            if 'input_default' in profile:
                print("\nSetting input default device...")
                set_device_if_available(profile['input_default'], set_default_input_device, True)
                
            if 'input_communication' in profile:
                print("\nSetting input communication device...")
                set_device_if_available(profile['input_communication'], set_default_input_communication_device, True)
                
            self.current_profile = profile
            print(f"Profile activated: {name}")
            show_notification(f"Profile activated: {name}", "speaker")
            return True
            
        except Exception as e:
            print(f"Error activating profile: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def create_profile_card(self, profile):
        """Создает HTML-карточку для профиля"""
        card = f"""
        <div class="profile-card" id="profile-{profile['name']}">
            <h3>{profile['name']}</h3>
            <div class="profile-details">"""
        
        # Добавляем информацию об устройстах
        if profile.get('output_default'):
            card += f'<div class="device-info">Default Output: {profile["output_default"]}</div>'
        if profile.get('output_communication'):
            card += f'<div class="device-info">Communication Output: {profile["output_communication"]}</div>'
        if profile.get('input_default'):
            card += f'<div class="device-info">Default Input: {profile["input_default"]}</div>'
        if profile.get('input_communication'):
            card += f'<div class="device-info">Communication Input: {profile["input_communication"]}</div>'
        
        # Добавляем статус Activate on Startup
        activate_on_startup = profile.get('activate_on_startup', False)
        startup_status = "Enabled" if activate_on_startup else "Disabled"
        card += f'<div class="device-info">Activate on Startup: {startup_status}</div>'
        
        # Добавляем кнопку удаления
        card += f"""
            </div>
            <button class="delete-btn" onclick="deleteProfile('{profile['name']}')">Delete</button>
        </div>
        """
        return card

# Создаем глобальный экземпляр ProfileManager в начале файла, после определения класса
profile_manager = None

def toggle_sound_volume():
    """Включает/выключает звук"""
    try:
        # Инициализируем COM
        pythoncom.CoInitialize()
        
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        if volume.GetMute() == 0:
            volume.SetMute(1, None)
            show_notification("Sound: OFF", "speaker")
        else:
            volume.SetMute(0, None)
            show_notification("Sound: ON", "speaker")
            
    except Exception as e:
        print(f"Error toggling sound volume: {e}")
    finally:
        # Освобождаем COM
        pythoncom.CoUninitialize()

def monitor_processes():
    """Мониторит процессы и активирует профили при необходимости"""
    global running
    
    activated_apps = set()  # Множество для хранения уже активированных приложений
    
    while running:
        try:
            # Обновляем статус устройств
            profile_manager.update_device_status()
            
            # Проверяем кажды�� профиль
            for profile in profile_manager.get_profiles():
                if not profile.get('trigger_app'):
                    continue
                    
                app_key = profile['trigger_app'].lower()
                app_running = is_process_running(app_key)
                
                if app_running:
                    # В обычном режиме активируем только если приложение не было активировано
                    if app_key not in activated_apps:
                        if activate_profile(profile['name']):
                            show_notification(f"Profile activated: {profile['name']}")
                            activated_apps.add(app_key)
                else:
                    # Если приложение больше не запущено, удаляем его из активированных
                    activated_apps.discard(app_key)
                    
        except Exception as e:
            pass
                
        time.sleep(1)  # Пауза между проверками

def activate_profile(name):
    """Активирует профиль по имени"""
    try:
        profile = None
        for p in profile_manager.profiles:
            if p.get('name') == name:
                profile = p
                break

        if not profile:
            print(f"Profile not found: {name}")
            return False
            
        print(f"Activating profile with settings: {profile}")
        print(f"Current audio devices: {get_audio_devices()}")
        print(f"Current input devices: {get_input_devices()}")
        
        # Обновляем статус устройств
        profile_manager.update_device_status()
        
        # Функция для проверки и установки у��тройства
        def set_device_if_available(device_name, setter_func, is_input=False):
            if not device_name:
                return
            
            print(f"\nProcessing device: {device_name}")
            print(f"Is input device: {is_input}")
            
            # Очищаем имя устройства от статуса (Disconnected)
            clean_name = device_name.replace(" (Disconnected)", "")
            print(f"Clean device name: {clean_name}")
            
            # Проверяем, подключено ли устройство
            devices_list = get_input_devices() if is_input else get_audio_devices()
            print(f"Available devices: {devices_list}")
            
            device_connected = False
            device_id = None
            
            # Сначала ищем среди подключенных устройств
            for device in devices_list:
                print(f"Checking device: {device}")
                if device[1] == clean_name:
                    device_connected = True
                    device_id = device[0]
                    print(f"Found matching device: {device}")
                    break
            
            # Если устройство не найдено среди подключенных, проверяем отклченные
            if not device_connected:
                device_type = 'input' if is_input else 'output'
                print(f"Device not connected, checking disconnected devices: {profile_manager.disconnected_devices[device_type]}")
                if clean_name in profile_manager.disconnected_devices[device_type]:
                    device_id = profile_manager.disconnected_devices[device_type][clean_name]['id']
                    print(f"Found in disconnected devices with ID: {device_id}")
            
            # Если устройство найдено и подключено, активируем его
            if device_connected and device_id:
                print(f"Setting device: {clean_name} (ID: {device_id})")
                setter_func(device_id)
            else:
                print(f"Device {clean_name} is disconnected or not found")
                show_notification(f"Device {clean_name} is disconnected", "speaker" if not is_input else "microphone")
        
        # Применяем настройки профиля
        if profile.get('input_default'):
            print("\nSetting input default device...")
            set_device_if_available(profile['input_default'], set_default_input_device, True)
            
        if profile.get('input_communication'):
            print("\nSetting input communication device...")
            set_device_if_available(profile['input_communication'], set_default_input_communication_device, True)
            
        if profile.get('output_default'):
            print("\nSetting output default device...")
            set_device_if_available(profile['output_default'], set_default_audio_device, False)
            
        if profile.get('output_communication'):
            print("\nSetting output communication device...")
            set_device_if_available(profile['output_communication'], set_default_communication_device, False)
            
        profile_manager.current_profile = profile
        print(f"Profile activated: {name}")
        show_notification(f"Profile activated: {name}", "speaker")
        return True
        
    except Exception as e:
        print(f"Error activating profile: {e}")
        return False

@app.route('/profiles', methods=['GET', 'POST', 'PUT'])
def handle_profiles():
    """Обработчик запросов для работы с профилями"""
    if request.method == 'GET':
        try:
            profiles = profile_manager.get_profiles()
            return jsonify({'status': 'success', 'profiles': profiles})
        except Exception as e:
            print(f"Error loading profiles: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    elif request.method in ['POST', 'PUT']:
        try:
            profile_data = request.get_json(force=True)  # Добавляем force=True для принудительного парсинга JSON
            print(f"Received profile data: {profile_data}")
            
            if not profile_data:
                print("Error: No profile data received")
                return jsonify({'status': 'error', 'message': 'No profile data received'}), 400
            
            if not profile_data.get('name'):
                print("Error: Profile name is required")
                return jsonify({'status': 'error', 'message': 'Profile name is required'}), 400

            result = profile_manager.save_profile(profile_data)
            if result['status'] == 'success':
                return jsonify({'status': 'success', 'message': 'Profile saved successfully'})
            else:
                return jsonify({'status': 'error', 'message': result.get('message', 'Failed to save profile')}), 400
            
        except Exception as e:
            print(f"Error saving profile: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    """Устаревший метод удаления профиля - перенаправляем на новый"""
    try:
        data = request.get_json()
        profile_name = data.get('name')
        
        if not profile_name:
            return jsonify({'status': 'error', 'message': 'Profile name is required'}), 400
            
        # Перенаправляем на новый метод
        return delete_profile_by_name(profile_name)
        
    except Exception as e:
        print(f"Error deleting profile: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/profiles/<profile_name>', methods=['DELETE'])
def delete_profile_by_name(profile_name):
    """Удаляет профиль по имени"""
    try:
        profiles_file = 'profiles.json'
        
        # Декодируем импрофиля из URL
        profile_name = unquote(profile_name)
        
        # Заружаем текущие профили с правильной кодировкой
        if not os.path.exists(profiles_file):
            return jsonify({'status': 'error', 'message': 'Profiles file not found'}), 404
            
        with open(profiles_file, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        
        # Находим и удаляем профиль
        profiles = [p for p in profiles if p['name'] != profile_name]
        
        # Сохраняем обновленный список с правильной кодировкой
        with open(profiles_file, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=4, ensure_ascii=False)
        
        # Обновляем профили в мониторинге процессов
        profile_manager.load_profiles()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"Error deleting profile: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def init_globals():
    """Инициализация глобальных переменных"""
    global profile_manager
    profile_manager = ProfileManager()

def main():
    try:
        # Загружаем настройки
        load_settings()
        
        # Устанавливаем модуль при первом запуске
        install_audio_cmdlets()
        
        init_globals()  # Инициализируем глобальные переменные
        
        global running, devices, input_devices, current_device_index, current_input_device_index
        running = True
        
        # Выводим текущие настройки
        print("\nCurrent hotkey settings:")
        for action, combo in hotkeys.items():
            print(f"{action}: keyboard='{combo['keyboard']}', mouse='{combo['mouse']}'")
        print()
        
        # Создаем слушатель изменений устройств
        device_listener = DeviceChangeListener()
        
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
        
        # Создаем и запускаем системный трей
        try:
            tray = setup_tray()
            app.tray = tray  # Сохраняем ссылку на трей в приложении Flask
            tray_thread = Thread(target=lambda: tray.run(), daemon=True)
            tray_thread.start()
            print("Tray icon started")
        except Exception as e:
            print(f"Error starting tray: {e}")
            return
        
        # Запускаем отслеживание клавиатуры и мыши
        try:
            tracker = KeyboardMouseTracker()
            tracker.start()
            print("Mouse and keyboard tracking started")

            # Запускаем обработчик горячих клавиш
            hotkey_thread = Thread(target=lambda: handle_hotkeys(tracker), daemon=True)
            hotkey_thread.start()
            print("Hotkey handler started")
        except Exception as e:
            print(f"Error starting input tracking: {e}")
            return

        # Запускаем мониторинг процессов
        try:
            process_monitor_thread = Thread(target=monitor_processes, daemon=True)
            process_monitor_thread.start()
            print("Process monitoring started")
        except Exception as e:
            print(f"Error starting process monitor: {e}")
            return

        # Запускаем Flask сервер в отдельном потоке
        try:
            flask_thread = Thread(target=lambda: app.run(host='127.0.0.1', port=5000, debug=False), daemon=True)
            flask_thread.start()
            print("Flask server started")
        except Exception as e:
            print(f"Error starting Flask server: {e}")
            return
        
        try:
            while running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            try:
                device_listener.stop()
                tray.stop()
                tracker.stop()
                running = False
            except Exception as e:
                print(f"Error during shutdown: {e}")
                
    except Exception as e:
        print(f"Critical error in main: {e}")
        import traceback
        traceback.print_exc()

def install_audio_cmdlets():
    """Устанавливает модуль AudioDeviceCmdlets при первом запуске"""
    try:
        powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        
        # Проверяем наличие модуля
        check_script = """
        if (Get-Module -ListAvailable -Name AudioDeviceCmdlets) {
            Write-Output "INSTALLED"
        } else {
            Write-Output "NOT_INSTALLED"
        }
        """
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            [powershell_path, "-Command", check_script],
            capture_output=True,
            text=True,
            encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        
        if "NOT_INSTALLED" in result.stdout:
            print("Installing AudioDeviceCmdlets module...")
            show_notification("Installing required module...", "speaker")
            
            # Устанавливаем модуль
            install_script = """
            Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Force
            Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
            Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser
            """
            
            result = subprocess.run(
                [powershell_path, "-Command", install_script],
                capture_output=True,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW,
                startupinfo=startupinfo
            )
            
            if result.returncode == 0:
                show_notification("Module installed successfully!", "speaker")
                print("AudioDeviceCmdlets module installed successfully")
            else:
                show_notification("Failed to install module", "speaker")
                print(f"Error installing module: {result.stderr}")
                
    except Exception as e:
        print(f"Error checking/installing AudioDeviceCmdlets: {e}")

def get_default_output_device():
    """Получает текущее устройство вывода по умолчанию"""
    try:
        pythoncom.CoInitialize()
        try:
            devices = AudioUtilities.GetSpeakers()
            if devices:
                return devices.GetId()
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error getting default output device: {e}")
    return None

def get_default_communication_output_device():
    """Получает текущее устройство вывода для связи по умолчанию"""
    try:
        pythoncom.CoInitialize()
        try:
            devices = AudioUtilities.GetSpeakers()
            if devices:
                return devices.GetId()
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error getting default communication output device: {e}")
    return None

def get_default_input_device():
    """Получает текущее устройство ввода по умолчанию"""
    try:
        pythoncom.CoInitialize()
        try:
            devices = AudioUtilities.GetMicrophone()
            if devices:
                return devices.GetId()
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error getting default input device: {e}")
    return None

def get_default_communication_input_device():
    """Получает текущее устройство ввода для с��язи ��о умолчанию"""
    try:
        pythoncom.CoInitialize()
        try:
            devices = AudioUtilities.GetMicrophone()
            if devices:
                return devices.GetId()
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"Error getting default communication input device: {e}")
    return None

def is_process_running(process_path):
    """Пр��веряет, запущен ли процесс"""
    try:
        if not process_path:
            return False
            
        process_name = os.path.basename(process_path).lower()
        
        running_processes = list(psutil.process_iter(['name', 'exe']))
        
        for proc in running_processes:
            try:
                proc_info = proc.info
                
                if proc_info['exe']:
                    proc_exe = proc_info['exe'].lower()
                    proc_basename = os.path.basename(proc_exe)
                    
                    if proc_basename == process_name or proc_exe == process_path.lower():
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return False
        
    except Exception as e:
        return False

def is_device_connected(device_name, devices_list):
    """Проверяет, подключено ли устройство"""
    return any(device[1] == device_name for device in devices_list)

@app.route("/browser_closed", methods=["POST"])
def browser_closed():
    """Обработчик закрытия окна браузера"""
    try:
        # Останвливаем сервр
        if hasattr(app, 'tray') and app.tray:
            app.tray.stop_server()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/save_profile", methods=["POST"])
def save_profile_route():
    """Сораняет профиль устройств"""
    try:
        profile_data = request.json
        if not profile_data:
            return jsonify({
                "status": "error",
                "message": "No profile data received"
            })

        result = profile_manager.save_profile(profile_data)
        return jsonify(result)
    except Exception as e:
        print(f"Error saving profile: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/get_device_states", methods=["GET"])
def get_device_states():
    """Возвращает текущие состояния всех устройств"""
    try:
        output_states = {}
        input_states = {}
        
        # Состояния устройств вывода
        for device in devices:
            output_states[str(device[0])] = {
                'enabled': str(device[0]) in enabled_devices,
                'connected': True
            }
        
        # Добавляем отключенные устройства вывода
        for device_name, device_info in profile_manager.disconnected_devices['output'].items():
            device_id = str(device_info['id'])
            if device_id not in output_states:
                output_states[device_id] = {
                    'enabled': device_id in enabled_devices,
                    'connected': False
                }
        
        # Состояния устройств ввода
        for device in input_devices:
            input_states[str(device[0])] = {
                'enabled': str(device[0]) in enabled_input_devices,
                'connected': True
            }
        
        # Добавляем отключенные устройства ввода
        for device_name, device_info in profile_manager.disconnected_devices['input'].items():
            device_id = str(device_info['id'])
            if device_id not in input_states:
                input_states[device_id] = {
                    'enabled': device_id in enabled_input_devices,
                    'connected': False
                }
        
        return jsonify({
            "status": "success",
            "output_devices": output_states,
            "input_devices": input_states
        })
    except Exception as e:
        print(f"Error in get_device_states: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/select_app", methods=["GET"])
def select_app():
    """Открывает диалог выбора приложения"""
    try:
        root = tk.Tk()
        root.withdraw()  # Скрываем основное окно
        
        file_path = filedialog.askopenfilename(
            title="Select Application",
            filetypes=[
                ("Executable files", "*.exe"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            return jsonify({
                "status": "success",
                "path": file_path
            })
        else:
            return jsonify({
                "status": "cancelled"
            })
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route("/activate_profile", methods=["POST"])
def activate_profile_route():
    """Активирует профиль через API"""
    try:
        data = request.json
        profile_name = data.get('profile_name')
        
        if not profile_name:
            return jsonify({
                "status": "error",
                "message": "Profile name is required"
            })
            
        success = activate_profile(profile_name)
        return jsonify({
            "status": "success" if success else "error"
        })
        
    except Exception as e:
        print(f"Error in activate_profile route: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        })

if __name__ == '__main__':
    main()
