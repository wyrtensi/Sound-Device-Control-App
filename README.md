Playback Device Switch Sound Volume

Управление регулировкой громкости и переключение устройств воспроизведения горячими клавишами клавиатуры или мыши. Использует уведомления python. html, js для настройки (интерфейс), доступна в трее. Только для Windows. Использует python+powershell+html+js.

Фильтрует микрофоны по имени "microphone" чтобы исключить их из списка устройств. Просто переименуйте свои микрофоны в "microphone".


Вот список необходимых пакетов для работы этой программы. Вы можете установить их с помощью cmd:

pip install flask pynput pycaw pywin32 mouse pystray pillow comtypes

Также вам потребуется PowerShell модуль AudioDeviceCmdlets, который программа попытается установить автоматически при первом запуске. Если этого не произойдет, вы можете установить его вручную через PowerShell с правами администратора:

Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser

