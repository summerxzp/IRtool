from PyQt6.QtCore import QObject, pyqtSignal


class DataStore(QObject):
    """统一数据仓库：Autoruns / Network"""

    autoruns_updated = pyqtSignal(list)
    network_updated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._autoruns_entries = []
        self._network_connections = []

    def set_autoruns_entries(self, entries: list):
        self._autoruns_entries = entries or []
        self.autoruns_updated.emit(self._autoruns_entries)

    def get_autoruns_entries(self) -> list:
        return self._autoruns_entries

    def set_network_connections(self, connections: list):
        self._network_connections = connections or []
        self.network_updated.emit(self._network_connections)

    def get_network_connections(self) -> list:
        return self._network_connections
