from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from datetime import datetime
import ipaddress


@dataclass
class SysmonEvent:
    event_id: int = 0
    timestamp: str = ""
    timestamp_epoch: float = 0.0
    timestamp_valid: bool = True
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return 'unknown'

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['event_type'] = self.event_type
        return d


@dataclass
class DnsEvent(SysmonEvent):
    event_id: int = 22
    process_id: int = 0
    process_name: str = ""
    process_path: str = ""
    user: str = ""
    query_name: str = ""
    query_results: str = ""
    query_status: int = 0
    rule_name: str = ""
    _sort_process_name: str = field(default="", repr=False, compare=False)
    _sort_query_name: str = field(default="", repr=False, compare=False)
    _sort_user: str = field(default="", repr=False, compare=False)
    _sort_process_path: str = field(default="", repr=False, compare=False)

    @property
    def event_type(self) -> str:
        return 'dns'

    @classmethod
    def from_event_data(cls, event_data: Dict[str, Any], timestamp: datetime) -> 'DnsEvent':
        process_name = cls._extract_process_name(event_data.get('Image', ''))
        query_name = event_data.get('QueryName', '')
        user = event_data.get('User', '')
        process_path = event_data.get('Image', '')
        return cls(
            event_id=22,
            timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            timestamp_epoch=timestamp.timestamp(),
            process_id=int(event_data.get('ProcessId', 0)),
            process_name=process_name,
            process_path=process_path,
            user=user,
            query_name=query_name,
            query_results=event_data.get('QueryResults', ''),
            query_status=int(event_data.get('QueryStatus', 0)),
            rule_name=event_data.get('RuleName', ''),
            _sort_process_name=process_name.lower(),
            _sort_query_name=query_name.lower(),
            _sort_user=user.lower(),
            _sort_process_path=process_path.lower(),
            raw_data=event_data
        )

    @staticmethod
    def _extract_process_name(path: str) -> str:
        if not path:
            return ""
        return path.split('\\')[-1]


@dataclass
class FileCreateEvent(SysmonEvent):
    """文件创建事件 (EventID 11)"""
    event_id: int = 11
    process_id: int = 0
    process_name: str = ""
    process_path: str = ""
    user: str = ""
    target_filename: str = ""
    creation_utc_time: str = ""
    rule_name: str = ""
    _sort_process_name: str = field(default="", repr=False, compare=False)
    _sort_target_filename: str = field(default="", repr=False, compare=False)
    _sort_user: str = field(default="", repr=False, compare=False)
    _sort_process_path: str = field(default="", repr=False, compare=False)

    @property
    def event_type(self) -> str:
        return 'file_create'

    @property
    def is_suspicious(self) -> bool:
        suspicious_paths = [
            '\\temp\\', '\\tmp\\', '\\appdata\\local\\temp\\',
            '\\downloads\\', '\\programdata\\',
        ]
        target_lower = self.target_filename.lower()
        return any(p in target_lower for p in suspicious_paths)

    @classmethod
    def from_event_data(cls, event_data: Dict[str, Any], timestamp: datetime) -> 'FileCreateEvent':
        process_name = cls._extract_process_name(event_data.get('Image', ''))
        target_filename = event_data.get('TargetFilename', '')
        user = event_data.get('User', '')
        process_path = event_data.get('Image', '')
        return cls(
            event_id=11,
            timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            timestamp_epoch=timestamp.timestamp(),
            process_id=int(event_data.get('ProcessId', 0)),
            process_name=process_name,
            process_path=process_path,
            user=user,
            target_filename=target_filename,
            creation_utc_time=event_data.get('CreationUtcTime', ''),
            rule_name=event_data.get('RuleName', ''),
            _sort_process_name=process_name.lower(),
            _sort_target_filename=target_filename.lower(),
            _sort_user=user.lower(),
            _sort_process_path=process_path.lower(),
            raw_data=event_data
        )


@dataclass
class NetworkConnectEvent(SysmonEvent):
    """网络连接事件 (EventID 3)"""
    event_id: int = 3
    process_id: int = 0
    process_name: str = ""
    process_path: str = ""
    user: str = ""
    source_ip: str = ""
    source_port: int = 0
    destination_ip: str = ""
    destination_port: int = 0
    protocol: str = ""
    initiated: bool = False
    rule_name: str = ""
    _is_external_cache: bool = field(default=False, repr=False, compare=False)
    _sort_process_name: str = field(default="", repr=False, compare=False)
    _sort_user: str = field(default="", repr=False, compare=False)
    _sort_process_path: str = field(default="", repr=False, compare=False)
    _sort_destination: str = field(default="", repr=False, compare=False)

    @property
    def event_type(self) -> str:
        return 'network_connect'

    @property
    def is_external(self) -> bool:
        """判断是否为外连IP（排除局域网段）"""
        return self._is_external_cache

    @staticmethod
    def _is_private_ip(ip_str: str) -> bool:
        """判断IP是否为私有/局域网地址"""
        if not ip_str or ip_str in ['0.0.0.0', '::', '::ffff:0.0.0.0', '*']:
            return True
        try:
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            return False

    @classmethod
    def from_event_data(cls, event_data: Dict[str, Any], timestamp: datetime) -> 'NetworkConnectEvent':
        destination_ip = event_data.get('DestinationIp', '')
        destination_port = int(event_data.get('DestinationPort', 0)) if event_data.get('DestinationPort') else 0
        process_name = cls._extract_process_name(event_data.get('Image', ''))
        user = event_data.get('User', '')
        process_path = event_data.get('Image', '')
        return cls(
            event_id=3,
            timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            timestamp_epoch=timestamp.timestamp(),
            process_id=int(event_data.get('ProcessId', 0)),
            process_name=process_name,
            process_path=process_path,
            user=user,
            source_ip=event_data.get('SourceIp', ''),
            source_port=int(event_data.get('SourcePort', 0)) if event_data.get('SourcePort') else 0,
            destination_ip=destination_ip,
            destination_port=destination_port,
            protocol=event_data.get('Protocol', ''),
            initiated=event_data.get('Initiated', 'false').lower() == 'true',
            rule_name=event_data.get('RuleName', ''),
            _is_external_cache=not cls._is_private_ip(destination_ip),
            _sort_process_name=process_name.lower(),
            _sort_user=user.lower(),
            _sort_process_path=process_path.lower(),
            _sort_destination=f"{destination_ip}:{destination_port}".lower(),
            raw_data=event_data
        )

    @staticmethod
    def _extract_process_name(path: str) -> str:
        if not path:
            return ""
        return path.split('\\')[-1]


@dataclass
class CreateRemoteThreadEvent(SysmonEvent):
    """远程线程创建事件 (EventID 8)"""
    event_id: int = 8
    source_process_id: int = 0
    source_process_name: str = ""
    source_process_path: str = ""
    target_process_id: int = 0
    target_process_name: str = ""
    target_process_path: str = ""
    new_thread_id: int = 0
    start_address: str = ""
    start_module: str = ""
    start_function: str = ""
    user: str = ""
    rule_name: str = ""
    _sort_source_process_name: str = field(default="", repr=False, compare=False)
    _sort_target_process_name: str = field(default="", repr=False, compare=False)
    _sort_user: str = field(default="", repr=False, compare=False)
    _sort_source_process_path: str = field(default="", repr=False, compare=False)
    _sort_target_process_path: str = field(default="", repr=False, compare=False)

    @property
    def event_type(self) -> str:
        return 'create_remote_thread'

    @property
    def is_suspicious(self) -> bool:
        """判断是否为可疑的远程线程注入"""
        suspicious_sources = ['rundll32.exe', 'regsvr32.exe', 'mshta.exe', 'powershell.exe', 'cmd.exe']
        suspicious_targets = ['lsass.exe', 'svchost.exe', 'csrss.exe', 'services.exe']
        
        source_lower = self.source_process_name.lower()
        target_lower = self.target_process_name.lower()
        
        return (source_lower in suspicious_sources or
                target_lower in suspicious_targets)

    @classmethod
    def from_event_data(cls, event_data: Dict[str, Any], timestamp: datetime) -> 'CreateRemoteThreadEvent':
        source_process_name = cls._extract_process_name(event_data.get('SourceImage', ''))
        target_process_name = cls._extract_process_name(event_data.get('TargetImage', ''))
        user = event_data.get('User', '')
        source_process_path = event_data.get('SourceImage', '')
        target_process_path = event_data.get('TargetImage', '')
        return cls(
            event_id=8,
            timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            timestamp_epoch=timestamp.timestamp(),
            source_process_id=int(event_data.get('SourceProcessId', 0)),
            source_process_name=source_process_name,
            source_process_path=source_process_path,
            target_process_id=int(event_data.get('TargetProcessId', 0)),
            target_process_name=target_process_name,
            target_process_path=target_process_path,
            new_thread_id=int(event_data.get('NewThreadId', 0)) if event_data.get('NewThreadId') else 0,
            start_address=event_data.get('StartAddress', ''),
            start_module=event_data.get('StartModule', ''),
            start_function=event_data.get('StartFunction', ''),
            user=user,
            rule_name=event_data.get('RuleName', ''),
            _sort_source_process_name=source_process_name.lower(),
            _sort_target_process_name=target_process_name.lower(),
            _sort_user=user.lower(),
            _sort_source_process_path=source_process_path.lower(),
            _sort_target_process_path=target_process_path.lower(),
            raw_data=event_data
        )

    @staticmethod
    def _extract_process_name(path: str) -> str:
        if not path:
            return ""
        return path.split('\\')[-1]
