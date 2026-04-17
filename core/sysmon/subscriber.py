import win32evtlog
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional, List
from datetime import datetime
import time
import logging

from .parser import SysmonEventParser
from .models import SysmonEvent, DnsEvent, NetworkConnectEvent, CreateRemoteThreadEvent, FileCreateEvent
from .config_manager import EVENT_CONFIG, DEFAULT_ENABLED_EVENTS

logger = logging.getLogger('IRtool')


class SysmonSubscriber(QThread):
    event_received = pyqtSignal(object)
    events_batch_received = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    SYSMON_CHANNEL = 'Microsoft-Windows-Sysmon/Operational'

    def __init__(self, parent=None, filter_external_only: bool = False, enabled_events: Optional[List[str]] = None):
        super().__init__(parent)
        self._running = False
        self._last_record_id = 0
        self._poll_interval = 0.5
        self._filter_external_only = filter_external_only
        self._enabled_events = enabled_events or list(DEFAULT_ENABLED_EVENTS)
        self._event_ids = self._compute_event_ids()

    def _compute_event_ids(self) -> List[int]:
        event_ids = []
        for key in self._enabled_events:
            if key in EVENT_CONFIG:
                eid = EVENT_CONFIG[key]['event_id']
                if eid not in event_ids:
                    event_ids.append(eid)
        return sorted(event_ids) if event_ids else [3, 8, 22]

    def is_sysmon_available(self) -> bool:
        try:
            h = win32evtlog.EvtQuery(
                self.SYSMON_CHANNEL,
                win32evtlog.EvtQueryChannelPath,
                '*'
            )
            return True
        except Exception:
            return False

    def run(self):
        self._running = True
        self.status_changed.emit("connecting")

        try:
            self._init_last_record_id()
            self.status_changed.emit("connected")

            while self._running:
                events = self._poll_new_events()
                if events:
                    # 批量发射信号，减少信号开销
                    self.events_batch_received.emit(events)
                    # 保持向后兼容的单个事件信号
                    for event in events:
                        if not self._running:
                            break
                        self.event_received.emit(event)

                for _ in range(int(self._poll_interval / 0.1)):
                    if not self._running:
                        break
                    time.sleep(0.1)

        except Exception as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit("error")
        finally:
            self.status_changed.emit("disconnected")

    def _init_last_record_id(self):
        try:
            h = win32evtlog.EvtQuery(
                self.SYSMON_CHANNEL,
                win32evtlog.EvtQueryChannelPath | win32evtlog.EvtQueryReverseDirection,
                '*'
            )
            events = win32evtlog.EvtNext(h, 1)
            if events:
                xml_str = win32evtlog.EvtRender(events[0], win32evtlog.EvtRenderEventXml)
                _, record_id = SysmonEventParser.parse_event_with_record_id(xml_str)
                if record_id:
                    self._last_record_id = record_id
                    logger.info(f"[SysmonSubscriber] Starting after RecordID: {self._last_record_id}")
        except Exception as e:
            logger.warning(f"[SysmonSubscriber] Failed to get last RecordID: {e}")
            self._last_record_id = 0

    def _build_xpath_query(self) -> str:
        """构建XPath查询，采集指定事件ID"""
        event_ids_str = ' or '.join([f"EventID={eid}" for eid in self._event_ids])

        if self._last_record_id <= 0:
            xpath = f'*[System[{event_ids_str}]]'
        else:
            # 注意：XPath条件需要用括号包裹，避免优先级问题
            xpath = f"*[System[({event_ids_str}) and (EventRecordID > {self._last_record_id})]]"

        logger.debug(f"[SysmonSubscriber] XPath query: {xpath}")
        return xpath

    def _poll_new_events(self) -> List[SysmonEvent]:
        xpath = self._build_xpath_query()

        try:
            h = win32evtlog.EvtQuery(
                self.SYSMON_CHANNEL,
                win32evtlog.EvtQueryChannelPath,
                xpath
            )
        except Exception as e:
            logger.error(f"[SysmonSubscriber] EvtQuery failed: {e}")
            if "找不到指定的信道" in str(e) or "channel" in str(e).lower():
                return []
            raise

        parsed_events = []
        batch_count = 0
        try:
            while True:
                batch = win32evtlog.EvtNext(h, 100)
                if not batch:
                    break
                batch_count += 1

                for event_handle in batch:
                    try:
                        xml_str = win32evtlog.EvtRender(event_handle, win32evtlog.EvtRenderEventXml)
                        parsed, record_id = SysmonEventParser.parse_event_with_record_id(xml_str)

                        if parsed:
                            logger.debug(f"[SysmonSubscriber] Parsed event: ID={parsed.event_id}, Type={parsed.event_type}")
                            # 如果开启了外连IP过滤，只保留外连的网络连接事件
                            if self._filter_external_only and isinstance(parsed, NetworkConnectEvent):
                                if not parsed.is_external:
                                    continue
                            parsed_events.append(parsed)

                        if record_id and record_id > self._last_record_id:
                            self._last_record_id = record_id
                    except Exception as e:
                        logger.warning(f"[SysmonSubscriber] Failed to parse event: {e}")
        except Exception as e:
            logger.warning(f"[SysmonSubscriber] EvtNext error: {e}")

        if parsed_events:
            logger.debug(f"[SysmonSubscriber] Poll returned {len(parsed_events)} events from {batch_count} batches")
        return parsed_events

    def stop(self):
        self._running = False
        self.wait(3000)

    def get_existing_events(self, limit: int = 500, filter_external_only: bool = False) -> List[SysmonEvent]:
        """获取历史事件"""
        try:
            event_ids_str = ' or '.join([f"EventID={eid}" for eid in self._event_ids])
            xpath = f'*[System[{event_ids_str}]]'
            
            h = win32evtlog.EvtQuery(
                self.SYSMON_CHANNEL,
                win32evtlog.EvtQueryChannelPath | win32evtlog.EvtQueryReverseDirection,
                xpath
            )

            events = []
            batch = win32evtlog.EvtNext(h, limit)
            if batch:
                for event_handle in batch:
                    try:
                        xml_str = win32evtlog.EvtRender(event_handle, win32evtlog.EvtRenderEventXml)
                        parsed = SysmonEventParser.parse_event(xml_str)
                        if parsed:
                            # 如果开启了外连IP过滤
                            if filter_external_only and isinstance(parsed, NetworkConnectEvent):
                                if not parsed.is_external:
                                    continue
                            events.append(parsed)
                    except Exception as e:
                        logger.warning(f"[SysmonSubscriber] Failed to parse history event: {e}")

            events.reverse()
            return events

        except Exception as e:
            self.error_occurred.emit(str(e))
            return []
