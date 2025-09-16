# main.py
import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox

# Це потрібно, щоб Python міг знайти модулі всередині папки 'app'
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def main():
    """Головна функція для запуску додатку."""
    # Імпортуємо головне вікно тут, щоб sys.path вже був оновлений
    try:
        from app.main_window import ManhwaTranslatorApp
    except ImportError as e:
        QMessageBox.critical(None, "Помилка імпорту", f"Не вдалося знайти необхідні компоненти програми.\n"
                                                     f"Переконайтесь, що структура файлів правильна.\n\nДеталі: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = ManhwaTranslatorApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    # Перевіряємо, чи існує папка 'app', перш ніж запускати
    if not os.path.isdir('app'):
        app_dummy = QApplication(sys.argv)
        QMessageBox.critical(None, "Помилка структури", "Не знайдено папку 'app'. "
                                                       "Будь ласка, переконайтеся, що структура проєкту правильна.")
        sys.exit(1)
    main()
