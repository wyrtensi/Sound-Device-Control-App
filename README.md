Playback Device Switch Sound Volume

Control volume adjustment, music playback, and playback device switching using keyboard or mouse hotkeys. It utilizes Python notifications and HTML/JS for configuration (interface) and is accessible from the system tray. This program is designed exclusively for Windows and uses Python + PowerShell + HTML + JS.

It filters microphones by the name "microphone" to exclude them from the device list. Simply rename your microphones to "microphone" to achieve this.

Here is the list of required packages for this program. You can install them using CMD:

pip install flask pynput pycaw pywin32 mouse pystray pillow comtypes keyboard six

Additionally, you will need the PowerShell module AudioDeviceCmdlets, which the program will attempt to install automatically during the first run. If this does not happen, you can manually install it via PowerShell with administrator privileges:

Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser





