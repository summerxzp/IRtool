import sys
from unittest.mock import MagicMock


def _create_qt_mock():
    mock = MagicMock()
    mock.QObject = MagicMock
    mock.QRunnable = MagicMock
    mock.QThreadPool = MagicMock
    mock.QTimer = MagicMock()
    mock.QThread = MagicMock
    mock.pyqtSignal = MagicMock(return_value=MagicMock())
    mock.pyqtSlot = MagicMock(return_value=lambda f: f)
    mock.QIcon = MagicMock
    mock.QPixmap = MagicMock
    mock.QPainter = MagicMock
    mock.QColor = MagicMock
    mock.QAction = MagicMock
    mock.QMenu = MagicMock
    mock.QApplication = MagicMock
    mock.QMainWindow = MagicMock
    mock.QWidget = MagicMock
    mock.QDialog = MagicMock
    mock.QTableWidgetItem = MagicMock
    mock.QAbstractItemView = MagicMock
    mock.QHeaderView = MagicMock
    mock.QStyle = MagicMock
    return mock


_pyqt6_mock = _create_qt_mock()
_pyqt6_core_mock = _create_qt_mock()
_pyqt6_gui_mock = _create_qt_mock()
_pyqt6_widgets_mock = _create_qt_mock()

sys.modules.setdefault("PyQt6", _pyqt6_mock)
sys.modules.setdefault("PyQt6.QtCore", _pyqt6_core_mock)
sys.modules.setdefault("PyQt6.QtGui", _pyqt6_gui_mock)
sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6_widgets_mock)

try:
    import psutil
except ImportError:
    sys.modules.setdefault("psutil", MagicMock())
