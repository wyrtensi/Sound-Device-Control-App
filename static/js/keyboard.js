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
        
        // Загружаем существующие клавиши
        const keyboard = this.currentInput.getAttribute('data-keyboard');
        const mouse = this.currentInput.getAttribute('data-mouse');
        
        if (keyboard && keyboard !== "Нет") {
            keyboard.split('+').forEach(key => {
                const keyElement = this.findKeyElement(key.trim());
                if (keyElement) {
                    this.selectedKeys.keyboard.add(key.trim());
                    keyElement.classList.add('active');
                }
            });
        }
        
        if (mouse && mouse !== "Нет") {
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
            'лкм', 'пкм', 'скм'
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
        
        console.log('Current keys:', {
            keyboard: Array.from(this.selectedKeys.keyboard),
            mouse: Array.from(this.selectedKeys.mouse)
        });
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
            'лкм': 'mouseleft',
            'пкм': 'mouseright',
            'скм': 'mousemiddle',
            'arrowup': 'up',
            'arrowdown': 'down',
            'arrowleft': 'left',
            'arrowright': 'right'
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
            
            // Формируем строки клавиш
            const keyboardKeys = Array.from(this.selectedKeys.keyboard);
            const mouseKeys = Array.from(this.selectedKeys.mouse);
            
            console.log('Saving keys:', {
                keyboard: keyboardKeys,
                mouse: mouseKeys
            });
            
            // Обновляем атрибуты и значение в поле ввода
            this.currentInput.setAttribute('data-keyboard', keyboardKeys.join('+') || "Нет");
            this.currentInput.setAttribute('data-mouse', mouseKeys.join('+') || "Нет");
            
            // Обновляем отображаемое значение
            const allKeys = [...keyboardKeys, ...mouseKeys];
            this.currentInput.value = allKeys.length > 0 ? allKeys.join('+') : "Нет";

            // Отправляем разделенные данные на сервер
            fetch('/update_hotkey', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: action,
                    keyboard: keyboardKeys.join('+') || "Нет",
                    mouse: mouseKeys.join('+') || "Нет"
                })
            });
        }
        this.hideKeyboard();
    }
}

// Инициализация клавиатуры при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    const keyboard = new VirtualKeyboard();

    document.querySelectorAll('.hotkey-input').forEach(input => {
        input.addEventListener('focus', () => keyboard.showKeyboard(input));
    });
}); 