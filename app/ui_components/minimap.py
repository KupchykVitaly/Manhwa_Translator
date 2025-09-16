# app/ui_components/minimap.py
from PyQt6.QtWidgets import QWidget, QScrollArea
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QRect

class MinimapWidget(QWidget):
    def __init__(self, scroll_area1: QScrollArea, scroll_area2: QScrollArea, parent=None):
        super().__init__(parent)
        self.scroll_area1 = scroll_area1
        self.scroll_area2 = scroll_area2
        self.full_pixmap = QPixmap()
        self.minimap_pixmap = QPixmap()
        self.viewport_rect = QRect()
        self.is_dragging = False
        self.setFixedWidth(80)
        self.update_viewport()

    def set_pixmap(self, pixmap: QPixmap):
        self.full_pixmap = pixmap
        if not self.full_pixmap.isNull():
            self.minimap_pixmap = self.full_pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            self.minimap_pixmap = QPixmap()
        self.update_viewport()
        self.update()

    def update_viewport(self):
        if self.full_pixmap.isNull() or not self.scroll_area1.verticalScrollBar():
            self.viewport_rect = QRect()
            self.update()
            return
        scroll_bar = self.scroll_area1.verticalScrollBar()
        image_label = self.scroll_area1.widget()
        if not image_label or image_label.height() == 0: return
        total_height = image_label.height()
        visible_height = self.scroll_area1.viewport().height()
        height_ratio = visible_height / total_height if total_height > 0 else 0
        minimap_viewport_height = int(self.height() * height_ratio)
        scroll_ratio = scroll_bar.value() / (scroll_bar.maximum() or 1)
        minimap_viewport_y = int((self.height() - minimap_viewport_height) * scroll_ratio)
        self.viewport_rect = QRect(0, minimap_viewport_y, self.width(), minimap_viewport_height)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#23272a"))
        if not self.minimap_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.minimap_pixmap)
        if not self.viewport_rect.isNull():
            painter.fillRect(self.viewport_rect, QColor(200, 200, 220, 80))
            painter.setPen(QColor(220, 220, 255, 150))
            painter.drawRect(self.viewport_rect)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.full_pixmap.isNull():
            self.set_pixmap(self.full_pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self._scroll_from_mouse_pos(event.position().y())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self._scroll_from_mouse_pos(event.position().y())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False

    def _scroll_from_mouse_pos(self, y_pos):
        scroll_bar1 = self.scroll_area1.verticalScrollBar()
        scroll_bar2 = self.scroll_area2.verticalScrollBar()
        if not scroll_bar1 or not scroll_bar2: return
        y_pos = max(0, min(y_pos, self.height()))
        scroll_percentage = y_pos / self.height() if self.height() > 0 else 0
        target_scroll_value = int(scroll_bar1.maximum() * scroll_percentage)
        scroll_bar1.setValue(target_scroll_value)
        scroll_bar2.setValue(target_scroll_value)