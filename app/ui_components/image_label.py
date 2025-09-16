# app/ui_components/image_label.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QPainter, QPen
from PyQt6.QtCore import Qt, QRect

class ImageLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.original_pixmap = QPixmap()
        self.scaled_pixmap_display = QPixmap()
        self.rects = []
        self.selected_indices = []
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_pixmap(self, pixmap):
        self.original_pixmap = pixmap if pixmap else QPixmap()
        self.update_scaled_display()
        self.update()

    def set_rects(self, rects):
        self.rects = rects
        self.update()

    def set_selected_indices(self, indices):
        self.selected_indices = indices
        self.update()

    def update_scaled_display(self):
        if self.original_pixmap.isNull() or self.size().width() <= 0 or self.size().height() <= 0:
            self.scaled_pixmap_display = QPixmap()
            return
        self.scaled_pixmap_display = self.original_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.update()

    def paintEvent(self, event):
        if self.scaled_pixmap_display.isNull():
            return

        painter = QPainter(self)
        x_offset = (self.width() - self.scaled_pixmap_display.width()) // 2
        y_offset = (self.height() - self.scaled_pixmap_display.height()) // 2
        painter.drawPixmap(x_offset, y_offset, self.scaled_pixmap_display)

        if not self.rects or self.original_pixmap.width() == 0 or self.scaled_pixmap_display.width() == 0:
            return

        scale_factor = self.scaled_pixmap_display.width() / self.original_pixmap.width()

        for i, rect_data in enumerate(self.rects):
            original_rect = rect_data['rect']
            scaled_rect = QRect(
                x_offset + int(original_rect.x() * scale_factor),
                y_offset + int(original_rect.y() * scale_factor),
                int(original_rect.width() * scale_factor),
                int(original_rect.height() * scale_factor)
            )
            pen = QPen(Qt.GlobalColor.yellow, 3) if i in self.selected_indices else QPen(Qt.GlobalColor.red, 2)
            painter.setPen(pen)
            painter.drawRect(scaled_rect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scaled_display()