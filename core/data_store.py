from PyQt6.QtCore import QObject, pyqtSignal


class DataStore(QObject):
    """统一数据仓库：Autoruns / Network / Sysmon"""

    autoruns_updated = pyqtSignal(list)
    network_updated = pyqtSignal(list)
    network_history_updated = pyqtSignal(list)
    sysmon_event_added = pyqtSignal(object)
    sysmon_events_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._autoruns_entries = []
        self._network_connections_current = []
        self._network_connections_history = []
        self._sysmon_events = []
        self._sysmon_event_keys = set()

    def set_autoruns_entries(self, entries: list):
        self._autoruns_entries = entries or []
        self.autoruns_updated.emit(self._autoruns_entries)

    def get_autoruns_entries(self) -> list:
        return self._autoruns_entries

    def set_network_connections(self, current_connections: list, history_connections: list = None):
        self._network_connections_current = current_connections or []
        if history_connections is None:
            history_connections = self._network_connections_current
        self._network_connections_history = history_connections or []
        self.network_updated.emit(self._network_connections_current)
        self.network_history_updated.emit(self._network_connections_history)

    def get_network_connections(self, include_history: bool = False) -> list:
        if include_history:
            return self._network_connections_history
        return self._network_connections_current

    @staticmethod
    def _make_event_key(event) -> tuple:
        return (
            getattr(event, 'timestamp_epoch', 0),
            getattr(event, 'event_id', 0),
            getattr(event, 'process_id', getattr(event, 'source_process_id', 0)),
        )

    def add_sysmon_event(self, event):
        key = self._make_event_key(event)
        if key in self._sysmon_event_keys:
            return
        self._sysmon_event_keys.add(key)
        self._sysmon_events.append(event)
        self.sysmon_event_added.emit(event)

    def get_sysmon_events(self) -> list:
        return self._sysmon_events

    def set_sysmon_events(self, events: list):
        self._sysmon_events = events or []
        self._sysmon_event_keys = {self._make_event_key(e) for e in self._sysmon_events}
        self.sysmon_events_cleared.emit()

    def clear_sysmon_events(self):
        self._sysmon_events = []
        self._sysmon_event_keys = set()
        self.sysmon_events_cleared.emit()

    def get_sysmon_events_count(self) -> int:
        return len(self._sysmon_events)
