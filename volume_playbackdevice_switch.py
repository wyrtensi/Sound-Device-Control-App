import subprocess
import time
import keyboard

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
    result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True)
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
    subprocess.run(["powershell", "-Command", ps_script])

# Основная логика
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
    while True:
        if keyboard.is_pressed('win+page up'):
            # Переключаем на предыдущее устройство
            current_device_index = (current_device_index - 1) % len(devices_with_indexes)
            set_default_audio_device(devices_with_indexes[current_device_index][0])
            print(f"Переключено на: {devices_with_indexes[current_device_index][1]}")
            time.sleep(0.5)
        elif keyboard.is_pressed('win+page down'):
            # Переключаем на следующее устройство
            current_device_index = (current_device_index + 1) % len(devices_with_indexes)
            set_default_audio_device(devices_with_indexes[current_device_index][0])
            print(f"Переключено на: {devices_with_indexes[current_device_index][1]}")
            time.sleep(0.5)
        time.sleep(0.1)

if __name__ == "__main__":
    main()
