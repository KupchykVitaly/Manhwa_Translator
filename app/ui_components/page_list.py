# app/ui_components/page_list.py
from PyQt6.QtWidgets import QListWidget, QFrame
from PyQt6.QtGui import QKeyEvent, QCursor
from PyQt6.QtCore import Qt, QPoint, QTimer

class PageListWidget(QListWidget):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.is_panning = False
        self.is_reordering = False
        self.drag_start_pos = None
        self.dragged_item = None
        self.drop_indicator = QFrame(self)
        self.drop_indicator.setFrameShape(QFrame.Shape.VLine)
        self.drop_indicator.setFrameShadow(QFrame.Shadow.Plain)
        self.drop_indicator.setStyleSheet("background-color: #e34040; border: 0px;")
        self.drop_indicator.setFixedWidth(3)
        self.drop_indicator.hide()
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(50)
        self.scroll_timer.timeout.connect(self.auto_scroll)
        self.scroll_direction = 0

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Delete:
            self.parent_window.delete_page()
            return
        if key == Qt.Key.Key_Insert:
            self.parent_window.open_image_dialog()
            return
        item = self.currentItem()
        if not item or not event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            super().keyPressEvent(event)
            return
        if key == Qt.Key.Key_Left: self.parent_window.move_left()
        elif key == Qt.Key.Key_Right: self.parent_window.move_right()
        elif key == Qt.Key.Key_Home: self.parent_window.move_to_start()
        elif key == Qt.Key.Key_End: self.parent_window.move_to_end()
        else: super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.drag_start_pos = event.position().toPoint()
        item = self.itemAt(self.drag_start_pos)
        if item:
            self.is_reordering = True
            self.dragged_item = item
        else:
            self.is_panning = True
            self.pan_start_scroll = self.horizontalScrollBar().value()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.is_reordering:
            if self.is_panning:
                delta = event.position().x() - self.drag_start_pos.x()
                self.horizontalScrollBar().setValue(self.pan_start_scroll - int(delta))
                self.viewport().update()
            super().mouseMoveEvent(event)
            return
        pos = event.position().toPoint()
        self._update_drop_indicator(pos)
        margin = 35
        viewport_width = self.viewport().width()
        if pos.x() < margin:
            self.scroll_direction = -1
            if not self.scroll_timer.isActive(): self.scroll_timer.start()
        elif pos.x() > viewport_width - margin:
            self.scroll_direction = 1
            if not self.scroll_timer.isActive(): self.scroll_timer.start()
        else:
            self.scroll_direction = 0
            self.scroll_timer.stop()

    def mouseReleaseEvent(self, event):
        self.scroll_timer.stop()
        self.scroll_direction = 0
        if not self.is_reordering:
            if self.is_panning:
                self.is_panning = False
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            super().mouseReleaseEvent(event)
            return
        self.is_reordering = False
        self.drop_indicator.hide()
        from_item = self.dragged_item
        if not from_item: return
        pos = event.position().toPoint()
        to_item = self.itemAt(pos)
        from_row = self.row(from_item)
        if not to_item:
            item_to_move = self.takeItem(from_row)
            self.insertItem(self.count(), item_to_move)
            self.setCurrentItem(item_to_move)
        elif to_item is not from_item:
            item_to_move = self.takeItem(from_row)
            to_row = self.row(to_item)
            rect = self.visualItemRect(to_item)
            if pos.x() < rect.center().x(): self.insertItem(to_row, item_to_move)
            else: self.insertItem(to_row + 1, item_to_move)
            self.setCurrentItem(item_to_move)
        self.dragged_item = None
        self.parent_window.renumber_pages()

    def _update_drop_indicator(self, pos: QPoint):
        target_item = self.itemAt(pos)
        if not target_item and self.count() > 0:
            last_item = self.item(self.count() - 1)
            rect = self.visualItemRect(last_item)
            self.drop_indicator.move(rect.right(), rect.top())
            self.drop_indicator.setFixedHeight(rect.height())
            self.drop_indicator.show()
            return
        if target_item:
            rect = self.visualItemRect(target_item)
            if pos.x() < rect.center().x(): self.drop_indicator.move(rect.left(), rect.top())
            else: self.drop_indicator.move(rect.right(), rect.top())
            self.drop_indicator.setFixedHeight(rect.height())
            self.drop_indicator.show()

    def auto_scroll(self):
        if self.scroll_direction == 0: return
        scrollbar = self.horizontalScrollBar()
        step = 15
        new_value = scrollbar.value() + (self.scroll_direction * step)
        scrollbar.setValue(new_value)
        self._update_drop_indicator(self.mapFromGlobal(QCursor.pos()))