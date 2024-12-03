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

        // Добавляем обработчики для кнопок сброса памяти
        const resetBtn = document.getElementById('resetDeviceMemory');
        const modal = document.getElementById('resetMemoryModal');
        const modalContent = modal?.querySelector('.modal-content');
        const applyBtn = document.getElementById('applyReset');
        const cancelBtn = document.getElementById('cancelReset');

        if (resetBtn && modal && modalContent) {
            resetBtn.addEventListener('click', (event) => {
                // Позиционируем модальное окно относительно текущей позиции скролла
                const rect = resetBtn.getBoundingClientRect();
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                
                modalContent.style.top = `${rect.top + scrollTop - 100}px`; // Немного выше кнопки
                modalContent.style.left = '50%';
                modalContent.style.transform = 'translateX(-50%)';
                
                modal.style.display = 'block';
                modal.style.opacity = '0';
                modalContent.style.transform = 'translate(-50%, 20px)';
                
                // Зап��скаем анимаци
                requestAnimationFrame(() => {
                    modal.style.opacity = '1';
                    modalContent.style.transform = 'translate(-50%, 0)';
                });
                
                event.stopPropagation();
            });
        }

        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                if (window.profileManager) {
                    window.profileManager.resetDeviceMemory();
                    this.animateModalClose(modal);
                }
            });
        }

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.animateModalClose(modal);
            });
        }

        // Закрытие модального окна при клике вне его
        window.addEventListener('click', (event) => {
            if (event.target === modal) {
                this.animateModalClose(modal);
            }
        });

        // Добавляем обработчик для клавиши Escape
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && modal.style.display === 'block') {
                this.animateModalClose(modal);
            }
        });
    }

    animateModalClose(modal) {
        const modalContent = modal.querySelector('.modal-content');
        modal.style.opacity = '0';
        modalContent.style.transform = 'translate(-50%, 20px)';
        
        setTimeout(() => {
            modal.style.display = 'none';
            modalContent.style.transform = 'translate(-50%, 0)';
        }, 300);
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
        this.profiles = [];
        this.outputDevices = [];
        this.inputDevices = [];
        this.currentProfile = null;
        this.deviceUpdateInterval = null;
        this.currentlyEditingProfile = null;
        this.disconnectedDevices = {
            output: new Set(),
            input: new Set()
        };
        this.deviceStates = {
            output: new Map(),
            input: new Map()
        };

        // Добавляем структуры для хранения отключенных устройств в блоках
        this.blockDisconnectedDevices = {
            output: new Set(),
            input: new Set()
        };
        
        // Загружаем сохраненные отключенные устройства при инициализации
        this.loadBlockDisconnectedDevices();

        // Добавляем интервал для автоматического обновления профилей
        this.profileUpdateInterval = null;
        // Кэш для профилей
        this.profilesCache = new Map();

        // Инициализация
        this.init();
    }

    // Сохранение состояний устройств
    saveDeviceStates() {
        const data = {
            output: Array.from(this.deviceStates.output.entries()),
            input: Array.from(this.deviceStates.input.entries())
        };
        localStorage.setItem('deviceStates', JSON.stringify(data));
    }

    // Загрузка состояний устройств
    loadDeviceStates() {
        try {
            const data = localStorage.getItem('deviceStates');
            if (data) {
                const parsed = JSON.parse(data);
                this.deviceStates = {
                    output: new Map(parsed.output),
                    input: new Map(parsed.input)
                };
            }
        } catch (error) {
            console.error('Error loading device states:', error);
            this.deviceStates = {
                output: new Map(),
                input: new Map()
            };
        }
    }

    async init() {
        this.loadDisconnectedDevices();
        this.loadDeviceStates();
        await this.loadDevices();
        this.startDeviceUpdates();
        await this.loadProfiles();
        this.startProfileUpdates();
        this.setupEventListeners();
    }

    startDeviceUpdates() {
        this.stopDeviceUpdates();
        this.deviceUpdateInterval = setInterval(async () => {
            await this.loadDevices();
        }, 2000);
    }

    stopDeviceUpdates() {
        if (this.deviceUpdateInterval) {
            clearInterval(this.deviceUpdateInterval);
            this.deviceUpdateInterval = null;
        }
    }

    setupEventListeners() {
        // Добавляем обработчик для оистки интервала при закрытии страницы
        window.addEventListener('beforeunload', () => {
            this.stopDeviceUpdates();
        });

        // Wait for the DOM to be fully loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeElements());
        } else {
            this.initializeElements();
        }

        const cancelProfileBtn = document.getElementById('cancelProfileBtn');
        if (cancelProfileBtn) {
            cancelProfileBtn.addEventListener('click', () => this.hideProfileEditor());
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
    }

    async loadProfiles() {
        try {
            const response = await fetch('/profiles');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            if (data.status === 'success') {
                this.profiles = data.profiles.map(profile => ({
                    ...profile,
                    output_default: this.decodeDeviceName(profile.output_default),
                    output_communication: this.decodeDeviceName(profile.output_communication),
                    input_default: this.decodeDeviceName(profile.input_default),
                    input_communication: this.decodeDeviceName(profile.input_communication)
                }));
                await this.renderProfiles();
            }
        } catch (error) {
            console.error('Error loading profiles:', error);
            showNotification('Error loading profiles', true);
        }
    }

    // Добавляем метод для декодирования имен устройств
    decodeDeviceName(name) {
        if (!name) return name;
        try {
            // Сначала пробуем простое декодирование
            return decodeURIComponent(name);
        } catch (e) {
            try {
                // Если не получилось, пробуем через escape
                return decodeURIComponent(escape(name));
            } catch (e) {
                // Если и это не сработало, возвращаем оригинальное имя
                console.warn(`Unable to decode device name: ${name}`);
                return name;
            }
        }
    }

    // Добавляем метод для кодирования имен устройств
    encodeDeviceName(name) {
        if (!name) return name;
        try {
            // Кодируем как URI компонент
            return encodeURIComponent(name);
        } catch (e) {
            console.warn(`Unable to encode device name: ${name}`);
            return name;
        }
    }

    async saveProfile(profileData) {
        try {
            // Кодируем имена устройств перед сохранением
            const encodedProfile = {
                ...profileData,
                output_default: this.encodeDeviceName(profileData.output_default),
                output_communication: this.encodeDeviceName(profileData.output_communication),
                input_default: this.encodeDeviceName(profileData.input_default),
                input_communication: this.encodeDeviceName(profileData.input_communication)
            };

            const response = await fetch('/profiles', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(encodedProfile)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to save profile');
            }

            // Закрываем редактор
            const editor = document.getElementById('profileEditor');
            if (editor) {
                editor.style.display = 'none';
            }

            // Обновляем список профилей
            await this.loadProfiles();
            
            // Показываем уведомление об успехе
            showNotification('Profile saved successfully');
            
            return true;
        } catch (error) {
            console.error('Error saving profile:', error);
            showNotification('Error saving profile: ' + error.message, true);
            return false;
        }
    }

    async loadDevices() {
        try {
            const [outputResponse, inputResponse] = await Promise.all([
                fetch('/get_output_devices'),
                fetch('/get_input_devices')
            ]);

            if (!outputResponse.ok || !inputResponse.ok) {
                console.error('Error in device responses');
                this.outputDevices = [];
                this.inputDevices = [];
                return;
            }

            const outputData = await outputResponse.json();
            const inputData = await inputResponse.json();

            if (outputData.status !== 'success' || inputData.status !== 'success') {
                console.error('Error in device data');
                this.outputDevices = [];
                this.inputDevices = [];
                return;
            }

            this.outputDevices = outputData.devices || [];
            this.inputDevices = inputData.devices || [];
            await this.updateAllDeviceLists();

        } catch (error) {
            console.error('Error loading devices:', error);
            this.outputDevices = [];
            this.inputDevices = [];
        }
    }

    async updateAllDeviceLists() {
        // Обновляем отображени профилей
        await this.renderProfiles();

        // Обновляем селекторы в редакторе профиля, если он открыт
        if (this.currentlyEditingProfile) {
            await this.updateProfileEditorSelectors();
        }

        // Обновляем все другие списки устройств на странице
        this.updateDeviceSelectors();

        // Обновляем блоки управления устройствами
        this.updateDeviceControlBlocks();
    }

    updateDeviceSelectors() {
        // Обновляем все селекторы устройств на странице
        const selectors = {
            output: document.querySelectorAll('select[data-device-type="output"]'),
            input: document.querySelectorAll('select[data-device-type="input"]')
        };

        // Обновляем селекторы выходных устройств
        selectors.output.forEach(select => {
            const currentValue = select.value;
            select.innerHTML = '<option value="">Not Selected</option>';
            
            this.outputDevices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.name;
                option.textContent = device.name + (device.connected ? '' : ' (Disconnected)');
                select.appendChild(option);
            });

            // Если текущее значение суествует в списке устройств или это отключенное устройство
            if (currentValue) {
                const deviceExists = this.outputDevices.some(d => d.name === currentValue);
                if (!deviceExists) {
                    const option = document.createElement('option');
                    option.value = currentValue;
                    option.textContent = currentValue + ' (Disconnected)';
                    select.appendChild(option);
                }
                select.value = currentValue;
            }
        });

        // Обновляем селекторы входных устройств
        selectors.input.forEach(select => {
            const currentValue = select.value;
            select.innerHTML = '<option value="">Not Selected</option>';
            
            this.inputDevices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.name;
                option.textContent = device.name + (device.connected ? '' : ' (Disconnected)');
                select.appendChild(option);
            });

            // Если текущее значение существует в спске устройств или это отключенне устройство
            if (currentValue) {
                const deviceExists = this.inputDevices.some(d => d.name === currentValue);
                if (!deviceExists) {
                    const option = document.createElement('option');
                    option.value = currentValue;
                    option.textContent = currentValue + ' (Disconnected)';
                    select.appendChild(option);
                }
                select.value = currentValue;
            }
        });
    }

    async updateProfileEditorSelectors() {
        const outputDefaultSelect = document.getElementById('outputDefaultDevice');
        const outputCommSelect = document.getElementById('outputCommDevice');
        const inputDefaultSelect = document.getElementById('inputDefaultDevice');
        const inputCommSelect = document.getElementById('inputCommDevice');

        if (!outputDefaultSelect || !outputCommSelect || !inputDefaultSelect || !inputCommSelect) {
            return;
        }

        // Добавляем атрибуты для идентификации типа устройств
        outputDefaultSelect.setAttribute('data-device-type', 'output');
        outputCommSelect.setAttribute('data-device-type', 'output');
        inputDefaultSelect.setAttribute('data-device-type', 'input');
        inputCommSelect.setAttribute('data-device-type', 'input');

        // Сохраняем текущие выбранные значния
        const currentValues = {
            outputDefault: outputDefaultSelect.value,
            outputComm: outputCommSelect.value,
            inputDefault: inputDefaultSelect.value,
            inputComm: inputCommSelect.value
        };

        // Очищаем селекты
        outputDefaultSelect.innerHTML = '<option value="">Not Selected</option>';
        outputCommSelect.innerHTML = '<option value="">Not Selected</option>';
        inputDefaultSelect.innerHTML = '<option value="">Not Selected</option>';
        inputCommSelect.innerHTML = '<option value="">Not Selected</option>';

        // Функция для добавления устройств в селект
        const addDevicesToSelect = (select, devices, disconnectedDevices) => {
            // Добавляем подключенные устройства
            devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.name;
                option.textContent = device.name;
                select.appendChild(option);
            });

            // Добавляем отключенные устройства
            disconnectedDevices.forEach(deviceName => {
                if (!devices.some(d => d.name === deviceName)) {
                    const option = document.createElement('option');
                    option.value = deviceName;
                    option.textContent = `${deviceName} (Disconnected)`;
                    select.appendChild(option);
                }
            });
        };

        // Добавляем устройства в селекты вывода
        addDevicesToSelect(outputDefaultSelect, this.outputDevices, this.blockDisconnectedDevices.output);
        addDevicesToSelect(outputCommSelect, this.outputDevices, this.blockDisconnectedDevices.output);

        // Добавляем устройства в селекты ввода
        addDevicesToSelect(inputDefaultSelect, this.inputDevices, this.blockDisconnectedDevices.input);
        addDevicesToSelect(inputCommSelect, this.inputDevices, this.blockDisconnectedDevices.input);

        // Восстанавливаем выбранные значения
        outputDefaultSelect.value = currentValues.outputDefault;
        outputCommSelect.value = currentValues.outputComm;
        inputDefaultSelect.value = currentValues.inputDefault;
        inputCommSelect.value = currentValues.inputComm;
    }

    async renderProfiles() {
        try {
            const container = document.querySelector('.profile-cards');
            if (!container) {
                console.error('Profile cards container not found');
                return;
            }

            // Функция для декодирования Unicode escape-последовательностей
            const decodeUnicode = (str) => {
                if (!str) return '';
                try {
                    // Используем встроенный декодер JSON для корректной обработки Unicode
                    return JSON.parse(`"${str}"`);
                } catch (e) {
                    console.error('Error decoding Unicode:', e);
                    return str;
                }
            };

            // Функция для безопасного декодирования текста устройства
            const safeDecodeDevice = (device, status = '') => {
                if (!device) return 'Not Selected';
                return decodeUnicode(device) + status;
            };

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

            if (!this.profiles || this.profiles.length === 0) {
                return;
            }

            this.profiles.forEach(profile => {
                const card = document.createElement('div');
                card.className = 'profile-card';
                if (this.currentProfile && this.currentProfile.name === profile.name) {
                    card.classList.add('active');
                }

                // Определяем статусы устройств
                const outputDefaultStatus = profile.output_default && profile.output_default.includes('(Disconnected)') ? ' <span class="disconnected-status">(Disconnected)</span>' : '';
                const outputCommStatus = profile.output_communication && profile.output_communication.includes('(Disconnected)') ? ' <span class="disconnected-status">(Disconnected)</span>' : '';
                const inputDefaultStatus = profile.input_default && profile.input_default.includes('(Disconnected)') ? ' <span class="disconnected-status">(Disconnected)</span>' : '';
                const inputCommStatus = profile.input_communication && profile.input_communication.includes('(Disconnected)') ? ' <span class="disconnected-status">(Disconnected)</span>' : '';

                // Формируем текст горячих клавиш
                let hotkeyText = '';
                if (profile.hotkey) {
                    const keys = [];
                    if (profile.hotkey.keyboard && profile.hotkey.keyboard !== 'None') {
                        keys.push(profile.hotkey.keyboard);
                    }
                    if (profile.hotkey.mouse && profile.hotkey.mouse !== 'None') {
                        keys.push(profile.hotkey.mouse);
                    }
                    if (keys.length > 0) {
                        hotkeyText = keys.join(' + ');
                    }
                }

                card.innerHTML = `
                    <div class="card-content">
                        <div class="profile-name">${decodeUnicode(profile.name)}</div>
                        <div class="device-info">
                            <div><span class="device-type">Default Output:</span> ${safeDecodeDevice(profile.output_default, outputDefaultStatus)}</div>
                            ${profile.output_communication ? `<div><span class="device-type">Communication Output:</span> ${safeDecodeDevice(profile.output_communication, outputCommStatus)}</div>` : ''}
                            <div><span class="device-type">Default Input:</span> ${safeDecodeDevice(profile.input_default, inputDefaultStatus)}</div>
                            ${profile.input_communication ? `<div><span class="device-type">Communication Input:</span> ${safeDecodeDevice(profile.input_communication, inputCommStatus)}</div>` : ''}
                            ${profile.trigger_app ? `<div><span class="device-type">Trigger App:</span> ${this.getFileName(profile.trigger_app)}</div>` : ''}
                            ${profile.force_trigger ? `<div><span class="device-type">Force Mode:</span> Enabled</div>` : ''}
                            <div><span class="device-type">Activate on Startup:</span> ${profile.activate_on_startup ? 'Enabled' : 'Disabled'}</div>
                        </div>
                        ${hotkeyText ? `<div class="hotkey-badge">${hotkeyText}</div>` : ''}
                    </div>
                    <div class="card-actions">
                        <button class="delete-btn" onclick="event.stopPropagation(); deleteProfile('${profile.name}')">
                            Delete
                        </button>
                    </div>
                `;

                card.addEventListener('click', () => {
                    this.showProfileEditor(profile);
                });

                container.appendChild(card);
            });
        } catch (error) {
            console.error('Error rendering profiles:', error);
            showNotification('Error rendering profiles', true);
        }
    }

    getFileName(path) {
        if (!path) return '';
        const parts = path.split(/[/\\]/);
        return parts[parts.length - 1];
    }

    async showProfileEditor(profile = null) {
        try {
            const editor = document.getElementById('profileEditor');
            if (!editor) return;

            // Очищаем редактор перед показом нового профиля
            this.clearProfileEditor();

            // Показываем редактор сразу
            editor.style.display = 'block';
            editor.scrollIntoView({ behavior: 'smooth', block: 'start' });

            // Асинхронно загружаем данные устройств
            await this.updateProfileEditorSelectors();

            // Если редактируем существующий п��офиль
            if (profile) {
                // Используем кэш если профиль уже был открыт
                const cacheKey = profile.name;
                if (this.profilesCache.has(cacheKey)) {
                    const cachedData = this.profilesCache.get(cacheKey);
                    this.fillProfileEditor(cachedData);
                } else {
                    this.fillProfileEditor(profile);
                    // Кэшируем данные профиля
                    this.profilesCache.set(profile.name, profile);
                }
            }

        } catch (error) {
            console.error('Error showing profile editor:', error);
            showNotification('Error showing profile editor', true);
        }
    }

    fillProfileEditor(profile) {
        const nameInput = document.getElementById('profileName');
        const hotkeyInput = document.getElementById('profileHotkey');
        const forceTriggerCheckbox = document.getElementById('forceTriggerCheckbox');
        const activateOnStartupCheckbox = document.getElementById('activateOnStartupCheckbox');
        const triggerAppPath = document.getElementById('trigger-app-path');
        const outputDefaultSelect = document.getElementById('outputDefaultDevice');
        const outputCommSelect = document.getElementById('outputCommDevice');
        const inputDefaultSelect = document.getElementById('inputDefaultDevice');
        const inputCommSelect = document.getElementById('inputCommDevice');

        if (profile) {
            // Заполняем основные поля
            nameInput.value = profile.name;
            nameInput.dataset.originalName = profile.name;

            if (profile.hotkey) {
                hotkeyInput.dataset.keyboard = profile.hotkey.keyboard || 'None';
                hotkeyInput.dataset.mouse = profile.hotkey.mouse || 'None';
                hotkeyInput.value = [
                    profile.hotkey.keyboard !== 'None' ? profile.hotkey.keyboard : '',
                    profile.hotkey.mouse !== 'None' ? profile.hotkey.mouse : ''
                ].filter(Boolean).join(' + ');
            }

            if (profile.trigger_app) {
                triggerAppPath.textContent = profile.trigger_app;
            }

            if (forceTriggerCheckbox) {
                forceTriggerCheckbox.checked = profile.force_trigger || false;
            }
            if (activateOnStartupCheckbox) {
                activateOnStartupCheckbox.checked = profile.activate_on_startup || false;
            }

            // Устанавливаем значения устройств с проверкой
            const setDeviceValue = (select, value) => {
                if (select && value) {
                    // Проверяем, существует ли опция с таким значением
                    const optionExists = Array.from(select.options).some(opt => opt.value === value);
                    if (optionExists) {
                        select.value = value;
                    } else {
                        select.value = ''; // Если значение не найдено, устанавливаем пустое
                    }
                } else if (select) {
                    select.value = ''; // Если значение не задано, устанавливаем пустое
                }
            };

            setDeviceValue(outputDefaultSelect, profile.output_default);
            setDeviceValue(outputCommSelect, profile.output_communication);
            setDeviceValue(inputDefaultSelect, profile.input_default);
            setDeviceValue(inputCommSelect, profile.input_communication);
        }
    }

    clearProfileEditor() {
        const nameInput = document.getElementById('profileName');
        const hotkeyInput = document.getElementById('profileHotkey');
        const forceTriggerCheckbox = document.getElementById('forceTriggerCheckbox');
        const activateOnStartupCheckbox = document.getElementById('activateOnStartupCheckbox');
        const triggerAppPath = document.getElementById('trigger-app-path');

        nameInput.value = '';
        nameInput.dataset.originalName = '';
        hotkeyInput.dataset.keyboard = 'None';
        hotkeyInput.dataset.mouse = 'None';
        hotkeyInput.value = '';
        if (forceTriggerCheckbox) forceTriggerCheckbox.checked = false;
        if (activateOnStartupCheckbox) activateOnStartupCheckbox.checked = false;
        triggerAppPath.textContent = 'No application selected';
    }

    stopProfileUpdates() {
        if (this.profileUpdateInterval) {
            clearInterval(this.profileUpdateInterval);
            this.profileUpdateInterval = null;
        }
    }

    // Добавляем очистку при уничтожении
    destroy() {
        this.stopDeviceUpdates();
        this.stopProfileUpdates();
        this.profilesCache.clear();
    }

    setSelectedOption(select, value) {
        if (!select || !value) return;
        
        // Очищаем "(Disconnected)" из значения
        const cleanValue = value.replace(" (Disconnected)", "");
        
        // Ищем опцию по тексту
        for (let i = 0; i < select.options.length; i++) {
            const optionText = select.options[i].text.replace(" (Disconnected)", "");
            if (optionText === cleanValue) {
                select.selectedIndex = i;
                break;
            }
        }
    }

    hideProfileEditor() {
        this.currentlyEditingProfile = null;
        const editor = document.getElementById('profileEditor');
        if (editor) {
            editor.style.display = 'none';
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
            // Получаем текущий список профилей
            const currentProfiles = [...this.profiles];
            
            // Находим удаляемый профиль
            const profileToDelete = currentProfiles.find(p => p.name === profileName);
            if (!profileToDelete) {
                throw new Error('Profile not found');
            }

            // Кодируем только имя профиля для URL
            const encodedProfileName = this.encodeDeviceName(profileName);

            const response = await fetch(`/profiles/${encodedProfileName}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to delete profile');
            }

            const result = await response.json();
            if (result.status === 'success') {
                // Обновляем локальный список профилей
                this.profiles = currentProfiles.filter(p => p.name !== profileName);
                
                // Очищаем кэш ля этого профиля
                this.profilesCache.delete(profileName);
                
                // Обновляем отображение
                await this.renderProfiles();
                showNotification('Profile deleted successfully');
            } else {
                throw new Error(result.message || 'Failed to delete profile');
            }
        } catch (error) {
            console.error('Error deleting profile:', error);
            showNotification('Error deleting profile: ' + error.message, true);
        }
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

    updateDeviceControlBlocks() {
        console.log('Updating device control blocks...');

        // ункция создания элемента устройства
        const createDeviceElement = (device, isChecked = device.connected) => {
            const deviceElement = document.createElement('div');
            deviceElement.className = 'device-item';
            
            // Создаем чекбокс и добавляем обработчик события
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'device-checkbox';
            checkbox.checked = isChecked;
            checkbox.addEventListener('change', (e) => {
                // Сохраняем состояние чекбокса
                const type = device.type || (outputDevicesBlock.contains(deviceElement) ? 'output' : 'input');
                this.deviceStates[type].set(device.name, e.target.checked);
                this.saveDeviceStates();
            });

            deviceElement.appendChild(checkbox);
            deviceElement.insertAdjacentHTML('beforeend', `
                <span class="device-name">${device.name}</span>
                ${!device.connected ? '<span class="device-current">Disconnected</span>' : ''}
            `);
            
            return deviceElement;
        };

        // Обновляем блок Output Devices Control
        const outputDevicesBlock = document.querySelector('#outputDevices');
        if (outputDevicesBlock) {
            // Сохраняем текущие состояния
            outputDevicesBlock.querySelectorAll('.device-item').forEach(item => {
                const deviceName = item.querySelector('.device-name').textContent;
                const isChecked = item.querySelector('.device-checkbox').checked;
                this.deviceStates.output.set(deviceName, isChecked);
                
                // Если устройство больше не подключено, добавляем его в список отключенных
                if (!this.outputDevices.some(d => d.name === deviceName)) {
                    this.blockDisconnectedDevices.output.add(deviceName);
                }
            });

            // Очищаем список
            outputDevicesBlock.innerHTML = '';

            // Создаем список всех устройств
            const allDevices = new Map();
            
            // Добавляем подключенные устройства
            this.outputDevices.forEach(device => {
                allDevices.set(device.name, {
                    ...device,
                    type: 'output',
                    connected: true
                });
                // Удаляем из списка отключенных, если устройство снова подключено
                this.blockDisconnectedDevices.output.delete(device.name);
            });

            // Добавляем отключенные устройства
            this.blockDisconnectedDevices.output.forEach(deviceName => {
                if (!allDevices.has(deviceName)) {
                    allDevices.set(deviceName, {
                        name: deviceName,
                        type: 'output',
                        connected: false
                    });
                }
            });

            // Отображаем все устройства
            allDevices.forEach(device => {
                const isChecked = this.deviceStates.output.has(device.name) ? 
                    this.deviceStates.output.get(device.name) : device.connected;
                outputDevicesBlock.appendChild(createDeviceElement(device, isChecked));
            });
        }

        // Обновляем блок Input Devices Control
        const inputDevicesBlock = document.querySelector('#inputDevices');
        if (inputDevicesBlock) {
            // Сохраняем текущие состояния
            inputDevicesBlock.querySelectorAll('.device-item').forEach(item => {
                const deviceName = item.querySelector('.device-name').textContent;
                const isChecked = item.querySelector('.device-checkbox').checked;
                this.deviceStates.input.set(deviceName, isChecked);
                
                // Если устройство больше не подключено, добавляем его в список отключенных
                if (!this.inputDevices.some(d => d.name === deviceName)) {
                    this.blockDisconnectedDevices.input.add(deviceName);
                }
            });

            // Очищаем список
            inputDevicesBlock.innerHTML = '';

            // Создаем список всех устройств
            const allDevices = new Map();
            
            // Добавляем подключенные устройства
            this.inputDevices.forEach(device => {
                allDevices.set(device.name, {
                    ...device,
                    type: 'input',
                    connected: true
                });
                // Удаляем из списка откюченных, если устройство сова подключено
                this.blockDisconnectedDevices.input.delete(device.name);
            });

            // Добавляем отключенные устройства
            this.blockDisconnectedDevices.input.forEach(deviceName => {
                if (!allDevices.has(deviceName)) {
                    allDevices.set(deviceName, {
                        name: deviceName,
                        type: 'input',
                        connected: false
                    });
                }
            });

            // Отображаем все устройства
            allDevices.forEach(device => {
                const isChecked = this.deviceStates.input.has(device.name) ? 
                    this.deviceStates.input.get(device.name) : device.connected;
                inputDevicesBlock.appendChild(createDeviceElement(device, isChecked));
            });
        }

        // Сохраняем обновленные данные
        this.saveBlockDisconnectedDevices();
        this.saveDeviceStates();
    }

    // Сохрнение отключенных устройств
    saveDisconnectedDevices() {
        const data = {
            output: Array.from(this.disconnectedDevices.output),
            input: Array.from(this.disconnectedDevices.input)
        };
        localStorage.setItem('disconnectedDevices', JSON.stringify(data));
    }

    // Загрузка отключенных устройств
    loadDisconnectedDevices() {
        try {
            const data = localStorage.getItem('disconnectedDevices');
            if (data) {
                const parsed = JSON.parse(data);
                this.disconnectedDevices = {
                    output: new Set(parsed.output),
                    input: new Set(parsed.input)
                };
            }
        } catch (error) {
            console.error('Error loading disconnected devices:', error);
            this.disconnectedDevices = {
                output: new Set(),
                input: new Set()
            };
        }
    }

    resetDeviceMemory() {
        try {
            this.blockDisconnectedDevices = {
                output: new Set(),
                input: new Set()
            };
            
            this.deviceStates = {
                output: new Map(),
                input: new Map()
            };

            localStorage.removeItem('blockDisconnectedDevices');
            localStorage.removeItem('deviceStates');

            const outputDevicesBlock = document.querySelector('#outputDevices');
            if (outputDevicesBlock) {
                outputDevicesBlock.innerHTML = '';
                this.outputDevices.forEach(device => {
                    const deviceElement = createDeviceElement({
                        ...device,
                        type: 'output',
                        connected: true
                    }, true);
                    outputDevicesBlock.appendChild(deviceElement);
                });
            }

            const inputDevicesBlock = document.querySelector('#inputDevices');
            if (inputDevicesBlock) {
                inputDevicesBlock.innerHTML = '';
                this.inputDevices.forEach(device => {
                    const deviceElement = createDeviceElement({
                        ...device,
                        type: 'input',
                        connected: true
                    }, true);
                    inputDevicesBlock.appendChild(deviceElement);
                });
            }
            
            showNotification('Device memory has been reset');
        } catch (error) {
            console.error('Error resetting device memory:', error);
            showNotification('Error resetting device memory', true);
        }
    }

    // Добавляем метод для загрузки отключенных устройств блоков
    loadBlockDisconnectedDevices() {
        try {
            const data = localStorage.getItem('blockDisconnectedDevices');
            if (data) {
                const parsed = JSON.parse(data);
                this.blockDisconnectedDevices = {
                    output: new Set(parsed.output),
                    input: new Set(parsed.input)
                };
            }
        } catch (error) {
            console.error('Error loading block disconnected devices:', error);
            this.blockDisconnectedDevices = {
                output: new Set(),
                input: new Set()
            };
        }
    }

    // Добавляем метод для сохранения отключенных устройств блоков
    saveBlockDisconnectedDevices() {
        const data = {
            output: Array.from(this.blockDisconnectedDevices.output),
            input: Array.from(this.blockDisconnectedDevices.input)
        };
        localStorage.setItem('blockDisconnectedDevices', JSON.stringify(data));
    }

    startProfileUpdates() {
        // Останавливаем предыдущий интервал если он существует
        if (this.profileUpdateInterval) {
            clearInterval(this.profileUpdateInterval);
        }

        // Создаем новый интервал для обновления профилей каждые 2 секунды
        this.profileUpdateInterval = setInterval(async () => {
            await this.checkProfileUpdates();
        }, 2000);
    }

    async checkProfileUpdates() {
        try {
            const response = await fetch('/profiles');
            if (!response.ok) return;

            const data = await response.json();
            if (data.status !== 'success') return;

            const newProfiles = data.profiles || [];
            let hasChanges = false;

            // Проверяем изменения
            if (this.profiles.length !== newProfiles.length) {
                hasChanges = true;
            } else {
                // Сравниваем каждый профиль
                for (let i = 0; i < newProfiles.length; i++) {
                    const newProfile = newProfiles[i];
                    const oldProfile = this.profiles[i];
                    if (JSON.stringify(newProfile) !== JSON.stringify(oldProfile)) {
                        hasChanges = true;
                        break;
                    }
                }
            }

            // Обновляем только если есть измененя
            if (hasChanges) {
                this.profiles = newProfiles;
                await this.renderProfiles();
            }
        } catch (error) {
            console.error('Error checking profile updates:', error);
        }
    }

    // Добавляем новый метод для кодироания профиля перед сохраненем в JSON
    encodeProfile(profile) {
        return {
            ...profile,
            output_default: this.encodeDeviceName(profile.output_default),
            output_communication: this.encodeDeviceName(profile.output_communication),
            input_default: this.encodeDeviceName(profile.input_default),
            input_communication: this.encodeDeviceName(profile.input_communication)
        };
    }
}

function createNewProfile() {
    const profileManager = window.profileManager;
    if (profileManager) {
        profileManager.createNewProfile();
    } else {
        console.error('ProfileManager not initialized');
        showNotification('Error: ProfileManager not initialized', true);
    }
}

function deleteProfile(profileName) {
    const profileManager = window.profileManager;
    if (profileManager) {
        profileManager.deleteProfile(profileName);
    } else {
        console.error('ProfileManager not initialized');
        showNotification('Error: ProfileManager not initialized', true);
    }
}

// Initialize ProfileManager after DOM load
document.addEventListener('DOMContentLoaded', () => {
    window.profileManager = new ProfileManager();
});

window.addEventListener('themeChange', (event) => {
    const theme = event.detail.theme;
    if (theme === 'light') {
        document.body.classList.add('light-theme');
    } else {
        document.body.classList.remove('light-theme');
    }
});

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

window.addEventListener('beforeunload', () => {
    if (window.profileManager) {
        window.profileManager.destroy();
    }
});

window.addEventListener('beforeunload', async () => {
    try {
        // Отправляем запрос на сервер о закрытии окна
        await fetch('/browser_closed', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
    } catch (e) {
        console.error('Error notifying server about window close:', e);
    }
}); 