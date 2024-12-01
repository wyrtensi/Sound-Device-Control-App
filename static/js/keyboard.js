class VirtualKeyboard {
    constructor() {
        this.selectedKeys = {
            keyboard: new Set(),
            mouse: new Set()
        };
        this.currentInput = null;
        this.modal = document.getElementById('keyboardModal');
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.querySelectorAll('.keyboard-modal .key').forEach(key => {
            key.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleKey(key);
            });
        });

        document.getElementById('applyHotkey').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.applyHotkey();
        });

        document.getElementById('cancelHotkey').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.hideKeyboard();
        });

        document.getElementById('clearHotkey').addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.clearSelection();
        });
    }

    showKeyboard(inputElement) {
        this.currentInput = inputElement;
        this.clearSelection();
        
        // Load existing keys
        const keyboard = this.currentInput.getAttribute('data-keyboard');
        const mouse = this.currentInput.getAttribute('data-mouse');
        
        if (keyboard && keyboard !== "None") {
            keyboard.split('+').forEach(key => {
                const keyElement = this.findKeyElement(key.trim());
                if (keyElement) {
                    this.selectedKeys.keyboard.add(key.trim());
                    keyElement.classList.add('active');
                }
            });
        }
        
        if (mouse && mouse !== "None") {
            mouse.split('+').forEach(key => {
                const keyElement = this.findKeyElement(key.trim());
                if (keyElement) {
                    this.selectedKeys.mouse.add(key.trim());
                    keyElement.classList.add('active');
                }
            });
        }

        this.modal.style.display = 'block';
    }

    hideKeyboard() {
        this.modal.style.display = 'none';
        this.clearSelection();
        this.currentInput = null;
    }

    isMouseKey(keyName) {
        const mouseKeys = new Set([
            'scrollup', 'scrolldown', 
            'mouseleft', 'mouseright', 'mousemiddle',
            'lmb', 'rmb', 'mmb'
        ]);
        return mouseKeys.has(keyName.toLowerCase());
    }

    toggleKey(keyElement) {
        const keyName = keyElement.getAttribute('data-key');
        const normalizedKey = this.normalizeKeyName(keyName);
        const isMouseKey = this.isMouseKey(normalizedKey);
        const keySet = isMouseKey ? 'mouse' : 'keyboard';
        
        if (this.selectedKeys[keySet].has(normalizedKey)) {
            keyElement.classList.remove('active');
            this.selectedKeys[keySet].delete(normalizedKey);
        } else {
            keyElement.classList.add('active');
            this.selectedKeys[keySet].add(normalizedKey);
        }
    }

    findKeyElement(keyName) {
        const normalizedKey = this.normalizeKeyName(keyName);
        return Array.from(document.querySelectorAll('.keyboard-modal .key')).find(
            key => this.normalizeKeyName(key.getAttribute('data-key')) === normalizedKey
        );
    }

    normalizeKeyName(keyName) {
        if (!keyName) return '';
        
        const keyMap = {
            'scrollup': 'scrollup',
            'scrolldown': 'scrolldown',
            'mouseleft': 'mouseleft',
            'mouseright': 'mouseright',
            'mousemiddle': 'mousemiddle',
            'control': 'ctrl',
            'windows': 'win',
            'command': 'win',
            'return': 'enter',
            'escape': 'esc',
            'lmb': 'mouseleft',
            'rmb': 'mouseright',
            'mmb': 'mousemiddle'
        };

        const normalized = keyName.toLowerCase();
        return keyMap[normalized] || normalized;
    }

    clearSelection() {
        document.querySelectorAll('.keyboard-modal .key.active').forEach(key => {
            key.classList.remove('active');
        });
        this.selectedKeys.keyboard.clear();
        this.selectedKeys.mouse.clear();
    }

    applyHotkey() {
        if (this.currentInput) {
            const action = this.currentInput.getAttribute('data-action');
            
            // Form key strings
            const keyboardKeys = Array.from(this.selectedKeys.keyboard);
            const mouseKeys = Array.from(this.selectedKeys.mouse);
            
            // Update attributes and input value
            this.currentInput.setAttribute('data-keyboard', keyboardKeys.join('+') || "None");
            this.currentInput.setAttribute('data-mouse', mouseKeys.join('+') || "None");
            
            // Update displayed value
            const allKeys = [...keyboardKeys, ...mouseKeys];
            this.currentInput.value = allKeys.length > 0 ? allKeys.join('+') : "None";

            // Send separated data to server
            fetch('/update_hotkey', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: action,
                    keyboard: keyboardKeys.join('+') || "None",
                    mouse: mouseKeys.join('+') || "None"
                })
            });
        }
        this.hideKeyboard();
    }
}

class ProfileManager {
    constructor() {
        this.currentProfile = null;
        this.profiles = [];
        this.setupEventListeners();
        this.loadProfiles();
    }

    setupEventListeners() {
        // Wait for the DOM to be fully loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeElements());
        } else {
            this.initializeElements();
        }
    }

    initializeElements() {
        const createProfileBtn = document.getElementById('createProfileBtn');
        if (createProfileBtn) {
            createProfileBtn.addEventListener('click', () => this.createNewProfile());
        }

        const saveProfileBtn = document.getElementById('saveProfileBtn');
        if (saveProfileBtn) {
            saveProfileBtn.addEventListener('click', () => this.saveProfile());
        }

        const profileHotkeyInput = document.getElementById('profileHotkey');
        if (profileHotkeyInput) {
            const keyboard = new VirtualKeyboard();
            profileHotkeyInput.addEventListener('focus', () => keyboard.showKeyboard(profileHotkeyInput));
        }

        const selectTriggerAppBtn = document.getElementById('selectTriggerAppBtn');
        if (selectTriggerAppBtn) {
            selectTriggerAppBtn.addEventListener('click', () => this.selectTriggerApp());
        }

        const clearTriggerAppBtn = document.getElementById('clearTriggerAppBtn');
        if (clearTriggerAppBtn) {
            clearTriggerAppBtn.addEventListener('click', () => this.clearTriggerApp());
        }

        const cancelProfileBtn = document.getElementById('cancelProfileBtn');
        if (cancelProfileBtn) {
            cancelProfileBtn.addEventListener('click', () => this.hideProfileEditor());
        }
    }

    async loadProfiles() {
        try {
            const response = await fetch('/profiles');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data.status === 'success') {
                this.profiles = data.profiles || [];
                this.renderProfiles();
            }
        } catch (error) {
            console.error('Error loading profiles:', error);
            showNotification('Error loading profiles', true);
        }
    }

    async saveProfile() {
        const profileName = document.getElementById('profileName').value.trim();
        if (!profileName) {
            showNotification('Please enter profile name', true);
            return;
        }

        const outputDefault = document.getElementById('outputDefaultDevice').value;
        const outputComm = document.getElementById('outputCommDevice').value;
        const inputDefault = document.getElementById('inputDefaultDevice').value;
        const inputComm = document.getElementById('inputCommDevice').value;
        const hotkeyInput = document.getElementById('profileHotkey');
        const triggerAppPath = document.getElementById('trigger-app-path').textContent;

        const profile = {
            name: profileName,
            output_default: outputDefault,
            output_communication: outputComm,
            input_default: inputDefault,
            input_communication: inputComm,
            hotkey: {
                keyboard: hotkeyInput.dataset.keyboard || "None",
                mouse: hotkeyInput.dataset.mouse || "None"
            },
            trigger_app: triggerAppPath !== 'No application selected' ? triggerAppPath : null
        };

        try {
            const existingProfile = this.profiles.find(p => p.name === profileName);
            const method = existingProfile ? 'PUT' : 'POST';

            console.log('Sending profile data:', profile);

            const response = await fetch('/profiles', {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(profile)
            });

            if (!response.ok) {
                throw new Error('Failed to save profile');
            }

            const result = await response.json();
            if (result.status === 'success') {
                await this.loadProfiles();
                this.hideProfileEditor();
                showNotification('Profile saved successfully');
            } else {
                throw new Error(result.message || 'Failed to save profile');
            }
        } catch (error) {
            console.error('Error saving profile:', error);
            showNotification('Error saving profile: ' + error.message, true);
        }
    }

    async activateProfile(name) {
        try {
            const response = await fetch(`/profiles/${name}/activate`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to activate profile');
            }

            const data = await response.json();
            if (data.status === 'success') {
                this.currentProfile = this.profiles.find(p => p.name === name);
                this.renderProfiles();
                showNotification(`Profile activated: ${name}`);
            } else {
                throw new Error(data.message || 'Failed to activate profile');
            }
        } catch (error) {
            console.error('Error activating profile:', error);
            showNotification('Error activating profile', true);
        }
    }

    async deleteProfile(profileName) {
        try {
            const response = await fetch(`/profiles/${profileName}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Failed to delete profile');
            }

            const result = await response.json();
            if (result.status === 'success') {
                // Обновляем список профилей
                const profilesResponse = await fetch('/profiles');
                const profilesData = await profilesResponse.json();
                if (profilesData.status === 'success') {
                    profiles = profilesData.profiles;
                    await renderProfiles();
                    showNotification('Profile deleted successfully');
                }
            } else {
                throw new Error(result.message || 'Failed to delete profile');
            }
        } catch (error) {
            console.error('Error deleting profile:', error);
            showNotification('Error deleting profile: ' + error.message, true);
        }
    }

    getDeviceName(deviceId, devices) {
        const device = devices.find(([id, name]) => id === deviceId);
        return device ? device[1] : 'Not Selected';
    }

    getFileName(path) {
        if (!path) return '';
        const parts = path.split(/[/\\]/);
        return parts[parts.length - 1];
    }

    async renderProfiles() {
        const container = document.querySelector('.profile-cards');
        
        // Получаем списки устройств
        let outputDevices = [];
        let inputDevices = [];
        try {
            const outputResponse = await fetch('/get_output_devices');
            const outputResult = await outputResponse.json();
            if (outputResult.status === 'success') {
                outputDevices = outputResult.devices;
            }

            const inputResponse = await fetch('/get_input_devices');
            const inputResult = await inputResponse.json();
            if (inputResult.status === 'success') {
                inputDevices = inputResult.devices;
            }
        } catch (error) {
            console.error('Error loading devices:', error);
        }

        // Сохраняем карточку создания нового профиля
        container.innerHTML = `
            <div class="profile-card new-profile" id="newProfileCard">
                <div class="card-content" onclick="createNewProfile()">
                    <div class="card-title">Create New Profile</div>
                    <button class="create-profile-btn">
                        <span class="plus-icon">+</span>
                    </button>
                </div>
            </div>
        `;

        this.profiles.forEach(profile => {
            const card = document.createElement('div');
            card.className = 'profile-card existing-profile';
            if (this.currentProfile && this.currentProfile.name === profile.name) {
                card.classList.add('active');
            }
            
            const hotkeyText = `${profile.hotkey.keyboard !== 'None' ? profile.hotkey.keyboard : ''}${
                profile.hotkey.mouse !== 'None' ? ' + ' + profile.hotkey.mouse : ''}`;

            const outputDefaultName = this.getDeviceName(profile.output_default, outputDevices);
            const outputCommName = this.getDeviceName(profile.output_communication, outputDevices);
            const inputDefaultName = this.getDeviceName(profile.input_default, inputDevices);
            const inputCommName = this.getDeviceName(profile.input_communication, inputDevices);

            card.innerHTML = `
                <div class="card-content">
                    <div class="profile-info">
                        <div class="profile-name">${profile.name}</div>
                        <div class="device-info">
                            <div><span class="device-type">Default Output:</span> ${outputDefaultName}</div>
                            ${outputCommName !== 'Not Selected' ? `<div><span class="device-type">Communication Output:</span> ${outputCommName}</div>` : ''}
                            <div><span class="device-type">Default Input:</span> ${inputDefaultName}</div>
                            ${inputCommName !== 'Not Selected' ? `<div><span class="device-type">Communication Input:</span> ${inputCommName}</div>` : ''}
                            ${profile.trigger_app ? `<div><span class="device-type">Trigger App:</span> ${this.getFileName(profile.trigger_app)}</div>` : ''}
                        </div>
                        ${hotkeyText ? `<div class="hotkey-badge">${hotkeyText}</div>` : ''}
                    </div>
                    <div class="card-actions">
                        <button class="delete-btn" onclick="event.stopPropagation(); deleteProfile('${profile.name}')">
                            Delete
                        </button>
                    </div>
                </div>
            `;

            // Добавляем обработчик клика для редактирования
            card.addEventListener('click', () => {
                this.showProfileEditor(profile);
            });

            container.appendChild(card);
        });
    }

    createNewProfile() {
        this.currentProfile = null;
        this.showProfileEditor();
    }

    editProfile(profile) {
        this.currentProfile = profile;
        this.showProfileEditor(profile);
    }

    async showProfileEditor(profile = null) {
        const editor = document.getElementById('profileEditor');
        if (!editor) {
            console.error('Profile editor not found');
            return;
        }

        // Заполняем базовые поля
        document.getElementById('profileName').value = profile ? profile.name : '';
        
        const hotkeyInput = document.getElementById('profileHotkey');
        if (hotkeyInput) {
            if (profile && profile.hotkey) {
                hotkeyInput.dataset.keyboard = profile.hotkey.keyboard;
                hotkeyInput.dataset.mouse = profile.hotkey.mouse;
            } else {
                hotkeyInput.dataset.keyboard = 'None';
                hotkeyInput.dataset.mouse = 'None';
            }
            updateHotkeyInputValue(hotkeyInput);
        }

        // Обновляем путь к приложению
        const triggerAppPath = document.getElementById('trigger-app-path');
        if (triggerAppPath) {
            console.log('Setting trigger app path:', profile?.trigger_app);
            triggerAppPath.textContent = profile && profile.trigger_app ? profile.trigger_app : 'No application selected';
        } else {
            console.error('trigger-app-path element not found');
        }

        // Показываем редактор
        editor.style.display = 'block';
        editor.scrollIntoView({ behavior: 'smooth', block: 'start' });

        console.log('Loading profile:', profile);  // Отладочный вывод

        // Асинхронно загружаем списки устройств
        try {
            const [outputResponse, inputResponse] = await Promise.all([
                fetch('/get_output_devices'),
                fetch('/get_input_devices')
            ]);

            if (outputResponse.ok && inputResponse.ok) {
                const outputData = await outputResponse.json();
                const inputData = await inputResponse.json();

                if (outputData.status === 'success' && inputData.status === 'success') {
                    // Заполняем селекты устройств вывода
                    const outputDefaultSelect = document.getElementById('outputDefaultDevice');
                    const outputCommSelect = document.getElementById('outputCommDevice');
                    
                    if (outputDefaultSelect && outputCommSelect) {
                        outputDefaultSelect.innerHTML = '<option value="">Not Selected</option>';
                        outputCommSelect.innerHTML = '<option value="">Not Selected</option>';
                        
                        outputData.devices.forEach(device => {
                            const option = document.createElement('option');
                            option.value = device[0];  // ID устройства
                            option.textContent = device[1];  // Имя устройства
                            
                            const optionComm = option.cloneNode(true);
                            outputDefaultSelect.appendChild(option);
                            outputCommSelect.appendChild(optionComm);
                        });
                    }

                    // Заполняем селекты устройств ввода
                    const inputDefaultSelect = document.getElementById('inputDefaultDevice');
                    const inputCommSelect = document.getElementById('inputCommDevice');
                    
                    if (inputDefaultSelect && inputCommSelect) {
                        inputDefaultSelect.innerHTML = '<option value="">Not Selected</option>';
                        inputCommSelect.innerHTML = '<option value="">Not Selected</option>';
                        
                        inputData.devices.forEach(device => {
                            const option = document.createElement('option');
                            option.value = device[0];  // ID устройства
                            option.textContent = device[1];  // Имя устройства
                            
                            const optionComm = option.cloneNode(true);
                            inputDefaultSelect.appendChild(option);
                            inputCommSelect.appendChild(optionComm);
                        });
                    }

                    // Устанавливаем значения из профиля, если он есть
                    if (profile) {
                        console.log('Setting device values:', {  // Отладочный вывод
                            output_default: profile.output_default,
                            output_communication: profile.output_communication,
                            input_default: profile.input_default,
                            input_communication: profile.input_communication
                        });

                        if (outputDefaultSelect) outputDefaultSelect.value = profile.output_default || '';
                        if (outputCommSelect) outputCommSelect.value = profile.output_communication || '';
                        if (inputDefaultSelect) inputDefaultSelect.value = profile.input_default || '';
                        if (inputCommSelect) inputCommSelect.value = profile.input_communication || '';
                    }
                }
            }
        } catch (error) {
            console.error('Error loading devices:', error);
            showNotification('Error loading device list', true);
        }
    }

    hideProfileEditor() {
        const editor = document.getElementById('profileEditor');
        if (editor) {
            editor.style.display = 'none';
        }
        this.currentProfile = null;
    }

    async selectTriggerApp() {
        try {
            console.log('Sending request to select trigger app...');
            const response = await fetch('/select_trigger_app', {
                method: 'POST'
            });

            console.log('Response status:', response.status);
            const data = await response.json();
            console.log('Response data:', data);

            const triggerAppPath = document.getElementById('trigger-app-path');
            if (!triggerAppPath) {
                console.error('trigger-app-path element not found');
                return;
            }

            if (data.success && data.path) {
                console.log('Setting trigger app path to:', data.path);
                triggerAppPath.textContent = data.path;
                showNotification('Application selected successfully');
            } else {
                console.error('Failed to select application:', data.error || 'Unknown error');
                if (data.error) {
                    showNotification(data.error, true);
                }
            }
        } catch (error) {
            console.error('Error selecting trigger app:', error);
            showNotification('Error selecting application: ' + error.message, true);
        }
    }

    clearTriggerApp() {
        const triggerAppPath = document.getElementById('trigger-app-path');
        if (triggerAppPath) {
            triggerAppPath.textContent = 'No application selected';
            showNotification('Trigger application cleared');
        }
    }
}

// Initialize ProfileManager after DOM load
document.addEventListener('DOMContentLoaded', () => {
    const profileManager = new ProfileManager();
});

window.addEventListener('themeChange', (event) => {
    const theme = event.detail.theme;
    if (theme === 'light') {
        document.body.classList.add('light-theme');
    } else {
        document.body.classList.remove('light-theme');
    }
});

function setupDevicePolling() {
    setInterval(async () => {
        await loadDevices();
    }, 2000); // Check every 2 seconds
}

function showNotification(message, isError = false) {
    const notification = document.createElement('div');
    notification.className = `notification${isError ? ' error' : ''}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    // Показываем уведомление
    setTimeout(() => {
        notification.style.display = 'block';
        notification.style.opacity = '1';
    }, 100);

    // Скрываем и удаляем чере 3 секунды
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
} 