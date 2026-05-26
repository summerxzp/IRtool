import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from .models import SysmonEvent, DnsEvent, NetworkConnectEvent, CreateRemoteThreadEvent, FileCreateEvent

logger = logging.getLogger('SysmonEventParser')


class SysmonEventParser:
    NS = '{http://schemas.microsoft.com/win/2004/08/events/event}'

    EVENT_PARSERS = {
        3: '_parse_network_connect_event',
        8: '_parse_create_remote_thread_event',
        11: '_parse_file_create_event',
        22: '_parse_dns_event',
    }

    @classmethod
    def parse_event(cls, event_xml: str) -> Optional[SysmonEvent]:
        try:
            root = ET.fromstring(event_xml)
            event_id, timestamp = cls._parse_system_data(root)
            event_data = cls._parse_event_data(root)

            parser_method = cls.EVENT_PARSERS.get(event_id)
            if parser_method:
                return getattr(cls, parser_method)(event_data, timestamp)

            return SysmonEvent(
                event_id=event_id,
                timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
                timestamp_epoch=timestamp.timestamp(),
                timestamp_valid=timestamp.year != 1970,
                raw_data=event_data
            )
        except Exception as e:
            logger.warning(f"解析事件失败: {e}")
            return SysmonEvent(
                event_id=0,
                timestamp="",
                timestamp_epoch=0,
                timestamp_valid=False,
                raw_data={"_parse_error": str(e), "_raw_xml": event_xml}
            )

    @classmethod
    def parse_event_with_record_id(cls, event_xml: str) -> Tuple[Optional[SysmonEvent], Optional[int]]:
        try:
            root = ET.fromstring(event_xml)

            record_id_elem = root.find(f'.//{cls.NS}EventRecordID')
            record_id = int(record_id_elem.text) if record_id_elem is not None and record_id_elem.text else None

            event_id, timestamp = cls._parse_system_data(root)
            event_data = cls._parse_event_data(root)

            parser_method = cls.EVENT_PARSERS.get(event_id)
            if parser_method:
                event = getattr(cls, parser_method)(event_data, timestamp)
            else:
                event = SysmonEvent(
                    event_id=event_id,
                    timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
                    timestamp_epoch=timestamp.timestamp(),
                    timestamp_valid=timestamp.year != 1970,
                    raw_data=event_data
                )

            return event, record_id
        except Exception as e:
            logger.warning(f"解析事件(含record_id)失败: {e}")
            return SysmonEvent(
                event_id=0,
                timestamp="",
                timestamp_epoch=0,
                timestamp_valid=False,
                raw_data={"_parse_error": str(e), "_raw_xml": event_xml}
            ), None

    @classmethod
    def _parse_system_data(cls, root: ET.Element) -> Tuple[int, datetime]:
        system = root.find(f'.//{cls.NS}System')

        event_id = 0
        timestamp = datetime(1970, 1, 1)

        if system is not None:
            event_id_elem = system.find(f'{cls.NS}EventID')
            if event_id_elem is not None and event_id_elem.text:
                try:
                    event_id = int(event_id_elem.text)
                except ValueError:
                    pass

            time_created = system.find(f'{cls.NS}TimeCreated')
            if time_created is not None:
                time_str = time_created.get('SystemTime', '')
                if time_str:
                    timestamp = cls._parse_timestamp(time_str)

        return event_id, timestamp

    @classmethod
    def _parse_timestamp(cls, time_str: str) -> datetime:
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            pass

        for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'):
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue

        return datetime(1970, 1, 1)

    @classmethod
    def _parse_event_data(cls, root: ET.Element) -> Dict[str, Any]:
        event_data = {}
        data_elements = root.findall(f'.//{cls.NS}Data')

        for data in data_elements:
            name = data.get('Name', '')
            value = data.text or ''
            event_data[name] = value

        return event_data

    @classmethod
    def _parse_dns_event(cls, event_data: Dict[str, Any], timestamp: datetime) -> DnsEvent:
        return DnsEvent.from_event_data(event_data, timestamp)

    @classmethod
    def _parse_network_connect_event(cls, event_data: Dict[str, Any], timestamp: datetime) -> NetworkConnectEvent:
        return NetworkConnectEvent.from_event_data(event_data, timestamp)

    @classmethod
    def _parse_create_remote_thread_event(cls, event_data: Dict[str, Any], timestamp: datetime) -> CreateRemoteThreadEvent:
        return CreateRemoteThreadEvent.from_event_data(event_data, timestamp)

    @classmethod
    def _parse_file_create_event(cls, event_data: Dict[str, Any], timestamp: datetime) -> FileCreateEvent:
        return FileCreateEvent.from_event_data(event_data, timestamp)
