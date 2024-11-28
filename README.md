Sound Device Switch Sound Volume
![image](https://github.com/user-attachments/assets/02de48b0-698b-416b-8cc5-6d1eea045e8e)

Control volume adjustment, media button controls, and playback device switching using keyboard or mouse hotkeys. It utilizes Python notifications and HTML/JS for configuration (interface) and is accessible from the system tray. This program is designed exclusively for Windows and uses Python + PowerShell + HTML + JS + CSS. Tested on python 3.12.

It filters microphones by the name "microphone" to exclude them from the device list. Simply rename your microphones to "microphone" to achieve this.
![image](https://github.com/user-attachments/assets/2a08f2ed-6898-49d4-8a4f-29a0213d7091)

Here is the list of required packages for this program. You can install them using CMD:

pip install flask pynput pycaw pywin32 mouse pystray pillow comtypes keyboard six
![image](https://github.com/user-attachments/assets/5ca2f87c-1ba6-42d1-8009-cddb9a5b5da9)

Additionally, you will need the PowerShell module AudioDeviceCmdlets, which the program will attempt to install automatically during the first run. If this does not happen, you can manually install it via PowerShell with administrator privileges:

Install-Module -Name AudioDeviceCmdlets -Force -Scope CurrentUser
![image](https://github.com/user-attachments/assets/828751e2-8673-4f8b-a9f5-1fbd3b17c32f)

![image](https://github.com/user-attachments/assets/64039e2c-595a-4502-afbf-e137b6110e13)

![image](https://github.com/user-attachments/assets/c99c136a-624b-4504-b2a9-8f88d0f5464b)

![image](https://github.com/user-attachments/assets/f228e526-6a54-436f-be4c-838697a33d8e)




