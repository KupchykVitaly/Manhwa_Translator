# app/core/worker.py
import sys
import traceback
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

class Worker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(tuple)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            exctype, value = sys.exc_info()[:2]
            self.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.finished.emit(result)