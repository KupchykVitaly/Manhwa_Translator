# app/ui_components/drop_zone.py
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QCursor
from PyQt6.QtCore import Qt, pyqtSignal

class DropZoneWidget(QFrame):
    files_dropped = pyqtSignal(list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel("Перетягніть сторінки сюди\n\nабо\n")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("dropZoneLabel")
        self.btn_browse = QPushButton("Обрати файли")
        self.btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_browse.setFixedSize(250, 50)
        self.btn_browse.setObjectName("dropZoneButton")
        layout.addWidget(self.label)
        layout.addWidget(self.btn_browse, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QFrame#dropZone { border: 3px dashed #4a4d50; border-radius: 15px; background-color: #23272a; }
            QLabel#dropZoneLabel { font-size: 16pt; color: #8e9297; border: none; background-color: transparent; }
            QPushButton#dropZoneButton { font-size: 12pt; font-weight: bold; background-color: #7289da; color: white; border-radius: 8px; }
            QPushButton#dropZoneButton:hover { background-color: #677bc4; }
        """)
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self.styleSheet().replace("border: 3px dashed #4a4d50;", "border: 3px dashed #7289da;"))
    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg')):
                paths.append(url.toLocalFile())
        if paths:
            self.files_dropped.emit(paths)
        self.setStyleSheet(self.styleSheet().replace("border: 3px dashed #7289da;", "border: 3px dashed #4a4d50;"))
    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("border: 3px dashed #7289da;", "border: 3px dashed #4a4d50;"))