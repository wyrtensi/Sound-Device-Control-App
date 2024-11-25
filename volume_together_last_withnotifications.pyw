import subprocess
import time
import keyboard
import mouse
import ctypes
import tkinter as tk
from threading import Thread

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
    # Запуск PowerShell в скрытом режиме с флагом CREATE_NO_WINDOW
    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW  # Скрываем окно PowerShell
    )
    # Обрабатываем вывод, разделяя по строкам
    devices = result.stdout.strip().split('\n')
    # Фильтруем устройства, исключая те, что содержат слово "microphone" в названии
    devices = [device.split(',') for device in devices if device.strip() and "microphone" not in device.lower()]
    print(f"Получены устройства: {devices}")  # Отладочный вывод
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
        creationflags=subprocess.CREATE_NO_WINDOW  # Скрываем окно PowerShell
    )

# Обработчик событий мыши для регулировки громкости
def on_event(event):
    if keyboard.is_pressed("win"):
        try:
            # Проверяем направление прокрутки
            if event.delta > 0:  # Прокрутка вверх
                send_volume_message(APPCOMMAND_VOLUME_UP)
            elif event.delta < 0:  # Прокрутка вниз
                send_volume_message(APPCOMMAND_VOLUME_DOWN)
        except AttributeError:
            # Игнорируем другие типы событий, которые не имеют delta
            pass

# Функция для отображения уведомления в правом нижнем углу
def show_notification(device_name):
    root = tk.Tk()
    root.overrideredirect(True)  # Убираем заголовок окна
    
    # Получаем размеры экрана
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Задаем размер окна
    window_width = 350
    window_height = 60
    
    # Расчет позиции для правого нижнего угла
    x_position = screen_width - window_width - 10
    y_position = screen_height - window_height - 80
    
    # Устанавливаем геометрию окна
    root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
    
    # Устанавливаем окно поверх других окон
    root.attributes("-topmost", 1)
    
    # Устанавливаем темный фон
    root.configure(bg="#333333")
    
    # Создаем метку с текстом уведомления, делаем текст жирным
    label = tk.Label(root, text=f"Переключено на: {device_name}", font=("Arial", 12, "bold"), fg="white", bg="#333333")
    label.pack(expand=True)

    # Закрываем окно через 1 секунду (1000 миллисекунд)
    root.after(1000, root.destroy)
    root.mainloop()

# Основная логика для переключения аудиоустройств
def main():
    devices = get_audio_devices()
    
    if not devices or len(devices) == 0:
        print("Нет доступных устройств для переключения.")
        return

    # Получаем список индексов устройств
    devices_with_indexes = [(device[0], device[1]) for device in devices if len(device) == 2]

    if len(devices_with_indexes) == 0:
        print("Нет устройств для переключения.")
        return

    print(f"Устройства вывода: {devices_with_indexes}")  # Отладочный вывод

    current_device_index = 0
    # Устанавливаем глобальный обработчик событий мыши для регулировки громкости
    mouse.hook(on_event)

    # Основной цикл для переключения устройств по клавишам
    while True:
        if keyboard.is_pressed('win+page up'):
            # Переключаем на предыдущее устройство
            current_device_index = (current_device_index - 1) % len(devices_with_indexes)
            set_default_audio_device(devices_with_indexes[current_device_index][0])
            print(f"Переключено на: {devices_with_indexes[current_device_index][1]}")

            # Показываем уведомление в отдельном потоке
            Thread(target=show_notification, args=(devices_with_indexes[current_device_index][1],)).start()

            time.sleep(0.5)
        elif keyboard.is_pressed('win+page down'):
            # Переключаем на следующее устройство
            current_device_index = (current_device_index + 1) % len(devices_with_indexes)
            set_default_audio_device(devices_with_indexes[current_device_index][0])
            print(f"Переключено на: {devices_with_indexes[current_device_index][1]}")

            # Показываем уведомление в отдельном потоке
            Thread(target=show_notification, args=(devices_with_indexes[current_device_index][1],)).start()

            time.sleep(0.5)
        
        time.sleep(0.1)  # Пауза между проверками нажатий клавиш

if __name__ == "__main__":
    main()