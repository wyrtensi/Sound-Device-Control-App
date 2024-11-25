Volume control and playback device switch with hotkey and mouse.

Uses python notifications.

win+mouse scroll for volume control.

win+page up, win+page down for playback device switch.

Tray icon to show its launched and be able to close it without using task manager.

Requires requirements to be installed via cmd:
pip install pystray pillow
pip install keyboard
pip install mouse
pip install pycaw
pip install pyinstaller
pip install comtypes

Requires module to be installed via powershell(administrative):
Install-Module -Name AudioDeviceCmdlets -Force -SkipPublisherCheck
