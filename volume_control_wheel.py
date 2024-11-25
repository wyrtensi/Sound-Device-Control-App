import keyboard
import mouse
import ctypes
import time

# Константы Windows для отправки сообщений
WM_APPCOMMAND = 0x319
APPCOMMAND_VOLUME_UP = 0x0a
APPCOMMAND_VOLUME_DOWN = 0x09

# Получение главного окна (для вызова индикатора громкости)
def send_volume_message(app_command):
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.SendMessageW(hwnd, WM_APPCOMMAND, 0, app_command * 0x10000)

# Обработчик событий мыши
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

def main():
    print("Volume control using Win + Mouse Scroll is running...")

    # Устанавливаем глобальный обработчик событий мыши
    mouse.hook(on_event)

    # Оставляем программу работать
    try:
        print("Press Ctrl+C to exit.")
        while True:
            time.sleep(1)  # Спящий режим для минимизации нагрузки
    except KeyboardInterrupt:
        print("Program terminated.")
        mouse.unhook_all()  # Отключаем обработчики при завершении

if __name__ == "__main__":
    main()
