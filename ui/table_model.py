from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QColor
from typing import List, Any, Optional, Callable


class HighPerformanceTableModel(QAbstractTableModel):
    MAX_ROWS = 50000

    def __init__(self, columns: List[str], parent=None):
        super().__init__(parent)
        self._columns = columns
        self._data: List[list] = []
        self._sort_values: List[list] = []
        self._backgrounds: List[list] = []
        self._foregrounds: List[list] = []
        self._tooltips: List[list] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row < 0 or row >= len(self._data):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            val = self._data[row][col]
            return str(val) if val is not None else ""

        if role == Qt.ItemDataRole.EditRole:
            val = self._sort_values[row][col] if row < len(self._sort_values) else None
            return val if val is not None else self._data[row][col]

        if role == Qt.ItemDataRole.BackgroundRole:
            if row < len(self._backgrounds):
                bg = self._backgrounds[row][col]
                if bg is not None:
                    return bg

        if role == Qt.ItemDataRole.ForegroundRole:
            if row < len(self._foregrounds):
                fg = self._foregrounds[row][col]
                if fg is not None:
                    return fg

        if role == Qt.ItemDataRole.ToolTipRole:
            if row < len(self._tooltips):
                tip = self._tooltips[row][col]
                if tip is not None:
                    return tip

        return None

    def set_data_bulk(self, rows: List[list],
                      sort_values: Optional[List[list]] = None,
                      backgrounds: Optional[List[list]] = None,
                      foregrounds: Optional[List[list]] = None,
                      tooltips: Optional[List[list]] = None):
        self.beginResetModel()
        self._data = rows[:self.MAX_ROWS]
        self._sort_values = sort_values[:self.MAX_ROWS] if sort_values else []
        self._backgrounds = backgrounds[:self.MAX_ROWS] if backgrounds else []
        self._foregrounds = foregrounds[:self.MAX_ROWS] if foregrounds else []
        self._tooltips = tooltips[:self.MAX_ROWS] if tooltips else []
        self.endResetModel()

    def row_count_matches(self, count: int) -> bool:
        return len(self._data) == count

    def append_rows(self, new_rows: List[list],
                    sort_values: Optional[List[list]] = None,
                    backgrounds: Optional[List[list]] = None,
                    foregrounds: Optional[List[list]] = None,
                    tooltips: Optional[List[list]] = None):
        if not new_rows:
            return

        total = len(self._data) + len(new_rows)
        trim_count = max(0, total - self.MAX_ROWS)

        if trim_count > 0:
            self.beginRemoveRows(QModelIndex(), 0, trim_count - 1)
            self._data = self._data[trim_count:]
            if self._sort_values:
                self._sort_values = self._sort_values[trim_count:]
            if self._backgrounds:
                self._backgrounds = self._backgrounds[trim_count:]
            if self._foregrounds:
                self._foregrounds = self._foregrounds[trim_count:]
            if self._tooltips:
                self._tooltips = self._tooltips[trim_count:]
            self.endRemoveRows()

        start = len(self._data)
        end = start + len(new_rows) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self._data.extend(new_rows)
        if sort_values:
            if not self._sort_values:
                self._sort_values = [[] for _ in self._data[:start]]
            self._sort_values.extend(sort_values)
        if backgrounds:
            if not self._backgrounds:
                self._backgrounds = [[] for _ in self._data[:start]]
            self._backgrounds.extend(backgrounds)
        if foregrounds:
            if not self._foregrounds:
                self._foregrounds = [[] for _ in self._data[:start]]
            self._foregrounds.extend(foregrounds)
        if tooltips:
            if not self._tooltips:
                self._tooltips = [[] for _ in self._data[:start]]
            self._tooltips.extend(tooltips)
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self._data = []
        self._sort_values = []
        self._backgrounds = []
        self._foregrounds = []
        self._tooltips = []
        self.endResetModel()

    def get_row_data(self, row: int) -> Optional[list]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None
