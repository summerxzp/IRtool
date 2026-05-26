# core/network_monitor.py
import psutil
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import json
import socket
import time


@dataclass
class NetworkConnection:
    timestamp: str
    timestamp_epoch: float
    pid: int
    process_name: str
    process_path: str
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str
    family: str
    first_seen_epoch: float = 0.0
    last_seen_epoch: float = 0.0
    
    def to_dict(self):
        return asdict(self)


class NetworkMonitor:
    """网络监控核心类"""
    
    # 需要监控的连接状态
    VALID_STATUSES = [
        'ESTABLISHED', 'LISTEN', 'TIME_WAIT', 
        'CLOSE_WAIT', 'SYN_SENT', 'SYN_RECV', 'NONE'
    ]
    
    def __init__(self):
        self._process_cache: Dict[int, Tuple[str, str, float, float]] = {}
        self._cache_ttl = 5.0
        
    def get_connections(self, status_filter: Optional[List[str]] = None) -> List[NetworkConnection]:
        """获取当前所有网络连接"""
        self._cleanup_expired_cache()
        
        connections = []
        
        for conn in psutil.net_connections(kind='inet'):
            if conn.pid is None:
                pid = 0
                proc_name = "[无进程]"
                proc_path = "[无进程]"
            else:
                pid = conn.pid
                proc_name, proc_path = self._get_process_info(conn.pid)
                
            laddr = (conn.laddr.ip, conn.laddr.port) if conn.laddr else ("", 0)
            raddr = (conn.raddr.ip, conn.raddr.port) if conn.raddr else ("", 0)
            protocol_type = "TCP" if conn.type == socket.SOCK_STREAM else "UDP" if conn.type == socket.SOCK_DGRAM else "UNKNOWN"

            if status_filter and conn.status not in status_filter:
                continue
            
            status_for_display = conn.status
            if protocol_type == "UDP" and conn.status == "NONE":
                status_for_display = ""
            
            now = datetime.now()
            epoch = now.timestamp()
            nc = NetworkConnection(
                timestamp=now.strftime("%Y/%m/%d %H:%M:%S"),
                timestamp_epoch=epoch,
                pid=pid,
                process_name=proc_name,
                process_path=proc_path,
                local_address=laddr[0],
                local_port=laddr[1],
                remote_address=raddr[0] if raddr[0] else "",
                remote_port=raddr[1] if raddr[0] else 0,
                status=status_for_display,
                family=protocol_type,
                first_seen_epoch=epoch,
                last_seen_epoch=epoch,
            )
            connections.append(nc)
            
        return connections
    
    def _cleanup_expired_cache(self):
        now = time.time()
        expired_pids = [
            pid for pid, (_, _, _, timestamp) in self._process_cache.items()
            if now - timestamp > self._cache_ttl
        ]
        for pid in expired_pids:
            del self._process_cache[pid]
    
    def _get_process_info(self, pid: int) -> tuple:
        if pid in self._process_cache:
            name, path, create_time, timestamp = self._process_cache[pid]
            if time.time() - timestamp < self._cache_ttl:
                try:
                    proc = psutil.Process(pid)
                    if proc.create_time() == create_time:
                        return name, path
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            del self._process_cache[pid]
        
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            path = proc.exe()
            create_time = proc.create_time()
            self._process_cache[pid] = (name, path, create_time, time.time())
            return name, path
        except psutil.NoSuchProcess:
            return "[已结束]", "[已结束]"
        except psutil.AccessDenied:
            return "[权限不足]", "[权限不足]"
        except Exception as e:
            return f"[错误: {str(e)}]", f"[错误: {str(e)}]"
    
    def kill_process(self, pid: int) -> tuple:
        """终止进程"""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=3)
            return True, f"进程 {pid} 已终止"
        except psutil.NoSuchProcess:
            return False, "进程不存在"
        except psutil.AccessDenied:
            return False, "权限不足，请以管理员身份运行"
        except Exception as e:
            return False, str(e)
    
    def clear_cache(self):
        """清理进程缓存"""
        self._process_cache.clear()
    
    def stop_monitoring(self):
        """停止监控 - 网络监控无需特殊停止逻辑，只需清理缓存"""
        self.clear_cache()
