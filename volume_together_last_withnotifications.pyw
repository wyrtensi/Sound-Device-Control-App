import subprocess
import time
import keyboard
import mouse
import ctypes
import tkinter as tk
from threading import Thread
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw
import os

# Константы Windows для отправки сообщений
WM_APPCOMMAND = 0x319
APPCOMMAND_VOLUME_UP = 0x0a
APPCOMMAND_VOLUME_DOWN = 0x09

# Получение главного окна (для вызова индикатора громкости)
def send_volume_message(app_command):
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.SendMessageW(hwnd, WM_APPCOMMAND, 0, app_command * 0x10000)

# Функция для получения списка аудиоустройств через PowerShell
def get_audio_devices():
    ps_script = """
    try {
        $devices = Get-AudioDevice -List
        $devices | ForEach-Object { "$($_.Index),$($_.Name)" }
    } catch {
        Write-Host "Ошибка при получении списка устройств"
    }
    """
    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    devices = result.stdout.strip().split('\n')
    devices = [device.split(',') for device in devices if device.strip() and "microphone" not in device.lower()]
    print(f"Получены устройства: {devices}")
    return devices

# Функция для установки устройства по умолчанию через PowerShell
def set_default_audio_device(device_index):
    ps_script = f"""
    try {{
        $device = Get-AudioDevice -List | Where-Object {{ $_.Index -eq {device_index} }}
        if ($device) {{
            Set-AudioDevice -Index $device.Index
            Write-Host "Переключено на: {device_index}"
        }} else {{
            Write-Host "Устройство не найдено!"
        }}
    }} catch {{
        Write-Host "Ошибка при установке устройства по умолчанию"
    }}
    """
    subprocess.run(
        ["powershell", "-Command", ps_script],
        creationflags=subprocess.CREATE_NO_WINDOW
    )

# Обработчик событий мыши для регулировки громкости
def on_event(event):
    if keyboard.is_pressed("win"):
        try:
            if event.delta > 0:
                send_volume_message(APPCOMMAND_VOLUME_UP)
            elif event.delta < 0:
                send_volume_message(APPCOMMAND_VOLUME_DOWN)
        except AttributeError:
            pass

# Функция для отображения уведомления
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

# Функция для выхода из программы
def quit_program(icon):
    icon.stop()  # Останавливаем значок в трее
    os._exit(0)  # Полное завершение программы

# Функция для создания значка в трее
def create_tray_icon():
    def create_image(width, height, color1, color2):
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle([width // 4, height // 4, 3 * width // 4, 3 * height // 4], fill=color2)
        return image

    icon_image = create_image(64, 64, "white", "black")
    menu = Menu(MenuItem("Выход", quit_program))
    icon = Icon("AudioSwitcher", icon_image, "Audio Switcher", menu)
    return icon

# Основная логика переключения аудиоустройств
def main():
    devices = get_audio_devices()
    if not devices or len(devices) == 0:
        print("Нет доступных устройств для переключения.")
        return

    devices_with_indexes = [(device[0], device[1]) for device in devices if len(device) == 2]
    if len(devices_with_indexes) == 0:
        print("Нет устройств для переключения.")
        return

    print(f"Устройства вывода: {devices_with_indexes}")

    current_device_index = 0
    mouse.hook(on_event)

    tray_icon = create_tray_icon()
    Thread(target=tray_icon.run, daemon=True).start()

    while True:
        if keyboard.is_pressed('win+page up'):
            current_device_index = (current_device_index - 1) % len(devices_with_indexes)
            set_default_audio_device(devices_with_indexes[current_device_index][0])
            Thread(target=show_notification, args=(devices_with_indexes[current_device_index][1],)).start()
            time.sleep(0.5)
        elif keyboard.is_pressed('win+page down'):
            current_device_index = (current_device_index + 1) % len(devices_with_indexes)
            set_default_audio_device(devices_with_indexes[current_device_index][0])
            Thread(target=show_notification, args=(devices_with_indexes[current_device_index][1],)).start()
            time.sleep(0.5)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
