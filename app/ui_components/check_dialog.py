# app/ui_components/check_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QComboBox, QTextEdit, QLabel, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSlot, QEvent, Qt

from ..core.api_manager import ApiKeyManager
from ..core.translators import GoogleTranslator, DeepLTranslator
from ..core.worker import Worker

class ServiceCheckDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Перевірка доступності сервісів")
        self.setMinimumSize(500, 450)

        self.key_manager = ApiKeyManager()
        self.thread = None
        self.worker = None

        main_layout = QVBoxLayout(self)

        service_layout = QHBoxLayout()
        service_layout.addWidget(QLabel("Оберіть сервіс для перевірки:"))
        self.service_combo = QComboBox()
        self.service_combo.addItem("Google Translate", "google")
        for service_name in self.key_manager.data["services"].keys():
             if service_name != 'google':
                self.service_combo.addItem(service_name.capitalize(), service_name)
        service_layout.addWidget(self.service_combo)
        main_layout.addLayout(service_layout)

        self.active_key_label = QLabel()
        main_layout.addWidget(self.active_key_label)

        main_layout.addWidget(QLabel("Текст для перевірки (буде перекладено на англійську):"))
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Введіть текст тут...")
        self.input_text.setText("Привіт, світ!")
        main_layout.addWidget(self.input_text)

        self.check_button = QPushButton("🔬 Перевірити")
        main_layout.addWidget(self.check_button)

        main_layout.addWidget(QLabel("Результат:"))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        main_layout.addWidget(self.result_text)
        
        self.status_label = QLabel("Готово до перевірки.")
        main_layout.addWidget(self.status_label)

        self.check_button.clicked.connect(self.run_check)
        self.service_combo.currentIndexChanged.connect(self.update_active_key_display)
        
        self.update_active_key_display()

    def changeEvent(self, event: QEvent):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.parent() and self.parent().windowState() & Qt.WindowState.WindowMinimized:
                for combo_box in self.findChildren(QComboBox):
                    combo_box.hidePopup()

    # ... (решта коду класу без змін) ...
    def mask_key(self, key):
        if not key: return "Не встановлено"
        if len(key) < 8: return "****"
        return f"{key[:4]}...{key[-4:]}"

    def update_active_key_display(self):
        service = self.service_combo.currentData()
        if service == 'google':
            self.active_key_label.setText("ℹ️ Для Google Translate API ключ не потрібен.")
            self.active_key_label.setStyleSheet("color: #888;")
        else:
            active_key = self.key_manager.get_active_key(service)
            self.active_key_label.setText(f"🔑 Активний ключ: {self.mask_key(active_key)}")
            self.active_key_label.setStyleSheet("color: #ccc;")

    @pyqtSlot()
    def run_check(self):
        service = self.service_combo.currentData()
        text_to_check = self.input_text.toPlainText().strip()
        api_key = self.key_manager.get_active_key(service)

        if not text_to_check:
            self.result_text.setText("❌ Помилка: Введіть текст для перевірки.")
            return

        if service != 'google' and not api_key:
            self.result_text.setText(f"❌ Помилка: Для сервісу '{service.capitalize()}' не встановлено активний API ключ.")
            QMessageBox.warning(self, "Ключ не знайдено", "Будь ласка, встановіть активний ключ у налаштуваннях API.")
            return

        self.check_button.setEnabled(False)
        self.status_label.setText("Обробка запиту...")
        self.result_text.clear()

        self.thread = QThread()
        self.worker = Worker(self._translation_task, text_to_check, service, api_key)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_check_finished)
        self.thread.start()

    def _translation_task(self, text, service, api_key):
        """Ця функція виконується в окремому потоці."""
        try:
            translator = None
            if service == 'deepl':
                translator = DeepLTranslator(api_key)
            else: # google
                translator = GoogleTranslator()

            # Перекладаємо один елемент
            result_batch = translator.translate_batch(
                items=[{'text': text}],
                src_lang='auto',
                dest_lang='EN-US' # Використовуємо EN-US для сумісності з DeepL
            )
            return result_batch[0]
        except Exception as e:
            return e


    @pyqtSlot(object)
    def on_check_finished(self, result):
        if isinstance(result, Exception):
            self.status_label.setText("❌ Помилка перевірки.")
            self.result_text.setText(f"Сталася помилка:\n\n{result}")
        else:
            translated_text = result.get('translated', 'Не вдалося отримати переклад.')
            if "ПОМИЛКА" in translated_text:
                 self.status_label.setText("❌ Помилка перевірки.")
            else:
                 self.status_label.setText("✅ Успіх! Сервіс працює.")
            self.result_text.setText(translated_text)

        self.check_button.setEnabled(True)
        if self.thread:
            self.thread.quit()
            self.thread.wait()
            self.thread = None
            self.worker = None