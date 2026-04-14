import win32evtlog
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional, List
from datetime import datetime
import time
import logging

from .parser import SysmonEventParser
from .models import SysmonEvent, DnsEvent, NetworkConnectEvent, CreateRemoteThreadEvent

logger = logging.getLogger('IRtool')


class SysmonSubscriber(QThread):
    event_received = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    SYSMON_CHANNEL = 'Microsoft-Windows-Sysmon/Operational'

    # 采集的事件ID: 3=网络连接, 8=远程线程创建, 22=DNS查询
    EVENT_IDS = [3, 8, 22]

    def __init__(self, parent=None, filter_external_only: bool = False):
        super().__init__(parent)
        self._running = False
        self._last_record_id = 0
        self._poll_interval = 0.5
        self._filter_external_only = filter_external_only  # 是否只采集外连IP

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
                record_id = SysmonEventParser.extract_record_id(xml_str)
                if record_id:
                    self._last_record_id = record_id
                    logger.info(f"[SysmonSubscriber] Starting after RecordID: {self._last_record_id}")
        except Exception as e:
            logger.warning(f"[SysmonSubscriber] Failed to get last RecordID: {e}")
            self._last_record_id = 0

    def _build_xpath_query(self) -> str:
        """构建XPath查询，采集指定事件ID"""
        event_ids_str = ' or '.join([f"EventID={eid}" for eid in self.EVENT_IDS])
        
        if self._last_record_id <= 0:
            xpath = f'*[System[{event_ids_str}]]'
        else:
            xpath = f"*[System[({event_ids_str}) and EventRecordID > {self._last_record_id}]]"
        
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
            if "找不到指定的信道" in str(e) or "channel" in str(e).lower():
                return []
            raise

        parsed_events = []
        try:
            while True:
                batch = win32evtlog.EvtNext(h, 100)
                if not batch:
                    break

                for event_handle in batch:
                    try:
                        xml_str = win32evtlog.EvtRender(event_handle, win32evtlog.EvtRenderEventXml)
                        parsed = SysmonEventParser.parse_event(xml_str)
                        
                        if parsed:
                            # 如果开启了外连IP过滤，只保留外连的网络连接事件
                            if self._filter_external_only and isinstance(parsed, NetworkConnectEvent):
                                if not parsed.is_external:
                                    continue
                            parsed_events.append(parsed)

                        record_id = SysmonEventParser.extract_record_id(xml_str)
                        if record_id and record_id > self._last_record_id:
                            self._last_record_id = record_id
                    except Exception as e:
                        logger.warning(f"[SysmonSubscriber] Failed to parse event: {e}")
        except Exception as e:
            logger.warning(f"[SysmonSubscriber] EvtNext error: {e}")

        return parsed_events

    def stop(self):
        self._running = False
        self.wait(3000)

    def get_existing_events(self, limit: int = 500, filter_external_only: bool = False) -> List[SysmonEvent]:
        """获取历史事件"""
        try:
            event_ids_str = ' or '.join([f"EventID={eid}" for eid in self.EVENT_IDS])
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
