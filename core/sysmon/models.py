from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from datetime import datetime
import ipaddress


@dataclass
class SysmonEvent:
    event_id: int = 0
    timestamp: str = ""
    timestamp_epoch: float = 0.0
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

    @property
    def event_type(self) -> str:
        return 'dns'

    @classmethod
    def from_event_data(cls, event_data: Dict[str, Any], timestamp: datetime) -> 'DnsEvent':
        return cls(
            event_id=22,
            timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            timestamp_epoch=timestamp.timestamp(),
            process_id=int(event_data.get('ProcessId', 0)),
            process_name=cls._extract_process_name(event_data.get('Image', '')),
            process_path=event_data.get('Image', ''),
            user=event_data.get('User', ''),
            query_name=event_data.get('QueryName', ''),
            query_results=event_data.get('QueryResults', ''),
            query_status=int(event_data.get('QueryStatus', 0)),
            rule_name=event_data.get('RuleName', ''),
            raw_data=event_data
        )

    @staticmethod
    def _extract_process_name(path: str) -> str:
        if not path:
            return ""
        return path.split('\\')[-1]


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

    @property
    def event_type(self) -> str:
        return 'network_connect'

    @property
    def is_external(self) -> bool:
        """判断是否为外连IP（排除局域网段）"""
        return not self._is_private_ip(self.destination_ip)

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
        return cls(
            event_id=3,
            timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            timestamp_epoch=timestamp.timestamp(),
            process_id=int(event_data.get('ProcessId', 0)),
            process_name=cls._extract_process_name(event_data.get('Image', '')),
            process_path=event_data.get('Image', ''),
            user=event_data.get('User', ''),
            source_ip=event_data.get('SourceIp', ''),
            source_port=int(event_data.get('SourcePort', 0)) if event_data.get('SourcePort') else 0,
            destination_ip=event_data.get('DestinationIp', ''),
            destination_port=int(event_data.get('DestinationPort', 0)) if event_data.get('DestinationPort') else 0,
            protocol=event_data.get('Protocol', ''),
            initiated=event_data.get('Initiated', 'false').lower() == 'true',
            rule_name=event_data.get('RuleName', ''),
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
                target_lower in suspicious_targets or
                (source_lower != target_lower and target_lower in suspicious_targets))

    @classmethod
    def from_event_data(cls, event_data: Dict[str, Any], timestamp: datetime) -> 'CreateRemoteThreadEvent':
        return cls(
            event_id=8,
            timestamp=timestamp.strftime("%Y/%m/%d %H:%M:%S"),
            timestamp_epoch=timestamp.timestamp(),
            source_process_id=int(event_data.get('SourceProcessId', 0)),
            source_process_name=cls._extract_process_name(event_data.get('SourceImage', '')),
            source_process_path=event_data.get('SourceImage', ''),
            target_process_id=int(event_data.get('TargetProcessId', 0)),
            target_process_name=cls._extract_process_name(event_data.get('TargetImage', '')),
            target_process_path=event_data.get('TargetImage', ''),
            new_thread_id=int(event_data.get('NewThreadId', 0)) if event_data.get('NewThreadId') else 0,
            start_address=event_data.get('StartAddress', ''),
            start_module=event_data.get('StartModule', ''),
            start_function=event_data.get('StartFunction', ''),
            user=event_data.get('User', ''),
            rule_name=event_data.get('RuleName', ''),
            raw_data=event_data
        )

    @staticmethod
    def _extract_process_name(path: str) -> str:
        if not path:
            return ""
        return path.split('\\')[-1]
