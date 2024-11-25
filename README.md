Sound volume control and playback device switch with hotkey and mouse. Uses python notifications. For Windows. Uses python+powershell.

Filters microphones by name "microphone" to exclude em from device list. Simply rename your microphones to "microphone".




win+mouse scroll for sound volume control.

win+page up, win+page down for playback device switch.




Tray icon to show its launched and be able to close it without using task manager.




Requires requirements to be installed via cmd:

pip install pystray pillow keyboard mouse pycaw pyinstaller comtypes




Requires module to be installed via powershell(administrative):

Install-Module -Name AudioDeviceCmdlets -Force -SkipPublisherCheck

