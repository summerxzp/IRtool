from PyQt6.QtCore import QObject, pyqtSignal


class DataStore(QObject):
    """统一数据仓库：Autoruns / Network / Sysmon"""

    autoruns_updated = pyqtSignal(list)
    network_updated = pyqtSignal(list)
    sysmon_event_added = pyqtSignal(object)
    sysmon_events_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._autoruns_entries = []
        self._network_connections = []
        self._sysmon_events = []

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

    def add_sysmon_event(self, event):
        self._sysmon_events.append(event)
        self.sysmon_event_added.emit(event)

    def get_sysmon_events(self) -> list:
        return self._sysmon_events

    def set_sysmon_events(self, events: list):
        self._sysmon_events = events or []
        self.sysmon_event_added.emit(None)

    def clear_sysmon_events(self):
        self._sysmon_events = []
        self.sysmon_events_cleared.emit()

    def get_sysmon_events_count(self) -> int:
        return len(self._sysmon_events)
