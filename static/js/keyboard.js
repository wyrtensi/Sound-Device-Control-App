class VirtualKeyboard {
    constructor() {
        this.modal = document.getElementById('keyboardModal');
        this.selectedKeys = {
            keyboard: new Set(),
            mouse: new Set()
        };
        this.currentInput = null;
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Важно: добавляем селектор .mouse-key для поиска клавиш мыши
        document.querySelectorAll('.keyboard-modal .key, .keyboard-modal .mouse-key').forEach(key => {
            key.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleKey(key);
            });
        });

        // Добавляем опциональную цепочку для безопасного доступа
        document.getElementById('applyHotkey')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.applyHotkey();
        });

        document.getElementById('cancelHotkey')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.hideKeyboard();
        });

        document.getElementById('clearHotkey')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.clearSelection();
        });
    }

    // Новый метод для определения клавиш мыши
    isMouseKey(keyName) {
        const mouseKeys = new Set([
            'scrollup', 'scrolldown', 
            'mouseleft', 'mouseright', 'mousemiddle',
            'lmb', 'rmb', 'mmb'
        ]);
        return mouseKeys.has(keyName.toLowerCase());
    }

    // Новый метод для нормализации имен клавиш
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

    // Обновленный метод для переключения клавиш
    toggleKey(keyElement) {
        const keyName = keyElement.getAttribute('data-key');
        const normalizedKey = this.normalizeKeyName(keyName);
        const isMouseKey = keyElement.classList.contains('mouse-key') || this.isMouseKey(normalizedKey);
        const keySet = isMouseKey ? 'mouse' : 'keyboard';
        
        if (this.selectedKeys[keySet].has(normalizedKey)) {
            keyElement.classList.remove('active');
            this.selectedKeys[keySet].delete(normalizedKey);
        } else {
            keyElement.classList.add('active');
            this.selectedKeys[keySet].add(normalizedKey);
        }
    }

    // Обновленный метод для поиска элементов клавиш
    findKeyElement(keyName) {
        const normalizedKey = this.normalizeKeyName(keyName);
        return Array.from(document.querySelectorAll('.keyboard-modal .key, .keyboard-modal .mouse-key')).find(
            key => this.normalizeKeyName(key.getAttribute('data-key')) === normalizedKey
        );
    }

    // Обновленный метод для применения горячих клавиш
    applyHotkey() {
        if (!this.currentInput) return;

        // Преобразуем клавиши в нижний регистр
        const keyboard = Array.from(this.selectedKeys.keyboard)
            .map(key => key.toLowerCase())
            .join('+') || "None";
            
        const mouse = Array.from(this.selectedKeys.mouse)
            .map(key => key.toLowerCase())
            .join('+') || "None";

        this.currentInput.setAttribute('data-keyboard', keyboard);
        this.currentInput.setAttribute('data-mouse', mouse);
        this.currentInput.value = [...this.selectedKeys.keyboard, ...this.selectedKeys.mouse]
            .map(key => key.toLowerCase())
            .join('+') || "None";

        this.hideKeyboard();
        
        // Генерируем событие изменения для обновления профиля
        const event = new Event('change', { bubbles: true });
        this.currentInput.dispatchEvent(event);
    }

    // Метод для очистки выбранных клавиш
    clearSelection() {
        document.querySelectorAll('.keyboard-modal .key.active, .keyboard-modal .mouse-key.active').forEach(key => {
            key.classList.remove('active');
        });
        this.selectedKeys.keyboard.clear();
        this.selectedKeys.mouse.clear();
    }

    // Метод для показа клавиатуры
    showKeyboard(input) {
        this.currentInput = input;
        this.clearSelection();
        
        // Загружаем текущие значения
        const keyboard = input.getAttribute('data-keyboard') || '';
        const mouse = input.getAttribute('data-mouse') || '';
        
        // Устанавливаем активные клавиши
        [...keyboard.split('+'), ...mouse.split('+')].filter(key => key && key !== 'None').forEach(key => {
            const element = this.findKeyElement(key);
            if (element) {
                this.toggleKey(element);
            }
        });
        
        if (this.modal) {
            this.modal.style.display = 'block';
        }
    }

    // Метод для скрытия клавиатуры
    hideKeyboard() {
        if (this.modal) {
            this.modal.style.display = 'none';
        }
        this.currentInput = null;
    }
}

// Функция для получения имени файла из полного пути
function getFileName(path) {
    if (!path) return '';
    // Заменяем обратные слеши на прямые для единообразия
    const normalizedPath = path.replace(/\\/g, '/');
    // Получаем последний элемент пути
    return normalizedPath.split('/').pop();
}

// Функция для активации профиля
async function activateProfile(profileName) {
    try {
        const response = await fetch('/activate_profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ profile_name: profileName })
        });
        const data = await response.json();
        return data.status === 'success';
    } catch (error) {
        console.error('Error activating profile:', error);
        return false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем виртуальную клавиатуру
    const virtualKeyboard = new VirtualKeyboard();

    // Добавляем обработчик для кнопки выбора приложения
    document.getElementById('selectTriggerAppBtn').addEventListener('click', async function(e) {
        e.preventDefault();
        try {
            const response = await fetch('/select_app');
            const data = await response.json();
            
            if (data.status === 'success') {
                document.getElementById('trigger-app-path').textContent = data.path;
            }
        } catch (error) {
            console.error('Error selecting app:', error);
        }
    });

    // Добавляем обработчик для кнопки очистки пути приложения
    document.getElementById('clearTriggerAppBtn').addEventListener('click', function(e) {
        e.preventDefault();
        document.getElementById('trigger-app-path').textContent = 'No application selected';
    });

    // Функция для инициализации обработчиков виртуальной клавиатуры
    function initVirtualKeyboardHandlers(element = document) {
        element.querySelectorAll('.hotkey-input, .profile-hotkey-input, [data-type="hotkey"], #profileHotkey, input[data-keyboard]').forEach(input => {
            // Проверяем, не был ли уже добавлен обработчик
            if (!input.hasAttribute('data-keyboard-initialized')) {
                input.setAttribute('data-keyboard-initialized', 'true');
                input.addEventListener('click', function(e) {
                    e.preventDefault();
                    virtualKeyboard.showKeyboard(this);
                });
            }
        });
    }

    // Инициализируем обработчики для существующих полей
    initVirtualKeyboardHandlers();

    // Наблюдаем за изменениями в DOM для инициализации новых полей
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length) {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // Проверяем, то это HTML элемент
                        initVirtualKeyboardHandlers(node);
                        // Также проверяем, не является ли node контейнеро�� для нашего поля
                        if (node.querySelector) {
                            initVirtualKeyboardHandlers(node);
                        }
                    }
                });
            }
        });
    });

    // Начинаем наблюдение за всем документом
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Добавляем стили для индикации состояния
    const style = document.createElement('style');
    style.textContent = `
        .device-checkbox {
            position: relative;
        }
        .device-checkbox.processing {
            pointer-events: none;
            opacity: 0.5;
        }
        .device-checkbox.processing::before {
            content: '⟳';
            position: absolute;
            left: -20px;
            animation: spin 1s linear infinite;
            color: orange;
            font-weight: bold;
        }
        @keyframes spin {
            100% { transform: rotate(360deg); }
        }
        .device-item {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }
        .device-name {
            margin-left: 8px;
        }
        .device-status {
            margin-left: auto;
            padding-left: 8px;
            color: #ff6b6b;
            font-style: italic;
        }
        .device-item.disconnected {
            opacity: 0.7;
        }
    `;
    document.head.appendChild(style);

    // Храним все известные устройства и их состояния
    let knownDevices = {
        output: new Map(),
        input: new Map()
    };

    // Загружаем сохраненные устройства
    try {
        const saved = localStorage.getItem('knownDevices');
        if (saved) {
            const parsed = JSON.parse(saved);
            knownDevices = {
                output: new Map(parsed.output),
                input: new Map(parsed.input)
            };
        }
    } catch (error) {
        console.error('Error loading known devices:', error);
    }

    // Функция для сохранения устройств
    function saveKnownDevices() {
        const data = {
            output: Array.from(knownDevices.output.entries()),
            input: Array.from(knownDevices.input.entries())
        };
        localStorage.setItem('knownDevices', JSON.stringify(data));
    }

    // Функция для обновления списка устройств
    async function updateDeviceList() {
        try {
            const [outputResponse, inputResponse] = await Promise.all([
                fetch('/get_output_devices'),
                fetch('/get_input_devices')
            ]);

            if (!outputResponse.ok || !inputResponse.ok) {
                throw new Error('Failed to fetch devices');
            }

            const outputData = await outputResponse.json();
            const inputData = await inputResponse.json();

            if (outputData.status === 'success' && inputData.status === 'success') {
                // Обновляем списки устройств
                updateKnownDevices(outputData.devices, false);
                updateKnownDevices(inputData.devices, true);

                // Обновляем отображение
                const outputContainer = document.getElementById('outputDevices');
                if (outputContainer) {
                    updateDeviceContainer(outputContainer, outputData.devices, false);
                }

                const inputContainer = document.getElementById('inputDevices');
                if (inputContainer) {
                    updateDeviceContainer(inputContainer, inputData.devices, true);
                }
            }
        } catch (error) {
            console.error('Error updating device list:', error);
        }
    }

    // Функция для обновления списка известных устройств
    function updateKnownDevices(devices, isInput) {
        const type = isInput ? 'input' : 'output';
        
        // Обновляем информацию о существующих устройствах
        devices.forEach(device => {
            const existingDevice = knownDevices[type].get(device.name);
            knownDevices[type].set(device.name, {
                ...device,
                enabled: existingDevice ? existingDevice.enabled : device.enabled
            });
        });

        // Помечаем неподключенные устройства
        knownDevices[type].forEach((device, name) => {
            const currentDevice = devices.find(d => d.name === name);
            if (!currentDevice) {
                device.connected = false;
            }
        });

        saveKnownDevices();
    }

    // Функция для обновления контейнера устройств
    function updateDeviceContainer(container, devices, isInput) {
        const type = isInput ? 'input' : 'output';
        
        // Сохраняем текущие состояния чекбоксов
        const currentStates = new Map();
        container.querySelectorAll('.device-item').forEach(item => {
            const deviceName = item.querySelector('.device-name').textContent;
            const checkbox = item.querySelector('.device-checkbox');
            currentStates.set(deviceName, {
                checked: checkbox.checked,
                processing: checkbox.classList.contains('processing')
            });
        });

        // Очищаем контейнер
        container.innerHTML = '';

        // Получаем все устройства
        const allDevices = Array.from(knownDevices[type].values());

        // Сортируем: сначала подключенные, потом отключенные
        const sortedDevices = allDevices.sort((a, b) => {
            if (a.connected === b.connected) return 0;
            return a.connected ? -1 : 1;
        });

        // Добавляем устройства в контейнер
        sortedDevices.forEach(device => {
            const deviceItem = document.createElement('div');
            deviceItem.className = 'device-item' + (!device.connected ? ' disconnected' : '');

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'device-checkbox';
            checkbox.setAttribute('data-device-id', device.id);
            if (isInput) {
                checkbox.setAttribute('data-is-input', '');
            }

            // Восстанавливаем состояние чекбокса
            const savedState = currentStates.get(device.name);
            checkbox.checked = savedState ? savedState.checked : device.enabled;
            if (savedState?.processing) {
                checkbox.classList.add('processing');
            }

            checkbox.addEventListener('change', handleCheckboxChange);

            const deviceName = document.createElement('span');
            deviceName.className = 'device-name';
            deviceName.textContent = device.name;

            deviceItem.appendChild(checkbox);
            deviceItem.appendChild(deviceName);

            if (!device.connected) {
                const status = document.createElement('span');
                status.className = 'device-status';
                status.textContent = '(Disconnected)';
                deviceItem.appendChild(status);
            }

            container.appendChild(deviceItem);
        });
    }

    // Функция для обработки изменения чекбокса
    async function handleCheckboxChange(event) {
        const checkbox = event.target;
        if (checkbox.classList.contains('processing')) {
            return;
        }

        const deviceId = checkbox.getAttribute('data-device-id');
        const isInput = checkbox.hasAttribute('data-is-input');
        const newState = checkbox.checked;
        const endpoint = isInput ? '/set_input_device_enabled' : '/set_device_enabled';
        const type = isInput ? 'input' : 'output';
        const deviceName = checkbox.closest('.device-item').querySelector('.device-name').textContent;

        checkbox.classList.add('processing');

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_index: deviceId,
                    enabled: newState
                })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            // Проверяем состояние на сервере
            const verifyResponse = await fetch('/get_device_states');
            const verifyData = await verifyResponse.json();

            if (verifyData.status === 'success') {
                const devices = isInput ? verifyData.input_devices : verifyData.output_devices;
                const serverState = devices[deviceId]?.enabled;
                if (serverState !== undefined) {
                    checkbox.checked = serverState;
                    // Обновляем состояние в knownDevices
                    const device = knownDevices[type].get(deviceName);
                    if (device) {
                        device.enabled = serverState;
                        saveKnownDevices();
                    }
                }
            }
        } catch (error) {
            console.error('Error:', error);
            checkbox.checked = !newState;
        } finally {
            checkbox.classList.remove('processing');
        }
    }

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
            
            // Запускаем анимацию
            requestAnimationFrame(() => {
                modal.style.opacity = '1';
                modalContent.style.transform = 'translate(-50%, 0)';
            });
            
            event.stopPropagation();
        });
    }

    if (applyBtn) {
        applyBtn.addEventListener('click', () => {
            // Очищаем память устройств
            knownDevices = {
                output: new Map(),
                input: new Map()
            };
            // Удаляем сохраненные данные
            localStorage.removeItem('knownDevices');
            
            // Обновляем отображение
            const outputContainer = document.getElementById('outputDevices');
            const inputContainer = document.getElementById('inputDevices');
            
            if (outputContainer) outputContainer.innerHTML = '';
            if (inputContainer) inputContainer.innerHTML = '';
            
            // Запускаем обновление списка устройств
            updateDeviceList();
            
            // Закрываем модальное окно
            animateModalClose(modal);
            
            // Показываем уведомление
            showNotification('Device memory has been reset');
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            animateModalClose(modal);
        });
    }

    // Закрытие модального окна при клике вне его
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            animateModalClose(modal);
        }
    });

    // Добавляем обработчик для клавиши Escape
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal.style.display === 'block') {
            animateModalClose(modal);
        }
    });

    // Функция для анимации закрытия модального окна
    function animateModalClose(modal) {
        const modalContent = modal.querySelector('.modal-content');
        modal.style.opacity = '0';
        modalContent.style.transform = 'translate(-50%, 20px)';
        
        setTimeout(() => {
            modal.style.display = 'none';
            modalContent.style.transform = 'translate(-50%, 0)';
        }, 300);
    }

    // Запускаем периодическое обновление списка устройств
    updateDeviceList();
    setInterval(updateDeviceList, 2000);

    // Добавляем обработчик для активации профиля
    document.querySelectorAll('.profile-item').forEach(profileItem => {
        const profileName = profileItem.getAttribute('data-profile-name');
        const hotkeyInput = profileItem.querySelector('.profile-hotkey-input');
        
        if (hotkeyInput) {
            const keyboard = hotkeyInput.getAttribute('data-keyboard');
            const mouse = hotkeyInput.getAttribute('data-mouse');
            
            if (keyboard !== 'None' || mouse !== 'None') {
                // Добавляем горячую клавишу в список активных
                const hotkey = {
                    keyboard: keyboard || 'None',
                    mouse: mouse || 'None'
                };
                
                // При совпадении горячей клавиши активируем профиль
                document.addEventListener('keydown', async function(e) {
                    if (checkHotkeyMatch(e, hotkey)) {
                        e.preventDefault();
                        await activateProfile(profileName);
                    }
                });
            }
        }
    });
});

// Функция для проверки совпадения горячих клавиш
function checkHotkeyMatch(event, hotkey) {
    const pressedKeys = new Set();
    
    if (event.ctrlKey) pressedKeys.add('ctrl');
    if (event.altKey) pressedKeys.add('alt');
    if (event.shiftKey) pressedKeys.add('shift');
    if (event.metaKey) pressedKeys.add('win');
    
    // Добавляем нажатую клавишу
    if (event.key) {
        pressedKeys.add(event.key.toLowerCase());
    }
    
    // Получаем горячие клавиши профиля
    const profileKeys = hotkey.keyboard.toLowerCase().split('+').filter(k => k !== 'none');
    
    // Проверяем совпадение количества и состава клавиш
    if (pressedKeys.size !== profileKeys.length) return false;
    
    return profileKeys.every(key => pressedKeys.has(key));
}