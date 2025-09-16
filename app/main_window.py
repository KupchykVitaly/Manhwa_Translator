# app/main_window.py

import sys
import os
import traceback
import easyocr
import cv2
import numpy as np

# Оновлені імпорти з нової структури
from .core.translators import GoogleTranslator, DeepLTranslator
from .core.api_manager import ApiKeyManager
from .core.worker import Worker
from .ui_components.settings_dialog import SettingsDialog
from .ui_components.check_dialog import ServiceCheckDialog
from .ui_components.image_label import ImageLabel
from .ui_components.drop_zone import DropZoneWidget
from .ui_components.minimap import MinimapWidget
from .ui_components.page_list import PageListWidget

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QListWidget, QListWidgetItem, QTextEdit,
    QFileDialog, QGroupBox, QFormLayout, QFontComboBox, QSpinBox,
    QStatusBar, QFrame, QComboBox, QGridLayout, QProgressBar, QStackedWidget,
    QSplitter, QMessageBox
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QFont, QFontDatabase,
    QColor, QFontMetrics, QIcon
)
from PyQt6.QtCore import Qt, QRect, pyqtSlot, QSize, QThread, QEvent

class ManhwaTranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Перекладач Манхви")
        self.setGeometry(100, 100, 1600, 900)

        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fonts_path = os.path.join(base_path, 'fonts')
        self.loaded_fonts = self.load_fonts(fonts_path)
        self.setStyleSheet(self.get_stylesheet())

        self._is_scrolling = False
        self._is_first_show = True

        self._setup_ui()
        self._connect_signals()

        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        self.image_path = None; self.current_pixmap = QPixmap()
        self.found_rects = []; self.translated_pixmap = QPixmap()
        self.thread = None; self.worker = None

        self.translation_groups = []
        self.sentences_to_translate = []

        self.view_stack.setCurrentWidget(self.drop_zone)
        self.ocr_reader = None

        self._update_language_combos()
        self.start_ocr_initialization()
        self.update_page_control_buttons()

    def changeEvent(self, event: QEvent):
        """Перехоплює зміну стану вікна (напр. згортання)."""
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                for combo_box in self.findChildren(QComboBox):
                    combo_box.hidePopup()

    def _setup_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        image_panel_widget = QWidget()
        left_layout = QVBoxLayout(image_panel_widget)
        left_layout.setContentsMargins(0,0,0,0)

        top_panel_container = QWidget()
        settings_panel_layout = QHBoxLayout(top_panel_container)
        settings_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        service_group = QGroupBox("Сервіс перекладу")
        service_layout = QHBoxLayout(service_group)
        self.translator_service_combo = QComboBox()
        self.translator_service_combo.addItem("Google Translate", "google")
        self.translator_service_combo.addItem("DeepL", "deepl")
        self.btn_settings = QPushButton("⚙️ API")
        self.btn_check_service = QPushButton("🔬 Перевірка")
        service_layout.addWidget(self.translator_service_combo)
        service_layout.addWidget(self.btn_settings)
        service_layout.addWidget(self.btn_check_service)

        lang_group = QGroupBox("Мова")
        lang_layout = QHBoxLayout(lang_group)
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        arrow_label = QLabel("→")
        lang_layout.addWidget(self.source_lang_combo)
        lang_layout.addWidget(arrow_label)
        lang_layout.addWidget(self.target_lang_combo)

        ocr_mode_group = QGroupBox("Режим розпізнавання (OCR)")
        ocr_mode_layout = QHBoxLayout(ocr_mode_group)
        self.ocr_mode_combo = QComboBox()
        self.ocr_mode_combo.addItem("Стандартний", "standard")
        self.ocr_mode_combo.addItem("Покращений (OpenCV)", "opencv")
        self.ocr_mode_combo.setToolTip("Покращений режим може підвищити точність на складних зображеннях.")
        ocr_mode_layout.addWidget(self.ocr_mode_combo)

        settings_panel_layout.addWidget(service_group)
        settings_panel_layout.addWidget(lang_group)
        settings_panel_layout.addWidget(ocr_mode_group)
        settings_panel_layout.addStretch()

        top_panel_container.setMaximumHeight(100)
        left_layout.addWidget(top_panel_container)

        self.image_splitter = QSplitter(Qt.Orientation.Horizontal)
        original_frame = QFrame(); original_frame.setObjectName("imageFrame")
        original_frame_layout = QVBoxLayout(original_frame)
        original_frame_layout.addWidget(QLabel("Оригінал:"))
        self.view_stack = QStackedWidget()
        self.drop_zone = DropZoneWidget()
        self.original_scroll_area = QScrollArea(); self.original_scroll_area.setWidgetResizable(False)
        self.original_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.original_image_label = ImageLabel()
        self.original_scroll_area.setWidget(self.original_image_label)
        self.view_stack.addWidget(self.drop_zone)
        self.view_stack.addWidget(self.original_scroll_area)
        original_frame_layout.addWidget(self.view_stack)
        translated_frame = QFrame(); translated_frame.setObjectName("imageFrame")
        translated_layout = QVBoxLayout(translated_frame)
        translated_layout.addWidget(QLabel("Переклад:"))
        self.translated_scroll_area = QScrollArea(); self.translated_scroll_area.setWidgetResizable(False)
        self.translated_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.translated_image_label = QLabel(); self.translated_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.translated_scroll_area.setWidget(self.translated_image_label)
        translated_layout.addWidget(self.translated_scroll_area)
        self.image_splitter.addWidget(original_frame)
        self.image_splitter.addWidget(translated_frame)
        self.image_splitter.handle(1).setDisabled(True)
        left_layout.addWidget(self.image_splitter)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        pages_group = QGroupBox("Сторінки")
        pages_layout = QVBoxLayout(pages_group)
        self.page_list_widget = PageListWidget(self)
        self.page_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.page_list_widget.setIconSize(QSize(80, 120))
        self.page_list_widget.setMovement(QListWidget.Movement.Static)
        self.page_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.page_list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.page_list_widget.setWrapping(False)
        self.page_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.page_list_widget.setWordWrap(True)
        pages_layout.addWidget(self.page_list_widget)

        page_buttons_panel = QWidget()
        page_buttons_layout = QGridLayout(page_buttons_panel)
        page_buttons_layout.setContentsMargins(0, 5, 0, 0)
        self.btn_add_page = QPushButton("+ Додати (Ins)")
        self.btn_delete_page = QPushButton("❌ Видалити (Del)")
        separator = QFrame(); separator.setFrameShape(QFrame.Shape.VLine); separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.btn_to_start = QPushButton("⇤")
        self.btn_left = QPushButton("←")
        self.btn_right = QPushButton("→")
        self.btn_to_end = QPushButton("⇥")
        self.btn_to_start.setToolTip("Перемістити на початок (Ctrl+Home)")
        self.btn_left.setToolTip("Перемістити вліво (Ctrl+Left)")
        self.btn_right.setToolTip("Перемістити вправо (Ctrl+Right)")
        self.btn_to_end.setToolTip("Перемістити в кінець (Ctrl+End)")
        page_buttons_layout.addWidget(self.btn_add_page, 0, 0)
        page_buttons_layout.addWidget(self.btn_delete_page, 1, 0)
        page_buttons_layout.addWidget(separator, 0, 1, 2, 1)
        nav_left_layout = QVBoxLayout()
        nav_left_layout.setSpacing(2)
        nav_left_layout.addWidget(self.btn_left)
        nav_left_layout.addWidget(self.btn_to_start)
        nav_right_layout = QVBoxLayout()
        nav_right_layout.setSpacing(2)
        nav_right_layout.addWidget(self.btn_right)
        nav_right_layout.addWidget(self.btn_to_end)
        page_buttons_layout.addLayout(nav_left_layout, 0, 2, 2, 1)
        page_buttons_layout.addLayout(nav_right_layout, 0, 3, 2, 1)
        page_buttons_layout.setColumnStretch(4, 1)
        pages_layout.addWidget(page_buttons_panel)

        right_layout.addWidget(pages_group, 3)
        right_layout.addWidget(QLabel("Знайдені текстові блоки:"))
        self.text_list = QListWidget()
        right_layout.addWidget(self.text_list, 1)

        edit_group = QGroupBox("Редагування виділеного блоку")
        form_layout = QFormLayout()
        self.original_text = QTextEdit(); self.original_text.setReadOnly(True)
        self.translated_text = QTextEdit()
        font_metrics = QFontMetrics(self.translated_text.font())
        line_height = font_metrics.height()
        compact_height = int(line_height * 5)
        self.original_text.setFixedHeight(compact_height)
        self.translated_text.setFixedHeight(compact_height)
        self.font_combo = QComboBox()
        if self.loaded_fonts: self.font_combo.addItems(self.loaded_fonts)
        else: self.font_combo = QFontComboBox()
        self.font_size_spin = QSpinBox(); self.font_size_spin.setRange(6, 72)
        form_layout.addRow("Оригінал:", self.original_text)
        form_layout.addRow("Переклад:", self.translated_text)
        form_layout.addRow("Шрифт:", self.font_combo)
        form_layout.addRow("Розмір:", self.font_size_spin)
        edit_group.setLayout(form_layout)
        right_layout.addWidget(edit_group)

        action_buttons_layout = QGridLayout()
        self.btn_process = QPushButton("Розпізнати та Перекласти")
        self.btn_render = QPushButton("Відтворити")
        self.btn_save = QPushButton("Зберегти")
        action_buttons_layout.addWidget(self.btn_process, 0, 0, 1, 2)
        action_buttons_layout.addWidget(self.btn_render, 1, 0)
        action_buttons_layout.addWidget(self.btn_save, 1, 1)
        right_layout.addLayout(action_buttons_layout)
        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.hide()
        right_layout.addWidget(self.progress_bar)

        self.minimap = MinimapWidget(self.original_scroll_area, self.translated_scroll_area)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(image_panel_widget)
        self.main_splitter.addWidget(self.minimap)
        self.main_splitter.addWidget(right_widget)
        main_layout.addWidget(self.main_splitter)
        
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setStretchFactor(2, 0)
        
        initial_width = self.width()
        minimap_width = self.minimap.width()
        tools_width = int(initial_width * 0.28)
        image_width = initial_width - tools_width - minimap_width
        self.main_splitter.setSizes([image_width, minimap_width, tools_width])
        right_widget.setMinimumWidth(400)


    def showEvent(self, event):
        """Ця функція більше не керує розмірами спліттера."""
        super().showEvent(event)
        if self._is_first_show:
            # Цей блок залишається, але без логіки розмірів,
            # оскільки вона тепер в _setup_ui.
            self._is_first_show = False

    def _connect_signals(self):
        self.translator_service_combo.currentIndexChanged.connect(self._update_language_combos)
        self.btn_settings.clicked.connect(self.open_settings_dialog)
        self.btn_check_service.clicked.connect(self.open_service_checker)
        self.drop_zone.btn_browse.clicked.connect(self.open_image_dialog)
        self.drop_zone.files_dropped.connect(self.add_pages)
        self.btn_process.clicked.connect(self.start_full_process)
        self.btn_render.clicked.connect(self.render_translated_image)
        self.btn_save.clicked.connect(self.save_translated_image)
        self.text_list.currentRowChanged.connect(self.update_edit_panel)
        self.translated_text.textChanged.connect(self.update_data_from_panel)
        self.font_combo.currentTextChanged.connect(self.update_data_from_panel)
        self.font_size_spin.valueChanged.connect(self.update_data_from_panel)
        self.original_scroll_bar = self.original_scroll_area.verticalScrollBar()
        self.translated_scroll_bar = self.translated_scroll_area.verticalScrollBar()
        self.original_scroll_bar.valueChanged.connect(self.sync_scroll_from_original)
        self.translated_scroll_bar.valueChanged.connect(self.sync_scroll_from_translated)
        self.original_scroll_bar.valueChanged.connect(self.minimap.update_viewport)
        self.original_scroll_bar.rangeChanged.connect(self.minimap.update_viewport)
        # Сигнал splitterMoved тепер не потрібен для балансування, але корисний для оновлення розміру зображення
        self.main_splitter.splitterMoved.connect(self.update_image_display_sizes)
        self.page_list_widget.currentItemChanged.connect(self.on_page_selected)
        self.page_list_widget.model().rowsMoved.connect(self.renumber_pages)
        self.btn_add_page.clicked.connect(self.open_image_dialog)
        self.btn_delete_page.clicked.connect(self.delete_page)
        self.btn_left.clicked.connect(self.move_left)
        self.btn_right.clicked.connect(self.move_right)
        self.btn_to_start.clicked.connect(self.move_to_start)
        self.btn_to_end.clicked.connect(self.move_to_end)

    def _update_language_combos(self):
        service = self.translator_service_combo.currentData()
        self.source_lang_combo.clear()
        self.target_lang_combo.clear()
        if service == 'deepl':
            self.source_lang_combo.addItem("Авто-визначення", "auto")
            for name, code in DeepLTranslator.SUPPORTED_SOURCE_LANGS.items():
                self.source_lang_combo.addItem(name, code)
            for name, code in DeepLTranslator.SUPPORTED_TARGET_LANGS.items():
                self.target_lang_combo.addItem(name, code)
        else:
            google_source_langs = {"Авто-визначення": "auto", "Корейська": "ko", "Англійська": "en", "Японська": "ja", "Китайська": "zh-cn"}
            google_target_langs = {"Українська": "uk", "Англійська": "en", "Російська": "ru"}
            for name, code in google_source_langs.items():
                self.source_lang_combo.addItem(name, code)
            for name, code in google_target_langs.items():
                self.target_lang_combo.addItem(name, code)
            self.target_lang_combo.setCurrentText("Українська")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def open_service_checker(self):
        dialog = ServiceCheckDialog(self)
        dialog.exec()

    def _distribute_text_to_group(self, group_index, new_text):
        group_indices = self.translation_groups[group_index]
        original_words_in_group = [self.found_rects[idx]['text'].split() for idx in group_indices]
        total_original_words = sum(len(words) for words in original_words_in_group)
        translated_words = new_text.split()
        total_translated_words = len(translated_words)
        start_index = 0
        for j, idx in enumerate(group_indices):
            num_original_words = len(original_words_in_group[j])
            share = num_original_words / total_original_words if total_original_words > 0 else 0
            num_translated_words = round(share * total_translated_words)
            if j == len(group_indices) - 1:
                chunk = translated_words[start_index:]
            else:
                chunk = translated_words[start_index : start_index + num_translated_words]
            self.found_rects[idx]['translated'] = " ".join(chunk)
            start_index += num_translated_words

    def open_image_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Обрати зображення", "", "Images (*.png *.jpg *.jpeg)")
        if paths:
            self.add_pages(paths)

    def add_pages(self, paths: list):
        self.status_bar.showMessage(f"Додавання {len(paths)} сторінок...")
        for path in paths:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setText(os.path.basename(path))
            thumb = QPixmap(path).scaled(self.page_list_widget.iconSize(),
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
            item.setIcon(QIcon(thumb))
            self.page_list_widget.addItem(item)
        self.renumber_pages()
        if self.page_list_widget.count() > 0 and self.image_path is None:
            self.page_list_widget.setCurrentRow(0)
        self.status_bar.showMessage(f"Готово. Всього сторінок: {self.page_list_widget.count()}", 5000)

    def delete_page(self):
        selected_item = self.page_list_widget.currentItem()
        if not selected_item: return
        reply = QMessageBox.question(self, 'Підтвердження',
                                       f"Ви впевнені, що хочете видалити сторінку '{selected_item.text()}'?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            row = self.page_list_widget.currentRow()
            self.page_list_widget.takeItem(row)
            self.renumber_pages()
            if self.page_list_widget.count() == 0:
                self.display_page(None)
            elif row >= self.page_list_widget.count():
                self.page_list_widget.setCurrentRow(self.page_list_widget.count() - 1)
            else:
                self.page_list_widget.setCurrentRow(row)

    def renumber_pages(self):
        for i in range(self.page_list_widget.count()):
            item = self.page_list_widget.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            item.setText(f"{i + 1}. {os.path.basename(path)}")
        self.update_page_control_buttons()

    def move_left(self):
        current_row = self.page_list_widget.currentRow()
        if current_row > 0:
            item = self.page_list_widget.takeItem(current_row)
            self.page_list_widget.insertItem(current_row - 1, item)
            self.page_list_widget.setCurrentItem(item)
            self.page_list_widget.scrollToItem(item)
            self.renumber_pages()

    def move_right(self):
        current_row = self.page_list_widget.currentRow()
        if current_row < self.page_list_widget.count() - 1:
            item = self.page_list_widget.takeItem(current_row)
            self.page_list_widget.insertItem(current_row + 1, item)
            self.page_list_widget.setCurrentItem(item)
            self.page_list_widget.scrollToItem(item)
            self.renumber_pages()

    def move_to_start(self):
        current_row = self.page_list_widget.currentRow()
        if current_row > 0:
            item = self.page_list_widget.takeItem(current_row)
            self.page_list_widget.insertItem(0, item)
            self.page_list_widget.setCurrentItem(item)
            self.page_list_widget.scrollToItem(item)
            self.renumber_pages()

    def move_to_end(self):
        current_row = self.page_list_widget.currentRow()
        if current_row < self.page_list_widget.count() - 1:
            item = self.page_list_widget.takeItem(current_row)
            self.page_list_widget.insertItem(self.page_list_widget.count(), item)
            self.page_list_widget.setCurrentItem(item)
            self.page_list_widget.scrollToItem(item)
            self.renumber_pages()

    def on_page_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        path = current.data(Qt.ItemDataRole.UserRole) if current else None
        self.display_page(path)
        self.update_page_control_buttons()

    def display_page(self, path):
        if not path:
            self.image_path = None
            self.current_pixmap = QPixmap()
            self.original_image_label.set_pixmap(self.current_pixmap)
            self.translated_image_label.setPixmap(QPixmap())
            self.minimap.set_pixmap(QPixmap())
            self.text_list.clear()
            self.clear_edit_panel()
            self.original_image_label.set_selected_indices([])
            self.found_rects = []
            self.view_stack.setCurrentWidget(self.drop_zone)
            self.update_button_states()
            return

        self.image_path = path
        self.current_pixmap = QPixmap(path)
        if self.current_pixmap.isNull():
            self.status_bar.showMessage(f"Помилка: не вдалося завантажити зображення {path}")
            self.image_path = None
            return

        self.original_image_label.set_pixmap(self.current_pixmap)
        self.minimap.set_pixmap(self.current_pixmap)
        self.translated_pixmap = QPixmap()
        self.translated_image_label.setPixmap(QPixmap())
        self.translated_image_label.setFixedSize(0,0)
        self.status_bar.showMessage(f"Відкрито: {path}")
        self.text_list.clear()
        self.clear_edit_panel()
        self.original_image_label.set_rects([])
        self.original_image_label.set_selected_indices([])
        self.found_rects = []
        self.view_stack.setCurrentWidget(self.original_scroll_area)
        QApplication.processEvents()
        self.balance_image_splitter()
        self.update_image_display_sizes()
        self.update_button_states()

    @pyqtSlot(int)
    def sync_scroll_from_original(self, value):
        if not self._is_scrolling:
            self._is_scrolling = True
            self.translated_scroll_bar.setValue(value)
            self._is_scrolling = False

    @pyqtSlot(int)
    def sync_scroll_from_translated(self, value):
        if not self._is_scrolling:
            self._is_scrolling = True
            self.original_scroll_bar.setValue(value)
            self._is_scrolling = False

    def start_ocr_initialization(self):
        self.set_buttons_enabled(False)
        self.status_bar.showMessage("Завантаження OCR-моделей... Це може зайняти хвилину.")
        self.progress_bar.setRange(0, 0); self.progress_bar.setFormat("Ініціалізація..."); self.progress_bar.show()
        self.thread = QThread()
        self.worker = Worker(self._initialize_ocr_task)
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.on_ocr_initialized)
        self.thread.started.connect(self.worker.run)
        self.worker.error.connect(self.on_task_error)
        self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _initialize_ocr_task(self):
        ocr_langs = ['ko', 'en']
        try:
            reader = easyocr.Reader(ocr_langs, gpu=True)
            device = "GPU"
        except Exception:
            reader = easyocr.Reader(ocr_langs, gpu=False)
            device = "CPU"
        return reader, device, ocr_langs

    def on_ocr_initialized(self, result):
        self.ocr_reader, device, ocr_langs = result
        self.progress_bar.hide()
        self.status_bar.showMessage(f"OCR завантажено для {ocr_langs} ({device}). Готово до роботи!")
        self.set_buttons_enabled(True)

    def get_stylesheet(self):
        return """
            QWidget { background-color: #2c2f33; color: #ffffff; font-family: 'Segoe UI'; font-size: 11pt; }
            QPushButton { background-color: #7289da; color: white; border: none; padding: 8px 16px; border-radius: 5px; }
            QPushButton:hover { background-color: #677bc4; }
            QPushButton:pressed { background-color: #5b6eae; }
            QPushButton:disabled { background-color: #4a4d50; color: #8e9297; }
            QSplitter::handle { background-color: #4a4d50; }
            QSplitter::handle:horizontal { width: 5px; }
            QSplitter::handle:hover { background-color: #7289da; }
            QSplitterHandle:disabled { background-color: #2c2f33; image: none; }
            QProgressBar { border: 2px solid #4a4d50; border-radius: 5px; text-align: center; color: white; font-weight: bold; }
            QProgressBar::chunk { background-color: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #FF007A, stop: 1 #00D1FF); border-radius: 3px; margin: 2px; }
            QComboBox { background-color: #4a4d50; border-radius: 5px; padding: 5px; min-width: 100px;}
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #4a4d50; selection-background-color: #7289da; }
            QFrame#imageFrame { background-color: #23272a; border: 1px solid #4a4d50; border-radius: 8px; }
            QScrollArea { border: none; }
            QTextEdit, QSpinBox { background-color: #4a4d50; border-radius: 5px; padding: 5px; }
            QListWidget { background-color: #4a4d50; border-radius: 5px; padding: 5px; font-family: 'Malgun Gothic', 'Arial'; }
            QListWidget::item { border-radius: 4px; padding: 2px; color: #b0b3b8;}
            QListWidget::item:selected { background-color: rgba(114, 137, 218, 0.8); border: 2px solid #7289da; color: white;}
            QGroupBox { border: 1px solid #4a4d50; border-radius: 8px; margin-top: 10px; padding: 10px 5px 5px 5px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; }
            QStatusBar { background-color: #23272a; }
        """

    def load_fonts(self, fonts_dir):
        loaded_font_families = []
        if not os.path.isdir(fonts_dir):
            print(f"Папку зі шрифтами не знайдено: {fonts_dir}")
            return []
        for font_file in os.listdir(fonts_dir):
            if font_file.lower().endswith(('.ttf', '.otf')):
                font_path = os.path.join(fonts_dir, font_file)
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    family = QFontDatabase.applicationFontFamilies(font_id)[0]
                    loaded_font_families.append(family)
        return loaded_font_families

    def update_image_display_sizes(self, *_):
        if self.current_pixmap.isNull():
            self.original_image_label.setFixedSize(0,0)
            self.translated_image_label.setFixedSize(0,0)
            return
        available_width = self.original_scroll_area.viewport().width()
        if available_width <= 0: return

        display_width = min(self.current_pixmap.width(), available_width - 5)
        if self.current_pixmap.width() > 0:
            aspect_ratio = self.current_pixmap.height() / self.current_pixmap.width()
            display_height = int(display_width * aspect_ratio)
        else:
            display_height = 0
        self.original_image_label.setFixedSize(display_width, display_height)
        self.translated_image_label.setFixedSize(display_width, display_height)
        self.original_image_label.update_scaled_display()
        self.display_translated_image()
        QApplication.processEvents()
        self.minimap.update_viewport()

    def render_translated_image(self):
        if self.current_pixmap.isNull(): return
        self.status_bar.showMessage("Виконується відтворення...")
        QApplication.processEvents()
        self.translated_pixmap = self.current_pixmap.copy()
        painter = QPainter(self.translated_pixmap)
        comic_fonts_with_spacing = ["Badaboom", "CCShoutOut", "Anime Ace"]
        for item in self.found_rects:
            if not item.get('translated', ''): continue
            rect, text = item['rect'], item['translated']
            font_name = item['font']
            font_size = item['font_size']
            font = QFont(font_name, font_size)
            if any(comic_font in font_name for comic_font in comic_fonts_with_spacing):
                font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
            painter.setFont(font)
            painter.fillRect(rect, Qt.GlobalColor.white)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), text)
        painter.end()
        self.display_translated_image()
        self.status_bar.showMessage("Відтворення завершено.")
        self.update_button_states()

    def display_translated_image(self):
        if self.translated_pixmap.isNull() or self.translated_image_label.size().width() <= 0:
            self.translated_image_label.setPixmap(QPixmap())
            return
        scaled_pixmap = self.translated_pixmap.scaled(
            self.translated_image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.translated_image_label.setPixmap(scaled_pixmap)

    def save_translated_image(self):
        if self.translated_pixmap.isNull(): return
        original_path = self.image_path
        base_name = os.path.basename(original_path)
        name, ext = os.path.splitext(base_name)
        default_save_path = os.path.join(os.path.dirname(original_path), f"{name}_translated.png")
        path, _ = QFileDialog.getSaveFileName(self, "Зберегти зображення", default_save_path, "PNG (*.png)")
        if path:
            self.translated_pixmap.save(path)
            self.status_bar.showMessage(f"Збережено в: {path}")

    def balance_image_splitter(self):
        try:
            sizes = self.main_splitter.sizes()
            total_image_width = sizes[0] + sizes[1]
            half_width = total_image_width // 2
            self.image_splitter.setSizes([half_width, total_image_width - half_width])
        except Exception:
             pass # Може виникнути при першому запуску, ігноруємо

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.balance_image_splitter()
        self.update_image_display_sizes()
        if hasattr(self, 'minimap'):
            self.minimap.update_viewport()

    def update_data_from_panel(self):
        current_item = self.text_list.currentItem()
        if not current_item: return
        group_index = current_item.data(Qt.ItemDataRole.UserRole)
        if 0 <= group_index < len(self.translation_groups):
            new_font = self.font_combo.currentText()
            new_size = self.font_size_spin.value()
            group_indices = self.translation_groups[group_index]
            for idx in group_indices:
                self.found_rects[idx]['font'] = new_font
                self.found_rects[idx]['font_size'] = new_size
            new_translated_text = self.translated_text.toPlainText()
            self._distribute_text_to_group(group_index, new_translated_text)
            self.update_button_states()

    def update_edit_panel(self, current_row):
        if 0 <= current_row < len(self.translation_groups):
            group_index = current_row
            group_indices = self.translation_groups[group_index]
            self.original_image_label.set_selected_indices(group_indices)
            original_text = " ".join([self.found_rects[i]['text'] for i in group_indices])
            translated_text = " ".join([self.found_rects[i]['translated'] for i in group_indices])
            self.original_text.setText(original_text)
            self.translated_text.setText(translated_text)
            first_item_data = self.found_rects[group_indices[0]]
            font_name = first_item_data.get('font', self.loaded_fonts[0] if self.loaded_fonts else "Arial")
            self.font_combo.setCurrentText(font_name)
            self.font_size_spin.setValue(first_item_data.get('font_size', 14))

    def on_task_error(self, error_info):
        exctype, value, tb_str = error_info
        print(tb_str)
        QMessageBox.critical(self, "Помилка виконання", f"Сталася помилка:\n{value}\n\nДеталі в консолі.")
        self.status_bar.showMessage(f"Помилка: {value}")
        self.progress_bar.hide()
        self.set_buttons_enabled(True)

    def _preprocess_with_opencv(self, image_path):
        try:
            with open(image_path, "rb") as f:
                image_bytes = np.frombuffer(f.read(), np.uint8)
            img = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            processed_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                  cv2.THRESH_BINARY, 11, 2)
            return processed_img
        except Exception as e:
            print(f"Помилка під час обробки OpenCV: {e}")
            return None

    def _ocr_task(self, image_path, mode):
        if mode == "opencv":
            processed_image = self._preprocess_with_opencv(image_path)
            if processed_image is None:
                return self.ocr_reader.readtext(image_path)
            return self.ocr_reader.readtext(processed_image)
        else: # standard
            return self.ocr_reader.readtext(image_path)

    def start_full_process(self):
        if not self.image_path or not self.ocr_reader: return
        self.set_buttons_enabled(False)
        self.status_bar.showMessage("Крок 1/2: Розпізнавання тексту...")
        self.progress_bar.setRange(0, 0); self.progress_bar.setFormat("Аналіз зображення..."); self.progress_bar.show()
        ocr_mode = self.ocr_mode_combo.currentData()
        self.thread = QThread()
        self.worker = Worker(self._ocr_task, self.image_path, ocr_mode)
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.on_detection_finished_and_start_translation)
        self.thread.started.connect(self.worker.run)
        self.worker.error.connect(self.on_task_error)
        self.worker.finished.connect(self.thread.quit); self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _group_text_bubbles(self, ocr_results, max_distance=70):
        if not ocr_results: return []
        sorted_blocks = sorted(
            [{
                'id': i,
                'rect': QRect(int(bbox[0][0]), int(bbox[0][1]), int(bbox[1][0] - bbox[0][0]), int(bbox[2][1] - bbox[1][1])),
                'text': text
            } for i, (bbox, text, prob) in enumerate(ocr_results)],
            key=lambda b: (b['rect'].center().y(), b['rect'].center().x())
        )
        if not sorted_blocks: return []
        groups = []
        current_group = [sorted_blocks[0]['id']]
        for i in range(1, len(sorted_blocks)):
            prev_box = sorted_blocks[i-1]
            current_box = sorted_blocks[i]
            vertical_distance = current_box['rect'].top() - prev_box['rect'].bottom()
            if 0 <= vertical_distance < max_distance:
                current_group.append(current_box['id'])
            else:
                groups.append(current_group)
                current_group = [current_box['id']]
        groups.append(current_group)
        return groups

    def on_detection_finished_and_start_translation(self, results):
        self.found_rects = []
        for (bbox, text, prob) in results:
            top_left, _, bottom_right, _ = bbox
            rect = QRect(int(top_left[0]), int(top_left[1]), int(bottom_right[0] - top_left[0]), int(bottom_right[1] - top_left[1]))
            default_font = self.loaded_fonts[0] if self.loaded_fonts else "Arial"
            self.found_rects.append({'rect': rect, 'text': text, 'translated': '', 'font': default_font, 'font_size': 14})
        self.translation_groups = self._group_text_bubbles(results)
        self.sentences_to_translate = []
        for group_idx, group in enumerate(self.translation_groups):
            combined_text = " ".join(self.found_rects[i]['text'] for i in group)
            self.sentences_to_translate.append(combined_text)
        self.original_image_label.set_rects(self.found_rects)
        self.text_list.clear()
        for i, sentence in enumerate(self.sentences_to_translate):
            item = QListWidgetItem(f"{i+1}. {sentence[:60]}...")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.text_list.addItem(item)
        self.status_bar.showMessage(f"Розпізнано {len(self.found_rects)} блоків, згруповано в {len(self.translation_groups)} речень. Переклад...")
        self.progress_bar.setFormat("Переклад речень...")
        QApplication.processEvents()
        self.translate_all_blocks()

    def _translation_task(self, items, src_lang, dest_lang, service, api_key=""):
        try:
            translator = None
            if service == 'deepl':
                translator = DeepLTranslator(api_key)
            else:
                translator = GoogleTranslator()
            return translator.translate_batch(items, src_lang, dest_lang)
        except Exception as e:
            return e # Повертаємо виняток, а не викликаємо raise

    def translate_all_blocks(self):
        if not self.sentences_to_translate:
            self.progress_bar.hide()
            self.set_buttons_enabled(True)
            return
        service = self.translator_service_combo.currentData()
        source_lang_code = self.source_lang_combo.currentData()
        target_lang_code = self.target_lang_combo.currentData()
        api_key = None
        if service != 'google':
            key_manager = ApiKeyManager()
            api_key = key_manager.get_active_key(service)
            if not api_key:
                QMessageBox.warning(self, f"Немає API ключа",
                                    f"Для сервісу '{service.capitalize()}' не обрано активний API ключ.")
                self.progress_bar.hide()
                self.set_buttons_enabled(True)
                self.open_settings_dialog()
                return
        items_to_translate = [{'text': sentence} for sentence in self.sentences_to_translate]
        self.thread = QThread()
        self.worker = Worker(self._translation_task,
                             items_to_translate,
                             source_lang_code,
                             target_lang_code,
                             service,
                             api_key=api_key)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_translation_finished)
        self.worker.error.connect(self.on_task_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_translation_finished(self, result):
        if isinstance(result, Exception):
            self.on_task_error((type(result), result, traceback.format_exc()))
            return

        translated_sentences_items = result
        translated_sentences = [item.get('translated', 'ПОМИЛКА') for item in translated_sentences_items]
        for i, group_indices in enumerate(self.translation_groups):
             if i < len(translated_sentences):
                self._distribute_text_to_group(i, translated_sentences[i])
        self.status_bar.showMessage("Розпізнавання та переклад завершено.")
        if self.text_list.count() > 0:
            self.text_list.setCurrentRow(0)
            self.update_edit_panel(0)
        self.progress_bar.hide()
        self.set_buttons_enabled(True)
        self.update_button_states()

    def clear_edit_panel(self):
        self.original_text.clear(); self.translated_text.clear()
        default_font = self.loaded_fonts[0] if self.loaded_fonts else "Arial"
        self.font_combo.setCurrentText(default_font)
        self.font_size_spin.setValue(12)
        self.original_image_label.set_selected_indices([])

    def set_buttons_enabled(self, enabled):
        is_ocr_ready = self.ocr_reader is not None
        master_enabled = enabled and is_ocr_ready
        self.btn_process.setEnabled(master_enabled)
        self.btn_render.setEnabled(master_enabled)
        self.btn_save.setEnabled(master_enabled)
        self.page_list_widget.setEnabled(master_enabled)
        self.btn_add_page.setEnabled(master_enabled)
        self.text_list.setEnabled(master_enabled)
        if master_enabled:
            self.update_button_states()
        else:
            self.btn_process.setEnabled(False)
            self.btn_render.setEnabled(False)
            self.btn_save.setEnabled(False)
            self.btn_delete_page.setEnabled(False)
            self.btn_left.setEnabled(False); self.btn_right.setEnabled(False)
            self.btn_to_start.setEnabled(False); self.btn_to_end.setEnabled(False)

    def update_button_states(self):
        if self.ocr_reader is None:
            self.set_buttons_enabled(False)
            return
        has_image = not self.current_pixmap.isNull()
        has_rects = bool(self.found_rects)
        has_translations = has_rects and any(item.get('translated') for item in self.found_rects)
        has_rendered_image = not self.translated_pixmap.isNull()
        self.btn_process.setEnabled(has_image)
        self.btn_render.setEnabled(has_translations)
        self.btn_save.setEnabled(has_rendered_image)
        self.update_page_control_buttons()

    def update_page_control_buttons(self):
        selected_item = self.page_list_widget.currentItem()
        count = self.page_list_widget.count()
        current_row = self.page_list_widget.currentRow()
        self.btn_delete_page.setEnabled(selected_item is not None)
        is_not_first = selected_item is not None and current_row > 0
        self.btn_left.setEnabled(is_not_first)
        self.btn_to_start.setEnabled(is_not_first)
        is_not_last = selected_item is not None and current_row < count - 1
        self.btn_right.setEnabled(is_not_last)
        self.btn_to_end.setEnabled(is_not_last)