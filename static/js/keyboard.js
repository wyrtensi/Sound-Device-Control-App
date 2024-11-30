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
        document.querySelectorAll('.key').forEach(key => {
            key.addEventListener('click', () => this.toggleKey(key));
        });

        document.getElementById('applyHotkey').addEventListener('click', () => this.applyHotkey());
        document.getElementById('cancelHotkey').addEventListener('click', () => this.hideKeyboard());
        document.getElementById('clearHotkey').addEventListener('click', () => this.clearSelection());
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
        
        if (keyElement.classList.contains('active')) {
            keyElement.classList.remove('active');
            this.selectedKeys[keySet].delete(normalizedKey);
        } else {
            keyElement.classList.add('active');
            this.selectedKeys[keySet].add(normalizedKey);
        }
    }

    findKeyElement(keyName) {
        const normalizedKey = this.normalizeKeyName(keyName);
        return Array.from(document.querySelectorAll('.key')).find(
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
        document.querySelectorAll('.key.active').forEach(key => {
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

// Initialize keyboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    const keyboard = new VirtualKeyboard();

    document.querySelectorAll('.hotkey-input').forEach(input => {
        input.addEventListener('focus', () => keyboard.showKeyboard(input));
    });

    loadDevices();  // Начальная загрузка
    setupDevicePolling();  // Запускаем периодическое обновление
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
    }, 2000); // Проверяем каждые 2 секунды
} 