from PyQt6.QtWidgets import QPushButton, QMenu, QWidget
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QPointF
from PyQt6.QtGui import QAction, QPainter, QColor, QPolygonF


class DropdownButton(QPushButton):
    """扁平风格下拉按钮，替代 QComboBox，完全自定义外观。"""

    currentIndexChanged = pyqtSignal(int)
    currentTextChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setProperty("class", "dropdown")
        self._items: list[str] = []
        self._item_data: list = []
        self._current_index: int = -1
        self._menu = QMenu(self)
        self._menu.setObjectName("dropdown_menu")
        self._menu.triggered.connect(self._on_triggered)
        self.clicked.connect(self._show_menu)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _show_menu(self):
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self._menu.exec(pos)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if self.isDown():
            painter.setBrush(QColor("#1a5fbf"))
        elif self.underMouse():
            painter.setBrush(QColor("#4c8dff"))
        else:
            painter.setBrush(QColor("#6b7280"))
        x = self.width() - 14
        y = self.height() // 2
        triangle = QPolygonF([
            QPointF(x - 4, y - 2),
            QPointF(x + 4, y - 2),
            QPointF(x, y + 3),
        ])
        painter.drawPolygon(triangle)
        painter.end()

    def addItems(self, items: list[str]):
        for text in items:
            self.addItem(text)

    def addItem(self, text: str, userData=None):
        self._items.append(text)
        self._item_data.append(userData)
        self._menu.addAction(text)
        if len(self._items) == 1:
            self.setCurrentIndex(0)

    def clear(self):
        self._items.clear()
        self._item_data.clear()
        self._menu.clear()
        self._current_index = -1
        self.setText("")

    def setCurrentIndex(self, index: int):
        if 0 <= index < len(self._items):
            self._current_index = index
            self.setText(self._items[index])
            self.currentIndexChanged.emit(index)
            self.currentTextChanged.emit(self._items[index])

    def currentIndex(self) -> int:
        return self._current_index

    def currentText(self) -> str:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return ""

    def currentData(self) -> object:
        if 0 <= self._current_index < len(self._item_data):
            return self._item_data[self._current_index]
        return None

    def setCurrentText(self, text: str):
        try:
            idx = self._items.index(text)
            self.setCurrentIndex(idx)
        except ValueError:
            pass

    def count(self) -> int:
        return len(self._items)

    def itemText(self, index: int) -> str:
        if 0 <= index < len(self._items):
            return self._items[index]
        return ""

    def itemData(self, index: int) -> object:
        if 0 <= index < len(self._item_data):
            return self._item_data[index]
        return None

    def _on_triggered(self, action: QAction):
        text = action.text()
        try:
            idx = self._items.index(text)
            self.setCurrentIndex(idx)
        except ValueError:
            pass
